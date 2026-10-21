"""Запрет плагинов повторов в прогоне компонента по отчёту и его признак в
ключе итога (SPEC 01M5FRYVP4NF81VT00FYPHPWJH, требования 1-2; ADR-0026,
«Решение» п. 4). Профили строятся прямо `project_profile.Profile`, argv
собирается без запуска процесса.
"""
import dataclasses
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from orchestrator import acceptance, project_profile

BAN = ["-p", "no:rerunfailures", "-p", "no:flaky"]
HEAD = ["python3", "-m", "pytest", "-q"]


def own_profile(**extra):
    fields = dict(command=tuple(HEAD), long_lived_dir="be/tests",
                  long_lived_name="test_<id>_<name>.py",
                  weakening_scope=("be/tests/**/*.py",),
                  mutation_claim_scope=("be/tests/test_*.py",),
                  report="junit-xml", runner="pytest-own", workdir="be",
                  component="default", project="p")
    fields.update(extra)
    return project_profile.Profile(**fields)


def component_profile(**extra):
    fields = dict(component="web", from_components=True,
                  plank_layout="be/tests/.plank/<id>")
    fields.update(extra)
    return own_profile(**fields)


def artel_profile():
    return project_profile.Profile(
        command=("python3", "-m", "pytest"), long_lived_dir="tests",
        long_lived_name="test_<id>_<name>.py",
        weakening_scope=("tests/**/*.py",),
        mutation_claim_scope=("tests/test_*.py",), report="junit-xml",
        component="default", project="artel")


class ReportArgvRerunBanTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tree = Path(tmp.name).resolve()
        self.report = self.tree / "r.xml"

    def argv(self, profile, cwd, subset=None):
        argv, refusal = acceptance._report_argv(profile, self.tree, cwd,
                                                subset, self.report)
        self.assertEqual(refusal, "")
        return argv

    def test_component_ban_right_after_command(self):
        """Компонент с `report` и командой pytest: `-p no:rerunfailures -p no:flaky` сразу за `command` — и в полном наборе, и в подмножестве.

        Ловит мутацию: флаги не добавлены (повтор упавшего теста снова
        выглядит зелёным в junit-xml); флаги дописаны после целей,
        `-p no:cacheprovider` или `report_args`; флаги добавлены только
        полному набору, а прогон подмножества остался без них.
        """
        rep = ["--junitxml", str(self.report)]
        cwd = self.tree / "be"
        self.assertEqual(self.argv(component_profile(), cwd),
                         [*HEAD, *BAN, "tests", "--ignore=tests/.plank",
                          "-p", "no:cacheprovider", *rep])
        self.assertEqual(self.argv(component_profile(), cwd,
                                   ["be/tests/test_a.py"]),
                         [*HEAD, *BAN, "tests/test_a.py",
                          "-p", "no:cacheprovider", *rep])

    def test_no_ban_outside_components(self):
        """Артель и `test_profile` с `runner: pytest-own` и `report` — argv без флагов запрета, побайтно прежний.

        Ловит мутацию: условие запрета — только `report` без
        `from_components` (флаги получают `test_profile` и артель, их
        прогон меняется вне границы задачи).
        """
        rep = ["--junitxml", str(self.report)]
        self.assertEqual(self.argv(artel_profile(), self.tree),
                         ["python3", "-m", "pytest", *rep])
        self.assertEqual(self.argv(own_profile(), self.tree / "be"),
                         [*HEAD, "tests", "--ignore=tests/.artel-plank",
                          "-p", "no:cacheprovider", *rep])


def digest(data: dict) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True,
                                     ensure_ascii=False).encode()).hexdigest()


def old_data(tree: str, profile) -> dict:
    """Прежний состав данных ключа `_report_suite_result_key` (база, без
    файлов блокировки)."""
    return {"tree": tree, "base": True, "locks": None,
            "tools": dict(profile.tools or {}),
            "command": list(profile.command), "report": profile.report,
            "report_args": list(project_profile.report_args_of(profile)),
            "select": list(profile.select),
            "component": profile.component or "default",
            "runner": profile.runner, "workdir": profile.workdir,
            "env": dict(profile.env)}


class SuiteResultKeyRerunBanTest(unittest.TestCase):

    def test_component_key_carries_no_rerun_plugins(self):
        """Ключ итога компонента с `report` — sha256 прежнего состава плюс `"no_rerun_plugins": true`; у `test_profile` и у того же профиля без `from_components` — прежний.

        Ловит мутацию: поле не добавлено (итог компонента, посчитанный до
        запрета повторов, переиспользуется из кэша); поле добавлено и
        профилю вне записи компонентов (его кэш итога сбрасывается).
        """
        tree = "1" * 40
        comp = component_profile()
        self.assertEqual(acceptance._report_suite_result_key(tree, comp, True),
                         digest(dict(old_data(tree, comp),
                                     no_rerun_plugins=True)))
        plain = dataclasses.replace(comp, from_components=False)
        self.assertEqual(acceptance._report_suite_result_key(tree, plain,
                                                             True),
                         digest(old_data(tree, plain)))
        self.assertEqual(acceptance._report_suite_result_key(
            tree, own_profile(), True), digest(old_data(tree, own_profile())))


if __name__ == "__main__":
    unittest.main()
