"""Сверка поля `merge_after` SPEC с заявленным Оператором на `approve` гейта SPEC (AC-9..AC-13).

Группа: долгоживущий
Красен до реализации: new строку «Порядок: после …» не разбирает — у задачи нет заявленного значения, approve на spec_gate пишет поле SPEC без сверки (SPEC без заявленной зависимости проходит, добавка без обоснования проходит, записи «добавлено аналитиком» нет), а предпосылка «колонка равна заявленному после new» краснеет сразу; test_ac13 зелёный с рождения (задача без заявленных зависимостей уже сегодня проходит гейт значением SPEC).

Песочница — `tests.sandbox.LightTransitionSandbox`: задача с заявленными
зависимостями заводится штатным `catalog.cmd_new` с файлом ТЗ, SPEC.md
лежит на диске `config.TASKS/<id>/` и читается гейтом через
`disk_backed_show`. `answer` в лёгкой песочнице не видит кодовой ветки
задачи: дерево её `ls_tree_files(…, ".")` отвечает «git не ответил»
(`None`) — проверка существования путей мандата зон не применяется,
предмет сценариев она не задевает. Значение колонки читается как перечень
id в порядке записи. Число зависимостей, форма элементов (полный id или
префикс), их порядок и вид потери/добавки — от зерна; зерно печатается и
входит в текст каждого провала.
"""
import contextlib
import io
import os
import random
import re
import unittest
from unittest import mock

from orchestrator import answer, catalog, config, fsm, store
from tests.sandbox import (LightTransitionSandbox, capture_new_task_id,
                           disk_backed_ls_tree_files)

DECLARED_ACTION = "merge_after заявлен Оператором"
ADDED_ACTION = "добавлено аналитиком"
REFUSED = "approve отклонён"
JUSTIFICATION = "## Обоснование зависимостей мержа"
MANDATE = "Зависимости мержа:"
ZONES = "orchestrator/catalog.py"
CHANNEL_MANDATE = re.compile(r"мандат|ANSWER|answer")
CHANNEL_ESCALATION = re.compile(r"эскалац", re.IGNORECASE)

SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: {zones}
budget_usd: 30
{field_line}---

# SPEC: фикстура сверки заявленных зависимостей

## Контекст

Фикстура. {context}

## Требования

1. Фикстура.
{justification}
## Критерии приёмки

AC-1. Фикстура.

## Не входит

Ничего.

## Материалы

