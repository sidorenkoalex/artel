"""Проверка `merge_after` по БД на `approve` гейта SPEC (AC-2..AC-5).

Группа: долгоживущий
Красен до реализации: approve на spec_gate сегодня поле merge_after не читает и колонки merge_after в таблице tasks нет — негодная зависимость не останавливает задачу на гейте, журнал о ней молчит, а чтение колонки падает KeyError.

Песочница — `tests.sandbox.LightTransitionSandbox`: SPEC.md задачи лежит на
диске `config.TASKS/<id>/` и читается гейтом через `disk_backed_show`.
Задачи-зависимости заводятся либо командой `new` (настоящие свежие id),
либо прямой строкой `store.insert_task` там, где сценарию нужен свой id,
состояние или target. Значение колонки читается как перечень id в порядке
записи (разделитель колонки не предмет критериев). Форма элементов
(полный id или префикс), их порядок и длина цепочки цикла — от зерна; зерно
печатается и входит в текст каждого провала.
"""
import contextlib
import io
import random
import re
import unittest

from orchestrator import catalog, config, fsm, idgen, store
from tests.sandbox import LightTransitionSandbox, capture_new_task_id

ZONES = "orchestrator/catalog.py"
CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

SPEC_TEXT = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: {zones}
budget_usd: 30
{field_line}---

# SPEC: фикстура гейта зависимостей мержа

## Контекст

Фикстура.

## Требования

1. Фикстура.

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


class MergeAfterSpecGateSandbox(LightTransitionSandbox):

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        path = self.root / ZONES
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# фикстура\n", encoding="utf-8")
        self.conn = store.db()

    # --- входы ---------------------------------------------------------------

    def note(self, text: str) -> str:
        return f"зерно: {self.seed}; {text}"

    def new_task(self) -> str:
        _, task_id = capture_new_task_id(catalog.cmd_new,
                                         f"Зависимость {self.rng.randrange(1 << 20)}")
        return task_id

    def insert(self, task_id: str, state: str,
               target: str = config.DEFAULT_TARGET) -> str:
        store.insert_task(self.conn, task_id, f"Фикстура {task_id}", state,
                          f"task/{task_id.lower()}-fixture", target,
                          config.DEFAULT_BUDGET_USD)
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

    # --- сценарий ------------------------------------------------------------

    def write_spec(self, task_id: str, field_value) -> None:
        field_line = "" if field_value is None else f"merge_after: {field_value}\n"
        tdir = config.TASKS / task_id
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "SPEC.md").write_text(
            SPEC_TEXT.format(task=task_id, zones=ZONES, field_line=field_line),
            encoding="utf-8")

    def set_task_state(self, task_id: str, state: str) -> None:
        self.conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, task_id))
        self.conn.commit()

    def approve_spec(self, task_id: str, field_value) -> str:
        """SPEC с `merge_after: field_value` (None — без поля) и `approve`
        на `spec_gate`; вывод вместе с текстом отказа `SystemExit`."""
        self.write_spec(task_id, field_value)
        self.set_task_state(task_id, "spec_gate")
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                fsm.cmd_approve(task_id)
            except SystemExit as exc:
                if exc.code not in (None, 0):
                    buf.write(f"\n{exc.code}")
        return buf.getvalue()

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

    def assert_refused(self, task_id: str, field_value, named: str,
                       reason: re.Pattern) -> None:
        """`approve` с `merge_after: field_value` отказывает мягко: задача на
        `spec_gate`, колонка пуста, журнал называет `named` и причину."""
        since = self.last_step_id(task_id)

        out = self.approve_spec(task_id, field_value)

        journal = self.journal_since(task_id, since)
        context = self.note(f"merge_after: {field_value}\nжурнал: {journal}\n"
                            f"вывод approve:\n{out}")
        self.assertEqual(self.row(task_id)["state"], "spec_gate", context)
        self.assertEqual(self.deps(task_id), [], context)
        self.assertTrue([e for e in journal if named in e and reason.search(e)],
                        self.note(f"журнал не называет {named} и причину "
                                  f"/{reason.pattern}/: {context}"))


