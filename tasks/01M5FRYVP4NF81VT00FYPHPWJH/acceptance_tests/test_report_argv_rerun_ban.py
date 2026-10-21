"""Запрет плагинов повторов в argv прогона по отчёту и признак запрета в ключе итога (AC-1, AC-2, AC-3).

Группа: разовый

Критерии называют закрытые имена `acceptance._report_argv`,
`acceptance._report_suite_result_key` и `acceptance._pytest_command`:
долгоживущий файл `tests/` закрытых имён не касается (правило ADR-0020),
поэтому проверка живёт в планке. Профили строятся прямо
`project_profile.Profile` — без `targets.yaml`, git и сети; argv
собирается без запуска процесса.

Красен до реализации: `_report_argv` сегодня не добавляет `-p no:rerunfailures -p no:flaky` компоненту с `report` (AC-1, AC-2 падают на отсутствии флагов), а данные ключа `_report_suite_result_key` у компонента не несут `no_rerun_plugins` — ключ компонента равен ключу прежнего состава (AC-3); сверки прежних составов артели, `test_profile` и `_pytest_command` зелёные с рождения.
"""
import dataclasses
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from orchestrator import acceptance, project_profile, stack
from orchestrator.advance_gates.acceptance import in_outcome_bounds

BAN = ["-p", "no:rerunfailures", "-p", "no:flaky"]


def artel_profile(**extra):
    """Профиль артели: `pult-pytest`, `report: junit-xml`, не компонент."""
    fields = dict(command=("python3", "-m", "pytest"), long_lived_dir="tests",
                  long_lived_name="test_<id>_<name>.py",
                  weakening_scope=("tests/**/*.py",),
                  mutation_claim_scope=("tests/test_*.py",),
                  report="junit-xml", component="default", project="artel")
    fields.update(extra)
    return project_profile.Profile(**fields)


def own_profile(**extra):
    """Запись `test_profile` с `runner: pytest-own`, `workdir` и `report`."""
    fields = dict(command=("python3", "-m", "pytest", "-q"),
                  long_lived_dir="be/tests",
                  long_lived_name="test_<id>_<name>.py",
                  weakening_scope=("be/tests/**/*.py",),
                  mutation_claim_scope=("be/tests/test_*.py",),
                  report="junit-xml", runner="pytest-own", workdir="be",
                  component="default", project="p")
    fields.update(extra)
    return project_profile.Profile(**fields)


def component_profile(**extra):
    """Компонент записи `components:` с `report` — тот же состав полей, что
    `own_profile`, плюс признак записи компонентов и `plank_layout`."""
    fields = dict(component="web", from_components=True,
                  plank_layout="be/tests/.plank/<id>")
    fields.update(extra)
    return own_profile(**fields)


def has_run(argv, seq) -> bool:
    return any(argv[i:i + len(seq)] == seq for i in range(len(argv)))


class ReportArgvBanTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tree = Path(tmp.name).resolve()
        self.report = self.tree / "r.xml"

    def argv(self, profile, cwd, subset=None, coll=False):
        argv, refusal = acceptance._report_argv(profile, self.tree, cwd,
                                                subset, self.report, coll)
        self.assertEqual(refusal, "", f"предпосылка: отказ подготовки {refusal}")
        return argv

    def test_ac1_component_ban_right_after_command_and_old_argv_elsewhere(self):
        """Компонент с `report` и командой pytest: флаги запрета сразу за `command`; артель, `test_profile` и `_pytest_command` — прежние побайтно.

        Сценарий: компонент `pytest-own` с `workdir` — полный набор (цель
        долгоживущих, `--ignore` выкладки, `-p no:cacheprovider`,
        `report_args`) и подмножество с ключом
        `--continue-on-collection-errors`; компонент с раннером пульта —
        полный набор и подмножество. Ожидаемый argv — прежний состав с
        четырьмя элементами запрета, вставленными сразу за `command`. Затем
        артель, `test_profile` (`pytest-own` и раннер пульта) — argv равен
        копии прежнего состава; `_pytest_command` — прежняя форма.

        Ловит мутацию: флаги дописаны в хвост argv (после `report_args`)
        или после целей/`-p no:cacheprovider`; флаги добавлены только
        полному набору, а прогон подмножества (планка, повтор) остался без
        них; флаги добавлены и артели либо `test_profile` (их argv
        сменился); флаги попали в `_pytest_command`.
        """
        cwd = self.tree / "be"
        rep = ["--junitxml", str(self.report)]
        head = ["python3", "-m", "pytest", "-q"]
        cases = (
            ("компонент pytest-own, полный набор", component_profile(), cwd,
             None, False,
             [*head, *BAN, "tests", "--ignore=tests/.plank",
              "-p", "no:cacheprovider", *rep]),
            ("компонент pytest-own, подмножество", component_profile(), cwd,
             ["be/tests/test_a.py"], True,
             [*head, *BAN, "tests/test_a.py", "-p", "no:cacheprovider",
              acceptance.CONTINUE_ON_COLLECTION_ERRORS, *rep]),
            ("компонент pult-pytest, полный набор",
             component_profile(runner="pult-pytest", workdir="",
                               long_lived_dir="tests", plank_layout=""),
             self.tree, None, False, [*head, *BAN, *rep]),
            ("компонент pult-pytest, подмножество",
             component_profile(runner="pult-pytest", workdir="",
                               long_lived_dir="tests", plank_layout=""),
             self.tree, ["tests/test_b.py"], False,
             [*head, *BAN, "tests/test_b.py", *rep]),
            # Прежний состав артели и `test_profile` (копия до задачи).
            ("артель, полный набор", artel_profile(), self.tree, None, False,
             ["python3", "-m", "pytest", *rep]),
            ("артель, подмножество", artel_profile(), self.tree,
             ["tests/test_a.py"], False,
             ["python3", "-m", "pytest", "tests/test_a.py", *rep]),
            ("test_profile pytest-own, полный набор", own_profile(), cwd,
             None, False,
             [*head, "tests", "--ignore=tests/.artel-plank",
              "-p", "no:cacheprovider", *rep]),
            ("test_profile pytest-own, подмножество", own_profile(), cwd,
             ["be/tests/test_a.py"], True,
             [*head, "tests/test_a.py", "-p", "no:cacheprovider",
              acceptance.CONTINUE_ON_COLLECTION_ERRORS, *rep]),
            ("test_profile pult-pytest", artel_profile(project="p"),
             self.tree, None, False, ["python3", "-m", "pytest", *rep]),
        )
        for name, profile, run_cwd, subset, coll, expected in cases:
            with self.subTest(name):
                self.assertEqual(self.argv(profile, run_cwd, subset, coll),
                                 expected)
        python = stack.pytest_python_executable()
        timeout = f"timeout={stack.PER_TEST_TIMEOUT_SEC}"
        self.assertEqual(
            acceptance._pytest_command("tests/x.py"),
            [python, "-m", "pytest", "tests/x.py", "-p", "no:cacheprovider",
             "-p", "timeout", "-o", timeout])
        self.assertEqual(
            acceptance._pytest_command("t.py", command=["python3", "-m",
                                                        "pytest", "-q"]),
            [python, "-m", "pytest", "-q", "t.py", "-p", "no:cacheprovider",
             "-p", "timeout", "-o", timeout])

    def test_ac2_ban_present_exactly_when_in_outcome_bounds(self):
        """Четыре вида профиля с командой pytest: флаги запрета в argv есть ровно тогда, когда `in_outcome_bounds(profile)` истинно.

        Сценарий: артель, `test_profile` (раннер пульта, `report`),
        `test_profile` с `runner: pytest-own` и `report`, компонент с
        `report`; для каждого — полный набор и подмножество. Наличие
        подряд идущих `-p no:rerunfailures -p no:flaky` сверяется с
        `in_outcome_bounds`; предпосылка — граница истинна только у
        компонента.

        Ловит мутацию: условие запрета — `project_profile.reported`
        без `from_components` (флаги получает `test_profile` с
        `pytest-own` и `report`) либо `from_components` без `report`;
        условие проверяет `runner: pytest-own` и пропускает компонент с
        раннером пульта.
        """
        kinds = (
            ("артель", artel_profile(), self.tree),
            ("test_profile", artel_profile(project="p"), self.tree),
            ("test_profile pytest-own с report", own_profile(),
             self.tree / "be"),
            ("компонент с report", component_profile(), self.tree / "be"),
            ("компонент с report, раннер пульта",
             component_profile(runner="pult-pytest", workdir="",
                               long_lived_dir="tests", plank_layout=""),
             self.tree),
        )
        bounds = {name: in_outcome_bounds(p) for name, p, _ in kinds}
        self.assertEqual([n for n, b in bounds.items() if b],
                         ["компонент с report",
                          "компонент с report, раннер пульта"],
                         "предпосылка: граница исходов")
        for name, profile, cwd in kinds:
            for subset in (None, ["be/tests/test_a.py" if profile.workdir
                                  else "tests/test_a.py"]):
                with self.subTest(name, subset=subset):
                    argv = self.argv(profile, cwd, subset)
                    self.assertEqual(has_run(argv, BAN), bounds[name], argv)


