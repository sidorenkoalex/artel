"""Юнит-тесты классификатора ошибок агента (SPEC T082, требования 1-2).

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

from orchestrator import config, failure_classification, providers  # noqa: E402


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


UNSUPPORTED_MODEL_OUTPUT = (
    "API Error: 400 {\"type\":\"error\",\"error\":{\"type\":"
    "\"invalid_request_error\",\"message\":\"This Claude Code version "
    "does not support this model; version 2.1.251 or newer is required\"}}\n")


class ModelUnsupportedClassTest(unittest.TestCase):
    """Класс «модель не поддерживается CLI» (SPEC 01M2XJKV84SQ9VEVR0VNVKDNGJ,
    требование 4, AC-9): собственный класс раньше якоря «API Error:»,
    вне связки транзиентных, с подписью для журнала."""

    def test_unsupported_model_text_is_its_own_class(self):
        """Ловит мутацию: сигнатура добавлена в список «системного
        кандидата» или проверяется ПОСЛЕ якоря «API Error:», который
        перехватывает её первым — детерминированный отказ снова лечится
        повторами с паузами."""
        failure_class = failure_classification.classify_attempt_failure(
            UNSUPPORTED_MODEL_OUTPUT)

        self.assertEqual(failure_class,
                         failure_classification.MODEL_UNSUPPORTED_CLASS)
        self.assertNotEqual(failure_class, "system_candidate")
        self.assertNotIn(failure_class,
                         failure_classification.TRANSIENT_SYSTEM_CLASSES)
        self.assertIn(failure_class, failure_classification.CLASS_LABELS)

    def test_signature_is_case_insensitive_like_the_others(self):
        """Ловит мутацию: сравнение идёт по исходному регистру, а не по
        `lowered`, как у остальных списков."""
        self.assertEqual(
            failure_classification.classify_attempt_failure(
                "DOES NOT SUPPORT THIS MODEL"),
            failure_classification.MODEL_UNSUPPORTED_CLASS)

    def test_the_general_api_error_anchor_still_works(self):
        """Ловит мутацию: новая проверка написана по подстроке «API Error»
        или «model» и забирает себе весь класс 1."""
        self.assertEqual(
            failure_classification.classify_attempt_failure(
                "API Error: 500 Internal Server Error"),
            "system_candidate")
        self.assertEqual(
            failure_classification.classify_attempt_failure(
                "API Error: 400 model name is invalid"),
            "system_candidate")

    def test_required_cli_version_is_parsed_from_the_attempt_text(self):
        """Ловит мутацию: требуемая версия не читается из текста попытки
        (`None` для текста инцидента) либо читается из любого числа вида
        X.Y.Z, не из фразы «version X or newer is required»."""
        self.assertEqual(
            failure_classification.required_cli_version(UNSUPPORTED_MODEL_OUTPUT),
            "2.1.251")
        self.assertIsNone(failure_classification.required_cli_version(
            "Claude Code 2.1.236 does not support this model"))


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


class ProviderSignaturesTest(unittest.TestCase):
    """Сигнатуры берутся у провайдера, набор классов остаётся общим
    (SPEC 01M31ZHSA6HMH40C2JTDPQJQNZ, требование 9).

    Планка задачи проверяет, что класс ТЕКСТА зависит от провайдера;
    здесь — два угла, которые она не называет: провайдер не вправе
    расширить набор классов, и порядок его таблицы решает исход."""

    class _Provider(providers.RoleExecutorProvider):
        """Провайдер с чужой таблицей сигнатур."""

        name = "stub-signatures"

        def __init__(self, table):
            self._table = table

        def failure_signatures(self):
            return self._table

    def classify(self, text: str, table) -> str | None:
        return failure_classification.classify_attempt_failure(
            text, self._Provider(table))

    def test_a_class_outside_the_common_set_is_not_returned(self):
        """Класс, которого нет в общем наборе, игнорируется — даже когда
        его сигнатура совпала.

        Ловит мутацию: класс провайдера возвращается как есть — дальше
        по течению `CLASS_LABELS[failure_class]` падает `KeyError` прямо
        в точке учёта провалившейся попытки, и шаг теряет и запись
        классификации, и алерт своего настоящего класса.
        """
        table = (providers.FailureSignature("своё-имя", ("отказ",)),
                 providers.FailureSignature("1a", ("отказ",)))

        self.assertEqual(self.classify("тут отказ", table), "1a")

    def test_the_first_matching_entry_of_the_table_wins(self):
        """Текст, подходящий двум записям таблицы, получает класс
        ПЕРВОЙ из них.

        Ловит мутацию: таблица обходится в произвольном порядке
        (например, через словарь, собранный по классам) — общий якорь
        CLI начинает перехватывать детерминированный отказ, и тот снова
        лечится тремя попытками с минутным бэкоффом.
        """
        table = (providers.FailureSignature(
                     failure_classification.MODEL_UNSUPPORTED_CLASS,
                     ("нет такой модели",)),
                 providers.FailureSignature("system_candidate", ("ошибка:",)))

        self.assertEqual(self.classify("ошибка: нет такой модели", table),
                         failure_classification.MODEL_UNSUPPORTED_CLASS)
        self.assertNotIn(failure_classification.MODEL_UNSUPPORTED_CLASS,
                         failure_classification.TRANSIENT_SYSTEM_CLASSES)


if __name__ == "__main__":
    unittest.main()
