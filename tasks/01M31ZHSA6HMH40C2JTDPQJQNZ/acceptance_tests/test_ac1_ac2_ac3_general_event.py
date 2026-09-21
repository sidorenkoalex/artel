"""AC-1, AC-2, AC-3 — 01M31ZHSA6HMH40C2JTDPQJQNZ: разбор строки вывода
объявлен интерфейсом провайдера, а событие общего вида несёт пять
предметов требования 1, разбивку по ОБЩИМ видам и полный итог запуска.

Источник — SPEC.md, «Критерии приёмки»:

AC-1. `orchestrator/providers/base.py::RoleExecutorProvider` объявляет
разбор строки вывода в событие общего вида, и событие различает пять
предметов требования 1: текст для лога; вызов инструмента (имя и
аргументы); результат инструмента; учёт токенов разбивкой по видам; итог
запуска. Базовая реализация тела не несёт — тем же `NotImplementedError`,
что остальные методы интерфейса.

AC-2. Учёт токенов события общего вида разложен по четырём ОБЩИМ видам —
`input`, `output`, `cache_write`, `cache_read` (`models.PRICE_KINDS`), а
не по именам счётчиков Claude.

AC-3. Итог запуска события общего вида несёт: разбивку по видам,
стоимость в долларах от CLI ЛИБО её явное отсутствие (отличимое от нуля),
признак ошибки и её текст.

Имён новых членов интерфейса критерии не называют — планка читает состав
из самого `base.py` (`_provider.new_callables`) и ищет названные
критерием ЗНАЧЕНИЯ в том, что провайдер отдал (`_sample.leaves`/
`_sample.has_breakdown`), не диктуя форму события.

Красен до реализации: `orchestrator/providers/base.py` не объявляет ни
одного члена сверх шести методов задачи 01M2ZNTHSNFYSTF904P6SZTPYF —
`_provider.new_callables()` пуст, разбирать строку провайдеру нечем.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _provider  # noqa: E402
import _sample  # noqa: E402
from orchestrator import models  # noqa: E402
from orchestrator.providers.base import RoleExecutorProvider  # noqa: E402


class GeneralEventTest(unittest.TestCase):

    def setUp(self):
        self.provider = _provider.claude()

    def parsed(self, line: str) -> list:
        return _provider.parse_results(self.provider, line)

    def leaves(self, line: str) -> list:
        return _sample.leaves(self.parsed(line))

    def test_ac1_interface_declares_line_parsing_without_a_body(self):
        """`base.py` объявляет разбор строки вывода, и базовая реализация
        тела не несёт — `NotImplementedError`, как у остальных методов
        интерфейса.

        Ловит мутацию: разбор объявлен только у `ClaudeProvider` (в базе
        метода нет) либо база отдаёт `None`/пустое событие вместо
        `NotImplementedError` — второй провайдер, забывший реализовать
        разбор, тихо даст шаг без лога, без трения и без стоимости
        вместо громкого отказа.
        """
        members = _provider.new_callables()

        self.assertTrue(members,
                        "orchestrator/providers/base.py не объявляет ни "
                        "одного члена сверх интерфейса до задачи "
                        f"({sorted(_provider.PRE_TASK_MEMBERS)}) — разбор "
                        f"строки вывода провайдеру не поручен")
        base = RoleExecutorProvider()
        for name, arity in members:
            with self.subTest(member=name):
                args = (_sample.TEXT_LINE,) * arity
                with self.assertRaises(NotImplementedError):
                    getattr(base, name)(*args)

    def test_ac1_general_event_tells_the_five_subjects_apart(self):
        """Пять строк образца дают пять РАЗНЫХ событий, и каждое несёт
        своё: текст ассистента, имя и аргумент вызова инструмента, текст
        результата инструмента, разбивку токенов, итог запуска.

        Ловит мутацию: вызов инструмента и его результат складываются в
        одно и то же событие (или результат инструмента гасится, как его
        гасит `render_agent_line`) — метрика трения шага, которой нужны
        вызов и результат вместе, теряет половину своих сигналов и
        навсегда показывает 0.0.
        """
        subjects = {
            "текст": _sample.TEXT_LINE,
            "вызов инструмента": _sample.TOOL_USE_LINE,
            "результат инструмента": _sample.TOOL_RESULT_LINE,
            "итог запуска": _sample.RESULT_LINE,
            "служебное событие": _sample.SYSTEM_LINE,
        }
        seen = {name: repr(self.parsed(line))
                for name, line in subjects.items()}
        for name, text in seen.items():
            others = [other for key, other in seen.items() if key != name]
            self.assertNotIn(text, others,
                             f"событие «{name}» неотличимо от другого "
                             f"предмета требования 1")

        self.assertIn(_sample.ASSISTANT_TEXT, self.leaves(_sample.TEXT_LINE))
        tool_leaves = self.leaves(_sample.TOOL_USE_LINE)
        self.assertIn(_sample.TOOL_NAME, tool_leaves)
        self.assertIn(_sample.TOOL_ARG, tool_leaves)
        self.assertNotIn(_sample.TOOL_RESULT_TEXT, tool_leaves,
                         "результат инструмента приехал в событие вызова")
        self.assertIn(_sample.TOOL_RESULT_TEXT,
                      self.leaves(_sample.TOOL_RESULT_LINE))
        self.assertIn(_sample.RESULT_TEXT, self.leaves(_sample.RESULT_LINE))

    def test_ac2_token_accounting_uses_the_four_common_kinds(self):
        """Разбивка токенов события общего вида — по `input`, `output`,
        `cache_write`, `cache_read`, а не по именам счётчиков Claude.

        Ловит мутацию: событие общего вида отдаёт разбивку именами
        счётчиков Claude (`input_tokens`, `cache_creation_input_tokens`)
        — второй провайдер обязан будет притворяться Claude, чтобы его
        токены вообще тарифицировались, а тариф каталога считает по
        общим видам.
        """
        event = self.parsed(_sample.TEXT_LINE)

        self.assertTrue(
            _sample.has_breakdown(event, _sample.EXPECTED_ASSISTANT_BY_KIND),
            f"в событии нет разбивки по общим видам "
            f"{models.PRICE_KINDS}: {event!r}")
        claude_named = [table for table in _sample.mappings(event)
                        if all(table.get(key) == count for key, count
                               in _sample.USAGE_ASSISTANT.items())]
        self.assertEqual(claude_named, [],
                         "разбивка события разложена по именам счётчиков "
                         "Claude, а не по общим видам цены")

    def test_ac3_run_result_carries_breakdown_price_and_error(self):
        """Итог запуска несёт разбивку по видам, цену от CLI, признак
        ошибки и её текст.

        Ловит мутацию: признак ошибки итога запуска не доезжает до
        события общего вида (или доезжает без текста) — строка `!
        ошибка агента: …` пропадает из лога шага, и Оператор видит
        оборвавшийся шаг без причины.
        """
        final = self.parsed(_sample.RESULT_LINE)
        failed = self.parsed(_sample.ERROR_RESULT_LINE)

        self.assertTrue(
            _sample.has_breakdown(final, _sample.EXPECTED_COST_BY_KIND),
            f"итог запуска без разбивки по видам: {final!r}")
        self.assertIn(_sample.RESULT_USD, _sample.leaves(final))
        self.assertIn(_sample.ERROR_TEXT, _sample.leaves(failed))
        self.assertTrue(any(item is True for item in _sample.leaves(failed)),
                        f"итог запуска не несёт признака ошибки: {failed!r}")
        self.assertNotIn(_sample.ERROR_TEXT, _sample.leaves(final),
                         "успешный итог запуска несёт чужой текст ошибки")

    def test_ac3_missing_price_differs_from_a_zero_price(self):
        """Итог запуска без цены отличим от итога с ценой ровно ноль.

        Ловит мутацию: отсутствие цены в итоге запуска подставляется
        нулём — бесплатный запуск и запуск провайдера, который цены не
        сообщает, становятся неотличимы, и шаг второго списывается как
        нулевой вместо расчёта по тарифу (требование 4).
        """
        absent = self.parsed(_sample.RESULT_WITHOUT_PRICE_LINE)
        zero = self.parsed(_sample.RESULT_ZERO_PRICE_LINE)

        self.assertNotEqual(repr(absent), repr(zero))
        # Именно число с плавающей точкой: `0.0 in [...]` совпало бы и с
        # `False` признака ошибки — Python считает их равными.
        self.assertTrue(
            any(isinstance(item, float) and item == 0.0
                for item in _sample.leaves(zero)),
            "итог запуска с ценой ноль не несёт самой цены")
        self.assertTrue(
            _sample.has_breakdown(absent, _sample.EXPECTED_COST_BY_KIND),
            f"итог запуска без цены потерял и разбивку по видам: {absent!r}")


if __name__ == "__main__":
    unittest.main()
