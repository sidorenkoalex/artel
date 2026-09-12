"""Приёмочный тест AC-6 задачи 01M2B6K76EAFDF5X1B3Z9XK30Q.

Красен до реализации: подсказка `config.AUTO_STOP["acceptance"]` сегодня
не несёт отсылки к записи журнала «приёмка: что проверит approve» —
`assertIn` ниже падает на реальном (пока не переписанном) тексте
подсказки.
"""
import unittest

from orchestrator import config


class AutoStopHintReferencesLogEntryTest(unittest.TestCase):

    def test_ac6_acceptance_hint_points_to_the_entry_report_in_the_log(self):
        """Подсказка состояния `acceptance` в `config.AUTO_STOP` ссылается
        на запись «приёмка: что проверит approve» в `artel.py log {id}`
        (SPEC требование 3, AC-6) — Оператор читает готовый разбор в
        журнале вместо того, чтобы гонять устаревший протокол
        `docs/operator-gates.md` руками.

        Ловит мутацию: правка подсказки `acceptance` без добавления
        отсылки к записи журнала (например, только косметическая правка
        соседнего текста) — ни один из `assertIn` ниже не найдёт нужную
        подстроку.
        """
        reason, hint = config.AUTO_STOP["acceptance"]

        combined = reason + " " + hint
        self.assertIn("приёмка: что проверит approve", combined,
                     "подсказка обязана называть точное действие журнала")
        self.assertIn("artel.py log", combined,
                     "подсказка обязана называть команду, которой "
                     "Оператор увидит эту запись")


if __name__ == "__main__":
    unittest.main()
