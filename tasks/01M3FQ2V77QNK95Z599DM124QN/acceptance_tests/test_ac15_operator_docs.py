"""AC-15 (tasks/01M3FQ2V77QNK95Z599DM124QN/SPEC.md): `docs/operator-session.md`
несёт пункт о том, что ручная сверка удалённых и ослабленных тестов на
гейте мержа уходит в пульт, а `docs/operator-gates.md` — как Оператор
выдаёт мандат командой `answer` со строкой-префиксом
`Ослабление тестов разрешено:`.

Оба файла — код рабочей копии (зона задачи), не артефакт задачи: читаются
с диска обычным способом, как это делают планки прошлых задач о
документации.

Красен до реализации: ни один из двух файлов сегодня не говорит о гейте
неослабления тестов и не знает строки мандата — оба теста падают на
отсутствии текста.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import MANDATE_MARKER, REPO_ROOT  # noqa: E402

SESSION_DOC = REPO_ROOT / "docs" / "operator-session.md"
GATES_DOC = REPO_ROOT / "docs" / "operator-gates.md"


class OperatorSessionDocTest(unittest.TestCase):

    def test_ac15_session_doc_hands_the_manual_check_to_the_pult(self):
        """`docs/operator-session.md` называет ручную сверку удалённых и
        ослабленных тестов на гейте мержа делом пульта, а не сессии
        Оператора.

        Ловит мутацию: код гейта написан, а протокол сессии остался
        прежним — Оператор продолжает сверять удалённые тесты руками на
        каждом мерже, платя за то, что уже автоматизировано, и задача не
        доносит до него, что рубеж появился.
        """
        self.assertTrue(SESSION_DOC.is_file(), f"{SESSION_DOC} не найден")
        text = SESSION_DOC.read_text(encoding="utf-8")
        lowered = text.lower()
        self.assertIn(
            "неослабления", lowered,
            "docs/operator-session.md обязан назвать гейт неослабления "
            "тестов (AC-15)")
        self.assertIn(
            "мерж", lowered,
            "пункт обязан относиться именно к гейту мержа (AC-15)")
        self.assertTrue(
            "удал" in lowered and "ослаблен" in lowered,
            "пункт обязан назвать предмет уходящей в пульт сверки — "
            "удалённые и ослабленные тесты (AC-15)")


class OperatorGatesDocTest(unittest.TestCase):

    def test_ac15_gates_doc_explains_how_to_issue_the_mandate(self):
        """`docs/operator-gates.md` несёт строку-префикс мандата
        дословно и называет команду `answer`, которой он выдаётся.

        Ловит мутацию: документация описывает мандат своими словами, без
        дословного префикса — Оператор пишет «Ослабление тестов
        разрешено» без двоеточия или другой формулировкой, гейт её не
        разбирает, и разрешение молча не срабатывает (ровно тот класс,
        которым уже живёт мандат расширения зон).
        """
        self.assertTrue(GATES_DOC.is_file(), f"{GATES_DOC} не найден")
        text = GATES_DOC.read_text(encoding="utf-8")
        self.assertIn(
            MANDATE_MARKER, text,
            f"docs/operator-gates.md обязан нести префикс «{MANDATE_MARKER}» "
            f"дословно (AC-15)")
        self.assertIn(
            "answer", text,
            "docs/operator-gates.md обязан назвать команду answer, которой "
            "мандат выдаётся (AC-15)")


if __name__ == "__main__":
    unittest.main()
