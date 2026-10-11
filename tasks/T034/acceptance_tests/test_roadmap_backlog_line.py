"""Приёмочные тесты T034: AC-14 — строка беклога «Подметалка minor».

Источник — tasks/T034/SPEC.md, «Критерии приёмки», требование 11: сама
эта задача закрывает строку беклога P3 «Подметалка minor», и она же
удаляет строку из docs/roadmap.md.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))


class Ac14BacklogLineRemovedTest(unittest.TestCase):
    """AC-14: строки «Подметалка minor» в docs/roadmap.md больше нет."""

    def test_ac14_backlog_line_is_gone(self):
        text = (REPO_ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8")

        self.assertNotIn("Подметалка minor", text)


if __name__ == "__main__":
    unittest.main()
