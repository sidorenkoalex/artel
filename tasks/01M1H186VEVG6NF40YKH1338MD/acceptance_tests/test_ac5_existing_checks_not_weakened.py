"""AC-5 (tasks/01M1H186VEVG6NF40YKH1338MD/SPEC.md): существующий набор
тестов (tests/) остаётся зелёным, ни одна существующая проверка
scripts/guard.py, orchestrator/fsm.py или CI-job id-format-greplint не
ослаблена.

Критерий несёт два самостоятельных утверждения (тот же приём, что
tasks/T064/acceptance_tests/test_ac4_existing_checks_not_weakened.py):

1. «существующий набор тестов (tests/) остаётся зелёным» — см. маркер
   skip ниже.
2. «ни одна существующая проверка guard.py/fsm.py/CI-job
   id-format-greplint не ослаблена» — тесты этого файла: регрессионный
   прогон уже существующих (не изобретённых этой задачей) публичных
   функций scripts/guard.py на заведомо нарушающих структуру входных
   данных, плюс структурная проверка, что job id-format-greplint не
   удалён из .github/workflows/ci.yml (SPEC требование 2 — «job
   id-format-greplint остаётся»).

Зелёный с рождения: эти функции и этот job уже существуют и уже
проходят/присутствуют на main — тест кодирует их СЕГОДНЯШНЕЕ поведение
как нижнюю границу, которую эта задача обязана сохранить. Красный
прогон здесь в любой момент (до или после реализации) означал бы
ослабление существующей проверки, а не прогресс задачи.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts import guard  # noqa: E402

# AC-5: skip — половина критерия «существующий набор тестов (tests/)
# остаётся зелёным» уже исполняется штатным CI-гейтом
# (.github/workflows/ci.yml, джоб python, `unittest discover -s tests
# -v`) на каждый коммит ветки задачи и требуется merge_gate
# (orchestrator/fsm.py, cmd_approve при state == "merge_gate") — тот же
# довод, что и
# tasks/T064/acceptance_tests/test_ac4_existing_checks_not_weakened.py.
# Дублирующий здесь subprocess-прогон всего набора ловил бы окружение
# машины, а не дефект задачи, и не даёт новой гарантии сверх штатного
# гейта. Вторая половина критерия («ни одна проверка не ослаблена»)
# покрыта тестами ниже.


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

NO_REDNESS_MARKER_SOURCE = '''import unittest


class AcceptanceTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        self.assertTrue(True)
'''


class ExistingChecksNotWeakenedTest(unittest.TestCase):

    def test_ac5_unsupported_schema_version_is_still_rejected(self):
        """Существующий отказ по неподдерживаемой версии схемы жив.
        
        Ловит мутацию: новая проверка встроена ранним return и
        перехватывает поток до старой валидации — старый отказ исчез бы.
        """
        errors = guard.schema_errors(
            "label", {"schema_version": guard.SUPPORTED_SCHEMA_VERSION + 1})

        self.assertTrue(
            errors,
            "schema_errors() обязан продолжать отклонять schema_version "
            "новее поддерживаемой (SPEC AC-5, принцип целостности)")

    def test_ac5_missing_required_section_is_still_rejected(self):
        """Существующий отказ по отсутствию обязательной секции жив.
        
        Ловит мутацию: тот же ранний return новой проверки — файл без
        секции, но без образца, прошёл бы мимо guard.
        """
        errors = guard.check_content("ветка:tasks/T999/SPEC.md",
                                     SPEC_MISSING_SECTION)

        self.assertTrue(
            any("Не входит" in e for e in errors),
            f"check_content() обязан продолжать требовать секцию "
            f"'## Не входит' у SPEC (SPEC AC-5): {errors}")

    def test_ac5_invalid_status_is_still_rejected(self):
        """Существующий отказ по недопустимому статусу артефакта жив.
        
        Ловит мутацию: перестроение цепочки проверок потеряло валидацию
        статуса — недопустимый статус прошёл бы.
        """
        errors = guard.check_content("ветка:tasks/T999/SPEC.md",
                                     SPEC_BAD_STATUS)

        self.assertTrue(
            any("недопустимый status" in e for e in errors),
            f"check_content() обязан продолжать отклонять недопустимый "
            f"status (SPEC AC-5): {errors}")

    def test_ac5_ac_traceability_still_flags_missing_ac(self):
        """Трассируемость AC по-прежнему ловит непокрытый критерий.
        
        Ловит мутацию: новая проверка возвращает успех до прохода
        трассируемости — непокрытый AC перестал бы блокировать выход.
        """
        meta = guard.yamlmini.frontmatter(SPEC_V2) or {}
        tested, markers = guard.scan_ac_content([AC_TEST_MISSING_AC2])

        errors = guard.traceability_errors_from_content(
            SPEC_V2, meta, tested, markers)

        self.assertTrue(
            any("AC-2" in e for e in errors),
            f"traceability_errors_from_content() обязан продолжать "
            f"называть AC без теста и без пометки (SPEC AC-5, T023): "
            f"{errors}")

    def test_ac5_redness_marker_check_still_flags_missing_marker(self):
        """Проверка маркера красноты по-прежнему ловит его отсутствие.
        
        Ловит мутацию: объединение проходов потеряло проверку маркера —
        файл без маркера прошёл бы.
        """
        errors = guard.redness_marker_errors_from_files(
            [("ветка:tasks/T999/acceptance_tests/test_ac.py",
              NO_REDNESS_MARKER_SOURCE)])

        self.assertTrue(
            any("Красен до реализации" in e for e in errors),
            f"redness_marker_errors_from_files() обязан продолжать "
            f"называть файл без маркера красноты (SPEC AC-5, T064): "
            f"{errors}")

    def test_ac5_ci_job_id_format_greplint_still_present(self):
        """CI-джоб проверки формата идентификатора остался в ci.yml после
        выноса образцов в общий источник.
        
        Ловит мутацию: вынос образцов удалил или переименовал джоб —
        grep по имени джоба в ci.yml упадёт.
        """
        ci_yml = (Path(__file__).resolve().parents[3] /
                  ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8")

        self.assertIn(
            "id-format-greplint:", ci_yml,
            "job id-format-greplint обязан оставаться в "
            ".github/workflows/ci.yml — эта задача меняет только "
            "источник образцов, не удаляет job (SPEC требование 2, "
            "AC-5)")
