"""Приёмочные тесты AC-9 (tasks/01M2XJKV84SQ9VEVR0VNVKDNGJ/SPEC.md):
вывод попытки с текстом «does not support this model» — отдельный класс
провала, проверяемый раньше общего якоря «API Error:»; такая попытка не
повторяется, паузы нет, исход шага — тот же именованный отказ, без
эскалации.

Красен до реализации: `failure_classification.classify_attempt_failure`
доводит этот текст до общего якоря «API Error:» и возвращает
`system_candidate` — обе проверки падают на этом, а шаг крутит все
`config.AGENT_ATTEMPTS` попыток и уходит в `escalated`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _sandbox import (INCIDENT_MODEL, REFUSAL_PREFIX,  # noqa: E402
                      StepRunSandbox, UNSUPPORTED_MODEL_OUTPUT)
from orchestrator import config, failure_classification  # noqa: E402


class ClassificationTest(unittest.TestCase):
    """Чистая функция классификации: текст попытки -> класс."""

    def test_ac9_unsupported_model_text_is_its_own_class_before_the_api_anchor(self):
        """Текст инцидента 19.09 получает собственный класс, не
        «системного кандидата», и не попадает в связку транзиентных
        (у которой минутный бэкофф между попытками).

        Ловит мутацию: новая сигнатура добавлена в список класса
        «системный кандидат» (или проверяется ПОСЛЕ якоря «API Error:»,
        который перехватывает её первым) — детерминированный отказ снова
        лечится повторами с паузами.
        """
        failure_class = failure_classification.classify_attempt_failure(
            UNSUPPORTED_MODEL_OUTPUT)

        self.assertIsNotNone(failure_class,
                             "текст обязан распознаваться как класс провала")
        self.assertNotEqual(failure_class, "system_candidate")
        self.assertNotIn(failure_class,
                         failure_classification.TRANSIENT_SYSTEM_CLASSES)
        self.assertIn(failure_class, failure_classification.CLASS_LABELS,
                      "у класса обязана быть подпись для журнала")

    def test_ac9_the_general_api_error_anchor_still_works(self):
        """Прочие «API Error:» остаются «системным кандидатом» — новый
        класс сужен до своей сигнатуры.

        Ловит мутацию: новая проверка написана по подстроке «API Error»
        (или «model») и забирает себе весь класс 1 — транзиентные сетевые
        отказы перестают ретраиться.
        """
        self.assertEqual(
            failure_classification.classify_attempt_failure(
                "API Error: 500 Internal Server Error"),
            "system_candidate")


class StepRefusesWithoutRetriesTest(StepRunSandbox):
    """Полный шаг: агент упал с этим текстом на первой попытке. Модель
    роли — из таблицы, версия CLI заведомо свежая: предполётная проверка
    пропускает шаг, и предмет теста — именно разбор вывода попытки."""

    def setUp(self):
        super().setUp()
        self.set_model(INCIDENT_MODEL)
        self.set_cli_version("9.9.9")

    def test_ac9_attempt_is_not_repeated_and_the_step_refuses_by_name(self):
        """Следующая попытка не запускается, паузы нет, задача остаётся
        где стояла, а отказ назван тем же именем, что и предполётный.

        Ловит мутацию: класс заведён, но `_run_attempts` о нём не знает —
        шаг доигрывает `config.AGENT_ATTEMPTS` попыток и уводит задачу в
        `escalated` (либо отказ оформлен безымянной эскалацией, и
        Оператор снова разбирает лог руками).
        """
        attempts = ((1, [UNSUPPORTED_MODEL_OUTPUT]),) * config.AGENT_ATTEMPTS

        self.run_step(*attempts)

        self.assertEqual(self.spawn.call_count, 1,
                         "детерминированный отказ не повторяется")
        self.assertEqual(self.pauses, [])
        self.assertEqual(self.journal_details("agent run retry"), [])
        self.assertNotEqual(self.state(), "escalated")
        self.assertTrue(self.entries_containing(REFUSAL_PREFIX),
                        self.journal_rows())


if __name__ == "__main__":
    unittest.main()
