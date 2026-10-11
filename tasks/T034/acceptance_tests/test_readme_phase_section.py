"""Приёмочные тесты T034: AC-13 — README, раздел «Текущая фаза».

Источник — tasks/T034/SPEC.md, «Критерии приёмки», требование 10:
раздел «Текущая фаза» README.md отстал от факта на момент задачи —
фаза A закрыта критерием задачи T033 (advance по зафиксированному
состоянию, симметрия с approve — последний пробел контура
hash-фиксации на гейтах из критерия выхода A, docs/roadmap.md §2),
ролей конвейера сейчас четыре (analyst, test_author, developer,
reviewer), а не две, как написано сейчас («роли-агенты — разработчик
и ревьювер»).
"""
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(REPO_ROOT))

PHASE_HEADING = "## Текущая фаза"


class Ac13ReadmePhaseSectionTest(unittest.TestCase):
    """AC-13: раздел «Текущая фаза» называет фазу A закрытой (T033) и
    число ролей конвейера равным четырём."""

    def phase_section(self) -> str:
        lines = (REPO_ROOT / "README.md").read_text(
            encoding="utf-8").splitlines()
        start = next(i for i, line in enumerate(lines)
                    if line.startswith(PHASE_HEADING))
        end = next((i for i in range(start + 1, len(lines))
                    if lines[i].startswith("## ")), len(lines))
        return "\n".join(lines[start:end])

    def test_ac13_phase_a_is_named_closed_with_a_reference_to_t033(self):
        section = self.phase_section()

        self.assertIn("T033", section,
                      "раздел не ссылается на критерий задачи T033")
        self.assertTrue(
            re.search(r"[Фф]аза\s+A\b[^\n]{0,120}\bзакры\w*", section)
            or re.search(r"\bзакры\w*[^\n]{0,120}[Фф]аза\s+A\b", section),
            f"раздел не называет фазу A закрытой:\n{section}")

    def test_ac13_pipeline_role_count_is_four(self):
        section = self.phase_section()

        self.assertTrue(
            re.search(r"\bчетыр(е|ёх)\b", section)
            or re.search(r"\b4\b[^\n]{0,20}рол", section)
            or re.search(r"рол[^\n]{0,20}\b4\b", section),
            f"раздел не называет число ролей конвейера равным четырём:\n"
            f"{section}")
        for role in ("analyst", "test_author", "developer", "reviewer"):
            with self.subTest(роль=role):
                self.assertIn(role, section)


if __name__ == "__main__":
    unittest.main()
