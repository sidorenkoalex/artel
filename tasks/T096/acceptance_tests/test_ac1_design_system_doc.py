"""Приёмочный тест T096 — AC-1 (tasks/T096/SPEC.md, «Критерии приёмки»).

AC-1: `docs/design-system.md` существует и документирует: палитру
(цветовые токены), типографику, раскладку борда/карточек/панелей,
состояния FSM с их цветовым кодированием, принципы самодостаточности
(без JS-фреймворков, без шага сборки, без внешних ресурсов/CDN).

Красен до реализации: `docs/design-system.md` — новый файл, который
создаёт разработчик; на момент написания теста (test_author, до
tests_writing -> in_dev) в репозитории его ещё нет, поэтому тест падает
на `FileNotFoundError`/`assertTrue` до появления файла, не на опечатке
теста.

Тест не пересказывает документ целиком (это невозможно для unittest над
свободным текстом), а проверяет присутствие маркеров каждой из шести тем,
перечисленных в AC-1 дословно — минимальная, но нетавтологичная проверка:
документ без слова «CDN» или без слов «сборк*» этот тест не пройдёт, то
есть он не зелёный по построению.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

DOC_PATH = REPO_ROOT / "docs" / "design-system.md"


class Ac1DesignSystemDocTest(unittest.TestCase):

    def setUp(self):
        if not DOC_PATH.exists():
            self.fail(f"{DOC_PATH} не существует (AC-1: файл должен "
                     f"существовать и документировать стандарт UI)")
        self.text = DOC_PATH.read_text(encoding="utf-8").lower()

    def test_ac1_documents_palette_color_tokens(self):
        self.assertIn("палитр", self.text,
                     "AC-1 требует раздел про палитру (цветовые токены)")

    def test_ac1_documents_typography(self):
        self.assertIn("типограф", self.text,
                     "AC-1 требует раздел про типографику")

    def test_ac1_documents_board_card_panel_layout(self):
        for keyword in ("борд", "карточ", "панел"):
            self.assertIn(keyword, self.text,
                         f"AC-1 требует раздел про раскладку "
                         f"борда/карточек/панелей (нет «{keyword}»)")

    def test_ac1_documents_fsm_states_color_coding(self):
        self.assertIn("fsm", self.text,
                     "AC-1 требует раздел про состояния FSM")
        self.assertIn("цвет", self.text,
                     "AC-1 требует, чтобы состояния FSM были описаны с "
                     "цветовым кодированием")

    def test_ac1_documents_self_sufficiency_principles(self):
        self.assertIn("самодостаточ", self.text,
                     "AC-1 требует принципы самодостаточности")
        self.assertIn("фреймворк", self.text,
                     "AC-1 требует явный запрет JS-фреймворков")
        self.assertIn("сборк", self.text,
                     "AC-1 требует явный запрет шага сборки")
        self.assertIn("cdn", self.text,
                     "AC-1 требует явный запрет внешних ресурсов/CDN")


if __name__ == "__main__":
    unittest.main()
