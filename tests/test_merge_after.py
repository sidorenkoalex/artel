"""Юнит-тесты `orchestrator/merge_after.py` и его опор (SPEC
01M44EP0D47F498TEE08MNGBYT) — углы, не покрытые долгоживущими файлами
задачи `tests/test_01m44ep0d47f498tee08mngbyt_*.py`: форма id, узел
разрешения префикса, повтор после разрешения, пропавшая из БД
зависимость на гейте мержа, строка мандата «нет» вперемешку с id и
повтор строки, совпадающее значение PLAN, миграция колонки.
"""
import sqlite3
import unittest

from orchestrator import config, idgen, merge_after, schema, store
from orchestrator.advance_gates import mandate
from tests.sandbox import LightTransitionSandbox

MARKER = mandate.MERGE_AFTER_MANDATE_MARKER


class TaskIdFormTest(unittest.TestCase):

    def test_form_accepts_ids_prefixes_and_legacy_rejects_rest(self):
        """Полный id, его префикс и `Tnnn` — годная форма; строчные буквы,
        буквы вне алфавита ULID, пробел и id длиннее полного — нет.

        Ловит мутацию: проверка длины снята (строка длиннее 26 символов
        алфавита проходит) либо алфавит не сверяется (строчный id или `I`
        проходят).
        """
        full = idgen.new_task_id()
        for good in (full, full[:8], "T101"):
            self.assertTrue(idgen.is_task_id_form(good), good)
        for bad in ("", full.lower(), full + "0", "01MI", "foo bar"):
            self.assertFalse(idgen.is_task_id_form(bad), bad)


class MergeAfterDbSandbox(LightTransitionSandbox):

    def setUp(self):
        super().setUp()
        self.conn = store.db()

    def insert(self, state: str, task_id: str | None = None) -> str:
        task_id = task_id or idgen.new_task_id()
        store.insert_task(self.conn, task_id, f"Фикстура {task_id}", state,
                          f"task/{task_id.lower()}-x", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        return task_id

    def set_deps(self, task_id: str, deps: list[str]) -> None:
        store.update_task(self.conn, task_id,
                          merge_after=merge_after.column(deps))


class TaskIdMatchesTest(MergeAfterDbSandbox):

    def test_exact_match_wins_over_longer_ids_with_same_prefix(self):
        """Id, который сам является префиксом другого id, разрешается в себя.

        Ловит мутацию: точное совпадение не проверяется первым — `T1` при
        наличии `T10` объявляется неоднозначным.
        """
        self.insert("in_dev", "T1")
        self.insert("in_dev", "T10")

        self.assertEqual(store.task_id_matches(self.conn, "T1"), ["T1"])
        self.assertEqual(sorted(store.task_id_matches(self.conn, "T1")
                                + store.task_id_matches(self.conn, "T10")),
                         ["T1", "T10"])


class CheckTest(MergeAfterDbSandbox):

    def test_prefix_and_full_id_of_same_task_is_a_repeat(self):
        """Префикс и полный id одной задачи в одном значении — повтор после разрешения.

        Ловит мутацию: повтор сверяется только по буквальному тексту
        элемента — в колонку попала бы одна задача дважды.
        """
        dep = self.insert("in_dev")

        ids, reasons = merge_after.check(self.conn, self.TASK,
                                         [dep, dep[:-1]])

        self.assertEqual(ids, [])
        self.assertTrue([r for r in reasons if "повтор" in r], reasons)

    def test_done_dependency_is_valid(self):
        """Зависимость в `done` годна — её мерж уже состоялся.

        Ловит мутацию: проверка состояния отказывает любой завершённой
        задаче (`done` спутан с `killed`).
        """
        dep = self.insert("done")

        self.assertEqual(merge_after.check(self.conn, self.TASK, [dep]),
                         ([dep], []))


class MergeGateMissingDependencyTest(MergeAfterDbSandbox):

    def test_dependency_missing_from_db_refuses_with_answer_channel(self):
        """Зависимость, пропавшая из БД, — отказ с каналом снятия, не «повтори approve».

        Ловит мутацию: пропавшая зависимость обрабатывается как
        незавершённая — Оператору советуют повторять `approve`, которая не
        пройдёт никогда.
        """
        ghost = idgen.new_task_id()
        self.set_deps(self.TASK, [ghost])
        t = store.get_task(self.conn, self.TASK)

        out = self.capture(merge_after.merge_gate_refuses, self.conn,
                           self.TASK, t)

        self.assertIn(ghost, out)
        self.assertIn(merge_after.MISSING_STATE, out)
        self.assertIn("answer", out)
        self.assertIn(MARKER, out)


class MandateLineTest(MergeAfterDbSandbox):

    def test_none_word_mixed_with_ids_refused(self):
        """«нет» рядом с id в одной строке — отказ проверки строки мандата.

        Ловит мутацию: «нет» молча отбрасывается из перечня до проверки
        (строка читается как перечень одних id) — неоднозначная строка
        проходит.
        """
        dep = self.insert("in_dev")

        found = mandate.refusals(f"{MARKER} {dep}, нет\n", None,
                                 conn=self.conn, task_id=self.TASK)

        self.assertTrue(found)

    def test_two_mandate_lines_refused(self):
        """Две строки «Зависимости мержа:» в одном ответе — отказ.

        Ловит мутацию: берётся первая строка, вторая молча теряется —
        Оператор не узнаёт, какое из двух значений вступило в силу.
        """
        first, second = self.insert("in_dev"), self.insert("in_dev")

        found = mandate.refusals(f"{MARKER} {first}\n{MARKER} {second}\n",
                                 None, conn=self.conn, task_id=self.TASK)

        self.assertTrue([f for f in found if "повторена" in f], found)


class PlanChannelSameValueTest(MergeAfterDbSandbox):

    def test_plan_value_equal_to_db_after_resolution_is_silent(self):
        """PLAN со значением, совпадающим с БД после разрешения префиксов, журнал не трогает.

        Ловит мутацию: сравнение идёт по сырому тексту PLAN — префикс
        прежней зависимости без обоснования даёт запись «отклонён».
        """
        dep = self.insert("in_dev")
        self.set_deps(self.TASK, [dep])
        t = store.get_task(self.conn, self.TASK)
        before = len(store.task_steps(self.conn, self.TASK))

        merge_after.apply_plan(self.conn, self.TASK, t,
                               {"merge_after": dep[:-2]},
                               "## Влияние на систему\n\nНет.\n")

        self.assertEqual(len(store.task_steps(self.conn, self.TASK)), before)
        self.assertEqual(merge_after.stored(
            store.get_task(self.conn, self.TASK)["merge_after"]), [dep])


class MigrationTest(unittest.TestCase):

    def test_migrate_adds_merge_after_to_old_tasks_table(self):
        """`migrate` догоняет таблицу `tasks` прошлой версии колонкой `merge_after`.

        Ловит мутацию: колонка добавлена только в DDL — БД, созданная до
        задачи, остаётся без неё, и чтение `t["merge_after"]` падает.
        """
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE tasks (id TEXT PRIMARY KEY, title TEXT, "
                     "state TEXT, branch TEXT)")
        try:
            schema.migrate(conn)
        except sqlite3.Error:
            pass  # прочие шаги миграции пустой БД здесь не предмет
        self.assertIn("merge_after", schema.table_columns(conn, "tasks"))


if __name__ == "__main__":
    unittest.main()
