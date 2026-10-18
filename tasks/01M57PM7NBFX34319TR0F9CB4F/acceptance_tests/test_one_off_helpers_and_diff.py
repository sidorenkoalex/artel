"""Разовые факты задачи: закрытые помощники очереди мержа при одном
проекте отвечают как до правки (вызов с одним `conn`), и дифф ветки не
трогает прежние тесты мьютекса, очереди, окна тишины и doctor.

Группа: разовый
Зелёный с рождения: до правки помощники `_head_task_id`/`_current_holder_id`/`_current_holder_label` принимают ровно `conn` и дают эти значения, а дифф ветки ещё пуст — планка держит их совместимость и неизменность названных файлов (AC-12, AC-15), краснеет правка, которая их нарушит.

AC-12 вынесен сюда, а не в долгоживущий файл `tests/`: критерий называет
закрытые имена `merge_queue._head_task_id`, `_current_holder_id`,
`_current_holder_label`, а долгоживущая группа допускает только
публичный интерфейс. Дифф ветки (AC-15) — помощник пульта
`_pult.changed_paths()` (база — точка расхождения с `origin`).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _pult import CODE_ROOT, changed_paths  # noqa: E402

sys.path.insert(0, str(CODE_ROOT))

from orchestrator import catalog, config, merge_queue, store  # noqa: E402
from tests.sandbox import TmpRootTest, _ts_ago, capture  # noqa: E402

UNCHANGED_TESTS = (
    "tests/test_merge_lock.py",
    "tests/test_notes.py",
    "tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py",
    "tests/test_merge_queue.py",
    "tests/test_doctor.py",
    "tests/test_merge_gate_ci_wait.py",
    "tests/test_main_ci_line.py",
)


class SingleProjectHelpersTest(TmpRootTest):
    """Один проект — артель: три задачи в `merge_gate`."""

    TASK_A, TASK_B, TASK_C = "T001", "T002", "T003"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        for tid in (self.TASK_A, self.TASK_B, self.TASK_C):
            store.insert_task(store.db(), tid, tid, "merge_gate",
                              f"task/{tid.lower()}", config.DEFAULT_TARGET,
                              25.0)

    def test_ac12_private_queue_helpers_with_single_conn_keep_old_results(self):
        """Вызов помощников с одним `conn` при одном проекте.

        Пустая очередь — голова `None`; записи B (5 мин назад) и A (10 мин
        назад) — голова A (FIFO). Без держателя `_current_holder_id` и
        `_current_holder_label` дают `"?"`; держатель A с pid 4242 — `"T001"`
        и `"T001 (pid 4242)"`.

        Ловит мутацию: проект стал обязательным аргументом помощника —
        вызов с одним `conn` падает `TypeError`; либо без проекта помощник
        фильтрует по `None` и отдаёт пустую голову/`"?"` при держателе."""
        conn = store.db()
        self.assertIsNone(merge_queue._head_task_id(conn))
        self.assertEqual(merge_queue._current_holder_id(conn), "?")
        self.assertEqual(merge_queue._current_holder_label(conn), "?")

        store.enqueue_merge_wait(conn, self.TASK_B, "sess-b", 999,
                                 "other-host", _ts_ago(300))
        store.enqueue_merge_wait(conn, self.TASK_C, "sess-c", 998,
                                 "other-host", _ts_ago(60))
        store.enqueue_merge_wait(conn, self.TASK_A, "sess-a", 997,
                                 "other-host", _ts_ago(600))
        store.set_merge_lock(conn, self.TASK_A, "sess-holder", 4242,
                             "holder-host", store.now())

        self.assertEqual(merge_queue._head_task_id(conn), self.TASK_A)
        self.assertEqual(merge_queue._current_holder_id(conn), self.TASK_A)
        self.assertEqual(merge_queue._current_holder_label(conn),
                         f"{self.TASK_A} (pid 4242)")


class BranchDiffTest(unittest.TestCase):

    def test_ac15_branch_diff_leaves_old_tests_untouched(self):
        """Пути задачи по правилу гейта зон не содержат ни одного из семи
        прежних файлов тестов мьютекса, очереди, окна тишины и doctor.

        Ловит мутацию: разработчик подогнал прежний тест под новое
        поведение (правка `tests/test_merge_lock.py` и т.п.) — путь
        появится в `changed_paths()`, пересечение станет непустым."""
        touched = sorted(set(changed_paths()) & set(UNCHANGED_TESTS))

        self.assertEqual(touched, [])


if __name__ == "__main__":
    unittest.main()
