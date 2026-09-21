"""AC-4 — 01M31ZHSA6HMH40C2JTDPQJQNZ: `ClaudeProvider` на записанном
образце потока отдаёт события общего вида с теми же значениями, которые
на том же образце извлекает код пульта до задачи.

Источник — SPEC.md, «Критерии приёмки»:

AC-4. `ClaudeProvider` на записанном образце потока Claude (события
`type: assistant` с блоками `text`/`tool_use`, `type: user` с блоками
`tool_result`, финальное `type: result` с `total_cost_usd` и `usage`)
отдаёт события общего вида с теми же значениями, которые на том же
образце извлекает код пульта до задачи.

Значения «до задачи» — литералы `_sample`: идентификатор и имя вызова
инструмента с ключевым аргументом (`agent_log._tool_use_calls`), текст и
признак ошибки результата инструмента (`agent_log._tool_results`), текст
ассистента (`agent_log.render_block`), цена и разбивка usage
(`spend.parse_cost_event`, `spend.stream_usage_by_type`). Сверка с
литералом, а не с повторным вызовом тех же функций: тест, сравнивающий
функцию с ней же, пережил бы любую их правку.

Красен до реализации: разбор строки провайдеру ещё не поручен —
`_provider.new_callables()` пуст, и на каждой строке образца провайдер
не отдаёт ничего.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _provider  # noqa: E402
import _sample  # noqa: E402

#: Идентификаторы вызовов инструмента в образце — по ним пульт связывает
#: вызов с его результатом (метрика трения шага).
CALL_ID = "t1"
REPEAT_CALL_ID = "t2"


class ClaudeProviderSampleTest(unittest.TestCase):

    def setUp(self):
        self.provider = _provider.claude()

    def leaves(self, line: str) -> list:
        return _sample.leaves(_provider.parse_results(self.provider, line))

    def test_ac4_assistant_text_and_tool_call_keep_their_values(self):
        """Событие ассистента несёт тот же текст, а вызов инструмента —
        тот же идентификатор, имя и ключевой аргумент, что извлекал
        пульт до задачи.

        Ловит мутацию: разбор блока `tool_use` теряет идентификатор
        вызова (`id`) — связать вызов с его результатом становится
        нечем, и оба сигнала трения, которым нужна эта пара, молча
        перестают срабатывать.
        """
        self.assertIn(_sample.ASSISTANT_TEXT, self.leaves(_sample.TEXT_LINE))

        tool = self.leaves(_sample.TOOL_USE_LINE)
        self.assertIn(CALL_ID, tool)
        self.assertIn(_sample.TOOL_NAME, tool)
        self.assertIn(_sample.TOOL_ARG, tool)
        self.assertIn(REPEAT_CALL_ID,
                      self.leaves(_sample.TOOL_USE_REPEAT_LINE))

    def test_ac4_tool_result_keeps_its_id_text_and_error_flag(self):
        """Результат инструмента несёт тот же идентификатор вызова, тот
        же текст и тот же признак ошибки.

        Ловит мутацию: разбор `tool_result` отдаёт текст, но не
        идентификатор вызова (или наоборот) — сигнал «ретрай после
        ошибки» перестаёт находить свой вызов, а размер результата
        больше не с чем сопоставить.
        """
        result = self.leaves(_sample.TOOL_RESULT_LINE)

        self.assertIn(CALL_ID, result)
        self.assertIn(_sample.TOOL_RESULT_TEXT, result)
        self.assertTrue(any(item is False for item in result),
                        f"результат инструмента без признака ошибки: "
                        f"{result!r}")

    def test_ac4_usage_and_final_result_keep_their_numbers(self):
        """Учёт токенов промежуточного события и итог запуска несут те
        же числа: разбивку по видам и цену `total_cost_usd`.

        Ловит мутацию: разбор `usage` промежуточного события ищет его в
        корне события, а не в `message.usage` (или наоборот) — половина
        токенов шага пропадает, и частичная стоимость оборванного шага
        считается по остатку.
        """
        assistant = _provider.parse_results(self.provider, _sample.TEXT_LINE)
        final = _provider.parse_results(self.provider, _sample.RESULT_LINE)

        self.assertTrue(
            _sample.has_breakdown(assistant,
                                  _sample.EXPECTED_ASSISTANT_BY_KIND),
            f"промежуточное событие без учёта токенов: {assistant!r}")
        self.assertTrue(
            _sample.has_breakdown(final, _sample.EXPECTED_COST_BY_KIND),
            f"итог запуска без разбивки по видам: {final!r}")
        self.assertIn(_sample.EXPECTED_COST_USD, _sample.leaves(final))
        self.assertIn(_sample.RESULT_TEXT, _sample.leaves(final))

    def test_ac4_service_event_and_non_json_line_stay_empty(self):
        """Служебное событие и не-JSON строка не притворяются ни
        текстом, ни вызовом, ни итогом запуска.

        Ловит мутацию: строка, не разобравшаяся в JSON, отдаётся как
        текст ассистента с тем же содержимым — трейсбек CLI уезжает в
        лог дважды, а сигналы трения получают вызовы-призраки.
        """
        service = _provider.parse_results(self.provider, _sample.SYSTEM_LINE)
        plain = _provider.parse_results(self.provider, _sample.PLAIN_LINE)

        self.assertNotIn(_sample.TOOL_NAME, _sample.leaves(service))
        self.assertNotIn(_sample.EXPECTED_COST_USD, _sample.leaves(service))
        self.assertNotEqual(repr(plain), repr(
            _provider.parse_results(self.provider, _sample.TEXT_LINE)))


if __name__ == "__main__":
    unittest.main()
