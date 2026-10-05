"""Канал PLAN: смена `merge_after` на переходе `in_dev -> verifying` (AC-9, AC-10).

Группа: долгоживущий
Красен до реализации: колонки merge_after в таблице tasks нет и гейт SPEC значение не записывает — каждый сценарий краснеет на предпосылке «прежнее значение записано гейтом SPEC», а переход in_dev -> verifying поле merge_after из PLAN не читает вовсе.

Песочница — `tests.sandbox.LightTransitionSandbox`: SPEC.md и PLAN.md
задачи лежат на диске `config.TASKS/<id>/` и читаются FSM через
`disk_backed_show`. Прежнее значение задача получает штатным `approve`
гейта SPEC (SPEC `schema_version: 1` — сразу в `in_dev`); затем PLAN.md с
полем `merge_after` и разделом «## Влияние на систему» сдаётся `advance`
из `in_dev`. Подменены только проверки вне предмета: отставание ветки от
main (ответ `rev-list --count` -> 0 через `in_repo_handlers` песочницы) и
Draft MR форжа; планки у задач сценария нет (SPEC `schema_version: 1`). Значение колонки читается как перечень id в порядке
записи. Форма элементов (полный id или префикс), число зависимостей и
вариант негодного значения — от зерна; зерно печатается и входит в текст
каждого провала.
"""
import random
import re
import subprocess
import unittest
from unittest import mock

from orchestrator import catalog, config, fsm, github_adapter, idgen, store
from tests.sandbox import LightTransitionSandbox, capture_new_task_id

SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 1
{field_line}---

# SPEC: фикстура канала PLAN

## Контекст

Фикстура.

## Требования

1. Фикстура.

## Критерии приёмки

Фикстура.

## Не входит

Ничего.
"""

PLAN_TEXT = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 1
{field_line}---

# PLAN: фикстура канала PLAN

## Подход

Фикстура.

## Шаги

1. Фикстура.

## Покрытие требований

Фикстура.

## Влияние на систему

{impact}
"""

JUSTIFIED = "- merge_after: порядок мержа меняется — {why}."
UNJUSTIFIED = "- Порядок мержа не меняется ({why})."


def ids_of(value) -> list[str]:
    """Перечень id в значении колонки `merge_after` (пусто/NULL — пустой)."""
    return re.findall(r"[0-9A-Za-z]+", value or "")


