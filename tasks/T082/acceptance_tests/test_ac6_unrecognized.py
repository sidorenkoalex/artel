"""Приёмочные тесты T082 — AC-6.

Источник — tasks/T082/SPEC.md, «Критерии приёмки».

AC-6. Попытка шага, текст которой не совпадает ни с одним списком
требований 1–2 и не содержит «API Error:», обрабатывается как обычный
провал — без изменения сегодняшнего поведения (та же пауза, тот же
потолок попыток).

Зелёный с рождения: критерий буквально требует ОТСУТСТВИЯ изменений
для нераспознанного текста — сегодняшнее поведение (`config.
RETRY_BACKOFF_SEC=5`, удвоение на попытку, эскалация по исчерпании
`AGENT_ATTEMPTS`) уже ему соответствует (`tests/test_agent_failure.py::
CmdRunFailureTest.test_backoff_pauses_grow_between_attempts`/
`test_escalates_after_retries_exhausted` проверяют то же самое как
регрессию для существующего кода). Этот файл — контрольный тест самого
T082: он обязан остаться зелёным И ПОСЛЕ реализации классификации,
поймав случайную порчу пути «нераспознанный текст», если реализация
классификатора случайно расширит один из списков требований 1–2/якорь
«API Error:» на этот текст.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import RunnerSandbox  # noqa: E402

from orchestrator import config  # noqa: E402


class UnrecognizedFailureUnchangedTest(RunnerSandbox):

    def test_ac6_unrecognized_text_keeps_second_scale_backoff_and_attempt_ceiling(self):
        out = self.run_agent(*[
            (1, ["упал: непонятная внутренняя ошибка агента\n"])
        ] * config.AGENT_ATTEMPTS)

        self.assertEqual(
            self.pauses,
            [config.RETRY_BACKOFF_SEC, config.RETRY_BACKOFF_SEC * 2],
            f"AC-6: нераспознанный текст обязан сохранить сегодняшний "
            f"секундный экспоненциальный бэкофф без изменений; вывод "
            f"run: {out!r}, паузы: {self.pauses}")
        self.assertEqual(
            self.popen.call_count, config.AGENT_ATTEMPTS,
            f"AC-6: потолок попыток для нераспознанного текста не "
            f"меняется; вывод run: {out!r}")
        self.assertEqual(
            self.task_row()["state"], "escalated",
            f"AC-6: исчерпание попыток нераспознанного провала всё ещё "
            f"эскалирует, как и сегодня; вывод run: {out!r}")


if __name__ == "__main__":
    unittest.main()
