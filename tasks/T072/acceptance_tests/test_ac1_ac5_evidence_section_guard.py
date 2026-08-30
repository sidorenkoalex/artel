"""Приёмочные тесты T072 — секция «Проверено исполнением» в REVIEW.md
(tasks/T072/SPEC.md, AC-1..AC-5).

Чёрный ящик над `scripts.guard.check_content`: фикстуры REVIEW.md строятся
текстом (по образцу tasks/T046/acceptance_tests/test_predlozheniya_
sisteme.py), без импорта/мока внутренней реализации проверки — сама
проверка «есть ли непустая секция при approved» появится только в этой
задаче, guard.py её сегодня не несёт.

Красен до реализации: AC-2, AC-3, AC-4 (test_ac2_*, test_ac3_*, test_ac4_*)
падают на текущем guard.py, потому что он ещё не знает о секции «Проверено
исполнением» — approved REVIEW.md без секции или с пустой секцией сегодня
проходит `check_content` без единого нарушения (никакой другой существующий
класс проверки эту секцию не задевает), а эти тесты требуют отказа. Как
только разработчик добавит проверку (требование 2 SPEC), тесты позеленеют
без изменения фикстур.

Зелёный с рождения: AC-1 (approved + заполненная секция уже проходит guard
сегодня — отсутствие проверки не запрещает лишний, никак не мешающий
раздел) и AC-5 (approved — не единственный статус, для которого guard
пропускает REVIEW.md без этой секции; для draft/changes_requested/escalate
он и сегодня, и после реализации требования 2 не должен требовать секцию —
проверка по SPEC условна на status == approved).
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from scripts import guard  # noqa: E402

# --------------------------------------------------------------------
# Фикстуры REVIEW.md — по образцу REVIEW_BASE из
# tasks/T046/acceptance_tests/test_predlozheniya_sisteme.py, с добавленной
# секцией «Проверено исполнением» на месте плейсхолдера {section}.
# --------------------------------------------------------------------

REVIEW_APPROVED_BASE = """---
task: T072
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 2
---

# REVIEW: тест секции «Проверено исполнением»

## Соответствие SPEC
| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | |

## Замечания

## Вердикт
approved
{section}"""

REVIEW_NONAPPROVED_BASE = """---
task: T072
type: review
author_role: reviewer
status: {status}
iteration: 1
schema_version: 2
---

# REVIEW: тест секции «Проверено исполнением» ({status})

## Соответствие SPEC
| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | major | нужно исправить X |

## Замечания
- major — file.py:10 — суть — предложение