def old_data(tree: str, profile, base: bool, locks=None) -> dict:
    """Копия прежнего состава данных ключа `_report_suite_result_key`."""
    data = {"tree": tree, "base": base, "locks": locks,
            "tools": dict(profile.tools or {}),
            "command": list(profile.command), "report": profile.report,
            "report_args": list(project_profile.report_args_of(profile)),
            "select": list(profile.select),
            "component": profile.component or "default",
            "runner": profile.runner, "workdir": profile.workdir,
            "env": dict(profile.env)}
    return data


def digest(data: dict) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True,
                                     ensure_ascii=False).encode()).hexdigest()


class SuiteResultKeyTest(unittest.TestCase):

    def test_ac3_component_key_carries_no_rerun_plugins_flag(self):
        """Ключ итога `test_profile` с `report` — sha256 прежнего состава данных; у компонента с `report` ключ иной, его данные — прежний состав плюс `"no_rerun_plugins": true`.

        Сценарий: ключ базы (`base=True`, без файлов блокировки) для
        `test_profile` с `runner: pytest-own` и `report` и для компонента с
        `report` (с `select` и `report_args`); дерево — произвольный sha.
        Ключ `test_profile` равен sha256 копии прежнего словаря; ключ
        компонента не равен ему и равен sha256 того же словаря с полем
        `no_rerun_plugins: true`.

        Ловит мутацию: поле не добавлено (итог компонента, посчитанный до
        запрета повторов, переиспользуется — ключ равен прежнему); поле
        добавлено и `test_profile` (его ключ сменился, кэш итога
        сбросился); поле записано иным значением или именем.
        """
        tree = "1" * 40
        plain = own_profile()
        comp = component_profile(select=("{tests}",),
                                 report_args=("--junitxml", "{path}"))
        self.assertEqual(acceptance._report_suite_result_key(tree, plain, True),
                         digest(old_data(tree, plain, True)))
        old = digest(old_data(tree, comp, True))
        key = acceptance._report_suite_result_key(tree, comp, True)
        self.assertIsNotNone(key)
        self.assertNotEqual(key, old)
        self.assertEqual(key, digest(dict(old_data(tree, comp, True),
                                          no_rerun_plugins=True)))
        changed = dataclasses.replace(comp, from_components=False)
        self.assertEqual(acceptance._report_suite_result_key(tree, changed,
                                                             True),
                         digest(old_data(tree, changed, True)),
                         "тот же профиль вне записи компонентов — прежний ключ")


if __name__ == "__main__":
    unittest.main()