Нет.
"""


def ids_of(value) -> list[str]:
    """Перечень id в значении колонки `merge_after` (пусто/NULL — пустой)."""
    return re.findall(r"[0-9A-Za-z]+", value or "")


def no_code_tree(branch, rel, *, repo=None):
    """`ls_tree_files` лёгкой песочницы: дерева кодовой ветки нет (`None`),
    артефакты задачи — с диска, как у `disk_backed_ls_tree_files`."""
    if rel == ".":
        return None
    return disk_backed_ls_tree_files(branch, rel, repo=repo)


class DeclaredSpecGateSandbox(LightTransitionSandbox):

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        path = self.root / ZONES
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# фикстура\n", encoding="utf-8")
        self.conn = store.db()
        env = mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: ""})
        env.start()
        self.addCleanup(env.stop)

    # --- входы ---------------------------------------------------------------

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def live_task(self) -> str:
        _, task_id = capture_new_task_id(
            catalog.cmd_new, f"Зависимость {self.rng.randrange(1 << 20)}")
        return task_id

    def all_ids(self) -> list[str]:
        return [r["id"] for r in store.all_tasks(self.conn)]

    def unique_prefix(self, task_id: str) -> str:
        """Префикс `task_id`, однозначный среди задач БД (длина — от зерна)."""
        others = [i for i in self.all_ids() if i != task_id]
        shortest = next(n for n in range(1, len(task_id) + 1)
                        if not any(o.startswith(task_id[:n]) for o in others))
        return task_id[:self.rng.randint(shortest, len(task_id))]

    def element(self, task_id: str) -> str:
        return task_id if self.rng.random() < 0.5 else self.unique_prefix(task_id)

    def tz_file(self, *order_lines: str, requirement: str = "Фикстура."):
        path = self.root / f"tz-{self.rng.randrange(1 << 30)}.md"
        order = "".join(f"{line}\n\n" for line in order_lines)
        path.write_text(f"Источник: фикстура {self.seed}.\n\nТребуется:\n"
                        f"1. {requirement}\n\n{order}Зоны: {ZONES}.\n",
                        encoding="utf-8")
        return path

    def declared_task(self, count: int | None = None) -> tuple[str, list[str]]:
        """Задача, заведённая `new --tz` со строкой «Порядок: после …» на
        `count` (по умолчанию одну-три, от зерна) живых зависимостей; (id,
        заявленные полные id в порядке строки)."""
        deps = [self.live_task()
                for _ in range(count or self.rng.randint(1, 3))]
        self.rng.shuffle(deps)
        line = f"Порядок: после {', '.join(self.element(d) for d in deps)}"
        out, task_id = capture_new_task_id(
            catalog.cmd_new, f"Задача {self.rng.randrange(1 << 20)}",
            str(self.tz_file(line)))
        self.assertEqual(self.deps(task_id), deps, self.note(
            f"предпосылка: new не заявил {deps} строкой «{line}»:\n{out}"))
        return task_id, deps

    # --- сценарий ------------------------------------------------------------

    def write_spec(self, task_id: str, field_value, justification=None,
                   context: str = "") -> None:
        field_line = "" if field_value is None else f"merge_after: {field_value}\n"
        section = ("" if justification is None
                   else f"\n{JUSTIFICATION}\n\n{justification}\n")
        tdir = config.TASKS / task_id
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "SPEC.md").write_text(
            SPEC_TEXT.format(task=task_id, zones=ZONES, field_line=field_line,
                             justification=section, context=context),
            encoding="utf-8")

    def set_state(self, task_id: str, state: str) -> None:
        self.conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, task_id))
        self.conn.commit()

    def run_cmd(self, fn, *args) -> str:
        """Вывод команды вместе с текстом ненулевого `SystemExit`."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                fn(*args)
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    buf.write(f"\n{exc.code}")
        return buf.getvalue()

    def approve_spec(self, task_id: str, field_value, justification=None,
                     context: str = "") -> str:
        """SPEC с `merge_after: field_value` (None — без поля) и `approve`
        на `spec_gate`."""
        self.write_spec(task_id, field_value, justification, context)
        self.set_state(task_id, "spec_gate")
        return self.run_cmd(fsm.cmd_approve, task_id)

    def answer(self, task_id: str, body: str) -> str:
        source = self.root / f"answer-{self.rng.randrange(1 << 30)}.txt"
        source.write_text(f"{body}\n\nОснование: решение Оператора "
                          f"({self.seed}).\n", encoding="utf-8")
        with mock.patch("orchestrator.gitcmd.ls_tree_files", no_code_tree):
            return self.run_cmd(answer.cmd_answer, task_id, str(source))

    def row(self, task_id: str):
        return store.get_task(self.conn, task_id)

    def deps(self, task_id: str) -> list[str]:
        return ids_of(self.row(task_id)["merge_after"])

    def last_step_id(self, task_id: str) -> int:
        rows = store.task_steps(self.conn, task_id)
        return rows[-1]["id"] if rows else 0

    def journal_since(self, task_id: str, since: int) -> list[str]:
        return [f"{r['action']} | {r['detail'] or ''}"
                for r in store.task_steps(self.conn, task_id) if r["id"] > since]

    # --- сверки --------------------------------------------------------------

    def spec_value_losing(self, declared: list[str]) -> tuple[str | None, list[str]]:
        """(значение поля SPEC либо `None` — без поля, потерянные id): поле
        без хотя бы одной заявленной зависимости."""
        kept = [d for d in declared if self.rng.random() < 0.5]
        if len(kept) == len(declared):
            kept.pop(self.rng.randrange(len(kept)))
        lost = [d for d in declared if d not in kept]
        if not kept or self.rng.random() < 0.3:
            return None, list(declared)
        self.rng.shuffle(kept)
        return ", ".join(self.element(d) for d in kept), lost

    def assert_refused(self, task_id: str, expected_column: list[str],
                       named: list[str], field_value, justification=None,
                       context: str = "", channels: bool = True) -> list[str]:
        """`approve` мягко отказывает: задача на `spec_gate`, колонка равна
        `expected_column`, запись журнала «approve отклонён» называет каждый
        id `named` (и, если `channels`, оба канала снятия)."""
        since = self.last_step_id(task_id)

        out = self.approve_spec(task_id, field_value, justification, context)

        journal = self.journal_since(task_id, since)
        note = self.note(f"merge_after: {field_value}\nобоснование: "
                         f"{justification}\nжурнал: {journal}\nвывод:\n{out}")
        self.assertEqual(self.row(task_id)["state"], "spec_gate", note)
        self.assertEqual(self.deps(task_id), expected_column, note)
        refusals = [e for e in journal if REFUSED in e
                    and all(n in e for n in named)]
        self.assertTrue(refusals, self.note(f"нет «{REFUSED}» с {named}: {note}"))
        if channels:
            self.assertTrue([e for e in refusals if CHANNEL_MANDATE.search(e)
                             and CHANNEL_ESCALATION.search(e)],
                            self.note(f"отказ не называет каналы снятия: {note}"))
        return journal

    def assert_passed(self, task_id: str, field_value, expected: list[str],
                      justification=None) -> list[str]:
        """`approve` уводит задачу со `spec_gate` и пишет значение SPEC
        (`expected` — полные id в порядке поля); записи журнала approve."""
        since = self.last_step_id(task_id)

        out = self.approve_spec(task_id, field_value, justification)

        journal = self.journal_since(task_id, since)
        note = self.note(f"merge_after: {field_value}\nобоснование: "
                         f"{justification}\nжурнал: {journal}\nвывод:\n{out}")
        self.assertNotEqual(self.row(task_id)["state"], "spec_gate", note)
        self.assertEqual(self.deps(task_id), expected, note)
        self.assertEqual(self.row(task_id)["zones"], ZONES, note)
        return journal


