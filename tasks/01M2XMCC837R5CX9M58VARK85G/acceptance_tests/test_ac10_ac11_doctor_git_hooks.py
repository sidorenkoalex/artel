"""AC-10, AC-11: проверка doctor с именем «git-hooks» и её починка под
`doctor --fix`.

Красен до реализации: в фасаде `orchestrator.doctor` нет ни одной чек-функции про git-хуки — резолвер ниже падает именованным `fail`.
"""
import inspect
import os
import shutil
import subprocess
import unittest
from unittest import mock

from orchestrator import doctor
from tests.sandbox import RealGitSandbox, capture

from _hooks import HOOK_NAMES, HOOKS_DIR, HOOKS_PATH_VALUE


def resolve_check(testcase) -> tuple:
    """(имя, функция) чек-функции doctor про git-хуки — по соглашению имён
    пакета (`check_root_pin` -> «root-pin», `check_git_identity` ->
    «git-identity»), то есть `check_git_hooks` -> «git-hooks»."""
    names = sorted(n for n in dir(doctor)
                   if n.startswith("check_") and "git_hook" in n
                   and callable(getattr(doctor, n)))
    if not names:
        testcase.fail("в orchestrator.doctor нет чек-функции про git-хуки "
                      "(ожидалось имя вида `check_git_hooks`) — требование 5 "
                      "SPEC не выполнено")
    return names[0], getattr(doctor, names[0])


class DoctorGitHooksCheckSandbox(RealGitSandbox):
    """`config.ROOT` — настоящий git-репозиторий с копией `scripts/git-hooks`."""

    def setUp(self):
        super().setUp()
        dest = self.root / "scripts" / "git-hooks"
        dest.mkdir(parents=True)
        for name in HOOK_NAMES:
            src = HOOKS_DIR / name
            self.assertTrue(src.is_file(),
                            f"нет файла хука {src} — требование 1 SPEC ещё "
                            f"не выполнено")
            shutil.copy2(src, dest / name)
        self.hook_files = [dest / name for name in HOOK_NAMES]

    def chmod_hooks(self, mode: int) -> None:
        for path in self.hook_files:
            os.chmod(path, mode)

    def hooks_path_config(self) -> str:
        res = subprocess.run(["git", "config", "--get", "core.hooksPath"],
                             cwd=self.root, capture_output=True, text=True)
        return res.stdout.strip()

    def executable(self) -> list:
        return [bool(path.stat().st_mode & 0o111) for path in self.hook_files]


class GitHooksCheckTest(DoctorGitHooksCheckSandbox):

    def test_ac10_check_is_ok_only_with_hookspath_and_executable_hooks(self):
        """Проверка «git-hooks» входит в набор `doctor` без `--fix`, даёт
        `ok` при `core.hooksPath = scripts/git-hooks` и исполняемых файлах
        хуков и `fail` с подсказкой `doctor --fix` в остальных случаях
        (путь не настроен; настроен, но файлы без бита исполнения).

        Ловит мутацию: проверка смотрит только на `core.hooksPath` и не
        сверяет бит исполнения файлов — git молча пропускает
        неисполняемый хук, защиты бы не было, а третья ветка сверки ниже
        («настроено, но файлы не исполняемы» -> fail) покраснела бы.
        """
        name, check = resolve_check(self)
        self.assertIn(name, inspect.getsource(doctor.all_checks),
                      "проверка не включена в набор doctor без --fix")

        self.chmod_hooks(0o755)
        self.assertEqual(self.hooks_path_config(), "")
        unset = check()
        self.assertEqual(unset.name, "git-hooks")
        self.assertEqual(unset.status, "fail", unset.detail)
        self.assertIn("doctor --fix", unset.detail)

        subprocess.run(["git", "config", "core.hooksPath", HOOKS_PATH_VALUE],
                       cwd=self.root, check=True, capture_output=True)
        enabled = check()
        self.assertEqual(enabled.name, "git-hooks")
        self.assertEqual(enabled.status, "ok", enabled.detail)

        self.chmod_hooks(0o644)
        not_executable = check()
        self.assertEqual(not_executable.name, "git-hooks")
        self.assertEqual(not_executable.status, "fail", not_executable.detail)
        self.assertIn("doctor --fix", not_executable.detail)


class DoctorFixInstallsGitHooksTest(DoctorGitHooksCheckSandbox):

    def run_fix(self) -> str:
        """`doctor --fix` без посторонних починок: предмет теста — только
        включение хуков, остальные `--fix`-ветки (сироты, игнорируемые
        файлы, мёртвые lease-группы, зависшие прогоны) замолчены."""
        with mock.patch.object(doctor, "all_checks", lambda conn: []), \
                mock.patch.object(doctor, "_remote_artifact_branch_names",
                                  return_value=set()), \
                mock.patch.object(doctor, "_fix_ignored_artifact_files",
                                  lambda conn: None), \
                mock.patch.object(doctor, "_fix_dead_lease_groups",
                                  lambda conn: None), \
                mock.patch.object(doctor, "_fix_hung_test_runs",
                                  lambda conn: None):
            return capture(lambda: doctor.cmd_doctor(fix=True))

    def test_ac11_fix_sets_hookspath_and_makes_the_hooks_executable(self):
        """`doctor --fix` на репозитории без `core.hooksPath` и с
        неисполняемыми файлами хуков выставляет путь и бит исполнения, а
        проверка «git-hooks» после него отвечает `ok`.

        Ловит мутацию: `--fix` выставляет только `git config
        core.hooksPath`, а `chmod` файлов хуков не делает — git тихо
        пропустил бы неисполняемый хук, защита main не включилась бы, и
        сверка битов исполнения (и следом статус проверки) покраснела бы.
        """
        _, check = resolve_check(self)
        self.chmod_hooks(0o644)
        self.assertEqual(self.hooks_path_config(), "")
        self.assertEqual(self.executable(), [False, False])

        self.run_fix()

        self.assertEqual(self.hooks_path_config(), HOOKS_PATH_VALUE)
        self.assertEqual(self.executable(), [True, True])
        self.assertEqual(check().status, "ok", check().detail)


if __name__ == "__main__":
    unittest.main()
