"""AC-4 (tasks/T064/SPEC.md): существующий набор тестов остаётся
зелёным, ни одна существующая проверка `scripts/guard.py` не ослаблена.

Критерий несёт два самостоятельных утверждения:

1. «существующий набор тестов остаётся зелёным» — см. маркер `skip`
   ниже.
2. «ни одна существующая проверка guard.py не ослаблена» — тесты этого
   файла: прямой регрессионный прогон уже существующих (не изобретённых
   этой задачей) публичных функций `scripts/guard.py`
   (`schema_errors`, `check_content`, `traceability_errors_from_content`
   — тот же набор, что и `tests/test_guard_schema.py`/
   `tests/test_acceptance_tests_flow.py`) на заведомо нарушающих
   структуру входных данных: они обязаны продолжать находить нарушение
   и после того, как разработчик добавит новую проверку маркера
   красноты (SPEC требования 1-2, 5 — «принцип целостности», ADR-0002).

Зелёный с рождения: эти функции уже существуют и уже проходят на
main — тест кодирует их СЕГОДНЯШНЕЕ поведение как нижнюю границу,
которую задача T064 обязана сохранить. Красный прогон здесь в любой
момент (до или после реализации T064) означал бы ослабление
существующей проверки, а не прогресс задачи.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts import guard  # noqa: E402

# AC-4: skip — половина критерия «существующий набор тестов (tests/)
# остаётся зелёным» уже исполняется штатным CI-гейтом
# (.github/workflows/ci.yml, джоб python, `unittest discover -s tests
# -v`) на каждый коммит ветки задачи и требуется `merge_gate`
# (orchestrator/fsm.py, cmd_approve при state == "merge_gate") — тот же
# довод, что и tasks/T053/acceptance_tests/test_ac7_full_suite_regression.py
# и tasks/T050/acceptance_tests/test_ac9_full_suite_regression.py.
# Дублирующий здесь subprocess-прогон всего набора ловил бы окружение
# машины, а не дефект задачи, и не даёт новой гарантии сверх штатного
# гейта. Вторая половина критерия («ни одна проверка guard.py не
# ослаблена») покрыта тестами ниже.


SPEC_MISSING_SECTION = """---
task: T999
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: без секции «Не входит»

## Контекст

## Требования

1. ...

## Критерии приёмки

AC-1. Критерий.
"""

SPEC_BAD_STATUS = """---
task: T999
type: spec
author_role: analyst
status: недопустимо
schema_version: 2
---

# SPEC: недопустимый status

## Контекст

## Требования

1. ...

## Критерии приёмки

AC-1. Критерий.

## Не входит
"""

SPEC_V2 = """---
task: T999
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: трассируемость AC

## Контекст

## Требования

1. ...

## Критерии приёмки

AC-1. Первый критерий.
AC-2. Второй критерий.

## Не входит
"""

AC_TEST_MISSING_AC2 = """import unittest


class AcceptanceTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        self.assertTrue(True)
"""


class ExistingGuardChecksNotWeakenedTest(unittest.TestCase):

    def test_ac4_unsupported_schema_version_is_still_rejected(self):
        errors = guard.schema_errors(
            "label", {"schema_version": guard.SUPPORTED_SCHEMA_VERSION + 1})

        self.assertTrue(
            errors,
            "schema_errors() обязан продолжать отклонять schema_version "
            "новее поддерживаемой (SPEC AC-4, принцип целостности)")

    def test_ac4_missing_required_section_is_still_rejected(self):
        errors = guard.check_content("ветка:tasks/T999/SPEC.md",
                                     SPEC_MISSING_SECTION)

        self.assertTrue(
            any("Не входит" in e for e in errors),
            f"check_content() обязан продолжать требовать секцию "
            f"'## Не входит' у SPEC (SPEC AC-4): {errors}")

    def test_ac4_invalid_status_is_still_rejected(self):
        errors = guard.check_content("ветка:tasks/T999/SPEC.md",
                                     SPEC_BAD_STATUS)

        self.assertTrue(
            any("недопустимый status" in e for e in errors),
            f"check_content() обязан продолжать отклонять недопустимый "
            f"status (SPEC AC-4): {errors}")

    def test_ac4_ac_traceability_still_flags_missing_ac(self):
        meta = guard.yamlmini.frontmatter(SPEC_V2) or {}
        tested, markers = guard.scan_ac_content([AC_TEST_MISSING_AC2])

        errors = guard.traceability_errors_from_content(
            SPEC_V2, meta, tested, markers)

        self.assertTrue(
            any("AC-2" in e for e in errors),
            f"traceability_errors_from_content() обязан продолжать "
            f"называть AC без теста и без пометки (SPEC AC-4, T023): "
            f"{errors}")