class SpecGateLossTest(DeclaredSpecGateSandbox):

    def test_ac9_spec_losing_declared_dependency_refused(self):
        """SPEC без заявленной зависимости (или без поля) — мягкий отказ approve с полным id и каналами снятия.

        Сценарий: задача заведена `new` с одной-тремя заявленными
        зависимостями; поле SPEC от зерна либо отсутствует, либо несёт
        часть заявленных (префиксами или полными id), потеряв хотя бы одну.
        Задача на `spec_gate`, колонка `merge_after` равна заявленному,
        журнал «approve отклонён» называет полный id каждой потерянной и
        оба канала снятия — мандат в ANSWER и эскалацию аналитика.

        Ловит мутацию: сверка с заявленным не делается (approve
        перезаписывает колонку значением SPEC, SPEC без поля стирает её)
        либо сверка идёт после записи колонки — заявленное значение
        потеряно, задача ушла с гейта.
        """
        task_id, declared = self.declared_task()
        field_value, lost = self.spec_value_losing(declared)

        self.assert_refused(task_id, declared, lost, field_value)


class SpecGateMatchAndAdditionTest(DeclaredSpecGateSandbox):

    def test_ac10_spec_with_all_declared_passes(self):
        """Поле SPEC со всеми заявленными в любом порядке и форме — approve проходит и пишет значение SPEC.

        Сценарий: заявленные одна-три зависимости; поле SPEC несёт их все,
        порядок перемешан, каждая — префиксом или полным id (от зерна).
        Задача ушла со `spec_gate`, колонка — полные id в порядке поля
        SPEC.

        Ловит мутацию: сверка сравнивает сырые элементы поля с заявленными
        полными id (префикс не разрешён) либо требует порядок строки ТЗ —
        годный SPEC отказан.
        """
        task_id, declared = self.declared_task()
        order = list(declared)
        self.rng.shuffle(order)

        self.assert_passed(task_id, ", ".join(self.element(d) for d in order),
                           order)

    def test_ac10_justified_addition_passes_and_journaled(self):
        """Добавка аналитика, названная в разделе обоснования, — approve проходит, журнал «добавлено аналитиком».

        Сценарий: заявленные одна-две зависимости; поле SPEC несёт их и
        ещё одну живую задачу (место — от зерна); раздел «## Обоснование
        зависимостей мержа» называет добавку полным id либо тем же
        элементом, что стоит в поле (от зерна). Задача ушла со
        `spec_gate`, колонка — полные id в порядке поля, журнал несёт
        запись «добавлено аналитиком» с полным id добавки.

        Ловит мутацию: обоснование ищется только по полному id (префикс,
        стоящий в поле, не засчитан) — approve отказан; либо запись
        «добавлено аналитиком» не делается.
        """
        task_id, declared = self.declared_task(self.rng.randint(1, 2))
        extra = self.live_task()
        order = declared + [extra]
        self.rng.shuffle(order)
        elements = {d: self.element(d) for d in order}
        named = extra if self.rng.random() < 0.5 else elements[extra]

        journal = self.assert_passed(
            task_id, ", ".join(elements[d] for d in order), order,
            justification=f"Нужна {named}: она правит тот же узел.")

        self.assertTrue([e for e in journal if ADDED_ACTION in e and extra in e],
                        self.note(f"нет «{ADDED_ACTION}» с {extra}: {journal}"))

    def test_ac10_unjustified_addition_refused(self):
        """Та же добавка без упоминания в разделе обоснования — мягкий отказ с полным id добавки.

        Сценарий: заявленные одна-две зависимости; поле SPEC несёт их и
        добавку (префиксом или полным id). От зерна: раздела «## Обоснование
        зависимостей мержа» нет; раздел есть, но называет только заявленные;
        либо добавка названа в «## Контексте», а не в разделе обоснования.
        Задача на `spec_gate`, колонка равна заявленному, журнал «approve
        отклонён» называет полный id добавки.

        Ловит мутацию: обоснование ищется по всему тексту SPEC, а не в
        разделе (добавка из «Контекста» засчитана), либо добавка
        принимается без обоснования — задача ушла с гейта.
        """
        task_id, declared = self.declared_task(self.rng.randint(1, 2))
        extra = self.live_task()
        order = declared + [extra]
        self.rng.shuffle(order)
        value = ", ".join(self.element(d) for d in order)
        variant = self.rng.choice(["нет раздела", "раздел без добавки",
                                   "добавка в контексте"])
        justification, context = None, ""
        if variant == "раздел без добавки":
            justification = f"Заявлены Оператором: {', '.join(declared)}."
        elif variant == "добавка в контексте":
            context = f"Рядом идёт {extra}."

        self.assert_refused(task_id, declared, [extra], value,
                            justification=justification, context=context,
                            channels=False)


