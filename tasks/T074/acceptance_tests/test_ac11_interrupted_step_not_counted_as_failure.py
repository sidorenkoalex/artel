"""Приёмочные тесты T074 — AC-11.

Источник — tasks/T074/SPEC.md, «Критерии приёмки».

AC-11. Шаг, прерванный `pause --now`, не считается провалом роли:
счётчики отказов/итераций роли не инкрементятся.

Кодовая база не несёт отдельной числовой колонки «счётчик отказов роли»
— единственное НАБЛЮДАЕМОЕ следствие исчерпания попыток агента сегодня
(`orchestrator/runner.py::cmd_run`, ретрай-цикл) — переход задачи в
`escalated` с `escalated_from`, записанным состоянием, и журнальной
записью «агент не отработал за N попытки». Критерий проверяется через
ОТСУТСТВИЕ этого следствия: после `pause --now` на бегущем шаге задача
обязана остаться в прежнем состоянии (не эскалирована как проваленная),
готовая к перезапуску по `resume` (требование 5, AC-12, AC-13) — если бы
прерывание засчиталось как провал роли, эскалация сработала бы уже
здесь, до всякого `resume`.

Красен до реализации: `orchestrator.pause` ещё не несёт
`cmd_pause_now` — `AttributeError` при вызове.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import InterruptSandbox, pause  # noqa: E402


class InterruptedStepNotCountedAsFailureTest(InterruptSandbox):

    def test_ac11_task_state_is_not_escalated_as_a_role_failure(self):
        self.enter_in_dev()
        proc = self.spawn_sleep_process()
        self.install_lease(proc.pid)

        self.capture(pause.cmd_pause_now, self.TASK)
        try:
            proc.wait(timeout=10)
        except Exception:
            pass

        row = self.task_row()
        self.assertEqual(
            row["state"], "in_dev",
            "AC-11: прерывание pause --now не должно эскалировать задачу "
            "как проваленный роли шаг — состояние обязано остаться "
            f"прежним, фактическое: {row['state']!r}")
        self.assertIsNone(
            row["escalated_from"],
            "AC-11: прерывание pause --now не должно помечать "
            "escalated_from — это след счётчика провалов роли")
        text = self.journal_text().lower()
        self.assertNotIn(
            "не отработал за", text,
            f"AC-11: журнал не должен нести формулировку исчерпания "
            f"попыток агента (та же, что при провале роли) — "
            f"фактический журнал:\n{self.journal_text()}")


if __name__ == "__main__":
    unittest.main()
