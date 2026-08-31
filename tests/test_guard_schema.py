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


class SchemaErrorsMessageTest(unittest.TestCase):
    """Тексты `schema_errors` называют требуемую форму и говорят, что
    сделать (tasks/T077/SPEC.md, требования 2-3)."""

    def test_non_integer_version_message_says_what_to_do(self):
        errors = guard.schema_errors("label", {"schema_version": "две"})

        self.assertEqual(
            errors,
            [f"label: schema_version 'две' — не целое число ≥ 1, замени "
             f"значение на целое число (например "
             f"{guard.SUPPORTED_SCHEMA_VERSION})"])

    def test_future_version_message_says_what_to_do(self):
        future = guard.SUPPORTED_SCHEMA_VERSION + 1

        errors = guard.schema_errors("label", {"schema_version": future})

        self.assertEqual(
            errors,
            [f"label: schema_version {future} новее поддерживаемой "
             f"{guard.SUPPORTED_SCHEMA_VERSION} — этот guard не понимает "
             f"формат настолько новой версии; замени значение на "
             f"{guard.SUPPORTED_SCHEMA_VERSION} или ниже, а если тебе "
             f"действительно нужны возможности версии {future} — "
             f"эскалируй, чтобы Оператор обновил guard"])


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


# --------------------------------------------------------------------------
# Тексты сообщений отказа guard.py переписаны, чтобы называть нарушенное
# требование целиком и говорить, что сделать (tasks/T077/SPEC.md).

SPEC_MD = """---
task: T900
type: spec
author_role: analyst
status: draft
schema_version: 2
---

# SPEC: пример

## Контекст
x

## Требования
1. x

## Критерии приёмки
AC-1. критерий

## Не входит
x
"""


class MissingFrontmatterBlockMessageTest(unittest.TestCase):
    def test_message_says_what_to_do(self):
        errors = guard.check_content("label", "Просто текст без шапки.\n")

        self.assertEqual(
            errors,
            ["label: нет frontmatter (--- ... ---) — добавь в начало файла "
             "блок между двумя строками '---' с обязательными полями "
             f"{', '.join(sorted(guard.REQUIRED_META))}"])


class MissingFrontmatterFieldsMessageTest(unittest.TestCase):
    def test_message_says_what_to_do(self):
        text = SPEC_MD.replace("author_role: analyst\n", "")

        errors = guard.check_content("label", text)

        self.assertIn(
            "label: добавь в frontmatter обязательные поля: author_role",
            errors)


class UnknownTypeMessageTest(unittest.TestCase):
    def test_message_says_what_to_do(self):
        text = SPEC_MD.replace("type: spec", "type: bogus")

        errors = guard.check_content("label", text)

        self.assertEqual(
            errors,
            [f"label: неизвестный type 'bogus' — замени поле type в "
             f"frontmatter на одно из: {', '.join(guard.RULES)}"])


class InvalidStatusMessageTest(unittest.TestCase):
    def test_message_says_what_to_do(self):
        text = SPEC_MD.replace("status: draft", "status: bogus")

        errors = guard.check_content("label", text)

        self.assertIn(
            "label: недопустимый status 'bogus' для spec — замени поле "
            "status в frontmatter на одно из валидных значений: "
            f"{', '.join(sorted(guard.RULES['spec']['statuses']))}",
            errors)


class MissingSectionMessageTest(unittest.TestCase):
    def test_message_says_what_to_do(self):
        text = SPEC_MD.replace("## Не входит\nx\n", "")

        errors = guard.check_content("label", text)

        self.assertIn(
            "label: отсутствует обязательная секция '## Не входит' — "
            "добавь в файл заголовок '## Не входит' и содержимое под ним",
            errors)


class SectionWrongLevelMessageTest(unittest.TestCase):
    """Заголовок секции присутствует, но не на уровне H2 (SPEC AC-2,
    фактура T071 — заголовок H3 вместо H2)."""

    def test_message_names_the_wrong_level_and_the_fix(self):
        text = SPEC_MD.replace("## Не входит", "### Не входит")

        errors = guard.check_content("label", text)

        self.assertIn(
            "label: заголовок секции 'Не входит' стоит на уровне H3 "
            "('### Не входит') — обязательные секции требуют уровень H2, "
            "ровно два символа '#': переименуй заголовок в '## Не входит'",
            errors)


class TaskFieldMessageTest(unittest.TestCase):
    def test_message_says_what_to_do(self):
        text = SPEC_MD.replace("task: T900", "task: TASK_ID")

        errors = guard.check_content("label", text)

        self.assertIn(
            "label: поле task не заполнено (осталось TASK_ID) — впиши в "
            "frontmatter реальный номер задачи вместо TASK_ID",
            errors)


