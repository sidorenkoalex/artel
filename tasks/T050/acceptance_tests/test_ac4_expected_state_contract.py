"""AC-4 (tasks/T050/SPEC.md): `set_state` требует обязательный параметр
`expected_state` и выполняет атомарный
`UPDATE tasks SET state=?, updated_at=? WHERE id=? AND state=?`.

Все вызовы `store.set_state` ниже передают `task_id`/`state`/`actor`/
`expected_state` по имени, не по позиции: SPEC не фиксирует, куда именно
`expected_state` встанет в сигнатуре (только то, что параметр обязателен
и назван так), поэтому тест не имеет права зависеть от порядка
позиционных аргументов сверх уже существующего `conn` первым.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config, store  # noqa: E402
from tests.sandbox import TmpRootTest  # noqa: E402

TASK = "T001"


class SetStateRequiresExpectedStateTest(TmpRootTest):

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        store.insert_task(store.db(), TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)

    def test_ac4_expected_state_is_a_mandatory_parameter(self):
        conn = store.db()

        with self.assertRaises(TypeError):
            store.set_state(conn, task_id=TASK, state="review", actor="test")

    def test_ac4_matching_expected_state_updates_state_and_updated_at(self):
        conn = store.db()
        before = dict(store.get_task(conn, TASK))

        store.set_state(conn, task_id=TASK, state="review", actor="test",
                        expected_state="in_dev")

        after = dict(store.get_task(store.db(), TASK))
        self.assertEqual(after["state"], "review")
        self.assertNotEqual(after["updated_at"], before["updated_at"],
                            "атомарный UPDATE обязан сдвигать updated_at "
                            "вместе со state")

    def test_ac4_mismatched_expected_state_changes_nothing(self):
        conn = store.db()
        before = dict(store.get_task(conn, TASK))  # реально state=in_dev

        try:
            store.set_state(conn, task_id=TASK, state="review", actor="test",
                            expected_state="acceptance")  # заведомо неверно
        except BaseException:
            pass

        after = dict(store.get_task(store.db(), TASK))
        self.assertEqual(after["state"], before["state"])
        self.assertEqual(after["updated_at"], before["updated_at"],
                         "несовпавший CAS не имеет права трогать строку, "
                         "даже updated_at")


if __name__ == "__main__":
    unittest.main()
