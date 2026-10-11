"""Приёмочный тест T096 — AC-4 (tasks/T096/SPEC.md, «Критерии приёмки»).

AC-4: `skills/ui-standards.md` создан (новый файл) и содержит: указание
читать `docs/design-system.md`, правила самодостаточности (запрет CDN,
запрет шага сборки, запрет демонов на этапе 1), явный чек «страница
открывается напрямую как file:// без сети».

Красен до реализации: `skills/ui-standards.md` — новый файл, который
создаёт разработчик; на момент написания теста его нет — падает на
отсутствии файла, не на опечатке.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

SKILL_PATH = REPO_ROOT / "skills" / "ui-standards.md"


class Ac4UiStandardsSkillTest(unittest.TestCase):

    def setUp(self):
        if not SKILL_PATH.exists():
            self.fail(f"{SKILL_PATH} не существует (AC-4: новый скил "
                     f"должен быть создан)")
        self.text = SKILL_PATH.read_text(encoding="utf-8")
        self.text_lower = self.text.lower()

    def test_ac4_instructs_reading_design_system_doc(self):
        self.assertIn("docs/design-system.md", self.text,
                     "AC-4 требует указание читать docs/design-system.md")

    def test_ac4_forbids_cdn(self):
        self.assertIn("cdn", self.text_lower,
                     "AC-4 требует явный запрет CDN")

    def test_ac4_forbids_build_step(self):
        self.assertIn("сборк", self.text_lower,
                     "AC-4 требует явный запрет шага сборки")

    def test_ac4_forbids_daemons_at_stage_1(self):
        self.assertIn("демон", self.text_lower,
                     "AC-4 требует явный запрет демонов на этапе 1")

    def test_ac4_has_file_url_no_network_check(self):
        self.assertIn("file://", self.text,
                     "AC-4 требует явный чек «страница открывается "
                     "напрямую как file:// без сети»")
        self.assertIn("без сети", self.text_lower,
                     "AC-4 требует, чтобы чек упоминал работу без сети")


if __name__ == "__main__":
    unittest.main()
