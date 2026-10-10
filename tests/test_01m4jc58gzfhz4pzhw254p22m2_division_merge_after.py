"""Деление задачи на гейте SPEC переписывает `merge_after` задач, зависящих
от поделённого родителя: элемент-родитель заменяется последней подзадачей
деления, прочие элементы и их порядок остаются; запись «было → стало» —
в журнал зависящей задачи; гейт мержа зависящей задачи больше не
отказывает «зависимость мержа убита» из-за родителя.

Группа: долгоживущий

Связка, которую держит файл: команда `approve` на `spec_gate` — FSM
(`killed` родителя, заведение подзадач) — БД (колонка `merge_after` и
журнал ЧУЖОЙ, зависящей задачи). Поэтому песочница переходов
(`tests.sandbox.LightTransitionSandbox`): SPEC родителя лежит на диске
временного каталога (`self.tdir`), git подменён песочницей целиком.

Входы порождаются при каждом запуске модулем `random`: число подзадач
деления, число зависящих задач, позиция родителя в их `merge_after` и
число соседних зависимостей. Зерно печатается и входит в текст провала.

Красен до реализации: деление сегодня только переводит родителя в `killed` и не трогает `merge_after` зависящих задач — колонка D по-прежнему называет родителя, записи «merge_after изменён» в журнале D нет, и approve на `merge_gate` D отказывает «зависимость мержа убита».
"""
import random
import unittest

from orchestrator import catalog, fsm, merge_after, store
from tests.sandbox import LightTransitionSandbox, capture_new_task_id

# Вымышленный путь зоны: сверка путей SPEC с `zones:` на входе approve
# обязана пройти, иначе до деления дело не дойдёт.
ZONE = "orchestrator/t4jc_zone.py"

DIVIDED_PREFIX = "поделена на:"


def division_spec(task_id: str, parts: int) -> str:
    """SPEC родителя на гейте с секцией «## Деление» из `parts` частей."""
    sections = "\n".join(
        f"### Часть {n} фикстуры\n\n"
        f"Зоны: {ZONE}\n"
        f"Порядок: {'первая, без зависимостей' if n == 1 else f'после части {n - 1}'}\n\n"
        f"Текст ТЗ части {n}.\n"
        for n in range(1, parts + 1))
    return f"""---
task: {task_id}
type: spec
author_role: analyst
status: ready
schema_version: 1
budget_usd: 15
zones: {ZONE}
---

# SPEC: Родитель, поделённый на гейте SPEC

## Контекст
Фикстура деления — короткий безобидный текст.

## Требования
1. Первое требование фикстуры.

## Критерии приёмки
AC-1. Первый критерий фикстуры.

## Деление

{sections}
## Не входит
- Всё остальное.
"""