class PlanChannelSandbox(LightTransitionSandbox):

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.conn = store.db()
        self.in_repo_handlers.append(self.branch_not_behind)
        patcher = mock.patch.object(github_adapter, "ensure_draft_mr",
                                    lambda conn, task_id, t: None)
        patcher.start()
        self.addCleanup(patcher.stop)

    @staticmethod
    def branch_not_behind(repo, *args):
        """Ответ точки расширения песочницы `in_repo_handlers`: ветка задачи
        не отстала от main (`rev-list --count` -> 0), подтяжки нет."""
        if args[:2] == ("rev-list", "--count"):
            return subprocess.CompletedProcess(list(args), 0, "0\n", "")
        return None

    # --- входы ---------------------------------------------------------------

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def new_task(self) -> str:
        _, task_id = capture_new_task_id(catalog.cmd_new,
                                         f"Зависимость {self.rng.randrange(1 << 20)}")
        return task_id

    def unique_prefix(self, task_id: str) -> str:
        others = [r["id"] for r in store.all_tasks(self.conn) if r["id"] != task_id]
        shortest = next(n for n in range(1, len(task_id) + 1)
                        if not any(o.startswith(task_id[:n]) for o in others))
        return task_id[:self.rng.randint(shortest, len(task_id))]

    def element(self, task_id: str) -> str:
        return task_id if self.rng.random() < 0.5 else self.unique_prefix(task_id)

    def field_line(self, deps) -> str:
        if deps is None:
            return ""
        return f"merge_after: {', '.join(self.element(d) for d in deps)}\n"

    # --- сценарий ------------------------------------------------------------

    def write_doc(self, task_id: str, name: str, text: str) -> None:
        tdir = config.TASKS / task_id
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / name).write_text(text, encoding="utf-8")

    def set_task_state(self, task_id: str, state: str) -> None:
        self.conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, task_id))
        self.conn.commit()

    def deps(self, task_id: str) -> list[str]:
        return ids_of(store.get_task(self.conn, task_id)["merge_after"])

    def state_of(self, task_id: str) -> str:
        return store.get_task(self.conn, task_id)["state"]

    def approve_spec(self, task_id: str, deps) -> str:
        """`approve` гейта SPEC с `merge_after: deps` — штатная запись
        прежнего значения; предпосылка: значение записано."""
        self.write_doc(task_id, "SPEC.md", SPEC_TEXT.format(
            task=task_id, field_line=self.field_line(deps)))
        self.set_task_state(task_id, "spec_gate")
        out = self.capture(fsm.cmd_approve, task_id)
        self.assertEqual(self.deps(task_id), list(deps or []), self.note(
            f"предпосылка: approve гейта SPEC {task_id} не записал "
            f"merge_after {deps}:\n{out}"))
        return out

    def advance_with_plan(self, task_id: str, plan_field_line: str,
                          justified: bool) -> str:
        why = f"фикстура {self.rng.randrange(1 << 20)}"
        impact = (JUSTIFIED if justified else UNJUSTIFIED).format(why=why)
        self.write_doc(task_id, "PLAN.md", PLAN_TEXT.format(
            task=task_id, field_line=plan_field_line, impact=impact))
        self.set_task_state(task_id, "in_dev")
        return self.capture(fsm.cmd_advance, task_id)

    def last_step_id(self, task_id: str) -> int:
        rows = store.task_steps(self.conn, task_id)
        return rows[-1]["id"] if rows else 0

    def journal_since(self, task_id: str, since: int) -> list[str]:
        return [f"{r['action']} | {r['detail'] or ''}"
                for r in store.task_steps(self.conn, task_id) if r["id"] > since]

    def prepared_task(self) -> tuple[str, list[str]]:
        """Задача в `in_dev` с прежним `merge_after` из одной-двух живых
        зависимостей, записанным гейтом SPEC."""
        task_id = self.new_task()
        old = [self.new_task() for _ in range(self.rng.randint(1, 2))]
        self.approve_spec(task_id, old)
        return task_id, old


class PlanChannelAppliesTest(PlanChannelSandbox):

    def test_ac9_justified_plan_value_replaces_db_value(self):
        """Обоснованный `merge_after` PLAN, отличный от БД, переписывает колонку полными id.

        Сценарий: прежнее значение — одна-две живые зависимости; PLAN несёт
        другой перечень (одна-две новые живые задачи, от зерна — с одной из
        прежних или без неё) префиксами или полными id, раздел «Влияние на
        систему» упоминает `merge_after`. После `advance` задача в
        `verifying`, колонка — новые полные id в порядке PLAN, одна запись
        журнала называет и все прежние, и все новые id.

        Ловит мутацию: значение PLAN применяется сырым (префиксы не
        разрешены) или запись журнала не называет прежнее значение —
        колонка расходится с полными id либо записи «было → стало» нет.
        """
        task_id, old = self.prepared_task()
        new = [self.new_task() for _ in range(self.rng.randint(1, 2))]
        if self.rng.random() < 0.5:
            new.append(self.rng.choice(old))
        self.rng.shuffle(new)
        since = self.last_step_id(task_id)

        out = self.advance_with_plan(task_id, self.field_line(new), justified=True)

        journal = self.journal_since(task_id, since)
        context = self.note(f"было {old}, PLAN {new}\nжурнал: {journal}\n"
                            f"вывод advance:\n{out}")
        self.assertEqual(self.state_of(task_id), "verifying", context)
        self.assertEqual(self.deps(task_id), new, context)
        self.assertTrue([e for e in journal
                         if all(i in e for i in old + new)], context)

    def test_ac9_empty_plan_value_clears_dependencies(self):
        """Пустое `merge_after:` в обоснованном PLAN снимает все зависимости.

        Сценарий: прежнее значение — одна-две живые зависимости; PLAN несёт
        пустое поле `merge_after:`, раздел «Влияние на систему» упоминает
        `merge_after`. После `advance` задача в `verifying`, колонка пуста,
        одна запись журнала называет все прежние id.

        Ловит мутацию: пустое поле читается как «поля нет» — колонка
        сохраняет прежние зависимости.
        """
        task_id, old = self.prepared_task()
        since = self.last_step_id(task_id)

        out = self.advance_with_plan(task_id, "merge_after:\n", justified=True)

        journal = self.journal_since(task_id, since)
        context = self.note(f"было {old}\nжурнал: {journal}\nвывод:\n{out}")
        self.assertEqual(self.state_of(task_id), "verifying", context)
        self.assertEqual(self.deps(task_id), [], context)
        self.assertTrue([e for e in journal if all(i in e for i in old)], context)

    def test_ac9_plan_without_field_keeps_db_value(self):
        """PLAN без поля `merge_after` значение в БД не меняет.

        Сценарий: прежнее значение — одна-две живые зависимости; PLAN поля
        не несёт, раздел «Влияние на систему» от зерна упоминает
        `merge_after` или нет. После `advance` задача в `verifying`, колонка
        — прежний перечень.

        Ловит мутацию: отсутствие поля в PLAN читается как пустое значение —
        зависимости сняты.
        """
        task_id, old = self.prepared_task()

        out = self.advance_with_plan(task_id, "",
                                     justified=self.rng.random() < 0.5)

        context = self.note(f"было {old}\nвывод:\n{out}")
        self.assertEqual(self.state_of(task_id), "verifying", context)
        self.assertEqual(self.deps(task_id), old, context)


