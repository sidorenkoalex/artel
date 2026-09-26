"""AC-3: пара `item.started`/`item.completed` одного `item.id` — вызов
инструмента, его результат и признак ошибки из `status`.

Красен до реализации: `CodexProvider.parse_output_line` ещё не реализован — базовый интерфейс поднимает `NotImplementedError`, вызовов и результатов из пары не получается вовсе.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _stream import (COMMAND, COMMAND_COMPLETED, COMMAND_FAILED,  # noqa: E402
                     COMMAND_ID, COMMAND_OUTPUT, COMMAND_STARTED, MCP_FAILED,
                     MCP_ID, provider)


class ToolCallPairTest(unittest.TestCase):
    """Вызов инструмента и его результат связаны идентификатором элемента."""

    def one_call(self, raw: str):
        calls = provider().parse_output_line(raw).tool_calls
        self.assertEqual(len(calls), 1, f"ожидался один вызов, получено {calls}")
        return calls[0]

    def one_result(self, raw: str):
        results = provider().parse_output_line(raw).tool_results
        self.assertEqual(len(results), 1,
                         f"ожидался один результат, получено {results}")
        return results[0]

    def test_ac3_started_gives_the_call_and_completed_gives_its_result(self):
        """`item.started` элемента `command_execution` даёт вызов (тот же
        идентификатор, непустое имя инструмента, ключевой аргумент —
        команда), `item.completed` того же `item.id` — результат с текстом
        `aggregated_output` и без признака ошибки при `status: completed`.

        Имя инструмента сверяется на непустоту, а не на литерал: AC-3
        требует «имя инструмента», конкретного слова не называя.

        Ловит мутацию: результат разбирается как ещё один вызов (обе
        строки пары кладутся в `tool_calls`) — метрика трения шага видит
        два вызова вместо одного на каждую команду, доля повторов
        удваивается, и порог трения начинает срабатывать на ровном шаге.
        """
        call = self.one_call(COMMAND_STARTED)

        self.assertEqual(call.id, COMMAND_ID)
        self.assertEqual(call.argument, COMMAND)
        self.assertTrue(call.name, "имя инструмента не названо")
        self.assertEqual(provider().parse_output_line(COMMAND_STARTED).tool_results,
                         (), "начало вызова результата ещё не несёт")

        result = self.one_result(COMMAND_COMPLETED)

        self.assertEqual(result.call_id, call.id,
                         "результат связан с вызовом идентификатором элемента")
        self.assertEqual(result.text, COMMAND_OUTPUT)
        self.assertFalse(result.is_error, "status: completed — не ошибка")
        self.assertEqual(provider().parse_output_line(COMMAND_COMPLETED).tool_calls,
                         (), "завершение вызова второй раз не заявляет")

    def test_ac3_the_error_flag_comes_from_status_not_from_the_error_field(self):
        """`status: "failed"` помечает результат ошибкой и у
        `command_execution`, и у `mcp_tool_call` — у второго ПРИ
        `error: null`.

        Ловит мутацию: признак ошибки берётся из поля `error` (самое
        естественное чтение имени поля) — провалившийся вызов MCP с
        `error: null` уезжает в пульт как успешный, и шаг, у которого
        инструмент не сработал ни разу, выглядит гладким.
        """
        failed = self.one_result(COMMAND_FAILED)

        self.assertEqual(failed.call_id, COMMAND_ID)
        self.assertTrue(failed.is_error, "status: failed — ошибка")

        mcp = self.one_result(MCP_FAILED)

        self.assertEqual(mcp.call_id, MCP_ID)
        self.assertTrue(mcp.is_error,
                        "status: failed при error: null — тоже ошибка")


if __name__ == "__main__":
    unittest.main()
