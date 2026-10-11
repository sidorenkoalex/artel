"""Приёмочные тесты T032 — `doctor.check_base_branch` (SPEC.md,
критерии AC-1..AC-3).

AC-1 проверяется не только по статусу `skip`: если бы early-return для
догфуда не появился, `check_base_branch` с `entry["forge"] == "github"`
и доступным `gh` пошёл бы дальше в боевой `subprocess.run` — тест это
ловит через `assert_not_called()`, а не полагается только на итоговый
статус (который мог бы случайно совпасть с skip по другой причине, см.
AC-3 «gh не найден»).

AC-2 — не тавтология и не подгадывание имени теста: тест ищет в
`tests/test_doctor.py` любой `test_*`, чей исходник упоминает и
`check_base_branch`, и `config.DEFAULT_TARGET` (или `DEFAULT_TARGET`),
затем реально ЗАПУСКАЕТ найденные тесты через `unittest` и требует,
чтобы они проходили. Просто наличие строки с нужными словами не
защитало бы от теста-заглушки; проверка прогона — защищает.

AC-3 воспроизводит песочницей то, что было в `check_base_branch` до
изменения (tasks/T032/SPEC.md, «Не входит» — минимум, названный в самом
AC-3): forge не github, gh не найден, сверка ok/warn через замену
`doctor.subprocess.run` (тот же приём, что `tests/test_doctor.py` для
`live_smoke`/`version`, см. tasks/T030/acceptance_tests/test_version.py)
— реальный `gh` в песочнице не нужен и не вызывается.
"""
import importlib
import inspect
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, doctor  # noqa: E402

EXTERNAL_TARGET = "sled"
EXTERNAL_ENTRY = {
    "forge": "github",
    "url": "https://example.invalid/sled",
    "base": "main",
}


class DogfoodSkipTest(unittest.TestCase):
    """AC-1: догфуд-target — честный skip, без боевого обращения к форджу."""

    def test_ac1_dogfood_target_returns_skip_without_calling_gh(self):
        entry = {
            "forge": "github",
            "url": "https://example.invalid/artel",
            "base": "main",
        }

        with mock.patch.object(doctor.shutil, "which",
                               return_value="/usr/bin/gh"), \
             mock.patch.object(doctor.subprocess, "run") as run:
            check = doctor.check_base_branch(config.DEFAULT_TARGET, entry)

        self.assertEqual(
            check.status, "skip",
            f"check_base_branch({config.DEFAULT_TARGET!r}, ...) вернул "
            f"статус {check.status!r}, ожидался skip")
        run.assert_not_called()
        self.assertIn(
            "догфуд", check.detail.lower(),
            f"причина skip не объясняет, что это догфуд, особый случай: "
            f"{check.detail!r}")


class ExternalTargetUnchangedTest(unittest.TestCase):
    """AC-3: поведение для внешнего target не меняется."""

    def test_ac3_non_github_forge_is_skipped(self):
        entry = dict(EXTERNAL_ENTRY, forge="gitlab")

        check = doctor.check_base_branch(EXTERNAL_TARGET, entry)

        self.assertEqual(check.status, "skip")

    def test_ac3_missing_gh_cli_is_skipped(self):
        with mock.patch.object(doctor.shutil, "which", return_value=None):
            check = doctor.check_base_branch(EXTERNAL_TARGET, EXTERNAL_ENTRY)

        self.assertEqual(check.status, "skip")

    def test_ac3_matching_base_branch_is_ok(self):
        def fake_run(args, **kwargs):
            return subprocess.CompletedProcess(args, 0, "main\n", "")

        with mock.patch.object(doctor.shutil, "which",
                               return_value="/usr/bin/gh"), \
             mock.patch.object(doctor.subprocess, "run",
                               side_effect=fake_run):
            check = doctor.check_base_branch(EXTERNAL_TARGET, EXTERNAL_ENTRY)

        self.assertEqual(check.status, "ok")

    def test_ac3_diverging_base_branch_is_warn(self):
        def fake_run(args, **kwargs):
            return subprocess.CompletedProcess(args, 0, "develop\n", "")

        with mock.patch.object(doctor.shutil, "which",
                               return_value="/usr/bin/gh"), \
             mock.patch.object(doctor.subprocess, "run",
                               side_effect=fake_run):
            check = doctor.check_base_branch(EXTERNAL_TARGET, EXTERNAL_ENTRY)

        self.assertEqual(check.status, "warn")


def _tests_covering_dogfood_skip(module) -> list[tuple[type, str]]:
    """Тесты в `module`, чей исходник вызывает `check_base_branch` для
    догфуд-target — минимальная эвристика для AC-2, без завязки на имя
    теста или класса."""
    found = []
    for attr_name in dir(module):
        obj = getattr(module, attr_name)
        if not (isinstance(obj, type) and issubclass(obj, unittest.TestCase)):
            continue
        for method_name in dir(obj):
            if not method_name.startswith("test"):
                continue
            method = getattr(obj, method_name)
            try:
                src = inspect.getsource(method)
            except (OSError, TypeError):
                continue
            if "check_base_branch" in src and "DEFAULT_TARGET" in src:
                found.append((obj, method_name))
    return found


class TestDoctorCoversDogfoodSkipTest(unittest.TestCase):
    """AC-2: `tests/test_doctor.py` содержит и реально проходит тест AC-1."""

    def test_ac2_test_doctor_has_a_passing_test_for_the_dogfood_skip(self):
        import tests.test_doctor as test_doctor_module
        importlib.reload(test_doctor_module)

        matches = _tests_covering_dogfood_skip(test_doctor_module)
        self.assertTrue(
            matches,
            "tests/test_doctor.py не содержит теста, вызывающего "
            "check_base_branch с config.DEFAULT_TARGET (AC-1 не покрыт "
            "тестом в основном тестовом наборе)")

        suite = unittest.TestSuite(cls(name) for cls, name in matches)
        result = unittest.TestResult()
        suite.run(result)

        self.assertEqual(
            len(result.failures) + len(result.errors), 0,
            "найденный в tests/test_doctor.py тест skip-ветки на догфуде "
            f"не проходит: {result.failures + result.errors}")


if __name__ == "__main__":
    unittest.main()
