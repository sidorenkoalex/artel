"""Приёмочные тесты T070 — AC-6, AC-7 (SPEC.md).

Красен до реализации: `orchestrator.pause` ещё не существует — см.
`_sandbox.py`.

Допущения интерфейса — см. `_sandbox.py`. AC-7 не фиксирует имя колонки
БД под пометку паузы (SPEC, требование 4 — «записью в БД задачи», без
схемы) — тест сверяет факт изменения строки `tasks` целиком, не
конкретное поле.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import PauseSandbox, invoke, pause  # noqa: E402


class Ac6StateUnchangedByPauseAndResumeTest(PauseSandbox):
    """AC-6: состояние задачи (`state`) не меняется ни командой `pause`,
    ни командой `resume` — FSM не получает нового состояния и не проходит
    переход."""

    def test_ac6_pause_and_resume_do_not_change_task_state(self):
        for state in ("in_dev", "review", "escalated"):
            with self.subTest(состояние=state):
                self.set_state(state)

                invoke(lambda: pause.cmd_pause(self.TASK))
                self.assertEqual(self.state(), state,
                                 f"pause сменил state из {state}")

                invoke(lambda: pause.cmd_resume(self.TASK))
                self.assertEqual(self.state(), state,
                                 f"resume сменил state из {state}")


class Ac7PauseMarkIsDbBackedNotFileBackedTest(PauseSandbox):
    """AC-7: пометка паузы читается из БД задачи; новый файл под пометку
    в рабочем каталоге/на диске задачи не заводится."""

    def _task_dir_snapshot(self) -> set:
        if not self.tdir.exists():
            return set()
        return {p.relative_to(self.tdir) for p in self.tdir.rglob("*")}

    def test_ac7_pause_does_not_create_any_file_in_the_task_dir(self):
        self.set_state("in_dev")
        before = self._task_dir_snapshot()

        invoke(lambda: pause.cmd_pause(self.TASK))

        after = self._task_dir_snapshot()
        self.assertEqual(
            after, before,
            f"pause завёл файл(ы) в рабочем каталоге задачи: "
            f"{after - before}")

    def test_ac7_resume_does_not_create_any_file_in_the_task_dir(self):
        self.set_state("in_dev")
        invoke(lambda: pause.cmd_pause(self.TASK))
        before = self._task_dir_snapshot()

        invoke(lambda: pause.cmd_resume(self.TASK))

        after = self._task_dir_snapshot()
        self.assertEqual(
            after, before,
            f"resume завёл файл(ы) в рабочем каталоге задачи: "
            f"{after - before}")

    def test_ac7_pause_mark_is_persisted_in_the_tasks_db_row(self):
        self.set_state("in_dev")
        before = self.task_dict()

        invoke(lambda: pause.cmd_pause(self.TASK))

        after = self.task_dict()
        self.assertNotEqual(
            before, after,
            "pause не изменил строку tasks в БД — пометке негде храниться")


if __name__ == "__main__":
    import unittest
    unittest.main()