class SpecGateMissingOrAmbiguousTest(MergeAfterSpecGateSandbox):

    def test_ac2_missing_task_keeps_spec_gate_and_column_empty(self):
        """Id отсутствующей задачи в `merge_after` — мягкий отказ approve с причиной «нет такой задачи».

        Сценарий: в `merge_after` — свежий id, которого нет в БД; от зерна
        рядом с ним (до или после) стоит годная существующая зависимость.
        Задача остаётся на `spec_gate`, колонка `merge_after` пуста (годный
        элемент тоже не записан), журнал задачи называет отсутствующий id и
        причину.

        Ловит мутацию: отсутствующий элемент молча отбрасывается и в
        колонку пишутся только найденные — задача уходит с гейта, колонка
        непуста, отказа в журнале нет.
        """
        task = self.TASK
        missing = idgen.new_task_id()
        while missing in self.all_ids():
            missing = idgen.new_task_id()
        items = [missing]
        if self.rng.random() < 0.5:
            items.append(self.element(self.new_task()))
            self.rng.shuffle(items)

        self.assert_refused(task, ", ".join(items), missing,
                            re.compile(r"нет такой задачи", re.IGNORECASE))

    def test_ac2_ambiguous_prefix_keeps_spec_gate_and_column_empty(self):
        """Префикс, подходящий к двум задачам, — мягкий отказ approve с причиной «неоднозначен».

        Сценарий: две задачи с id, отличающимися только хвостом, заведены
        прямой строкой БД; в `merge_after` — их общий префикс (длина — от
        зерна). Задача на `spec_gate`, колонка пуста, журнал называет
        префикс и неоднозначность.

        Ловит мутацию: префикс разрешается первым совпадением (`LIMIT 1`)
        вместо узла `store.resolve_task_id` — задача уходит с гейта с
        одной из двух задач в колонке.
        """
        base = idgen.new_task_id()
        length = self.rng.randint(12, 20)
        prefix = base[:length]
        tails = self.rng.sample(CROCKFORD, 2)
        for tail in tails:
            self.insert(prefix + tail + base[length + 1:], "in_dev")

        self.assert_refused(self.TASK, prefix, prefix,
                            re.compile(r"неоднознач", re.IGNORECASE))


class SpecGateKilledForeignSelfTest(MergeAfterSpecGateSandbox):

    def test_ac3_killed_dependency_refused(self):
        """Зависимость в состоянии `killed` — мягкий отказ approve.

        Сценарий: зависимость заведена прямой строкой БД в `killed`; в
        `merge_after` — её id или однозначный префикс. Задача на
        `spec_gate`, колонка пуста, журнал называет элемент и причину
        (убитая задача).

        Ловит мутацию: проверка состояния зависимости снята — убитая задача
        записывается в колонку, задача уходит с гейта.
        """
        dep = self.insert(idgen.new_task_id(), "killed")
        element = self.element(dep)

        self.assert_refused(self.TASK, element, element,
                            re.compile(r"killed|убит", re.IGNORECASE))

    def test_ac3_dependency_of_other_target_refused(self):
        """Зависимость другого target — мягкий отказ approve.

        Сценарий: зависимость заведена прямой строкой БД с target, отличным
        от target задачи (имя — от зерна), в живом состоянии. Задача на
        `spec_gate`, колонка пуста, журнал называет элемент и причину
        (другой target/проект).

        Ловит мутацию: сверка target снята — зависимость чужого проекта
        записывается в колонку, задача уходит с гейта.
        """
        other = f"proekt{self.rng.randrange(1 << 20)}"
        dep = self.insert(idgen.new_task_id(),
                          self.rng.choice(["in_dev", "acceptance", "done"]),
                          target=other)
        element = self.element(dep)

        self.assert_refused(self.TASK, element, element,
                            re.compile(r"target|проект", re.IGNORECASE))

    def test_ac3_prefix_resolving_to_own_id_refused(self):
        """Префикс, разрешающийся в id самой задачи, — мягкий отказ approve.

        Сценарий: в `merge_after` — однозначный префикс собственного id
        задачи (не полный id; длина — от зерна), в БД есть и другие
        задачи. Задача на `spec_gate`, колонка пуста, журнал называет
        префикс и причину (ссылка на саму себя).

        Ловит мутацию: самоссылка сверяется только по буквальному
        совпадению элемента с id задачи, до разрешения префикса, — префикс
        собственного id проходит и пишется в колонку.
        """
        self.new_task()
        own = self.TASK
        prefix = self.unique_prefix(own)
        if prefix == own:
            prefix = own[:-1]
        self.assertEqual(store.resolve_task_id(self.conn, prefix), own,
                         self.note(f"предпосылка: {prefix} однозначен"))

        self.assert_refused(own, prefix, prefix,
                            re.compile(r"сам|собствен", re.IGNORECASE))


