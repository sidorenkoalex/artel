"""Юнит-тесты машиночитаемого поля `zones:` (01M1NKVPD2A79PQ6K0JVV1B2Q1,
часть 1 нарезки «Механика зон», требования 1, 3; AC-1, AC-4).

Приёмочные тесты задачи (`tasks/01M1NKVPD2A79PQ6K0JVV1B2Q1/acceptance_tests/
test_ac1_*.py`, `test_ac4_*.py`) уже закрывают AC-1/AC-4 чёрным ящиком через
`guard.check_content` — зафиксированы `tests_writing`, не дублируются здесь.
Этот файл проверяет напрямую `guard.requires_zones`/`guard.spec_zones_errors`
и граничные случаи, которые приёмочная планка не обязана перечислять
поимённо: версия-гейтинг по отдельности (тем же приёмом, что `tests/
test_guard_split_signals.py::RequiresSplitAssessmentTest`/`tests/
test_guard_schema.py::RequiresRegistryTest`), нечисловая/булева версия,
не-`spec` тип, и сам факт подключения проверки к `check_content`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import config  # noqa: E402
from scripts import guard  # noqa: E402


class RequiresZonesTest(unittest.TestCase):
    """Версия-гейтинг (тот же приём, что `requires_split_assessment`/
    `requires_registry`): SPEC ниже версии 4 не подпадает под требование
    поля `zones` — старый беклог (включая версию 3, текущий дефолт
    `templates/SPEC.md` ДО этой задачи) не должен упереться в guard
    задним числом."""

    def test_version_4_requires_the_field(self):
        """Ловит мутацию: граница `>= 4` сдвинута вверх (например `> 4`)
        — версия 4, версия этой самой задачи, перестала бы требовать
        поле."""
        self.assertTrue(guard.requires_zones({"schema_version": 4}))

    def test_version_above_4_requires_the_field(self):
        self.assertTrue(guard.requires_zones({"schema_version": 5}))

    def test_version_3_does_not_require_the_field(self):
        """Ловит мутацию: версия-гейтинг выпал целиком (функция всегда
        возвращает `True`) — SPEC версии 3 (текущий дефолт до этой
        задачи, включая SPEC самой этой задачи) упёрся бы в новое
        требование задним числом."""
        self.assertFalse(guard.requires_zones({"schema_version": 3}))

    def test_missing_field_does_not_require_the_field(self):
        """Ловит мутацию: отсутствие `schema_version` дефолтится не в
        версию 1, а в версию >= 4 — SPEC без поля вовсе ошибочно попал
        бы под новое требование."""
        self.assertFalse(guard.requires_zones({}))

    def test_non_integer_version_does_not_require_the_field(self):
        for version in ("четыре", 4.5, None):
            with self.subTest(версия=version):
                self.assertFalse(
                    guard.requires_zones({"schema_version": version}))

    def test_boolean_version_does_not_require_the_field(self):
        """`bool` — подкласс `int` в Python: `isinstance(True, int)` истинно,
        и без явного исключения `True` (== 1) читался бы как версия 1."""
        self.assertFalse(guard.requires_zones({"schema_version": True}))


class SpecZonesErrorsTest(unittest.TestCase):
    """`spec_zones_errors` — только для `type: spec` версии, требующей
    поле; сообщение называет поле `zones` по имени (AC-1)."""

    def test_non_spec_type_is_never_checked(self):
        """Ловит мутацию: проверка `type` выпала — PLAN/REVIEW версии 4
        без поля `zones` (у которого его в принципе не бывает) начали бы
        отказываться."""
        for atype in ("plan", "review", "test_report"):
            with self.subTest(тип=atype):
                errors = guard.spec_zones_errors(
                    "label", {"type": atype, "schema_version": 4})
                self.assertEqual(errors, [])

    def test_old_version_without_zones_passes(self):
        errors = guard.spec_zones_errors(
            "label", {"type": "spec", "schema_version": 3})
        self.assertEqual(errors, [])

    def test_new_version_without_zones_is_refused_and_names_the_field(self):
        errors = guard.spec_zones_errors(
            "label", {"type": "spec", "schema_version": 4})

        self.assertTrue(errors)
        self.assertIn("zones", " ".join(errors))
        self.assertIn("label", " ".join(errors), "путь в тексте отказа")

    def test_new_version_with_zones_passes(self):
        errors = guard.spec_zones_errors(
            "label", {"type": "spec", "schema_version": 4,
                     "zones": "orchestrator/store.py"})
        self.assertEqual(errors, [])

    def test_empty_string_zones_still_refused(self):
        """Пустая строка — то же самое, что отсутствие поля: пустое
        значение не годится в зону."""
        errors = guard.spec_zones_errors(
            "label", {"type": "spec", "schema_version": 4, "zones": ""})
        self.assertTrue(errors)


class CheckContentWiresZonesTest(unittest.TestCase):
    """Сквозной путь `check_content` — не только сам предикат (ловит
    мутацию: `spec_zones_errors` вызывается, но результат не подмешан
    к общему списку ошибок, тем же классом, что `tests/
    test_guard_split_signals.py::SplitAssessmentErrorsTest`)."""

    SPEC_NEW_VERSION_NO_ZONES = """---
task: T900
type: spec
author_role: analyst
status: ready
schema_version: 4
---

# SPEC: фикстура

## Контекст
Фикстура.

## Требования
1. Первое требование.

## Критерии приёмки
AC-1. Первый критерий.

## Не входит
- Всё остальное.
"""

    def test_check_names_zones_for_a_clean_new_version_spec(self):
        errors = guard.check_content("SPEC.md", self.SPEC_NEW_VERSION_NO_ZONES)

        self.assertTrue(any("zones" in e for e in errors), errors)

    def test_check_passes_once_zones_is_filled(self):
        text = self.SPEC_NEW_VERSION_NO_ZONES.replace(
            "schema_version: 4\n", "schema_version: 4\nzones: tests/\n")

        errors = guard.check_content("SPEC.md", text)

        self.assertEqual(errors, [])


class CommonZonesDeclarationTest(unittest.TestCase):
    """AC-4: `orchestrator/config.py` несёт именованный список общих зон
    ровно с этими четырьмя путями — не больше и не меньше (приёмочный
    тест `test_ac4_*.py` проверяет только надмножество; здесь — точный
    состав, чтобы опечатка в ПЯТОМ, лишнем пути не проскочила молча)."""

    def test_common_zones_is_exactly_the_four_paths(self):
        self.assertEqual(
            set(config.COMMON_ZONES),
            {"orchestrator/config.py", "docs/codebase-map.md", "tests/",
             "roles.yaml"})


if __name__ == "__main__":
    unittest.main()
