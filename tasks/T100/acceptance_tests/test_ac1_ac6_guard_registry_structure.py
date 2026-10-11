"""Приёмочные тесты T100 — структурные проверки guard'а для секции
«Реестр замечаний» в REVIEW.md (tasks/T100/SPEC.md, AC-1..AC-6).

Чёрный ящик над `scripts.guard.check_content` (по образцу
tasks/T072/acceptance_tests/test_ac1_ac5_evidence_section_guard.py):
фикстуры REVIEW.md строятся текстом, без импорта внутренней реализации —
сама проверка секции «Реестр замечаний» появится только в этой задаче.

Формат записи реестра: SPEC (требование 1) фиксирует id (`R<iteration>-
F<n>`) и перечень обязательных полей (файл/строка-или-пометка, суть,
последствие, ожидаемое решение, статус), но не фиксирует текстовый
синтаксис самой записи — это решение оставлено реализации. Фикстуры
ниже используют markdown-таблицу (колонки id | статус | файл/строка |
суть | последствие | решение) — тот же приём, что уже несут два других
структурированных раздела этого же файла («Соответствие SPEC» в
REVIEW.md, «Покрытие требований» в PLAN.md, оба — templates/*.md):
наименее произвольный выбор для нового раздела того же семейства
артефактов, не собственная выдумка с нуля. Спор реализации с этим
форматом — эскалация («спор с тестом», coding-standards.md), не тихая
правка теста.

Красен до реализации: AC-1, AC-2, AC-3, AC-4, AC-5 (test_ac1_*, test_ac2_*,
test_ac3_*, test_ac4_*, test_ac5_*) падают на сегодняшнем guard.py по
двум причинам сразу — `SUPPORTED_SCHEMA_VERSION` сегодня 2, и
`schema_version: 3` в фикстурах отклоняется как «новее поддерживаемой»
ещё до того, как дело доходит до раздела «Реестр замечаний» (требование
6 этой же задачи); плюс самого раздела и его проверок в guard.py сегодня
нет вовсе — `check_content` не видит ни отсутствующей секции (AC-2), ни
повторяющегося id (AC-3), ни статуса вне пятёрки значений (AC-4), ни
пропущенного обязательного поля (AC-5). Как только разработчик поднимет
`SUPPORTED_SCHEMA_VERSION` до 3 и добавит структурные проверки реестра,
эти тесты позеленеют без изменения фикстур.

Зелёный с рождения: AC-6 — REVIEW.md со `schema_version` ниже 3 (или без
поля вовсе) уже сегодня проходит guard без единого нарушения (ни
`schema_errors`, ни любая другая существующая проверка не знают о
разделе «Реестр замечаний»), и обязан продолжать проходить точно так же
после этой задачи — требования 1-5 применяются только при
`schema_version >= 3` (SPEC, требование 6).
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from scripts import guard  # noqa: E402

TASK = "T100"

# --------------------------------------------------------------------
# Фикстуры REVIEW.md — status: draft (секция «Проверено исполнением»
# обязательна только при approved, review_evidence_errors) — структурные
# проверки реестра не должны зависеть от несвязанного правила.
# --------------------------------------------------------------------

REVIEW_BASE = """---
task: {task}
type: review
author_role: reviewer
status: draft
iteration: 1
schema_version: {schema_version}
---

# REVIEW: реестр замечаний — структурные проверки guard

## Соответствие SPEC

## Замечания

{registry_section}

## Вердикт
draft — ревью не завершено
"""

REVIEW_BASE_NO_SCHEMA = """---
task: {task}
type: review
author_role: reviewer
status: draft
iteration: 1
---

# REVIEW: реестр замечаний — совместимость без schema_version

## Соответствие SPEC

## Замечания

## Вердикт
draft — ревью не завершено
"""

REGISTRY_HEADER = ("## Реестр замечаний\n"
                   "| id | статус | файл/строка | суть | последствие | решение |\n"
                   "|---|---|---|---|---|---|\n")

SECTION_ABSENT = ""

SECTION_ONE_VALID_RECORD = (
    REGISTRY_HEADER +
    "| R1-F1 | open | scripts/guard.py:120 | нет структурной проверки "
    "реестра | approved проходит без валидации замечаний | добавить "
    "проверку раздела в guard.py |\n")

SECTION_DUPLICATE_ID = (
    REGISTRY_HEADER +
    "| R1-F1 | open | scripts/guard.py:120 | нет структурной проверки "
    "реестра | approved проходит без валидации замечаний | добавить "
    "проверку раздела в guard.py |\n"
    "| R1-F1 | fixed | scripts/guard.py:130 | второе замечание | второй "
    "риск | второе решение |\n")

SECTION_INVALID_STATUS = (
    REGISTRY_HEADER +
    "| R1-F1 | in_progress | scripts/guard.py:120 | статус вне пятёрки "
    "значений | approved проходит без валидации статуса | добавить "
    "проверку статуса в guard.py |\n")

SECTION_MISSING_FIELD = (
    REGISTRY_HEADER +
    "| R1-F1 | open | scripts/guard.py:120 |  | approved проходит без "
    "проверки обязательных полей | добавить проверку обязательных "
    "полей в guard.py |\n")


class WellFormedRecordPassesTest(unittest.TestCase):
    """AC-1: REVIEW.md со schema_version: 3 и корректно заполненной
    записью реестра (id, файл/строка, суть, последствие, решение,
    статус) не отклоняется guard'ом."""

    def test_ac1_well_formed_registry_record_passes_guard(self):
        text = REVIEW_BASE.format(task=TASK, schema_version=3,
                                  registry_section=SECTION_ONE_VALID_RECORD)

        errors = guard.check_content("REVIEW.md", text)

        self.assertEqual(
            errors, [],
            f"корректно заполненная запись реестра отклонена guard'ом: "
            f"{errors}")


