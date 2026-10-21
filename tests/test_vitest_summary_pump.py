"""Юнит-тесты передачи сводки Vitest насосом вывода шага
(`orchestrator/agent_log.py::vitest_summaries`/`OutputPump`, SPEC
01M5ENWTDD8NP9SMPFX3JN08J9, требования 2-3) — углы, не покрытые
долгоживущими файлами задачи: сбой записи, не роняющий насос, и несколько
блоков в одном результате инструмента.
"""
import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout

from orchestrator import agent_log
from tests.sandbox import TmpRootTest

BLOCK = (" Test Files  1 passed (1)\n"
         "      Tests  4 passed (4)\n"
         "   Duration  1.2s\n")


def tool_result_line(text: str) -> str:
    return json.dumps({"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "toolu_1", "content": text,
         "is_error": False}]}}, ensure_ascii=False) + "\n"


class VitestSummariesTest(unittest.TestCase):

    def test_each_block_of_one_output_is_a_summary(self):
        """Два блока Vitest в одном выводе — две детали в порядке появления.

        Ловит мутацию: разбор останавливается на первом блоке (`return` вместо
        `break` после найденной `Duration`) — второго прогона в журнале нет.
        """
        second = BLOCK.replace("4 passed (4)", "1 failed | 3 passed (4)") \
            .replace("1.2s", "87ms")
        self.assertEqual(agent_log.vitest_summaries(BLOCK + "\n" + second),
                         ["4 passed (4) in 1.20s",
                          "1 failed | 3 passed (4) in 0.09s"])


class PumpVitestSummaryTest(TmpRootTest):

    def test_summary_callback_failure_keeps_pump_reading(self):
        """Сбой получателя сводки Vitest не обрывает перекачку: строки после
        результата инструмента доходят до лога, `pump.error` пуст.

        Ловит мутацию: исключение получателя сводки Vitest не перехвачено —
        насос прекращает чтение пайпа на первом же прогоне Vitest, строка
        «дальше» не попадёт в лог.
        """
        seen = []

        def failing(summary):
            seen.append(summary)
            raise RuntimeError("БД занята")

        log = agent_log.new_agent_log("T001", "developer")
        stream = iter([tool_result_line(BLOCK), "дальше\n"])
        pump = agent_log.OutputPump(stream, log, on_vitest_summary=failing)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            pump.start()
            pump.join(5)

        self.assertEqual(seen, ["4 passed (4) in 1.20s"])
        self.assertIsNone(pump.error)
        self.assertEqual(log.read_text(encoding="utf-8"), "дальше\n")


if __name__ == "__main__":
    unittest.main()