class DivisionRewritesDependentsTest(LightTransitionSandbox):
    """Родитель P (задача песочницы) на `spec_gate` с секцией «## Деление»;
    зависящие задачи D держат P в `merge_after` в паре с соседями X."""

    TASK_TITLE = "Родитель, поделённый на гейте SPEC"

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rnd = random.Random(self.seed)
        self.parent = self.TASK
        self.parts = self.rnd.randint(2, 4)
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / "SPEC.md").write_text(
            division_spec(self.parent, self.parts), encoding="utf-8")
        self.set_state("spec_gate")
        # Зависящие задачи: у каждой P стоит на случайной позиции среди
        # 1..2 соседних зависимостей X (свежих задач, не P).
        self.dependents: dict[str, list[str]] = {}
        for n in range(self.rnd.randint(2, 3)):
            others = [self.new_task(f"Сосед {n}.{k}")
                      for k in range(self.rnd.randint(1, 2))]
            deps = list(others)
            deps.insert(self.rnd.randint(0, len(deps)), self.parent)
            dep_id = self.new_task(f"Зависящая задача {n}")
            store.update_task(store.db(), dep_id,
                              merge_after=merge_after.column(deps))
            self.dependents[dep_id] = deps

    # ------------------------------------------------------------ утилиты

    def new_task(self, title: str) -> str:
        _, task_id = capture_new_task_id(catalog.cmd_new, title)
        return task_id

    def msg(self, text: str = "") -> str:
        return f"зерно: {self.seed}; {text}"

    def divide(self) -> list[str]:
        """approve родителя на гейте SPEC; подзадачи деления в порядке
        записи «поделена на: …» журнала родителя."""
        out = self.capture(fsm.cmd_approve, self.parent)
        self.assertEqual("killed", store.task_state(store.db(), self.parent),
                         self.msg(f"деление не состоялось: {out}"))
        details = [r["detail"] or "" for r in
                   store.task_steps(store.db(), self.parent)
                   if DIVIDED_PREFIX in (r["detail"] or "")]
        self.assertTrue(details, self.msg(f"нет записи деления: {out}"))
        subtasks = [s.strip() for s in
                    details[-1].split(DIVIDED_PREFIX, 1)[1].split(",")]
        self.assertEqual(self.parts, len(subtasks), self.msg(details[-1]))
        return subtasks

    def stored_deps(self, task_id: str) -> list[str]:
        return merge_after.stored(
            store.get_task(store.db(), task_id)["merge_after"])

    def journal(self, task_id: str) -> list:
        return store.task_steps(store.db(), task_id)

    # ------------------------------------------------------------ критерии

    def test_ac1_parent_replaced_by_last_subtask_in_every_dependent(self):
        """Деление P на S1…Sn: у каждой зависящей задачи D элемент P в
        `merge_after` заменён на Sn на той же позиции, соседи X остались.

        Зависящих задач две-три, у каждой P стоит на случайной позиции
        рядом с одной-двумя другими зависимостями.

        Ловит мутацию: вместо последней подзадачи подставлена первая
        (`new_ids[0]`) — значение D называет S1, а не Sn; элемент P
        удалён вместо замены — значение короче прежнего; переписана только
        первая найденная зависящая задача — у второй D в колонке остаётся
        P; соседи X отброшены (значение — один Sn).
        """
        subtasks = self.divide()
        last = subtasks[-1]
        for dep_id, before in self.dependents.items():
            expected = [last if d == self.parent else d for d in before]
            self.assertEqual(
                expected, self.stored_deps(dep_id),
                self.msg(f"merge_after {dep_id}: было {before}, подзадачи "
                         f"{subtasks}"))

    def test_ac2_dependent_journal_names_old_and_new_value(self):
        """Деление P добавляет в журнал каждой зависящей задачи D запись
        `merge_after` «было → стало»: слева прежнее значение с P, справа
        новое — с Sn вместо P.

        Ловит мутацию: колонка D переписана прямым `store.update_task`
        мимо `merge_after.rewrite` — значение новое, а записи
        «merge_after изменён» в журнале D нет; запись сделана в журнал
        родителя P вместо журнала D.
        """
        subtasks = self.divide()
        last = subtasks[-1]
        for dep_id, before in self.dependents.items():
            after = [last if d == self.parent else d for d in before]
            records = [r["detail"] or "" for r in self.journal(dep_id)
                       if r["action"] == merge_after.CHANGED_ACTION]
            self.assertTrue(records, self.msg(
                f"в журнале {dep_id} нет «{merge_after.CHANGED_ACTION}»"))
            detail = records[-1]
            self.assertIn("→", detail, self.msg(detail))
            old_part, new_part = detail.split("→", 1)
            self.assertIn(merge_after.column(before), old_part,
                          self.msg(f"прежнее значение не названо: {detail}"))
            self.assertIn(merge_after.column(after), new_part,
                          self.msg(f"новое значение не названо: {detail}"))
            self.assertNotIn(self.parent, new_part, self.msg(detail))

    def test_ac3_merge_gate_of_dependent_does_not_refuse_on_parent(self):
        """После деления P approve на `merge_gate` зависящей задачи D не
        пишет отказ «зависимость мержа убита» по P.

        D ставится на `merge_gate`, approve вызывается командой; отказ
        «ждёт мержа зависимостей» по ещё не смерженной Sn законен и
        критерием не запрещён.

        Ловит мутацию: деление не переписывает `merge_after` зависящих
        задач (поведение до задачи) либо переписывает только колонку
        родителя — `merge_gate_refuses` видит P в `killed` и журналирует
        «approve отклонён: зависимость мержа убита» с id P.
        """
        self.divide()
        conn = store.db()
        for dep_id in self.dependents:
            conn.execute("UPDATE tasks SET state='merge_gate' WHERE id=?",
                         (dep_id,))
            conn.commit()
            try:
                out = self.capture(fsm.cmd_approve, dep_id)
            except SystemExit as exc:
                out = f"SystemExit: {exc}"
            refusals = [r["detail"] or "" for r in self.journal(dep_id)
                        if r["action"] == merge_after.MERGE_GATE_KILLED_ACTION
                        and self.parent in (r["detail"] or "")]
            self.assertEqual([], refusals, self.msg(
                f"approve {dep_id} отказал по убитому {self.parent}: {out}"))


if __name__ == "__main__":
    unittest.main()