class SpecGateAfterRejectTest(DeclaredSpecGateSandbox):

    def test_ac11_reject_and_second_pass_keep_declared(self):
        """После `reject` и повторного прохода `spec_writing -> spec_gate` колонка равна заявленному, сверка та же.

        Сценарий: задача с заявленными зависимостями на `spec_gate`
        отклоняется `reject` (возврат в `spec_writing`), затем снова
        приходит на `spec_gate`. Колонка равна заявленному; `approve` с SPEC,
        теряющим заявленную, мягко отказывает по ней; затем `approve` с SPEC
        со всеми заявленными проходит.

        Ловит мутацию: `reject` или повторный проход переписывает колонку
        (значением SPEC либо пустым) — заявленное потеряно, второй approve
        сверяет уже не с ним и пропускает потерю.
        """
        task_id, declared = self.declared_task()
        self.write_spec(task_id, None)
        self.set_state(task_id, "spec_gate")
        out = self.run_cmd(fsm.cmd_reject, task_id, f"доработать ({self.seed})")
        self.assertEqual(self.row(task_id)["state"], "spec_writing",
                         self.note(f"предпосылка: reject:\n{out}"))
        self.assertEqual(self.deps(task_id), declared,
                         self.note(f"колонка после reject:\n{out}"))
        self.write_spec(task_id, self.rng.choice(
            [None, ", ".join(self.element(d) for d in declared)]))
        out = self.run_cmd(fsm.cmd_advance, task_id)
        self.assertEqual(self.row(task_id)["state"], "spec_gate",
                         self.note(f"предпосылка: advance из spec_writing:\n{out}"))
        self.assertEqual(self.deps(task_id), declared, self.note(
            f"колонка после повторного прихода на spec_gate:\n{out}"))

        field_value, lost = self.spec_value_losing(declared)
        self.assert_refused(task_id, declared, lost, field_value)

        order = list(declared)
        self.rng.shuffle(order)
        self.assert_passed(task_id, ", ".join(self.element(d) for d in order),
                           order)