class PlanChannelRejectsTest(PlanChannelSandbox):

    def rejected_case(self, case: str, task_id: str, old: list[str]):
        """(строка поля PLAN, обоснован ли PLAN, элемент для журнала или None)."""
        if case == "нет такой задачи":
            missing = idgen.new_task_id()
            return f"merge_after: {missing}\n", True, missing
        if case == "убитая":
            dead = self.new_task()
            self.set_task_state(dead, "killed")
            element = self.element(dead)
            return f"merge_after: {element}\n", True, element
        if case == "собственная":
            return f"merge_after: {task_id}\n", True, task_id
        if case == "цикл":
            other = self.new_task()
            self.approve_spec(other, [task_id])
            element = self.element(other)
            return f"merge_after: {element}\n", True, element
        fresh = self.new_task()
        return f"merge_after: {self.element(fresh)}\n", False, None

    def test_ac10_rejected_plan_value_keeps_db_and_transition(self):
        """Негодный или необоснованный `merge_after` PLAN отклоняется, переход идёт дальше.

        Сценарий: для каждого варианта — своя задача с прежним значением из
        одной-двух живых зависимостей; PLAN несёт отличное от БД значение:
        несуществующий id, убитую задачу, id самой задачи, задачу, чья
        колонка уже ведёт в эту задачу (цикл), либо годную живую задачу без
        упоминания `merge_after` в «Влиянии на систему». После `advance`:
        задача в `verifying`, колонка — прежний перечень, в журнале есть
        запись об отклонении `merge_after` (для негодного элемента —
        называющая его).

        Ловит мутацию: отказ значения останавливает переход (задача
        остаётся в `in_dev`) либо проверка обоснования/элемента снята —
        колонка переписана негодным значением.
        """
        cases = ["нет такой задачи", "убитая", "собственная", "цикл",
                 "без обоснования"]
        self.rng.shuffle(cases)
        for case in cases:
            with self.subTest(case=case):
                task_id, old = self.prepared_task()
                field_line, justified, named = self.rejected_case(case, task_id, old)
                since = self.last_step_id(task_id)

                out = self.advance_with_plan(task_id, field_line, justified)

                journal = self.journal_since(task_id, since)
                context = self.note(f"{case}: было {old}, PLAN {field_line!r}\n"
                                    f"журнал: {journal}\nвывод:\n{out}")
                self.assertEqual(self.state_of(task_id), "verifying", context)
                self.assertEqual(self.deps(task_id), old, context)
                rejected = [e for e in journal
                            if "merge_after" in e and "отклон" in e.lower()]
                self.assertTrue(rejected, context)
                if named is not None:
                    self.assertTrue([e for e in rejected if named in e], context)


if __name__ == "__main__":
    unittest.main()
