"""Приёмочные тесты AC-1..AC-4: эталонный класс лёгкой песочницы
переходов в `tests/sandbox.py` (SPEC 01M1TKP45EM16ZMJGQKNZA5T7J,
требование 1).

Красен до реализации: `tests/sandbox.py` сегодня несёт только
`TmpRootTest`/`RealGitSandbox` общего назначения — ни один класс модуля
не подходит под `_sandbox.find_light_transition_sandbox_classes()`
(наследник `TmpRootTest` с `write_plan_ready`/`write_acceptance_plank`/
`advance_from_in_dev`), и `tests.sandbox` не несёт
`assert_acceptance_run_called` — тесты этого файла падают на
`assertEqual(len(candidates), 1, ...)` (AC-1..AC-3) и на
`AttributeError` при обращении к ещё не существующей функции (AC-4).
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import gitcmd, workspace  # noqa: E402
from tests import sandbox as sandbox_module  # noqa: E402

import _sandbox as plank  # noqa: E402

REAL_WORKSPACE_ENSURE = workspace.ensure


def _one_candidate(test_case) -> type:
    candidates = plank.find_light_transition_sandbox_classes()
    test_case.assertEqual(
        len(candidates), 1,
        f"ожидался ровно один класс лёгкой песочницы переходов в "
        f"tests.sandbox (наследник TmpRootTest c write_plan_ready/"
        f"write_acceptance_plank/advance_from_in_dev), найдено: "
        f"{candidates}")
    return candidates[0]


class Ac1LightTransitionSandboxClassTest(unittest.TestCase):

    def test_ac1_class_extends_tmp_root_test_and_patches_disk_backed_reads_and_workspace(self):
        """Найденный класс наследует `TmpRootTest` и на время теста
        подменяет `gitcmd.show`/`gitcmd.ls_tree_files` на
        `disk_backed_show`/`disk_backed_ls_tree_files`, а `workspace.
        ensure` — на что-то отличное от боевой реализации.

        Ловит мутацию: `setUp` класса перестаёт патчить `gitcmd.show`/
        `gitcmd.ls_tree_files` дисковыми реализациями эталона (например
        оставляет прежний `fake_git`-приём через `gitcmd.git`), либо
        перестаёт подменять `workspace.ensure` — `assertIs`/`assertIsNot`
        ниже поймают расхождение.
        """
        cls = _one_candidate(self)
        self.assertTrue(issubclass(cls, sandbox_module.TmpRootTest))

        def body(self_probe, captured):
            captured["gitcmd_show"] = gitcmd.show
            captured["gitcmd_ls_tree_files"] = gitcmd.ls_tree_files
            captured["workspace_ensure"] = workspace.ensure

        captured = plank.run_probe(cls, body)
        self.assertTrue(captured["_result_success"],
                        f"{captured['_result_errors']}\n"
                        f"{captured['_result_failures']}")
        self.assertIs(captured["gitcmd_show"], sandbox_module.disk_backed_show)
        self.assertIs(captured["gitcmd_ls_tree_files"],
                      sandbox_module.disk_backed_ls_tree_files)
        self.assertIsNot(
            captured["workspace_ensure"], REAL_WORKSPACE_ENSURE,
            "workspace.ensure обязан быть подменён на время теста, не "
            "боевой реализацией (которая реально зовёт git worktree add)")


class Ac2SandboxHelpersTest(unittest.TestCase):

    def test_ac2_write_acceptance_plank_lays_schema_version_2_without_skip_tests_and_a_stub_test(self):
        """`write_acceptance_plank` кладёт `acceptance_tests/` с `SPEC.md`
        `schema_version: 2` без поля `skip_tests` и минимум одним
        stub-тестом.

        Ловит мутацию: помощник перестаёт класть `schema_version: 2`
        (например пишет версию 1) или добавляет `skip_tests` в SPEC.md,
        либо кладёт пустой `acceptance_tests/` без единого `def test_` —
        соответствующая проверка ниже поймает расхождение.
        """
        cls = _one_candidate(self)

        def body(self_probe, captured):
            self_probe.write_acceptance_plank()
            captured["spec_text"] = (
                self_probe.tdir / "SPEC.md").read_text(encoding="utf-8")
            tests_dir = self_probe.tdir / "acceptance_tests"
            files = sorted(tests_dir.glob("*.py"))
            captured["has_py_file"] = bool(files)
            captured["has_test_method"] = any(
                "def test_" in f.read_text(encoding="utf-8") for f in files)

        captured = plank.run_probe(cls, body)
        self.assertTrue(captured["_result_success"],
                        f"{captured['_result_errors']}\n"
                        f"{captured['_result_failures']}")
        self.assertIn("schema_version: 2", captured["spec_text"])
        self.assertNotIn("skip_tests", captured["spec_text"])
        self.assertTrue(captured["has_py_file"], "acceptance_tests/ пуст")
        self.assertTrue(captured["has_test_method"],
                        "нет ни одного stub-теста в acceptance_tests/")

    def test_ac2_write_plan_ready_and_advance_from_in_dev_compose_the_documented_scenario(self):
        """`write_plan_ready` кладёт `PLAN.md` со `status: ready`;
        `advance_from_in_dev` воспроизводит сценарий существующих копий
        (заводит PLAN.md, переводит задачу в `in_dev`, прогоняет
        `fsm.cmd_advance` и возвращает захваченный stdout строкой).

        Ловит мутацию: `advance_from_in_dev` перестаёт заводить `PLAN.md`
        перед переходом (пропущен вызов `write_plan_ready` внутри) —
        `plan_exists_after_advance` ниже станет `False`.
        """
        cls = _one_candidate(self)

        def body(self_probe, captured):
            self_probe.write_plan_ready()
            captured["plan_text"] = (
                self_probe.tdir / "PLAN.md").read_text(encoding="utf-8")
            (self_probe.tdir / "PLAN.md").unlink()

            out = self_probe.advance_from_in_dev()
            captured["advance_out"] = out
            captured["plan_exists_after_advance"] = (
                self_probe.tdir / "PLAN.md").exists()

        captured = plank.run_probe(cls, body)
        self.assertTrue(captured["_result_success"],
                        f"{captured['_result_errors']}\n"
                        f"{captured['_result_failures']}")
        self.assertIn("status: ready", captured["plan_text"])
        self.assertIsInstance(captured["advance_out"], str)
        self.assertTrue(
            captured["plan_exists_after_advance"],
            "advance_from_in_dev обязан завести PLAN.md (write_plan_ready) "
            "перед переходом")


class Ac3FakeGitWhitelistAndExtensionPointTest(unittest.TestCase):

    WHITELISTED_CALLS = (
        ("checkout", "-q", "main"),
        ("commit", "-q", "-m", "x"),
        ("add", "-A"),
        ("reset", "-q", "--", "tasks/T1"),
        ("diff", "--cached"),
        ("status", "--porcelain"),
    )

    def test_ac3_fake_in_repo_accepts_the_six_whitelisted_calls(self):
        """Подменённый `gitcmd.in_repo` эталона без единой настройки
        сценария отвечает успехом на `checkout`/`commit`/`add`/`reset`/
        `diff --cached`/`status --porcelain`.

        Ловит мутацию: одна из шести подкоманд убрана из базового
        белого списка (например `reset`) — соответствующий вызов
        `gitcmd.in_repo` бросит исключение вместо `CompletedProcess`
        с `returncode == 0`.
        """
        cls = _one_candidate(self)

        def body(self_probe, captured):
            repo = self_probe.root / "wt"
            captured["rcs"] = []
            for args in self.WHITELISTED_CALLS:
                res = gitcmd.in_repo(repo, *args)
                captured["rcs"].append((args, res.returncode))

        captured = plank.run_probe(cls, body)
        self.assertTrue(captured["_result_success"],
                        f"{captured['_result_errors']}\n"
                        f"{captured['_result_failures']}")
        for args, rc in captured["rcs"]:
            self.assertEqual(rc, 0, f"безобидный вызов {args} обязан быть "
                             f"no-op успехом (returncode 0)")

    def test_ac3_extension_point_lets_a_scenario_override_merge_without_hardcoded_list(self):
        """Эталон несёт переопределяемую точку расширения (`in_repo_
        handlers` — список хуков, проверяемых ДО базового whitelist'а),
        через которую сценарий подключает свой ответ на `merge`
        (конфликт), не трогая сам whitelist.

        Ловит мутацию: точка расширения жёстко проверяет фиксированный
        набор подкоманд и не даёт добавленному хуку перехватить `merge`
        — добавленный конфликтный ответ не дойдёт до вызывающего кода,
        и `assertNotEqual`/`assertIn` ниже поймают откат к дефолтному
        no-op успеху.
        """
        cls = _one_candidate(self)

        def body(self_probe, captured):
            self_probe.assertTrue(
                hasattr(self_probe, "in_repo_handlers"),
                "эталон обязан нести список хуков-расширений in_repo_"
                "handlers")
            repo = self_probe.root / "wt"

            def conflict_on_merge(repo, *args):
                if args[:1] == ("merge",):
                    return subprocess.CompletedProcess(
                        ("git", "-C", str(repo), *args), 1, "",
                        "CONFLICT (content): Merge conflict in x")
                return None

            self_probe.in_repo_handlers.append(conflict_on_merge)
            res = gitcmd.in_repo(repo, "merge", "--no-ff", "sha")
            captured["merge_rc"] = res.returncode
            captured["merge_stderr"] = res.stderr

        captured = plank.run_probe(cls, body)
        self.assertTrue(captured["_result_success"],
                        f"{captured['_result_errors']}\n"
                        f"{captured['_result_failures']}")
        self.assertNotEqual(captured["merge_rc"], 0)
        self.assertIn("CONFLICT", captured["merge_stderr"])


class Ac4AssertAcceptanceRunCalledTest(unittest.TestCase):

    def test_ac4_checks_both_positional_tdir_and_keyword_code_root(self):
        """`assert_acceptance_run_called(acc_run, tdir, code_root)`
        проверяет вызов `acceptance.run` РОВНО с этими `tdir`/`code_root`
        — первым позиционным и именованным `code_root`.

        Ловит мутацию: проверка сверяет только один из двух аргументов
        (например забывает свериться с `code_root`) — второй `assertRaises`
        ниже не поймает вызов с ПРАВИЛЬНЫМ `tdir`, но чужим `code_root`.
        """
        tdir = Path("/tasks/T1")
        code_root = Path("/worktrees/T1")
        acc_run = mock.MagicMock()
        acc_run(tdir, code_root=code_root)

        sandbox_module.assert_acceptance_run_called(acc_run, tdir, code_root)

        with self.assertRaises(AssertionError):
            sandbox_module.assert_acceptance_run_called(
                acc_run, tdir, Path("/other/root"))
        with self.assertRaises(AssertionError):
            sandbox_module.assert_acceptance_run_called(
                acc_run, Path("/other/tdir"), code_root)


if __name__ == "__main__":
    unittest.main()
