"""Приёмочные тесты T077, AC-3 (tasks/T077/SPEC.md): для каждого
сообщения отказа, порождаемого правилом guard из списка требования 1,
текст называет нарушенное требование целиком, включая неочевидные
детали формы правила, а не только факт нарушения.

Критерий охватывает восемь категорий правил (SPEC, требование 1):
`RULES`-секции и статусы, `schema_version`, обязательные frontmatter-
поля, поле `task`, AC-разметка критериев приёмки, трассируемость
AC↔тест, маркер красноты (см. AC-1 отдельным файлом), секция «Проверено
исполнением» (уже соответствует — образец требования 3, T072). SPEC не
фиксирует буквальный ожидаемый текст для каждой из этих категорий —
изобретать конкретную формулировку значило бы тестировать не критерий,
а собственную догадку о нём (скил test-authoring). Эти тесты берут ДВА
несоответствия, проверяемых по самому коду guard.py (а не придуманных):
сообщение молчит о варианте, который тот же код принимает, или не
показывает форму, которую умеет показывать соседнее сообщение того же
правила. Полноту остальных сообщений (секции/статусы, schema_version,
frontmatter-поля, task) Оператор читает на приёмке по фактуре «мог бы
агент починить нарушение по одному этому тексту, не читая
scripts/guard.py» (SPEC, требование 1).

Красен до реализации: оба теста ниже проверяют сообщение по коду guard.py
как он есть сегодня, и оба падают.
- test_ac3_missing_test_or_marker_message_names_escalate_as_valid_marker
  — `traceability_errors_from_content` пишет «нет теста и нет пометки
  manual/skip», но `guard.AC_MARKER` в том же файле принимает ТРЕТЬЮ
  равноправную пометку — `escalate`; сообщение о ней молчит.
- test_ac3_leftover_plain_item_message_shows_the_required_ac_format —
  сообщение о пункте без AC-разметки не показывает требуемый формат
  (`AC-1.`, `AC-2.`, …), хотя соседнее сообщение той же функции
  `spec_ac_errors` (случай «вовсе не размечено») уже умеет его
  показывать.
"""
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from scripts import guard  # noqa: E402

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


class MissingTestOrMarkerMessageMentionsEscalateTest(unittest.TestCase):
    def test_ac3_missing_test_or_marker_message_names_escalate_as_valid_marker(self):
        meta = guard.yamlmini.frontmatter(SPEC_ONE_AC)

        errors = guard.traceability_errors_from_content(
            SPEC_ONE_AC, meta, set(), {})

        self.assertTrue(errors, "AC без теста и без пометки — ожидалась ошибка")
        joined = " ".join(errors)
        self.assertIn(
            "escalate", joined,
            f"сообщение называет только manual/skip, хотя пометка "
            f"escalate тоже валидна (guard.AC_MARKER): {errors}")


class LeftoverPlainNumberedItemMessageTest(unittest.TestCase):
    def test_ac3_leftover_plain_item_message_shows_the_required_ac_format(self):
        text = SPEC_ONE_AC.replace(
            "AC-1. критерий один",
            "AC-1. критерий один\n2. критерий без разметки")
        meta = guard.yamlmini.frontmatter(text)

        errors = guard.spec_ac_errors("SPEC.md", text, meta)

        self.assertTrue(errors, "пункт без AC-разметки — ожидалась ошибка")
        joined = " ".join(errors)
        self.assertTrue(
            re.search(r"AC-\d", joined),
            f"сообщение не показывает требуемый формат AC-n (например "
            f"«AC-1.»), хотя соседнее сообщение того же правила это "
            f"умеет: {errors}")


if __name__ == "__main__":
    unittest.main()
