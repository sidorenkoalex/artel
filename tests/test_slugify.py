"""Тесты для orchestrator.catalog.slugify (см. tasks/T003/SPEC.md)."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator.catalog import slugify  # noqa: E402


class SlugifyTest(unittest.TestCase):
    def test_cyrillic_transliterates_to_latin(self):
        self.assertEqual(slugify("Тест проверки"), "test-proverki")

    def test_latin_unchanged(self):
        self.assertEqual(slugify("Fix CI pipeline"), "fix-ci-pipeline")

    def test_mixed_cyrillic_latin_digits(self):
        self.assertEqual(slugify("API запрос v2"), "api-zapros-v2")

    def test_special_chars_collapse_and_trim(self):
        self.assertEqual(slugify("!!!  ---  "), "task")

    def test_empty_string(self):
        self.assertEqual(slugify(""), "task")

    def test_truncated_to_30(self):
        # 40 «а» → 40 латинских «a» → берём первые 30
        self.assertEqual(slugify("а" * 40), "a" * 30)

    def test_yo_and_capital_yo(self):
        self.assertEqual(slugify("Ёлка ёж"), "yolka-yozh")

    def test_soft_and_hard_signs_dropped(self):
        # ъ и ь исчезают, подъём → podyom, конь → kon
        self.assertEqual(slugify("Подъём коня"), "podyom-konya")

    def test_digraphs(self):
        # щ→sch, ю→yu, я→ya, ж→zh, х→kh, ц→ts, ч→ch, ш→sh
        self.assertEqual(slugify("щука южная"), "schuka-yuzhnaya")
        self.assertEqual(slugify("чашка цвета"), "chashka-tsveta")

    def test_trailing_separators_stripped(self):
        self.assertEqual(slugify("-- hello --"), "hello")


if __name__ == "__main__":
    unittest.main()