class MissingSectionRejectedTest(unittest.TestCase):
    """AC-2: guard отклоняет REVIEW.md со schema_version >= 3, где
    секции «Реестр замечаний» нет вовсе."""

    def test_ac2_schema_version_3_without_registry_section_is_rejected(self):
        text = REVIEW_BASE.format(task=TASK, schema_version=3,
                                  registry_section=SECTION_ABSENT)

        errors = guard.check_content("REVIEW.md", text)

        self.assertTrue(
            errors,
            "REVIEW.md со schema_version: 3 без секции «Реестр "
            "замечаний» прошёл guard без единого нарушения")
        self.assertTrue(
            any("Реестр замечаний" in e for e in errors),
            f"ни одно нарушение не называет секцию «Реестр замечаний»: "
            f"{errors}")


class DuplicateIdRejectedTest(unittest.TestCase):
    """AC-3: guard отклоняет REVIEW.md, где id двух записей реестра
    совпадают."""

    def test_ac3_duplicate_registry_ids_are_rejected(self):
        text = REVIEW_BASE.format(task=TASK, schema_version=3,
                                  registry_section=SECTION_DUPLICATE_ID)

        errors = guard.check_content("REVIEW.md", text)

        self.assertTrue(
            errors,
            "REVIEW.md с двумя записями реестра с одинаковым id "
            "прошёл guard без единого нарушения")
        self.assertTrue(
            any("R1-F1" in e for e in errors),
            f"ни одно нарушение не называет повторяющийся id R1-F1: "
            f"{errors}")


class InvalidStatusRejectedTest(unittest.TestCase):
    """AC-4: guard отклоняет запись реестра со статусом вне множества
    {open, fixed, rejected, accepted, needs_work}."""

    def test_ac4_status_outside_the_five_values_is_rejected(self):
        text = REVIEW_BASE.format(task=TASK, schema_version=3,
                                  registry_section=SECTION_INVALID_STATUS)

        errors = guard.check_content("REVIEW.md", text)

        self.assertTrue(
            errors,
            "запись реестра со статусом 'in_progress' (вне пятёрки "
            "допустимых значений) прошла guard без единого нарушения")
        self.assertTrue(
            any("in_progress" in e or "статус" in e.lower()
                for e in errors),
            f"ни одно нарушение не называет недопустимый статус "
            f"'in_progress' записи R1-F1: {errors}")


class MissingRequiredFieldRejectedTest(unittest.TestCase):
    """AC-5: guard отклоняет запись реестра, где отсутствует хотя бы
    одно из обязательных полей требования 1 (здесь — «суть»)."""

    def test_ac5_record_missing_required_field_is_rejected(self):
        text = REVIEW_BASE.format(task=TASK, schema_version=3,
                                  registry_section=SECTION_MISSING_FIELD)

        errors = guard.check_content("REVIEW.md", text)

        self.assertTrue(
            errors,
            "запись реестра с пустым обязательным полем «суть» прошла "
            "guard без единого нарушения")
        self.assertTrue(
            any("R1-F1" in e for e in errors),
            f"ни одно нарушение не называет запись R1-F1 с пропущенным "
            f"обязательным полем: {errors}")


class SchemaVersionBelowThreeUnaffectedTest(unittest.TestCase):
    """AC-6: REVIEW.md без поля schema_version, либо с schema_version
    < 3, проходит guard без применения к нему AC-1..AC-5 — так же, как
    REVIEW.md прежнего формата до этой задачи."""

    def test_ac6_missing_schema_version_field_ignores_registry_requirements(self):
        text = REVIEW_BASE_NO_SCHEMA.format(task=TASK)

        errors = guard.check_content("REVIEW.md", text)

        self.assertEqual(
            errors, [],
            f"REVIEW.md без поля schema_version (нет секции «Реестр "
            f"замечаний») отклонён guard'ом: {errors}")

    def test_ac6_schema_version_2_ignores_registry_requirements(self):
        text = REVIEW_BASE.format(task=TASK, schema_version=2,
                                  registry_section=SECTION_ABSENT)

        errors = guard.check_content("REVIEW.md", text)

        self.assertEqual(
            errors, [],
            f"REVIEW.md со schema_version: 2 (нет секции «Реестр "
            f"замечаний») отклонён guard'ом: {errors}")


if __name__ == "__main__":
    unittest.main()
