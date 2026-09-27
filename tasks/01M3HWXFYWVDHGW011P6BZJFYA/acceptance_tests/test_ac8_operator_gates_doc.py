"""AC-8 (tasks/01M3HWXFYWVDHGW011P6BZJFYA/SPEC.md): `docs/operator-gates.md`
несёт правило требования 9 — называет и случай без мандата (новый тест,
условие, названная причина), и случаи, где мандат нужен по-прежнему (без
причины, безусловный маркер, существующий метод, ранний `return` под
условием).

`docs/operator-gates.md` — файл кода рабочей копии (зона задачи), не
артефакт задачи: читается с диска обычным способом, тем же приёмом, что
планки прошлых задач о документации.

Красен до реализации: сегодня в документе нет ни абзаца о пропуске в
новом тесте (слов «новый тест» в нём нет вовсе), ни слова `return` —
п.6 гейта эскалации знает только общий мандат ослабления тестов.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import REPO_ROOT  # noqa: E402

GATES_DOC = REPO_ROOT / "docs" / "operator-gates.md"


def paragraphs() -> list:
    """Абзацы документа в нижнем регистре — правило проверяется по
    ОДНОМУ абзацу, а не по документу целиком: слова «новый», «условие» и
    «причина» порознь разбросаны по файлу и по отдельности ничего о
    правиле не говорят."""
    text = GATES_DOC.read_text(encoding="utf-8").lower()
    return [p for p in re.split(r"\n\s*\n", text) if p.strip()]


class OperatorGatesDocTest(unittest.TestCase):

    def setUp(self):
        self.assertTrue(GATES_DOC.is_file(), f"{GATES_DOC} не найден")
        self.chunks = paragraphs()

    def _paragraph_with(self, *needles: str) -> str:
        for chunk in self.chunks:
            if all(needle in chunk for needle in needles):
                return chunk
        return ""

    def test_ac8_gates_doc_names_the_case_without_mandate(self):
        """В документе есть абзац, где сказано: пропуск в НОВОМ тесте с
        УСЛОВИЕМ и названной ПРИЧИНОЙ мандата не требует.

        Ловит мутацию: код послаблён, а документ не тронут (или правка
        сведена к строке «пропуски в новых тестах разрешены» без условия
        и причины) — Оператор, читающий гейт по документу, не знает, на
        каком основании рубеж промолчал, и либо требует мандат там, где
        он больше не нужен, либо считает разрешённым любой пропуск в
        новом файле.
        """
        chunk = self._paragraph_with("нов", "услов", "причин", "мандат")

        self.assertTrue(
            chunk,
            "docs/operator-gates.md обязан нести абзац о пропуске в НОВОМ "
            "тесте с УСЛОВИЕМ и названной ПРИЧИНОЙ, которому мандат не "
            "нужен (AC-8)")
        self.assertTrue(
            "не требует" in chunk or "не нужен" in chunk
            or "не нужна" in chunk or "без мандата" in chunk,
            f"абзац обязан сказать, что мандат в этом случае НЕ нужен "
            f"(AC-8); абзац: {chunk}")

    def test_ac8_gates_doc_names_the_cases_where_mandate_is_still_needed(self):
        """Документ называет и случаи, где мандат по-прежнему нужен:
        пропуск без причины, безусловный маркер, пропуск в существующем
        методе и ранний `return` под условием.

        Ловит мутацию: документ описал только послабление — Оператор
        читает его как «пропуски в новых тестах больше не рубеж» и
        снимает мандат с безусловного `@skip` или с раннего `return`,
        которые задача, наоборот, ужесточает.
        """
        missing = [needle for needle in
                   ("без причин", "безусловн", "существующ", "return")
                   if not any(needle in chunk for chunk in self.chunks)]

        self.assertEqual(
            [], missing,
            "docs/operator-gates.md обязан назвать случаи, где мандат "
            "по-прежнему нужен (AC-8); не названы: " + ", ".join(missing))
        self.assertTrue(
            self._paragraph_with("return", "мандат"),
            "ранний return под условием обязан быть назван там же, где "
            "речь о мандате ослабления тестов (AC-8)")


if __name__ == "__main__":
    unittest.main()
