"""Приёмочные тесты T070 — AC-3 (SPEC.md).

Красен до реализации: `orchestrator.pause` ещё не существует — см.
`_sandbox.py`.

Допущения интерфейса — см. `_sandbox.py`. Симуляция «паузы, поставленной
во время бегущего шага» — `spawn_agent`, чей вызов сам ставит пометку
паузы ДО того, как отдать управление обратно `runner._cmd_run` (тот же
момент, в который реальный Оператор набрал бы `pause` в другом
терминале, пока агент ещё работает): проверка паузы в `run` идёт ДО
`spawn_agent` (требование 2 SPEC — «перед стартом агентного шага»),
поэтому пометка, поставленная уже ПОСЛЕ этой проверки, не может отменить
уже стартовавший шаг — только помешать следующему.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import PauseSandbox, invoke, pause  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from orchestrator import auto  # noqa: E402


class Ac3PauseDuringRunningAutoStepTest(PauseSandbox):
    """AC-3: пауза, поставленная во время бегущего цикла `auto`, не
    прерывает уже стартовавший агентный шаг: он дорабатывает штатно, а
    следующий шаг цикла не начинается."""

    def test_ac3_started_step_finishes_and_next_step_does_not_start(self):
        self.set_state("in_dev")

        def set_pause_mid_step() -> None:
            invoke(lambda: pause.cmd_pause(self.TASK))

        out, popen = self.run_with_mid_step_side_effect(
            lambda: auto.cmd_auto(self.TASK, session_id="session-auto"),
            set_pause_mid_step)

        self.assertEqual(
            popen.call_count, 1,
            f"пауза во время первого шага не должна была ни оборвать его, "
            f"ни позволить начаться следующему — агент спавнился "
            f"{popen.call_count} раз(а). Вывод auto: {out!r}")
        journal = self.journal_tail_text(0)
        self.assertIn(
            "agent run finished", journal,
            f"уже стартовавший шаг обязан был доработать штатно (запись "
            f"«agent run finished» в журнале), а не оборваться: {journal!r}")


if __name__ == "__main__":
    import unittest
    unittest.main()