## Вердикт
{status} — исправить X
{section}"""

SECTION_FILLED = """
## Проверено исполнением
Команда `python3 -m unittest discover -s tests` — 214 тестов, все зелёные.
"""

SECTION_EMPTY = """
## Проверено исполнением
"""

SECTION_ABSENT = ""


class ApprovedWithFilledSectionPassesTest(unittest.TestCase):
    """AC-1: approved + непустая секция «Проверено исполнением» — ок."""

    def test_ac1_approved_with_filled_evidence_section_passes(self):
        text = REVIEW_APPROVED_BASE.format(section=SECTION_FILLED)

        errors = guard.check_content("REVIEW.md", text)

        self.assertEqual(errors, [])


class ApprovedWithoutSectionRejectedTest(unittest.TestCase):
    """AC-2: approved без секции «Проверено исполнением» — отказ."""

    def test_ac2_approved_without_evidence_section_is_rejected(self):
        text = REVIEW_APPROVED_BASE.format(section=SECTION_ABSENT)

        errors = guard.check_content("REVIEW.md", text)

        self.assertTrue(
            errors,
            "approved REVIEW.md без секции «Проверено исполнением» прошёл "
            "guard без единого нарушения")
        self.assertTrue(
            any("Проверено исполнением" in e for e in errors),
            f"ни одно нарушение не называет секцию «Проверено исполнением»: "
            f"{errors}")


class ApprovedWithEmptySectionRejectedTest(unittest.TestCase):
    """AC-3: approved с пустой секцией (заголовок есть, содержимого нет)
    — отказ."""

    def test_ac3_approved_with_empty_evidence_section_is_rejected(self):
        text = REVIEW_APPROVED_BASE.format(section=SECTION_EMPTY)

        errors = guard.check_content("REVIEW.md", text)

        self.assertTrue(
            errors,
            "approved REVIEW.md с пустой секцией «Проверено исполнением» "
            "прошёл guard без единого нарушения")
        self.assertTrue(
            any("Проверено исполнением" in e for e in errors),
            f"ни одно нарушение не называет секцию «Проверено исполнением»: "
            f"{errors}")


class RejectionMessageNamesWhatIsMissingTest(unittest.TestCase):
    """AC-4: сообщение отказа в случаях AC-2 и AC-3 называет, что именно
    отсутствует (секция целиком или её содержимое), и что должно быть
    внутри секции."""

    # Слова из требования 1 SPEC («какие команды/тесты ревьювер реально
    # запускал и что они показали») — сообщение обязано пояснять содержимое
    # секции этими или близкими по смыслу словами, не абстрактным «неверно».
    CONTENT_HINT_KEYWORDS = ("команд", "тест", "запуск", "показал", "проверк",
                              "исполнен")

    def test_ac4_error_message_distinguishes_missing_section_from_empty_content(self):
        missing_errors = guard.check_content(
            "REVIEW.md", REVIEW_APPROVED_BASE.format(section=SECTION_ABSENT))
        empty_errors = guard.check_content(
            "REVIEW.md", REVIEW_APPROVED_BASE.format(section=SECTION_EMPTY))

        self.assertTrue(
            missing_errors,
            "AC-2 (секция отсутствует) не отклонён guard'ом — нечего "
            "сверять для AC-4")
        self.assertTrue(
            empty_errors,
            "AC-3 (секция пустая) не отклонён guard'ом — нечего сверять "
            "для AC-4")

        missing_text = " ".join(missing_errors)
        empty_text = " ".join(empty_errors)

        self.assertNotEqual(
            missing_text, empty_text,
            "сообщение для «секции нет вовсе» дословно совпадает с "
            "сообщением для «секция пустая» — AC-4 требует называть, что "
            "именно отсутствует (секция или содержимое), а не выдавать "
            "одну и ту же общую фразу на оба случая")

        self.assertTrue(
            any(kw in missing_text.lower() for kw in self.CONTENT_HINT_KEYWORDS),
            f"сообщение при отсутствующей секции не поясняет, что должно "
            f"быть внутри неё: {missing_text}")
        self.assertTrue(
            any(kw in empty_text.lower() for kw in self.CONTENT_HINT_KEYWORDS),
            f"сообщение при пустой секции не поясняет, что должно быть "
            f"внутри неё: {empty_text}")


class NonApprovedStatusPassesWithoutSectionTest(unittest.TestCase):
    """AC-5: статус, отличный от approved, — секция не обязательна.

    Статусы берутся из `guard.RULES["review"]["statuses"]` за вычетом
    approved (draft, changes_requested, escalate на сегодняшний день),
    а не литеральным списком — тест не должен рассыпаться, если Оператор
    добавит/переименует статус ревью (тот же принцип, что «предпосылки о
    значениях конфигурации» в скиле test-authoring)."""

    def test_ac5_non_approved_statuses_pass_without_evidence_section(self):
        non_approved = guard.RULES["review"]["statuses"] - {"approved"}
        self.assertTrue(non_approved, "в RULES['review']['statuses'] нет "
                         "статусов, кроме approved, — проверять нечего")

        for status in sorted(non_approved):
            with self.subTest(status=status):
                text = REVIEW_NONAPPROVED_BASE.format(
                    status=status, section=SECTION_ABSENT)

                errors = guard.check_content("REVIEW.md", text)

                self.assertEqual(
                    errors, [],
                    f"REVIEW.md со status: {status} без секции «Проверено "
                    f"исполнением» отклонён guard'ом: {errors}")


if __name__ == "__main__":
    unittest.main()