class SpecGateCycleTest(MergeAfterSpecGateSandbox):

    def test_ac4_cycle_through_existing_values_refused(self):
        """`merge_after: B` у задачи A, когда цепочка БД от B уже ведёт в A, — отказ «цикл».

        Сценарий: длина цепочки — от зерна: либо у B в БД уже записано
        `merge_after = A`, либо B -> C и C -> A (третья задача). Значения
        цепочки записаны штатным `approve` гейта SPEC самих B и C. Затем
        `approve` A с `merge_after: B`: A на `spec_gate`, колонка A пуста,
        журнал A называет элемент B и причину «цикл».

        Ловит мутацию: проверка цикла смотрит только на прямую обратную
        ссылку B -> A (без обхода графа) — цикл через C проходит; либо
        граф строится без нового значения A — цикла не видно вовсе.
        """
        a = self.TASK
        chain = [self.new_task() for _ in range(self.rng.randint(1, 2))]
        # Последний в цепочке ссылается на A, каждый предыдущий — на
        # следующего; утверждаются с конца, чтобы каждый шаг был годен.
        targets = chain[1:] + [a]
        for task_id, dep in reversed(list(zip(chain, targets))):
            out = self.approve_spec(task_id, self.element(dep))
            self.assertEqual(self.deps(task_id), [dep], self.note(
                f"предпосылка: approve {task_id} с merge_after {dep} не "
                f"записал колонку:\n{out}"))
        b_element = self.element(chain[0])

        self.assert_refused(a, b_element, b_element,
                            re.compile(r"цикл", re.IGNORECASE))


class SpecGateWritesColumnTest(MergeAfterSpecGateSandbox):

    def test_ac5_prefixes_written_as_full_ids_in_spec_order(self):
        """Годный `merge_after` префиксами — approve проходит и пишет полные id в порядке SPEC.

        Сценарий: от одной до трёх живых зависимостей (`new`), в
        `merge_after` каждая — однозначным префиксом или полным id, порядок
        перемешан от зерна. После `approve` задача ушла со `spec_gate`,
        колонка `merge_after` — полные id ровно в порядке SPEC, колонка
        `zones` записана тем же approve.

        Ловит мутацию: в колонку пишется сырое значение SPEC (префиксы не
        разрешены) либо id сортируются — перечень колонки расходится с
        ожидаемым.
        """
        deps = [self.new_task() for _ in range(self.rng.randint(1, 3))]
        self.rng.shuffle(deps)
        value = ", ".join(self.element(d) for d in deps)

        out = self.approve_spec(self.TASK, value)

        context = self.note(f"merge_after: {value}\nвывод approve:\n{out}")
        row = self.row(self.TASK)
        self.assertNotEqual(row["state"], "spec_gate", context)
        self.assertEqual(ids_of(row["merge_after"]), deps, context)
        self.assertEqual(row["zones"], ZONES, context)

    def test_ac5_spec_without_field_leaves_column_empty(self):
        """SPEC без `merge_after` — колонка пуста, переход идёт как раньше.

        Сценарий: в БД есть другие задачи (от зерна — одна или две), SPEC
        задачи поля не несёт. `approve` уводит задачу со `spec_gate`,
        колонка `merge_after` пуста, `zones` записана.

        Ловит мутацию: отсутствие поля читается как ошибка проверки (approve
        отказывает) либо в колонку попадает мусор (например, строка
        «None»).
        """
        for _ in range(self.rng.randint(1, 2)):
            self.new_task()

        out = self.approve_spec(self.TASK, None)

        context = self.note(f"вывод approve:\n{out}")
        row = self.row(self.TASK)
        self.assertNotEqual(row["state"], "spec_gate", context)
        self.assertEqual(ids_of(row["merge_after"]), [], context)
        self.assertEqual(row["zones"], ZONES, context)


if __name__ == "__main__":
    unittest.main()
