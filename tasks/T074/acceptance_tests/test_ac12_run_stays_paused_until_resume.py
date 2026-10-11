"""Приёмочные тесты T074 — AC-12.

Источник — tasks/T074/SPEC.md, «Критерии приёмки».

AC-12. После `pause --now` бегущего шага последующий `auto`/`run`
честно стоит на паузе (не начинает следующий агентный шаг) — по той же
механике, что и обычная пауза (T070), — пока не выполнен `resume`.

Требование 1 называет эту пометку «обычной пометкой паузы (как pause,
T070)» — сама механика отказа `run`/`auto` уже проверена приёмочными
тестами T070 (`tasks/T070/acceptance_tests/test_ac1_ac2_pause_blocks_run.py`);
здесь проверяется КОНКРЕТНО путь ПОСЛЕ `pause --now` на РЕАЛЬНО бегущем
шаге — что она действительно ставит ту же самую пометку (`pause.
is_paused`), которую читает `runner._cmd_run`, а не какую-то отдельную,
которую `run`/`auto` не видят.

Красен до реализации: `orchestrator.pause` ещё не несёт
`cmd_pause_now` — `AttributeError` при вызове.
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import InterruptSandbox, invoke, pause, runner  # noqa: E402

from tests.sandbox import FakeProc  # noqa: E402


class RunStaysPausedUntilResumeTest(InterruptSandbox):

    def test_ac12_run_refuses_to_start_next_step_after_pause_now(self):
        self.enter_in_dev()
        proc = self.spawn_sleep_process()
        self.install_lease(proc.pid)
        self.capture(pause.cmd_pause_now, self.TASK)
        try:
            proc.wait(timeout=10)
        except Exception:
            pass

        with mock.patch.object(runner, "spawn_agent") as popen:
            popen.return_value = FakeProc(["готово\n"])
            out, _ = invoke(lambda: runner.cmd_run(self.TASK))

        popen.assert_not_called()
        self.assertEqual(
            self.task_row()["state"], "in_dev",
            f"AC-12: run после pause --now не должен был сдвинуть "
            f"состояние или начать шаг — вывод: {out!r}")
        self.assertIn(
            pause.REFUSAL_ACTION,
            [r["action"] for r in self.journal()],
            f"AC-12: отказ обязан идти тем же механизмом, что и у "
            f"обычной pause (T070) — вывод: {out!r}")

    def test_ac12_resume_lets_run_start_the_step_again(self):
        self.enter_in_dev()
        proc = self.spawn_sleep_process()
        self.install_lease(proc.pid)
        self.capture(pause.cmd_pause_now, self.TASK)
        try:
            proc.wait(timeout=10)
        except Exception:
            pass

        self.capture(pause.cmd_resume, self.TASK)

        with mock.patch.object(runner, "spawn_agent") as popen:
            popen.return_value = FakeProc(["готово\n"])
            self.capture(runner.cmd_run, self.TASK)

        popen.assert_called_once()


if __name__ == "__main__":
    unittest.main()