class SpecAcMarkupMessagesTest(unittest.TestCase):
    """Сообщения `spec_ac_errors` (SPEC T023) называют форму и действие."""

    def test_not_marked_message_says_what_to_do(self):
        text = SPEC_MD.replace("AC-1. критерий", "1. критерий")
        meta = guard.yamlmini.frontmatter(text)

        errors = guard.spec_ac_errors("label", text, meta)

        self.assertEqual(
            errors,
            ["label: критерии приёмки не размечены AC-n (AC-1., AC-2., "
             "…) — размечай каждый пункт в формате 'AC-<номер>. текст' с "
             "точки в начале строки, либо укажи skip_tests в frontmatter, "
             "если тесты на этот SPEC осознанно пропущены"])

    def test_duplicate_numbers_message_says_what_to_do(self):
        text = SPEC_MD.replace(
            "AC-1. критерий", "AC-1. критерий раз\nAC-1. критерий два")
        meta = guard.yamlmini.frontmatter(text)

        errors = guard.spec_ac_errors("label", text, meta)

        self.assertEqual(
            errors,
            ["label: номера AC-n повторяются: [1, 1] — перенумеруй "
             "критерии так, чтобы каждый номер AC-n встречался ровно один "
             "раз"])

    def test_leftover_plain_item_message_shows_the_required_format(self):
        text = SPEC_MD.replace(
            "AC-1. критерий", "AC-1. критерий\n2. пункт без разметки")
        meta = guard.yamlmini.frontmatter(text)

        errors = guard.spec_ac_errors("label", text, meta)

        self.assertEqual(
            errors,
            ["label: в критериях приёмки остались пункты без "
             "AC-разметки (обычный '1. текст' вместо 'AC-1. текст') — "
             "замени нумерацию таких пунктов на формат 'AC-<номер>. "
             "текст', например 'AC-1.', 'AC-2.'"])


class TraceabilityMessagesTest(unittest.TestCase):
    """Сообщения `traceability_errors_from_content` (SPEC T023, T077 AC-3)
    называют escalate как валидную пометку и говорят, что сделать."""

    SPEC_ONE_AC = "## Критерии приёмки\nAC-1. критерий\n"
    META = {"schema_version": 2}

    def test_missing_test_or_marker_message_mentions_escalate(self):
        errors = guard.traceability_errors_from_content(
            self.SPEC_ONE_AC, self.META, set(), {})

        self.assertEqual(
            errors,
            ["AC-1: нет теста и нет пометки manual/skip/escalate — "
             "добавь тестовый метод 'def test_ac1_...' в "
             "acceptance_tests/, либо пометку "
             "'# AC-1: manual|skip|escalate — причина' в том же каталоге"])

    def test_marker_on_unknown_ac_message_says_what_to_do(self):
        errors = guard.traceability_errors_from_content(
            self.SPEC_ONE_AC, self.META, {1}, {9: ("manual", "причина")})

        self.assertEqual(
            errors,
            ["AC-9: пометка на критерий, которого нет в SPEC — убери эту "
             "пометку либо добавь критерий AC-9 в раздел «Критерии "
             "приёмки» SPEC"])

    def test_marker_without_reason_message_says_what_to_do(self):
        errors = guard.traceability_errors_from_content(
            self.SPEC_ONE_AC, self.META, set(), {1: ("skip", "")})

        self.assertEqual(
            errors,
            ["AC-1: пометка skip без причины — впиши причину после тире "
             "в той же строке, например '# AC-1: skip — <причина>'"])

    def test_test_on_unknown_ac_message_says_what_to_do(self):
        errors = guard.traceability_errors_from_content(
            self.SPEC_ONE_AC, self.META, {9}, {1: ("manual", "ок")})

        self.assertEqual(
            errors,
            ["AC-9: тест на критерий, которого нет в SPEC (SPEC T023, "
             "требование 3 — только из критериев) — переименуй тест на "
             "существующий AC-номер либо добавь критерий AC-9 в раздел "
             "«Критерии приёмки» SPEC"])


class RednessMarkerMessageTest(unittest.TestCase):
    """Сообщение `redness_marker_errors_from_files` называет требование
    «на той же строке после двоеточия» и говорит, что сделать (SPEC T077
    AC-1, фактура T069)."""

    def test_message_names_same_line_after_colon_and_says_what_to_do(self):
        errors = guard.redness_marker_errors_from_files(
            [("test_x.py", '"""Обычный докстринг."""\n')])

        self.assertEqual(
            errors,
            ["test_x.py: нет маркера «Красен до реализации:» или "
             "«Зелёный с рождения:» с непустым объяснением на той же "
             "строке сразу после двоеточия в докстринге модуля — допиши "
             "объяснение сразу после двоеточия на той же строке, "
             "например «Красен до реализации: <причина>» (перенос "
             "объяснения на следующую строку не считается заполненным "
             "маркером)"])


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
