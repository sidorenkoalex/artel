"""Юнит-тесты `orchestrator.store.journal` (SPEC 01M1GCHKG8DDK4DCZWCE3DYKWC,
требования 1-2, AC-1/AC-2): identity сессии в каждой новой записи журнала.
"""
import os
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, store  # noqa: E402
from tests.sandbox import TaskSeededTmpRootTest  # noqa: E402

TASK = "T001"


class JournalSessionIdTest(TaskSeededTmpRootTest):

    def last_step(self):
        return store.task_steps(store.db(), TASK)[-1]

    def test_default_resolves_the_current_session_from_the_environment(self):
        with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": "sess-env"}):
            store.journal(store.db(), TASK, "operator", "тест")

        self.assertEqual(self.last_step()["session_id"], "sess-env")

    def test_explicit_session_id_wins_over_the_environment(self):
        with mock.patch.dict(os.environ, {"ARTEL_SESSION_ID": "sess-env"}):
            store.journal(store.db(), TASK, "operator", "тест",
                          session_id="sess-explicit")

        self.assertEqual(self.last_step()["session_id"], "sess-explicit")

    def test_falls_back_to_parent_pid_without_env_var(self):
        env = dict(os.environ)
        env.pop("ARTEL_SESSION_ID", None)
        with mock.patch.dict(os.environ, env, clear=True):
            store.journal(store.db(), TASK, "operator", "тест")

        self.assertEqual(self.last_step()["session_id"], f"ppid-{os.getppid()}")


class BulkJournalReadsTest(TaskSeededTmpRootTest):
    """`store.all_steps`/`store.task_steps_since` — выборки «много записей
    разом» (SPEC 01M3GKJFN90ATK2KECNDZXPPP6, требования 3-4): читатели
    отчёта и дозора перестали брать журнал выборкой на каждую задачу и
    полной историей на каждый опрос."""

    OTHER = "T002"

    def setUp(self):
        super().setUp()
        store.insert_task(store.db(), self.OTHER, "Вторая", "in_dev",
                         "task/t002", config.DEFAULT_TARGET, 25.0)
        conn = store.db()
        for actor, action in (("fsm", "state -> review"),
                             ("operator", "state -> merge_gate"),
                             ("developer", "agent run завершён")):
            store.journal(conn, TASK, actor, action, "деталь")
            store.journal(conn, self.OTHER, actor, action, "деталь")

    def steps_statements(self, call) -> list:
        """SQL к `steps`, фактически выполненный вызовом `call`, — тем же
        приёмом `set_trace_callback`, что счётчик запросов отчёта
        (`tests/test_report.py::_StepsQueries`)."""
        conn = store.db()
        statements: list = []
        conn.set_trace_callback(statements.append)
        try:
            call(conn)
        finally:
            conn.set_trace_callback(None)
        return [s for s in statements
                if re.search(r"\bfrom\s+steps\b", str(s), re.I)]

    def test_all_steps_returns_the_whole_journal_ordered_by_id(self):
        """Ловит мутацию: `ORDER BY id` заменён на `ORDER BY task_id` (или
        отбор сузился до одной задачи) — читатель отчёта получил бы журнал
        не в сквозной хронологии, а доли гейтов и журнал Оператора по дням
        стоят именно на ней.

        Утрату `ORDER BY` целиком этот тест поймать не может и не
        заявляет: `steps` — rowid-таблица, `id` — алиас rowid, и `SCAN`
        без сортировки даёт сегодня тот же порядок. Это свойство
        закреплено на самом выполненном SQL — тестом ниже."""
        rows = store.all_steps(store.db())

        ids = [r["id"] for r in rows]
        self.assertEqual(sorted(ids), ids)
        self.assertEqual({TASK, self.OTHER}, {r["task_id"] for r in rows})
        self.assertEqual(6, len(rows))

    def test_all_steps_asks_sql_itself_for_the_chronological_order(self):
        """Хронология журнала — обещание ЗАПРОСА, а не совпадение плана:
        порядок строк rowid-таблицы без `ORDER BY` SQLite вправе сменить
        (индекс, `UNION`, сужение колонок), и результат выборки такую
        утрату не показывает.

        Ловит мутацию: `ORDER BY id` убран из `store.all_steps` — тест
        выше и побайтное сравнение планки (AC-4) остаются зелёными, а
        доли гейтов, журнал Оператора по дням, ряд роста карты и метрика
        трения встают на порядок, который никем не обещан."""
        statements = self.steps_statements(store.all_steps)

        self.assertEqual(1, len(statements),
                         f"выборка не одна: {statements}")
        self.assertRegex(statements[0], r"(?i)order\s+by\s+id\b")

    def test_all_steps_carries_every_column_its_readers_read(self):
        """Ловит мутацию: из списка колонок выпала одна из нужных
        (`detail`/`ts`/`actor`) — читатели отчёта падали бы `IndexError`
        на обращении по имени колонки, а не тихо работали бы хуже."""
        row = store.all_steps(store.db())[0]

        for column in ("id", "task_id", "ts", "actor", "action", "detail"):
            self.assertIsNotNone(row[column], f"колонки {column} нет в выборке")

    def test_steps_of_action_takes_only_that_action_and_filters_in_sql(self):
        """Ловит мутацию: отбор по `action` считается в Python поверх
        полной выборки журнала — результат тот же, а прочитанный объём
        снова растёт со всем журналом пульта (это и был дефект R1-F2:
        ряд роста карты зовёт эту выборку трижды на каждый target)."""
        conn = store.db()

        rows = store.steps_of_action(conn, "state -> merge_gate")

        self.assertEqual(["state -> merge_gate"] * 2,
                         [r["action"] for r in rows])
        self.assertEqual([TASK, self.OTHER], [r["task_id"] for r in rows])
        self.assertEqual(sorted(r["id"] for r in rows),
                         [r["id"] for r in rows])
        self.assertEqual([], store.steps_of_action(conn, "такого нет"))

        statements = self.steps_statements(
            lambda c: store.steps_of_action(c, "state -> merge_gate"))
        self.assertEqual(1, len(statements), f"выборка не одна: {statements}")
        # Трасса `set_trace_callback` отдаёт SQL с уже подставленным
        # параметром, поэтому в тексте стоит само значение, не `?`.
        self.assertRegex(statements[0],
                         r"(?i)where\s+action='state -> merge_gate'")

    def test_task_steps_since_takes_only_rows_of_that_task_after_the_id(self):
        """Ловит мутацию: фильтр `task_id=?` потерян (осталось только `id >
        ?`) — дозор одной задачи печатал бы записи ЧУЖИХ задач; либо
        граница взята нестрого (`id >= ?`) — уже показанная запись
        печаталась бы второй раз."""
        conn = store.db()
        own = store.task_steps(conn, TASK)

        rows = store.task_steps_since(conn, TASK, own[0]["id"])

        self.assertEqual([r["id"] for r in own[1:]], [r["id"] for r in rows])
        self.assertEqual({TASK}, {r["task_id"] for r in rows})
        self.assertEqual([], store.task_steps_since(conn, TASK,
                                                    own[-1]["id"]))


if __name__ == "__main__":
    unittest.main()
