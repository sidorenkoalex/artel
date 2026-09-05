"""AC-5 (SPEC: «Частичная стоимость шага по видам токенов, калибровка
курса») — «Курс роли без одной из четырёх цен требования 1 —
именованный отказ (явно определённая ошибка/маркер), а не тихий ноль
или пропуск этого вида токена при расчёте.»

Сценарий — роль ЕСТЬ в `config.TOKEN_RATES` (не путать с ролью,
отсутствующей в таблице целиком — это уже существующий, отдельный
случай: `partial_cost_usd` возвращает `None`, см.
`tests/test_step_cost.py::PartialCostUsdTest.
test_unknown_role_returns_none_and_stays_silent`, эта задача его не
трогает), но у её записи не хватает ОДНОГО из четырёх ценовых полей
AC-1 — например, `cache_read_usd_per_token` пропущен.

«Именованный отказ» тест проверяет минимально буквально: расчёт
ОБЯЗАН явно упасть (любое исключение) — не вернуть число молча. Тихий
ноль или тихий пропуск вида токена сам по себе НЕ бросает исключение и
возвращает валидное число — это ровно то, что запрещено требованием, и
ровно то, что ловит `assertRaises` ниже.

Красен до реализации: `spend.partial_cost_usd` сегодня принимает
`partial_tokens: int` и делает `partial_tokens * effective` — вызов с
`TOKENS_BY_TYPE` (словарь) на месте `int` падает `TypeError` в обоих
тестах ниже (`assertRaises` в первом тесте пока «проходит» по этой
чужой причине, не по неполноте курса — контрольный второй тест сегодня
красен именно из-за той же `TypeError`, что и обнажает подмену:
`assertIsInstance(result, float)` не доходит до сравнения типа,
исключение прерывает тело теста раньше).
"""
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config, spend  # noqa: E402

TOKENS_BY_TYPE = {
    "input_tokens": 100,
    "output_tokens": 50,
    "cache_creation_input_tokens": 10,
    "cache_read_input_tokens": 9000,
}


class IncompleteRateTableNamedFailureTest(unittest.TestCase):

    def test_ac5_role_missing_one_of_four_prices_raises_instead_of_returning_a_number(self):
        """Курс роли, у которого не хватает ровно одной из четырёх цен
        (`cache_read_usd_per_token`), приводит к явному исключению при
        расчёте частичной стоимости — не к числу.

        Ловит мутацию: расчёт использует `rate.get(field, 0)` вместо
        `rate[field]` (тихий ноль/пропуск вида токена вместо отказа) —
        тогда `spend.partial_cost_usd` вернёт валидный `float` вместо
        исключения, `assertRaises` не сработает и тест провалится.
        """
        role = "test_author"
        complete = config.TOKEN_RATES[role]
        incomplete = {k: v for k, v in complete.items()
                     if k != "cache_read_usd_per_token"}

        with mock.patch.dict(config.TOKEN_RATES, {role: incomplete}):
            with self.assertRaises(Exception):
                spend.partial_cost_usd(role, TOKENS_BY_TYPE)

    def test_ac5_the_same_breakdown_with_the_complete_rate_does_not_raise(self):
        """Контрольная проверка: ТА ЖЕ разбивка usage с ПОЛНЫМ курсом
        (все четыре цены на месте) считается без исключений — отказ в
        предыдущем тесте вызван именно неполнотой курса, а не самой
        разбивкой или ролью.

        Ловит мутацию: реализация бросает исключение при ЛЮБОМ вызове
        `partial_cost_usd` (например, из-за не связанной с курсом
        ошибки в разборе `tokens_by_type`) — тогда этот тест, ожидающий
        штатное вычисление, тоже упадёт, и стало бы ясно, что предыдущий
        тест проходит по ложной причине.
        """
        role = "test_author"
        complete = dict(config.TOKEN_RATES[role])
        complete.setdefault("cache_creation_usd_per_token", 0.000005)
        complete.setdefault("cache_read_usd_per_token", 0.000001)

        with mock.patch.dict(config.TOKEN_RATES, {role: complete}):
            result = spend.partial_cost_usd(role, TOKENS_BY_TYPE)

        self.assertIsInstance(result, float)


if __name__ == "__main__":
    unittest.main()
