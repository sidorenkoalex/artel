"""Тесты версии схемы артефактов (см. tasks/T017/SPEC.md, требование 3).

Смысл поля `schema_version` — детектировать расхождение форматов писателя
и читателя проверкой, а не чужим сбоем позже. Отсюда три проверяемых
утверждения: артефакт без поля валиден как версия 1 (вся история Фазы 0),
артефакт версии выше поддерживаемой отклоняется, шаблоны поле несут.
"""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import yamlmini  # noqa: E402
from scripts import guard  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent

PLAN_MD = """---
task: T017
type: plan
author_role: developer
status: ready
{extra}---

# PLAN: версия схемы

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""


class SchemaVersionTest(unittest.TestCase):
    """Guard и версия формата: своё читаем, чужое из будущего — нет."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "PLAN.md"

    def write(self, extra: str = "") -> Path:
        self.path.write_text(PLAN_MD.format(extra=extra), encoding="utf-8")
        return self.path

    def test_artifact_without_the_field_is_valid(self):
        """История Фазы 0 (T001–T016) не редактируется и остаётся валидной."""
        self.assertEqual(guard.check(self.write()), [])

    def test_supported_version_is_valid(self):
        self.assertEqual(
            guard.check(self.write(
                f"schema_version: {guard.SUPPORTED_SCHEMA_VERSION}\n")), [])

    def test_future_version_is_rejected(self):
        """Критерий приёмки 3: schema_version: 999 guard отклоняет."""
        errors = guard.check(self.write("schema_version: 999\n"))

        self.assertTrue(any("schema_version 999" in e for e in errors), errors)
        self.assertTrue(any(str(guard.SUPPORTED_SCHEMA_VERSION) in e
                            for e in errors), "названа поддерживаемая версия")

    def test_non_integer_versions_are_rejected(self):
        """Версия — целое число: строка, дробь и bool версией не считаются."""
        for raw in ("две", "1.5", "true", "0", "-1"):
            with self.subTest(значение=raw):
                errors = guard.check(self.write(f"schema_version: {raw}\n"))

                self.assertTrue(any("schema_version" in e for e in errors),
                                f"'{raw}' принято за версию: {errors}")

    def test_the_version_does_not_replace_the_other_checks(self):
        """Версия — не пропуск: секции и статус проверяются как прежде."""
        self.path.write_text(
            "---\ntask: T017\ntype: plan\nauthor_role: developer\n"
            "status: ready\nschema_version: 1\n---\n\n# PLAN\n",
            encoding="utf-8")

        errors = guard.check(self.path)

        self.assertTrue(any("Влияние на систему" in e for e in errors), errors)


class TemplatesCarryTheVersionTest(unittest.TestCase):
    """Требование 3: поле есть в каждом шаблоне, и оно — текущая версия."""

    def test_every_template_declares_the_current_version(self):
        for name in ("SPEC.md", "PLAN.md", "REVIEW.md", "TEST_REPORT.md"):
            with self.subTest(шаблон=name):
                path = REPO_ROOT / "templates" / name

                meta = yamlmini.frontmatter(path.read_text(encoding="utf-8"))

                self.assertEqual(meta.get("schema_version"),
                                 guard.SUPPORTED_SCHEMA_VERSION)


REVIEW_MD = """---
task: T072
type: review
author_role: reviewer
status: {status}
iteration: 1
schema_version: 2
---

# REVIEW: секция «Проверено исполнением»

## Соответствие SPEC
| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | |

## Замечания

## Вердикт
{status}
{section}"""


class ReviewEvidenceSectionTest(unittest.TestCase):
    """Секция «Проверено исполнением» при status: approved (tasks/T072/SPEC.md,
    требования 1, 2, 4)."""

    def test_approved_with_filled_section_passes(self):
        text = REVIEW_MD.format(
            status="approved",
            section="\n## Проверено исполнением\n"
                    "`python3 -m unittest discover -s tests` — зелёный.\n")

        self.assertEqual(guard.check_content("REVIEW.md", text), [])

    def test_approved_without_section_is_rejected(self):
        text = REVIEW_MD.format(status="approved", section="")

        errors = guard.check_content("REVIEW.md", text)

        self.assertTrue(any("Проверено исполнением" in e for e in errors), errors)

    def test_approved_with_empty_section_is_rejected(self):
        text = REVIEW_MD.format(status="approved",
                                 section="\n## Проверено исполнением\n")

        errors = guard.check_content("REVIEW.md", text)

        self.assertTrue(any("Проверено исполнением" in e for e in errors), errors)

    def test_missing_and_empty_messages_differ(self):
        missing = guard.check_content(
            "REVIEW.md", REVIEW_MD.format(status="approved", section=""))
        empty = guard.check_content(
            "REVIEW.md", REVIEW_MD.format(status="approved",
                                          section="\n## Проверено исполнением\n"))

        self.assertNotEqual(missing, empty)

    def test_non_approved_statuses_do_not_require_the_section(self):
        for status in guard.RULES["review"]["statuses"] - {"approved"}:
            with self.subTest(status=status):
                text = REVIEW_MD.format(status=status, section="")

                self.assertEqual(guard.check_content("REVIEW.md", text), [])


class UnreadableArtifactTest(unittest.TestCase):
    """Guard зовётся из FSM: нечитаемый файл — нарушение, а не исключение."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def test_undecodable_file_is_a_violation(self):
        path = self.dir / "PLAN.md"
        path.write_bytes(b"---\ntask: T\xff17\n---\n")

        errors = guard.check(path)

        self.assertEqual(len(errors), 1)
        self.assertIn("не прочитан", errors[0])

    def test_directory_in_place_of_a_file_is_a_violation(self):
        path = self.dir / "PLAN.md"
        path.mkdir()

        self.assertTrue(any("не прочитан" in e for e in guard.check(path)))


if __name__ == "__main__":
    unittest.main()
