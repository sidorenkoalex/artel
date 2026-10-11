"""AC-17 (tasks/01M1GCN1FPSC1A6WK9WD1Q1V8X/SPEC.md): скилы ролей developer
(`skills/coding-standards.md`, roles.yaml) и reviewer
(`skills/review-checklist.md`, roles.yaml) дополнены протоколом описи —
части читать по порядку, включённое в опись целиком не перечитывать
инструментом чтения, исключённое по AC-2 читать адресно по ссылке из
описи.

Мандат на правку `skills/` под эту задачу — ТЗ, требование 7
(«Мандат на правку skills/ под эту задачу предоставлен ТЗ»), поэтому
проверка содержимого этих файлов здесь законна несмотря на то, что
`skills/` — обычно защищённый путь.

Красен до реализации: ни один из трёх пунктов протокола сегодня не
упомянут ни в одном из двух файлов.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

DEVELOPER_SKILL = REPO_ROOT / "skills" / "coding-standards.md"
REVIEWER_SKILL = REPO_ROOT / "skills" / "review-checklist.md"


def _has_all(text: str, *fragments: str) -> list[str]:
    return [f for f in fragments if f not in text]


class Ac17SkillsProtocolTest(unittest.TestCase):

    def test_ac17_developer_skill_documents_the_manifest_protocol(self):
        text = DEVELOPER_SKILL.read_text(encoding="utf-8")

        missing = _has_all(text, "по порядку", "опис", "адресно")
        self.assertEqual(
            missing, [],
            f"skills/coding-standards.md не несёт протокол описи "
            f"(части по порядку / не перечитывать включённое / читать "
            f"исключённое адресно) — отсутствуют фрагменты: {missing}")

    def test_ac17_reviewer_skill_documents_the_manifest_protocol(self):
        text = REVIEWER_SKILL.read_text(encoding="utf-8")

        missing = _has_all(text, "по порядку", "опис", "адресно")
        self.assertEqual(
            missing, [],
            f"skills/review-checklist.md не несёт протокол описи — "
            f"отсутствуют фрагменты: {missing}")


if __name__ == "__main__":
    unittest.main()
