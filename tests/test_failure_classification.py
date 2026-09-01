"""Юнит-тесты классификатора ошибок агента (SPEC T082, требования 1-2;
перенесено из runner.py в orchestrator/failure_classification.py в T091
— декомпозиция диспетчеров fsm/runner).

Приёмочные тесты (`tasks/T082/acceptance_tests/`) проверяют классификацию
только через наблюдаемый эффект `runner.cmd_run` (прямой вызов был бы
фантазией об интерфейсе — на момент их написания функции не было).
Здесь, наоборот, — прямые тесты самой чистой функции: границы списков,
приоритет специфичных сигнатур над общим якорем «API Error:»,
регистронезависимость, и то, что классификатор читает ПОЛНЫЙ текст
попытки, а не усечённый `agent_log.log_tail`.
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config, failure_classification  # noqa: E402


class ClassifyAttemptFailureTest(unittest.TestCase):

    def test_403_substring_is_class_1a(self):
        self.assertEqual(
            failure_classification.classify_attempt_failure("Failed: API Error: 403 Request "
                                            "not allowed"), "1a")

    def test_failed_to_authenticate_case_insensitive(self):
        self.assertEqual(
            failure_classification.classify_attempt_failure("FAILED TO AUTHENTICATE — "
                                            "токен просрочен"), "1a")

    def test_connection_refused_is_class_1b(self):
        self.assertEqual(
            failure_classification.classify_attempt_failure("сеть: Connection refused, "
                                            "повтор позже"), "1b")

    def test_connectionrefused_camelcase_is_class_1b(self):
        self.assertEqual(
            failure_classification.classify_attempt_failure("connectionrefused"), "1b")

    def test_stream_broken_signature(self):
        self.assertEqual(
            failure_classification.classify_attempt_failure(
                "API Error: Connection lost mid-response. The response "
                "above may be incomplete."), "stream_broken")

    def test_session_limit_signatures(self):
        for phrase in ("session limit", "usage limit", "5-hour limit",
                      "resets at"):
            with self.subTest(phrase=phrase):
                self.assertEqual(
                    failure_classification.classify_attempt_failure(f"чтo-то {phrase} "
                                                    f"чтo-то"),
                    "session_limit")

    def test_bare_api_error_prefix_is_system_candidate(self):
        self.assertEqual(
            failure_classification.classify_attempt_failure(
                "API Error: 529 Overloaded, please retry later"),
            "system_candidate")

    def test_unrelated_text_is_unrecognized(self):
        self.assertIsNone(failure_classification.classify_attempt_failure(
            "упал: непонятная внутренняя ошибка агента"))

    def test_1a_takes_priority_over_the_generic_api_error_anchor(self):
        # Требование 1: специфичные списки (1а/1б/обрыв потока/класс 2)
        # обязаны перехватывать текст РАНЬШЕ общего якоря «API Error:» —
        # иначе 403 терялся бы в «системном кандидате».
        self.assertEqual(
            failure_classification.classify_attempt_failure(
                "API Error: 403 Request not allowed"), "1a")

    def test_session_limit_takes_priority_over_the_generic_api_error_anchor(self):
        self.assertEqual(
            failure_classification.classify_attempt_failure(
                "API Error: usage limit reached, try later"),
            "session_limit")

    def test_empty_text_is_unrecognized(self):
        self.assertIsNone(failure_classification.classify_attempt_failure(""))


class AttemptOutputTextTest(unittest.TestCase):
    """Классификатор смотрит на ПОЛНЫЙ текст попытки, не на усечённый
    `agent_log.log_tail` (LOG_TAIL_LINES/LOG_TAIL_CHARS): сигнатура класса
    за пределами хвоста лога всё равно обязана классифицироваться."""

    def test_reads_the_whole_file_not_just_the_tail(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "attempt.log"
            lines = ["API Error: 403 Request not allowed\n"]
            lines += [f"строка {i}\n" for i in range(1, 100)]
            path.write_text("".join(lines), encoding="utf-8")

            text = failure_classification._attempt_output_text(path)

            self.assertGreater(len(text.splitlines()), config.LOG_TAIL_LINES)
            self.assertEqual(failure_classification.classify_attempt_failure(text), "1a")

    def test_missing_file_is_empty_text(self):
        self.assertEqual(
            failure_classification._attempt_output_text(Path("/nonexistent/path.log")), "")


if __name__ == "__main__":
    unittest.main()
