"""Юнит-тесты orchestrator/pause.py (SPEC T070).

Приёмочные тесты (tasks/T070/acceptance_tests) кроют AC-1..AC-13 сквозным
путём через `run`/`auto`/`kill`/`approve`/`reject`/`advance`; здесь — сам
модуль в изоляции: точная форма журнальной записи, идемпотентность
повторного `pause`/`resume` и то, что пометка не задевает соседние
задачи, тем же приёмом, что `tests/test_release.py` уже применил к
своему модулю.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import catalog, config, pause, store  # noqa: E402
from tests.sandbox import TmpRootTest, capture  # noqa: E402


class PauseTest(TmpRootTest):
    TASK = "T001"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

    def row(self, task_id: str = None):
        return store.get_task(store.db(), task_id or self.TASK)

    def journal(self, task_id: str = None):
        return store.task_steps(store.db(), task_id or self.TASK)

    # ------------------------------------------------------------ is_paused

    def test_is_paused_false_by_default(self):
        self.assertFalse(pause.is_paused(self.row()))

    def test_is_paused_true_after_pause(self):
        pause.cmd_pause(self.TASK)

        self.assertTrue(pause.is_paused(self.row()))

    # ------------------------------------------------------------ cmd_pause

    def test_pause_sets_the_mark(self):
        capture(pause.cmd_pause, self.TASK)

        self.assertTrue(pause.is_paused(self.row()))

    def test_pause_does_not_change_state(self):
        capture(pause.cmd_pause, self.TASK)

        self.assertEqual(self.row()["state"], "in_dev")

    def test_pause_journals_actor_operator(self):
        capture(pause.cmd_pause, self.TASK)

        steps = self.journal()
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0]["actor"], "operator")
        self.assertEqual(steps[0]["action"], "pause")

    def test_pause_does_not_raise_or_exit(self):
        result = pause.cmd_pause(self.TASK)

        self.assertIsNone(result)

    def test_repeated_pause_prints_friendly_message_and_does_not_rejournal(self):
        capture(pause.cmd_pause, self.TASK)

        output = capture(pause.cmd_pause, self.TASK)

        self.assertTrue(output.strip())
        self.assertEqual(len(self.journal()), 1,
                         "повторный pause не должен добавлять вторую "
                         "запись журнала об уже случившемся факте")
        self.assertTrue(pause.is_paused(self.row()))

    def test_pause_does_not_touch_another_task(self):
        store.insert_task(store.db(), "T002", "Другая задача", "in_dev",
                          "task/t002-drugaya", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

        capture(pause.cmd_pause, self.TASK)

        self.assertFalse(pause.is_paused(self.row("T002")),
                         "pause одной задачи выставил пометку другой")

    # ----------------------------------------------------------- cmd_resume

    def test_resume_clears_the_mark(self):
        capture(pause.cmd_pause, self.TASK)

        capture(pause.cmd_resume, self.TASK)

        self.assertFalse(pause.is_paused(self.row()))

    def test_resume_does_not_change_state(self):
        capture(pause.cmd_pause, self.TASK)

        capture(pause.cmd_resume, self.TASK)

        self.assertEqual(self.row()["state"], "in_dev")

    def test_resume_journals_actor_operator(self):
        capture(pause.cmd_pause, self.TASK)
        journalled_before = len(self.journal())

        capture(pause.cmd_resume, self.TASK)

        steps = self.journal()[journalled_before:]
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0]["actor"], "operator")
        self.assertEqual(steps[0]["action"], "resume")

    def test_resume_does_not_raise_or_exit(self):
        result = pause.cmd_resume(self.TASK)

        self.assertIsNone(result)

    def test_resume_of_not_paused_task_prints_friendly_message_and_does_not_journal(self):
        output = capture(pause.cmd_resume, self.TASK)

        self.assertTrue(output.strip())
        self.assertEqual(self.journal(), [],
                         "resume неприостановленной задачи не должен "
                         "писать журнал — нечего снимать")

    def test_resume_does_not_touch_another_task(self):
        store.insert_task(store.db(), "T002", "Другая задача", "in_dev",
                          "task/t002-drugaya", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        capture(pause.cmd_pause, self.TASK)
        capture(pause.cmd_pause, "T002")

        capture(pause.cmd_resume, self.TASK)

        self.assertTrue(pause.is_paused(self.row("T002")),
                         "resume одной задачи снял пометку другой")


if __name__ == "__main__":
    unittest.main()