class SpecGateMandateTest(DeclaredSpecGateSandbox):

    def escalated_with_mandate(self, body_deps) -> tuple[str, list[str]]:
        """Задача с заявленными, эскалированная из `spec_writing`, после
        `answer` с мандатом (`body_deps` — перечень либо `None` — «нет»);
        (id, прежние заявленные)."""
        task_id, declared = self.declared_task(self.rng.randint(1, 2))
        self.conn.execute("UPDATE tasks SET state='escalated', "
                          "escalated_from='spec_writing' WHERE id=?", (task_id,))
        self.conn.commit()
        line = (f"{MANDATE} нет" if body_deps is None else
                f"{MANDATE} {', '.join(self.element(d) for d in body_deps)}")

        out = self.answer(task_id, line)

        self.assertEqual(self.deps(task_id), list(body_deps or []),
                         self.note(f"answer «{line}» не сменил колонку:\n{out}"))
        return task_id, declared

    def test_ac12_mandate_replaces_declared_value(self):
        """Мандат «Зависимости мержа: X» в `escalated` до гейта SPEC делает X заявленным.

        Сценарий: заявленные одна-две зависимости; `answer` с мандатом на
        одну-две другие живые задачи X — колонка равна X. На `spec_gate`
        SPEC без X (от зерна: прежние заявленные или без поля) — мягкий
        отказ с полным id из X; SPEC с `merge_after: X` без раздела
        обоснования — approve проходит, колонка — X.

        Ловит мутацию: сверка идёт с заявленным значением, сохранённым при
        `new` отдельно от колонки (мандат его не меняет), — SPEC с X
        требует обоснования и отказан, а SPEC с прежними проходит.
        """
        replacement = [self.live_task() for _ in range(self.rng.randint(1, 2))]
        task_id, declared = self.escalated_with_mandate(replacement)

        losing = (None if self.rng.random() < 0.5
                  else ", ".join(self.element(d) for d in declared))
        self.assert_refused(task_id, replacement, replacement, losing)

        self.assert_passed(task_id,
                           ", ".join(self.element(d) for d in replacement),
                           replacement)

    def test_ac12_mandate_none_clears_declared_value(self):
        """Мандат «Зависимости мержа: нет» снимает заявленное — SPEC без поля проходит.

        Сценарий: заявленные одна-две зависимости; `answer` с мандатом
        «нет» — колонка пуста; на `spec_gate` SPEC без поля `merge_after` —
        approve проходит, колонка пуста.

        Ловит мутацию: заявленное хранится отдельно от колонки и мандат его
        не снимает — SPEC без поля отказан как теряющий зависимости.
        """
        task_id, _declared = self.escalated_with_mandate(None)

        self.assert_passed(task_id, None, [])


class SpecGateWithoutDeclaredTest(DeclaredSpecGateSandbox):

    def test_ac13_tasks_without_declared_pass_spec_value_as_today(self):
        """Без строки, без ТЗ, подзадача деления и канарейка — колонка пуста, гейт пишет значение SPEC без обоснования.

        Сценарий: четыре варианта заведения (порядок — от зерна): ТЗ без
        строки «Порядок: после …» (пункт «Требуется» упоминает «после
        <id>»), `new` без ТЗ, `spawn_subtask` с телом, несущим «Порядок:
        после <id>», `cmd_new(..., canary=True)` с ТЗ, несущим «Порядок:
        после <id>». После заведения колонка пуста, записи «merge_after
        заявлен Оператором» нет; `approve` с SPEC, чьё поле называет одну-две
        живые задачи без раздела обоснования, проходит и пишет их полные id.

        Ловит мутацию: строку разбирают и канарейка/подзадача деления
        (колонка непуста), либо сверка добавки требует обоснования и при
        пустом заявленном — approve отказан.
        """
        variants = ["ТЗ без строки", "без ТЗ", "подзадача деления", "канарейка"]
        self.rng.shuffle(variants)
        for variant in variants:
            with self.subTest(variant=variant):
                live = self.live_task()
                title = f"Задача {self.rng.randrange(1 << 20)}"
                order_line = f"Порядок: после {self.element(live)}"
                if variant == "ТЗ без строки":
                    tz = self.tz_file(requirement=f"Сделать после {live}.")
                    _, task_id = capture_new_task_id(catalog.cmd_new, title,
                                                     str(tz))
                elif variant == "без ТЗ":
                    _, task_id = capture_new_task_id(catalog.cmd_new, title)
                elif variant == "подзадача деления":
                    _, task_id = capture_new_task_id(
                        catalog.spawn_subtask, self.TASK, self.TASK_TITLE,
                        title, f"Зоны: {ZONES}\n{order_line}\n\nТребуется:\n"
                               f"1. Фикстура.\n")
                else:
                    tz = self.tz_file(order_line)
                    buf = io.StringIO()
                    with contextlib.redirect_stdout(buf):
                        task_id = catalog.cmd_new(title, str(tz), canary=True)

                journal = [f"{r['action']} | {r['detail'] or ''}"
                           for r in store.task_steps(self.conn, task_id)]
                note = self.note(f"{variant}: журнал {journal}")
                self.assertEqual(self.deps(task_id), [], note)
                self.assertFalse([e for e in journal if DECLARED_ACTION in e],
                                 note)

                deps = [self.live_task() for _ in range(self.rng.randint(1, 2))]
                self.assert_passed(task_id,
                                   ", ".join(self.element(d) for d in deps),
                                   deps)


if __name__ == "__main__":
    unittest.main()
