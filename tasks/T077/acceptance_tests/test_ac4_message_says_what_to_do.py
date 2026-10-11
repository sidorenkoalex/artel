"""Приёмочные тесты T077, AC-4 (tasks/T077/SPEC.md): для каждого
сообщения из AC-3 текст говорит, что нужно сделать для исправления, а
не только что не так.

Тот же охват и то же ограничение, что и AC-3 (см. docstring
test_ac3_full_requirement_named.py) — SPEC не фиксирует буквальную
формулировку действия для каждой из восьми категорий. Эти тесты берут
два сообщения, которые сегодня — чистая констатация факта, без единого
глагола действия, и проверяют, что после правки такой глагол появится
(по образцу `review_evidence_errors`: «добавь секцию…», «впиши, какие
команды…» — SPEC требование 3, T072). Остальные категории — Оператор
на приёмке, той же фактурой, что и AC-3.

Красен до реализации: оба сообщения сегодня — «пометка {kind} без
причины» и «frontmatter без полей: …» — не содержат ни одного слова из
`ACTION_VERBS` ниже.
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from scripts import guard  # noqa: E402

# Глаголы повелительного наклонения — по образцу действующего сообщения
# `review_evidence_errors` (SPEC T072, требование 3, образец для этой
# задачи): «добавь секцию…», «впиши, какие команды…».
ACTION_VERBS = ("добавь", "впиши", "укажи", "напиши", "исправь", "замени",
                "используй", "переименуй", "убери")

SPEC_ONE_AC = """---
task: T999
type: spec
author_role: analyst
status: draft
schema_version: 2
---

# SPEC: t

## Контекст
x

## Требования
1. x

## Критерии приёмки
AC-1. критерий один

## Не входит
x
"""


class MarkerWithoutReasonMessageTest(unittest.TestCase):
    def test_ac4_marker_without_reason_message_says_to_add_a_reason(self):
        # `markers` собран напрямую как словарь, не через `scan_ac_content`
        # на тексте похожего вида: этот файл сам лежит под
        # tasks/T077/acceptance_tests/, а `scan_ac_content` разбирает
        # разметку `guard.AC_MARKER` текстом по любому *.py в этой
        # директории — включая эту (там же, где guard проверяет саму
        # задачу T077) — так что литеральный образец такого вида в
        # исходнике завёл бы фантомную пометку для собственной задачи.
        meta = guard.yamlmini.frontmatter(SPEC_ONE_AC)
        markers = {1: ("skip", "")}

        errors = guard.traceability_errors_from_content(
            SPEC_ONE_AC, meta, set(), markers)

        self.assertTrue(errors, "пометка без причины — ожидалась ошибка")
        reason_errors = [e for e in errors if "без причины" in e]
        self.assertTrue(reason_errors, errors)
        joined = " ".join(reason_errors).lower()
        self.assertTrue(
            any(v in joined for v in ACTION_VERBS),
            f"сообщение не говорит, что сделать (нет глагола действия): "
            f"{reason_errors}")


class MissingFrontmatterFieldsMessageTest(unittest.TestCase):
    def test_ac4_missing_frontmatter_fields_message_says_to_add_them(self):
        text = SPEC_ONE_AC.replace("author_role: analyst\n", "")

        errors = guard.check_content("SPEC.md", text)

        frontmatter_errors = [e for e in errors if "frontmatter" in e]
        self.assertTrue(
            frontmatter_errors,
            f"отсутствующее поле frontmatter не отмечено нарушением: {errors}")
        joined = " ".join(frontmatter_errors).lower()
        self.assertTrue(
            any(v in joined for v in ACTION_VERBS),
            f"сообщение не говорит, что сделать (нет глагола действия): "
            f"{frontmatter_errors}")


if __name__ == "__main__":
    unittest.main()
