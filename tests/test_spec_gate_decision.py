"""Разбор файла решения на гейте SPEC (`orchestrator/spec_gate_decision.py`) — края, не покрытые сквозными тестами задачи 01M6KB0SJHDA4D4GNEM7PGZ40P: ведущие нули номеров, голый маркер мандата, нечитаемые ANSWER-n, нумерация записи возврата."""
import unittest

from orchestrator import spec_gate_decision as decision
from orchestrator.advance_gates import mandate


def render(number: str = "1", **values) -> str:
    fields = {
        decision.FIELD_TEXT: "решено",
        decision.FIELD_CLAIMS: "нет",
        decision.FIELD_CHECK: "AC-1; не меняет файлов",
        decision.FIELD_TESTS: "нет",
        decision.FIELD_PRIOR: "первое решение",
        decision.FIELD_ZONES: "выполнимо в зонах SPEC",
    }
    fields.update(values)
    body = "\n".join(f"{name}: {value}" for name, value in fields.items())
    return f"{decision.HEADER}\n\n## Решения\n\n### Решение {number}\n{body}\n"


class ParseEdgesTest(unittest.TestCase):

    def test_subsection_number_with_leading_zero_refused(self):
        """«### Решение 01» — номер не подряд с 1: отказ разбора.

        Ловит мутацию: номер сверяется как `int(number) == i` без сверки
        записи — «01» проходит за «1».
        """
        with self.assertRaises(decision.DecisionError) as caught:
            decision.parse(render("01"))
        self.assertIn("01", str(caught.exception))
        self.assertEqual(decision.parse(render("1"))[0]["number"], 1)

    def test_numbered_returns_none_for_text_reason(self):
        """Причина текстом и запись с заголовком не по форме нумеруются «k» (`None`), запись по форме — решениями «n» с текстом поля «Текст».

        Ловит мутацию: `numbered` проверяет только заголовок — запись с
        заголовком без раздела получает номера «k.n».
        """
        self.assertIsNone(decision.numbered("причина текстом"))
        self.assertIsNone(decision.numbered(f"{decision.HEADER}\n\nтекст"))
        self.assertEqual(decision.numbered(render(**{decision.FIELD_TEXT: "итог"})),
                         [("1", "итог")])


class PriorRefusalTest(unittest.TestCase):

    def test_leading_zero_reference_is_nonexistent(self):
        """«№01» при прежнем «1» — ссылка на несуществующий номер.

        Ловит мутацию: номер ссылки приводится к `int` — «№01» засчитан
        ссылкой на «1».
        """
        problem = decision.prior_refusal("№1, №01: противоречий нет", ["1"])
        self.assertIsNotNone(problem)
        self.assertIn("№01", problem)
        self.assertIsNone(decision.prior_refusal("№1: противоречий нет", ["1"]))


class MandateRefusalTest(unittest.TestCase):

    def test_bare_marker_refused_without_reading_answers(self):
        """Голый маркер мандата тестов — отказ; поле без «мандат:» ANSWER-n не читает.

        Ловит мутацию: голый маркер даёт пустой список элементов и
        проходит молча («проверять нечего»).
        """
        line = f"мандат: {mandate.TEST_WEAKENING_MANDATE_MARKER}"
        self.assertIn("без элементов",
                      decision.mandate_refusal(line, lambda: ["x"]) or "")

        def unread():
            raise AssertionError("ANSWER-n прочитаны без строки мандата")

        self.assertIsNone(decision.mandate_refusal("нет", unread))

    def test_unread_answers_refused(self):
        """ANSWER-n не прочитаны (`None`) — отказ, а не проход.

        Ловит мутацию: `None` от чтения схлопывается в пустой список — отказ
        говорит «не подан answer», а не о непрочитанных ANSWER-n; либо
        исключение `TypeError` вместо отказа.
        """
        line = f"мандат: {mandate.TEST_WEAKENING_MANDATE_MARKER} tests/a.py"
        self.assertIn("не прочитаны",
                      decision.mandate_refusal(line, lambda: None) or "")
        answer = f"{mandate.TEST_WEAKENING_MANDATE_MARKER} tests/a.py\n"
        self.assertIsNone(decision.mandate_refusal(line, lambda: [answer]))


if __name__ == "__main__":
    unittest.main()
