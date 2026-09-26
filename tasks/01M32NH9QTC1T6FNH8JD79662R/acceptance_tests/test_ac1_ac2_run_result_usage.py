"""AC-1, AC-2: итог запуска `turn.completed` — разбивка токенов по четырём
общим видам цены и отсутствие цены от CLI.

Красен до реализации: `CodexProvider.parse_output_line` ещё не реализован — базовый интерфейс поднимает `NotImplementedError` на первой же строке.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _stream import (TURN_COMPLETED_LIVE, TURN_COMPLETED_TZ,  # noqa: E402
                     provider)


class RunResultTest(unittest.TestCase):
    """Итог запуска: `turn.completed` -> `base.RunResult`."""

    def run_result(self, raw: str):
        event = provider().parse_output_line(raw)
        self.assertIsNotNone(event.run_result,
                             "строка turn.completed — итог запуска")
        self.assertIsNotNone(event.run_result.tokens_by_type,
                             "итог запуска несёт разбивку токенов")
        return event.run_result

    def test_ac1_turn_completed_carries_the_breakdown_and_no_price(self):
        """Итог запуска образца ТЗ родителя: `input` 4966 (кэшированный
        вход вычтен), `cache_read` 12416, `cache_write` 0, `output` 6,
        цены от CLI нет и это не ноль, признак ошибки снят.

        Ловит мутацию: `cached_input_tokens` не вычитается из
        `input_tokens` — `input` становится 17382, и шаг на codex
        тарифицируется как будто весь его вход новый, хотя две трети
        объёма пришли из кэша по цене в десять раз ниже. Числа при этом
        выглядят правдоподобно: сумма токенов даже больше настоящей.
        """
        result = self.run_result(TURN_COMPLETED_TZ)

        self.assertEqual(dict(result.tokens_by_type),
                         {"input": 4966, "cache_read": 12416,
                          "cache_write": 0, "output": 6})
        # `None`, а не 0.0: «CLI цены не сообщил» и «запуск был бесплатен»
        # ветвятся в учёте по-разному (`spend.charge_step`).
        self.assertIsNone(result.usd, "цены от CLI нет — и это не 0.0")
        self.assertFalse(result.is_error, "успешный итог — не ошибка")

    def test_ac2_reasoning_tokens_are_not_added_to_the_output(self):
        """Итог живого запуска 0.155.1: `output` 8513 при
        `reasoning_output_tokens` 997, `input` 238229, `cache_read`
        1072000.

        Ловит мутацию: `reasoning_output_tokens` приплюсованы к
        `output_tokens` (буквальное чтение ТЗ родителя «токены
        рассуждений идут в output») — выход шага завышается на величину
        рассуждений по САМОЙ дорогой цене тарифа, и расхождение расчёта
        со счётом вендора никем не замечается: разбивка внутренне
        непротиворечива.
        """
        result = self.run_result(TURN_COMPLETED_LIVE)
        by_kind = dict(result.tokens_by_type)

        self.assertEqual(by_kind["output"], 8513)
        self.assertEqual(by_kind["input"], 238229)
        self.assertEqual(by_kind["cache_read"], 1072000)


if __name__ == "__main__":
    unittest.main()
