"""AC-6 — 01M3GKJBXEBHB6ZA48J7VG8Z8W: валидная строка мандата с отступом
проверку проходит.

Источник — SPEC.md, «Критерии приёмки»:

AC-6. Валидная строка мандата с ведущими пробелами (отступом) проверку
проходит: ANSWER коммитится, элементы разобраны те же, что и без отступа.

«Те же, что и без отступа» снимается наблюдаемой самой команды: в
состоянии `in_dev` `answer` пишет разобранные элементы мандата зон в
запись журнала (`orchestrator/answer.py:153-156`), поэтому два вызова
подряд — сначала со строкой с отступом, потом с той же строкой без
отступа — дают два списка, которые планка сверяет между собой. Состояние
`in_dev` выбрано только ради этой наблюдаемой: проверка требования 2
применяется в любом состоянии, где команда принимает файл.

Зелёный с рождения: сегодня `answer` строку мандата стрипает
(`orchestrator/answer.py:58`) и оба вызова проходят — тест сохранения
существующего поведения. Он краснеет ровно тогда, когда новая проверка
судит элементы по НЕ стрипнутой строке: первым элементом тогда оказывается
«  <путь>» с ведущими пробелами, и исправный мандат Оператора, записанный
с отступом (как его пишут в списках и цитатах), отказывает как «элемент
содержит пробел».
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _sandbox  # noqa: E402

#: Перечень элементов, одинаковый у обоих вызовов.
TAIL = f"{_sandbox.EXISTING_FILE}, {_sandbox.EXISTING_DIR}/"

#: Отступ, с которым Оператор пишет строку мандата в списке или цитате.
INDENT = "   "


class IndentedMandatePassesTest(_sandbox.AnswerMandateSandbox):

    def test_ac6_indented_mandate_line_passes_and_parses_the_same(self):
        """Строка мандата зон с ведущими пробелами — `answer` коммитит
        `ANSWER-1.md`; та же строка без отступа следующим вызовом даёт
        `ANSWER-2.md`, и оба разбора дают один и тот же список элементов.

        Ловит мутацию: новая проверка судит элементы по строке ДО `strip`
        (например разбирает `raw.splitlines()` без `line.strip()`, а
        прежний стрипающий разбор остался только в ветке журнала) —
        первый элемент строки с отступом оказывается «   orchestrator/answer.py»,
        проверка 2а видит в нём пробел и отказывает исправному мандату.
        """
        self.set_state("in_dev")

        self.succeed_answer(_sandbox.answer_text(
            INDENT + _sandbox.zones_mandate_line(TAIL)))
        self.assertEqual(["ANSWER-1.md"], self.answer_files(),
                         "мандат с отступом обязан пройти проверку")

        self.succeed_answer(_sandbox.answer_text(
            _sandbox.zones_mandate_line(TAIL)))
        self.assertEqual(["ANSWER-1.md", "ANSWER-2.md"], self.answer_files())

        parsed = self.journal_mandate_paths()
        self.assertEqual(2, len(parsed),
                         f"ожидались две записи мандата: {self.journal()}")
        self.assertEqual(
            parsed[1], parsed[0],
            "элементы строки с отступом разобраны иначе, чем без отступа")
        self.assertEqual([_sandbox.EXISTING_FILE, _sandbox.EXISTING_DIR + "/"],
                         parsed[0],
                         "разобраны не те элементы, что записаны в строке")


if __name__ == "__main__":
    unittest.main()
