"""Приёмочные тесты T074 — AC-8.

Источник — tasks/T074/SPEC.md, «Критерии приёмки».

AC-8. Lease задачи указывает на процесс другого host — прерывание не
выполняется: честный отказ с сообщением о том, что прерывание процессов
на другом host вне объёма.

Процесс, адресованный lease, — РЕАЛЬНЫЙ и живой (тот же
`spawn_sleep_process`, что и в остальных тестах T074): критерий про то,
что `pause --now` НЕ ТРОГАЕТ его именно из-за чужого host, не про то, что
адресуемый процесс сам по себе недоступен. Если бы прерывание всё-таки
случилось, тест поймал бы это по факту смерти процесса.

Красен до реализации: `orchestrator.pause` ещё не несёт
`cmd_pause_now` — `AttributeError` при вызове.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import InterruptSandbox, pause  # noqa: E402


class OtherHostRefusesInterruptTest(InterruptSandbox):

    def test_ac8_process_on_another_host_is_left_untouched(self):
        self.enter_in_dev()
        proc = self.spawn_sleep_process()
        self.install_lease(proc.pid, hostname="another-host.invalid")

        out = self.capture(pause.cmd_pause_now, self.TASK)

        self.assertIsNone(
            proc.poll(),
            "AC-8: процесс на чужом host не должен быть прерван")
        text = f"{out}\n{self.journal_text()}".lower()
        self.assertIn(
            "host", text,
            f"AC-8: отказ обязан честно называть причину — host вне "
            f"объёма; фактический вывод: {out!r}, журнал: "
            f"{self.journal_text()!r}")
        self.assertTrue(
            "вне объём" in text or "не вход" in text or "не поддерж" in text
            or "объём" in text,
            f"AC-8: отказ обязан явно называть прерывание на другом host "
            f"вне объёма задачи; фактический вывод: {out!r}, журнал: "
            f"{self.journal_text()!r}")


if __name__ == "__main__":
    unittest.main()
