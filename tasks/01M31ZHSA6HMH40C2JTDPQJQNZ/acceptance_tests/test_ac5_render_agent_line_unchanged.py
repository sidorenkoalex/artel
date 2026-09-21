"""AC-5 — 01M31ZHSA6HMH40C2JTDPQJQNZ: `agent_log.render_agent_line` на
образце потока даёт байт-в-байт те же строки, что до задачи.

Источник — SPEC.md, «Критерии приёмки»:

AC-5. `agent_log.render_agent_line` на том же образце даёт байт-в-байт те
же строки, что до задачи: текст ассистента, строка вызова инструмента,
строка `! ошибка агента: …`, не-JSON строка как есть, служебное событие —
пустая строка.

Зелёный с рождения: это тест сохранения существующего поведения —
рендер строк образца сегодня уже такой (ожидания в `_sample.
EXPECTED_RENDER` сняты с `orchestrator/agent_log.py:120-142` литералами,
не повторным вызовом той же функции). Красным он станет ровно тогда,
когда переезд разбора к провайдеру изменит хоть один символ строки,
которую видит Оператор в логе шага.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _provider  # noqa: E402
import _sample  # noqa: E402
from orchestrator import agent_log  # noqa: E402


class RenderAgentLineTest(unittest.TestCase):

    def render(self, line: str) -> str:
        return _sample.flex(agent_log.render_agent_line, line,
                            provider=_provider.claude())

    def test_ac5_every_line_of_the_sample_renders_as_before(self):
        """Каждая строка образца рендерится ровно в ту строку, которую
        пульт писал в лог шага до задачи.

        Ловит мутацию: разбор, переехавший к провайдеру, теряет пробел/
        перенос строки в строке вызова инструмента («· Read <файл>») или
        начинает пропускать не-JSON строку stderr — лог шага, по
        которому Оператор читает ход работы, меняется молча, а числа
        стоимости при этом остаются верными и ни один другой тест этого
        не замечает.
        """
        for line, expected in _sample.EXPECTED_RENDER.items():
            with self.subTest(line=line[:60]):
                self.assertEqual(self.render(line), expected)

    def test_ac5_error_result_line_keeps_its_prefix(self):
        """Финальное событие с ошибкой даёт строку `! ошибка агента: …`
        с текстом ошибки, а успешное — пустую строку.

        Ловит мутацию: признак ошибки итога запуска у события общего
        вида читается наоборот (или теряется), и провал агента уходит в
        лог как обычное служебное событие — Оператор видит молчаливо
        оборвавшийся шаг без причины.
        """
        self.assertEqual(self.render(_sample.ERROR_RESULT_LINE),
                         f"! ошибка агента: {_sample.ERROR_TEXT}\n")
        self.assertEqual(self.render(_sample.RESULT_LINE), "")


if __name__ == "__main__":
    unittest.main()
