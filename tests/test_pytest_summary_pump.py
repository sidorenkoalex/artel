"""Юнит-тесты распознавания итоговой строки pytest и её передачи насосом
вывода шага (`orchestrator/agent_log.py::pytest_summaries`/`OutputPump`,
SPEC 01M446X1B7FB8JDMYFP5APWTVE, требование 1) — углы, не покрытые
долгоживущими файлами задачи: формы итоговой строки, которые печатает
настоящий pytest, и сбой записи, не роняющий насос.
"""
import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout

from orchestrator import agent_log
from tests.sandbox import TmpRootTest


def tool_result_line(text: str) -> str:
    return json.dumps({"type": "user", "message": {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": "toolu_1", "content": text,
         "is_error": False}]}}, ensure_ascii=False) + "\n"


class PytestSummariesTest(unittest.TestCase):

    def test_real_pytest_forms_are_recognised_without_frame(self):
        """Итоговые строки с предупреждениями, ошибками, длительностью
        «(0:00:12)» и цветом ANSI — распознаются, рамка «=» снята.

        Ловит мутацию: шаблон знает только «failed»/«passed» подряд — строка
        с «warnings»/«errors» не распознается; ANSI-коды не снимаются —
        цветная строка `pytest` в терминале роли не распознается; рамка «=»
        не снимается — detail несёт «=».
        """
        text = ("collected 3 items\n"
                "== 1 failed, 2 passed, 3 warnings in 12.30s (0:00:12) ==\n"
                "\x1b[32m5 passed\x1b[0m\x1b[32m in 0.10s\x1b[0m\n"
                "===== 2 errors in 1.00s =====\n")
        self.assertEqual(agent_log.pytest_summaries(text), [
            "1 failed, 2 passed, 3 warnings in 12.30s (0:00:12)",
            "5 passed in 0.10s",
            "2 errors in 1.00s"])

    def test_words_without_counts_and_duration_are_not_a_summary(self):
        """Слова исходов без числа или без «in X.XXs» — не итоговая строка.

        Ловит мутацию: распознавание по слову «passed» или по «N passed»
        без длительности — листинг и строка прогресса дадут запись.
        """
        text = ("passed in review\n"
                "tests passed\n"
                "3 passed\n"
                "assert result == 'passed in 1s'\n")
        self.assertEqual(agent_log.pytest_summaries(text), [])


class PumpPytestSummaryTest(TmpRootTest):

    def test_summary_callback_failure_keeps_pump_reading(self):
        """Сбой получателя итоговой строки не обрывает перекачку: строки
        после результата инструмента доходят до лога, `pump.error` пуст.

        Ловит мутацию: исключение получателя не перехвачено — насос
        прекращает чтение пайпа на первом же прогоне pytest (агент повис бы
        на записи в переполненный пайп), строка «дальше» не попадёт в лог.
        """
        seen = []

        def failing(summary):
            seen.append(summary)
            raise RuntimeError("БД занята")

        log = agent_log.new_agent_log("T001", "developer")
        stream = iter([tool_result_line("==== 4 passed in 1.00s ===="),
                       "дальше\n"])
        pump = agent_log.OutputPump(stream, log, on_pytest_summary=failing)
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            pump.start()
            pump.join(5)

        self.assertEqual(seen, ["4 passed in 1.00s"])
        self.assertIsNone(pump.error)
        self.assertEqual(log.read_text(encoding="utf-8"), "дальше\n")


if __name__ == "__main__":
    unittest.main()
