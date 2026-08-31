"""Приёмочные тесты T074 — AC-10.

Источник — tasks/T074/SPEC.md, «Критерии приёмки».

AC-10. Стоимость шага, прерванного `pause --now`, учитывается по
механике T040 (частичные суммы промежуточных usage-событий из stream-
json лога шага); при отсутствии данных открывается алерт
`spend.unknown_cost`.

Требование 1 явно называет источник данных — «из stream-json лога
шага»: `pause --now` живёт в ДРУГОМ процессе, чем прерванный шаг (тот же
процесс уже мёртв к моменту, когда команда продолжает свою
последовательность — см. `_sandbox.py`, «Допущения интерфейса»), поэтому
частичная стоимость не может браться из памяти прерванного процесса —
только из уже записанных на диск строк лога (`agent_log.new_agent_log`
называет путь, `spend.stream_usage_tokens` уже умеет разбирать usage из
любой строки потока, не только из финального события — механика T040).
Тест кладёт такой лог НАПРЯМУЮ (`InterruptSandbox.write_step_log`), не
прогоняя настоящий процесс: критерий про то, что ЛОГ читается и его
usage-события учитываются, а не про то, как лог туда попал.

Красен до реализации: `orchestrator.pause` ещё не несёт
`cmd_pause_now` — `AttributeError` при вызове.
"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import InterruptSandbox, pause  # noqa: E402


def usage_event(input_tokens=10, output_tokens=5) -> str:
    """Строка потока с usage — не финальное событие `result` (T040:
    `stream_usage_tokens` разбирает usage и из `type: assistant`)."""
    return json.dumps({
        "type": "assistant",
        "message": {"usage": {"input_tokens": input_tokens,
                              "output_tokens": output_tokens}},
    }, ensure_ascii=False) + "\n"


class PartialCostOfInterruptedStepTest(InterruptSandbox):

    def test_ac10_partial_usage_events_are_summed_without_alert(self):
        self.enter_in_dev()
        proc = self.spawn_sleep_process()
        self.install_lease(proc.pid)
        self.write_step_log("developer", [
            "агент работает\n",
            usage_event(10, 5),
            usage_event(20, 8),
        ])

        self.capture(pause.cmd_pause_now, self.TASK)
        try:
            proc.wait(timeout=10)
        except Exception:
            pass

        self.assertEqual(
            self.unknown_cost_alerts(), [],
            "AC-10: в потоке лога были usage-события — восстановить есть "
            "что, алерт spend.unknown_cost заводиться не должен")
        text = self.journal_text().lower()
        self.assertIn(
            "частичн", text,
            f"AC-10: журнал обязан нести частичную сумму токенов из "
            f"промежуточных usage-событий лога — фактический журнал:\n"
            f"{self.journal_text()}")

    def test_ac10_no_recoverable_data_raises_unknown_cost_alert(self):
        self.enter_in_dev()
        proc = self.spawn_sleep_process()
        self.install_lease(proc.pid)
        self.write_step_log("developer", ["агент работает, без usage\n"])

        self.capture(pause.cmd_pause_now, self.TASK)
        try:
            proc.wait(timeout=10)
        except Exception:
            pass

        found = self.unknown_cost_alerts()
        self.assertEqual(
            len(found), 1,
            f"AC-10: в потоке лога нет ни одного usage-события — "
            f"восстановить нечего, обязан открыться ровно один алерт "
            f"spend.unknown_cost — найдено {len(found)}")
        self.assertEqual(found[0]["kind"], "incident")
        self.assertTrue(found[0]["source"].startswith("spend.unknown_cost"))
        text = self.journal_text().lower()
        self.assertIn(
            "неизвестна", text,
            f"AC-10: журнал обязан честно назвать стоимость шага "
            f"неизвестной — фактический журнал:\n{self.journal_text()}")


if __name__ == "__main__":
    unittest.main()
