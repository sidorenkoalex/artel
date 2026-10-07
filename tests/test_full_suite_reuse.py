"""Границы ключа и разбора полного прогона."""

import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

from orchestrator import acceptance, fsm_merge_gate, suite_run
from tests.sandbox import RealGitSandbox


class SuiteReuseBoundaryTest(RealGitSandbox):
    def test_base_command_uses_resolved_pytest_head(self):
        """Ловит мутацию: ключ базы сохраняет флаги прогона или сырой python3 и не узнаёт тот же pytest из профиля."""
        tree = acceptance.suite_tree_hash(self.root, base=True)
        default = acceptance.suite_result_key(tree, base=True)
        profile = acceptance.suite_result_key(
            tree, ["python3", "-m", "pytest"], base=True)
        with_output_flags = acceptance.suite_result_key(
            tree, ["python3", "-m", "pytest", "tests", "-vv", "-n", "2",
                   "-p", "xdist"], base=True)
        other = acceptance.suite_result_key(
            tree, ["/different/python3", "-m", "pytest"], base=True)
        self.assertIsNotNone(default)
        self.assertEqual(default, profile)
        self.assertEqual(default, with_output_flags)
        self.assertNotEqual(default, other)

    def test_staged_new_file_enters_tree_key(self):
        """Ловит мутацию: временный индекс начинается с HEAD и теряет новый файл, уже добавленный в индекс."""
        before = acceptance.suite_tree_hash(self.root)
        (self.root / "new.txt").write_text("новый файл\n", encoding="utf-8")
        self.git("add", "new.txt")
        after = acceptance.suite_tree_hash(self.root)
        self.assertIsNotNone(before)
        self.assertIsNotNone(after)
        self.assertNotEqual(after, before)

    def test_environment_failure_forces_run(self):
        """Ловит мутацию: неудача отпечатка пакетов превращается в постоянный пустой ключ и повторяет чужой итог."""
        red = "========== 1 failed in 0.10s ==========\n"
        with mock.patch.object(acceptance.importlib.metadata, "distributions",
                               side_effect=OSError("пакеты недоступны")), \
             mock.patch.object(acceptance, "run_full_suite",
                               side_effect=[(False, red), (True, red)]) as run:
            acceptance.full_suite(self.root, "ENV-FAIL")
            acceptance.full_suite(self.root, "ENV-FAIL")
        self.assertEqual(run.call_count, 2)


class SuiteSummaryTest(unittest.TestCase):
    def test_subtests_summary_is_finished(self):
        """Ловит мутацию: категория subtests в итоговой строке снова скрывает завершённый прогон базы."""
        output = ("= 1 failed, 4491 passed, 2 skipped, "
                  "1624 subtests passed in 753.22s (0:12:33) ==\n")
        self.assertIn("subtests passed", acceptance.run_summary_line(output))
        self.assertTrue(suite_run.parse(False, output).finished)


class MergeGateFreshSuiteTest(unittest.TestCase):
    def test_fresh_flag_reaches_appendix_suite_through_cycle(self):
        """Ловит мутацию: внешний цикл теряет --fresh-suite до прогона приложений или оставляет флаг следующему approve."""
        ctx = object()
        appendices = mock.Mock(return_value=("stopped", []))
        patches = (
            (fsm_merge_gate.merge_lock, "acquire", None),
            (fsm_merge_gate.merge_lock, "release", None),
            (fsm_merge_gate.store, "task_target", "artel"),
            (fsm_merge_gate.repo_context, "resolve", ctx),
            (fsm_merge_gate, "_profile_refusal_exit", None),
            (fsm_merge_gate, "_docs_ref_unsynced", False),
            (fsm_merge_gate, "_protected_path_diff_gate", False),
            (fsm_merge_gate, "_test_integrity_diff_gate", False),
            (fsm_merge_gate, "_ensure_branch_head_published", "ok"),
            (fsm_merge_gate, "_sync_main_or_wait", "fresh"),
            (fsm_merge_gate, "_acceptance_locks_refuse", False),
            (fsm_merge_gate, "_ci_ready_or_wait", "ok"),
            (fsm_merge_gate, "_refuse_if_main_red", None),
            (fsm_merge_gate, "_perform_carpentry_merge", ("ok", Path("/scratch"))),
        )
        with ExitStack() as stack:
            for module, name, result in patches:
                stack.enter_context(mock.patch.object(module, name, return_value=result))
            stack.enter_context(mock.patch.object(
                fsm_merge_gate, "_apply_plan_appendices", appendices))
            for fresh in (True, False):
                fsm_merge_gate._cmd_approve_merge_gate_cycle(
                    object(), "TASK", "session", {"branch": "task/branch"},
                    "merge_gate", fresh_suite=fresh)
        self.assertEqual([call.args[-1] for call in appendices.call_args_list],
                         [True, False])
