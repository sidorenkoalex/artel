"""AC-12: абзац «Правки main только командами» в `docs/operator-session.md`.

Красен до реализации: такого абзаца в документе нет — поиск заголовка падает первым же ассертом.
"""
import re
import unittest

from _hooks import REPO_ROOT

DOC = REPO_ROOT / "docs" / "operator-session.md"

HEADING = "Правки main только командами"
# Перечень команд требования 10 SPEC и маркер обхода.
EXPECTED = ("note", "doc-commit", "pin-update", "approve", "merge_gate",
            "ARTEL_PULT_GIT=1")


class OperatorSessionDocTest(unittest.TestCase):

    def test_ac12_doc_names_the_commands_and_the_bypass_marker(self):
        """В `docs/operator-session.md` есть абзац «Правки main только
        командами», и в нём самом (а не где-то ещё в документе) названы
        все четыре команды правки main и переменная обхода.

        Ловит мутацию: автор добавляет заголовок абзаца, но перечисляет в
        нём не все каналы правки main — например забывает `approve` на
        `merge_gate` (единственный путь push'а мержа) — Оператор,
        прочитавший такой абзац, считал бы мерж запрещённым; сверка
        перечня ниже покраснеет на пропущенном имени.
        """
        self.assertTrue(DOC.is_file(), f"нет документа {DOC}")
        text = DOC.read_text(encoding="utf-8")

        start = text.find(HEADING)
        self.assertNotEqual(start, -1,
                            f"в {DOC} нет абзаца «{HEADING}»")

        # Тело абзаца — от заголовка до следующего заголовка markdown
        # любого уровня (или до конца документа).
        rest = text[start + len(HEADING):]
        end = re.search(r"^#{1,6}\s", rest, re.M)
        body = rest[:end.start()] if end else rest

        for token in EXPECTED:
            self.assertIn(token, body,
                          f"в абзаце «{HEADING}» не назван {token!r}")


if __name__ == "__main__":
    unittest.main()
