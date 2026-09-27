"""AC-4 — 01M3GKJBXEBHB6ZA48J7VG8Z8W: мандат ослабления тестов — только
путь под `tests/` и только форма `путь::имя`.

Источник — SPEC.md, «Критерии приёмки»:

AC-4. `answer` с мандатом ослабления на путь вне `tests/` отказывает
именованно, как и на нарушенную форму `путь::имя`; мандат вида
`tests/<файл>.py` и `tests/<файл>.py::<Класс>::<метод>` проходит и ANSWER
коммитится.

Путь вне `tests/` взят СУЩЕСТВУЮЩИЙ в дереве кодовой ветки
(`orchestrator/answer.py`): так отказ обязан прийти из правила «не под
tests/», а не из проверки существования пути (требование 2б — про мандат
зон, не про этот маркер).

Красен до реализации: маркер «Ослабление тестов разрешено:» команда
`answer` сегодня не разбирает вовсе (разбирает только гейт неослабления
тестов, уже на переходе `in_dev -> verifying`) — файл с любым таким
мандатом коммитится без проверки. Два положительных метода на сегодняшнем
коде зелёные — контроль: они фиксируют, что новая проверка не начнёт
отказывать исправному мандату ни в форме пути, ни в форме `путь::имя`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _sandbox  # noqa: E402


class WeakeningMandateFormTest(_sandbox.AnswerMandateSandbox):

    def test_ac4_weakening_mandate_outside_tests_dir_refuses(self):
        """Мандат ослабления на путь вне `tests/` — `answer` отказывает
        именованно (назвав строку и элемент), ANSWER не создаётся.

        Ловит мутацию: проверка мандата ослабления сведена к той же
        проверке, что у мандата зон (существование пути в дереве) —
        `orchestrator/answer.py` в дереве есть, мандат проехал бы, и
        Оператор получил бы мандат ослабления тестов на путь, который гейт
        неослабления тестов всё равно никогда не рассматривает: мандат
        молча не сработал бы.
        """
        line = _sandbox.weakening_mandate_line(_sandbox.OUTSIDE_TESTS_PATH)

        message = self.refuse_answer(_sandbox.answer_text(line))

        self.assertIn(_sandbox.OUTSIDE_TESTS_PATH, message,
                      "отказ обязан назвать элемент вне tests/")
        self.assertIn(line, message, "отказ обязан назвать строку мандата")

    def test_ac4_weakening_mandate_with_broken_name_form_refuses(self):
        """Мандат ослабления формы `путь::` (разделитель есть, имени за ним
        нет) — `answer` отказывает именованно, ANSWER не создаётся.

        Ловит мутацию: форма не проверяется вовсе, проверяется только
        префикс `tests/` — элемент `tests/test_alpha.py::` доехал бы до
        гейта, где сверяется с квалифицированным именем находки
        (`<файл>::<Класс>::<метод>`) и не совпал бы ни с одной: мандат
        снова молча не сработал бы.
        """
        line = _sandbox.weakening_mandate_line(_sandbox.BROKEN_FORM_ELEMENT)

        message = self.refuse_answer(_sandbox.answer_text(line))

        self.assertIn(_sandbox.BROKEN_FORM_ELEMENT, message,
                      "отказ обязан назвать элемент с нарушенной формой")
        self.assertIn(line, message, "отказ обязан назвать строку мандата")

    def test_ac4_weakening_mandate_on_a_tests_file_commits_the_answer(self):
        """Мандат ослабления вида `tests/<файл>.py` проверку проходит:
        `ANSWER-1.md` коммитится и несёт строку мандата.

        Ловит мутацию: правило формы прочитано как «элемент ОБЯЗАН нести
        `::`» — мандат на файл целиком (им Оператор снимает разом удаление
        и переименование файла, docs/operator-gates.md) отказывал бы.
        """
        line = _sandbox.weakening_mandate_line(_sandbox.TESTS_FILE)

        self.succeed_answer(_sandbox.answer_text(line))

        self.assertEqual(["ANSWER-1.md"], self.answer_files())
        text = self.answer_text_in_branch(1)
        self.assertIsNotNone(text, "ANSWER-1.md не прочитан с ветки")
        self.assertIn(line, text)

    def test_ac4_weakening_mandate_on_a_qualified_method_commits_the_answer(self):
        """Мандат ослабления вида `tests/<файл>.py::<Класс>::<метод>`
        проверку проходит.

        Ловит мутацию: элемент проверяется целиком как путь репозитория
        (существование `tests/test_alpha.py::AlphaTest::test_x` в дереве) —
        квалифицированное имя метода, единственная форма точечного мандата,
        отказывало бы всегда.
        """
        line = _sandbox.weakening_mandate_line(_sandbox.TESTS_METHOD)

        self.succeed_answer(_sandbox.answer_text(line))

        self.assertEqual(["ANSWER-1.md"], self.answer_files())
        self.assertEqual([_sandbox.TESTS_METHOD],
                         self.weakening_mandate_elements(),
                         "гейт неослабления тестов обязан увидеть в этом "
                         "ANSWER ровно тот элемент, что разобрал answer")


if __name__ == "__main__":
    unittest.main()
