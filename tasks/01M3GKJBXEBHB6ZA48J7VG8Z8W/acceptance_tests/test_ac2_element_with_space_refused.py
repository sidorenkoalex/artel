"""AC-2 — 01M3GKJBXEBHB6ZA48J7VG8Z8W: элемент мандата с пробелом внутри
(тире, пояснение) отказывает при записи.

Источник — SPEC.md, «Критерии приёмки»:

AC-2. `answer` с файлом, где элемент мандата содержит пробел (тире или
пояснение внутри элемента — строка прецедента «Расширение зон разрешено:
orchestrator/artel.py — только разбор аргументов»), отказывает; текст
отказа называет строку, элемент и причину; `ANSWER-n.md` на артефактной
ветке не появляется и записи в журнале задачи нет.

Строка взята прецедентом 26.09 дословно (ANSWER-1 задачи 01M3FQ3J): путь
и пояснение в ОДНОМ элементе — ровно то, что гейт зон молча не засчитал.
`orchestrator/artel.py` в дереве кодовой ветки песочницы существует
(`_sandbox.CODE_BRANCH_TREE`), поэтому отказ обязан прийти из-за пробела в
элементе, а не из-за отсутствия пути: причину в тексте отказа критерий
требует назвать, и планка сверяет, что названа именно эта («пробел»/«не
похож на путь»), а не проверка существования.

Второй метод — та же строка в файле, где мандат стоит НЕ первой строкой
(«Материалы» SPEC: `answer` сегодня берёт только ПЕРВУЮ строку маркера, а
требование 2 обязывает покрывать ВСЕ строки мандатов файла).

Красен до реализации: `orchestrator/answer.py::_cmd_answer` для задачи в
`escalated` вообще не смотрит на содержимое файла ответа (`answer.py:124-125`)
— ANSWER коммитится, отказа нет ни на первой строке мандата, ни на
последующих.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _sandbox  # noqa: E402

#: Строка-прецедент 26.09 целиком.
PRECEDENT_LINE = _sandbox.zones_mandate_line(_sandbox.SPACED_ELEMENT)

#: Причина отказа: критерий требует её назвать, формулировку не
#: фиксирует — планка принимает любую из двух, которыми требование 2а
#: описывает само правило.
REASON_WORDS = ("пробел", "не похож на путь")


class ElementWithSpaceRefusedTest(_sandbox.AnswerMandateSandbox):

    def assert_names_line_element_and_reason(self, message: str) -> None:
        self.assertIn(_sandbox.SPACED_ELEMENT, message,
                      "текст отказа обязан назвать сам элемент")
        self.assertIn(PRECEDENT_LINE, message,
                      "текст отказа обязан назвать строку мандата целиком")
        self.assertTrue(
            any(word in message for word in REASON_WORDS),
            f"текст отказа не называет причину ({' / '.join(REASON_WORDS)}): "
            f"{message}")

    def test_ac2_element_with_space_refuses_naming_line_element_and_reason(self):
        """Файл ответа несёт строку прецедента, где пояснение с тире стоит
        ВНУТРИ элемента мандата зон — `answer` отказывает, назвав строку,
        элемент и причину; ни `ANSWER-1.md` на артефактной ветке, ни записи
        об ANSWER в журнале задачи не появляется.

        Ловит мутацию: проверка элемента сведена к существованию пути
        (`ls-tree` по элементу целиком) без правила «элемент не содержит
        пробела» — отказ придёт, но назовёт не ту причину, и Оператор,
        читая «пути нет в дереве», добавит в мандат путь вместо того чтобы
        вынести пояснение в отдельный абзац.
        """
        message = self.refuse_answer(_sandbox.answer_text(PRECEDENT_LINE))

        self.assert_names_line_element_and_reason(message)

    def test_ac2_same_element_on_a_later_mandate_line_also_refuses(self):
        """Тот же элемент, но строка мандата в файле не первая: перед ней
        идёт исправная строка мандата зон и абзац текста — `answer`
        отказывает так же.

        Ловит мутацию: проверка разбирает только ПЕРВУЮ строку маркера в
        файле (сегодняшнее поведение `_zones_mandate_marker_paths`) — второй
        мандат того же файла проехал бы без проверки, и прецедент 26.09
        повторился бы в файле с двумя строками мандата.
        """
        text = _sandbox.answer_text(
            _sandbox.zones_mandate_line(_sandbox.EXISTING_FILE),
            "",
            "Пояснение Оператора отдельным абзацем.",
            "",
            PRECEDENT_LINE)

        message = self.refuse_answer(text)

        self.assert_names_line_element_and_reason(message)


if __name__ == "__main__":
    unittest.main()
