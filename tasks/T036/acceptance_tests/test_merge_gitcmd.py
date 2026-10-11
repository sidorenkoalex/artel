"""Приёмочные тесты T036 — merge-последовательность `merge_gate` через
`gitcmd.git` (SPEC.md, критерии AC-1..AC-4).

Песочница для AC-2/AC-3 — `tests.test_invariants.FsmTest` (та же фикстура,
на которой уже стоит `MergeOnlyFromMergeGateTest`/`MergeNeedsGreenCiTest`
для этой же merge-последовательности): БД и артефакты во временном
каталоге, `subprocess.run` подменён на уровне `gitcmd.subprocess.run`
(требование 5 SPEC — патчить `gitcmd.git`, а не `fsm.subprocess.run`).
Своя песочница с нуля здесь дублировала бы catalog/ci/keychain-обвязку
без содержательной причины.

AC-1 — статическая проверка исходника `fsm.py`, а не поведения:
единственный вызов `subprocess.run` в модуле на момент написания этих
тестов (проверено `grep -n "subprocess\\." orchestrator/fsm.py`) — это
голая git-последовательность `merge_gate`, которую задача переводит на
`gitcmd.git`. Поэтому «нет прямых `subprocess.run(["git", ...])`»
эквивалентно «в `fsm.py` не осталось ни одного вызова `subprocess.run`
вообще» — проверяется через AST, не через текстовый grep (не путается
с упоминаниями `subprocess`/`subprocess.run` в комментариях и строках).

AC-4 («все существующие тесты зелёные») размечен `manual`: критерий уже
покрыт `.github/workflows/ci.yml` (`unittest discover -s tests -v` на
каждый пуш в чистом раннере) — это и есть проверка критерия. Дублировать
её здесь подпроцессом внутри acceptance_tests опасно ложным красным от
несвязанных с T036 экологических условий машины разработчика (тот же
довод и прецедент, что tasks/T035 AC-11).
"""
import ast
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import fsm, gitcmd, store  # noqa: E402
from tests.test_invariants import FsmTest  # noqa: E402

# AC-4: manual — критерий уже покрыт `.github/workflows/ci.yml`
# (`unittest discover -s tests -v` на каждый пуш в чистом раннере);
# повтор той же проверки подпроцессом внутри acceptance_tests ловил бы
# несвязанные с T036 экологические условия машины разработчика, а не
# дефект самой задачи (см. докстроку модуля, прецедент tasks/T035 AC-11).


class NoDirectGitSubprocessRunTest(unittest.TestCase):
    """AC-1: в fsm.py не остаётся прямых `subprocess.run(["git", ...])`."""

    def test_ac1_fsm_has_no_subprocess_run_call(self):
        source = (REPO_ROOT / "orchestrator" / "fsm.py").read_text(
            encoding="utf-8")
        tree = ast.parse(source, filename="fsm.py")
        offending_lines = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if (isinstance(func, ast.Attribute) and func.attr == "run"
                    and isinstance(func.value, ast.Name)
                    and func.value.id == "subprocess"):
                offending_lines.append(node.lineno)
        self.assertEqual(
            offending_lines, [],
            f"остались прямые subprocess.run(...) в fsm.py на строках "
            f"{offending_lines} — должны быть переведены на gitcmd.git")


class MergeFailureStillReportsTest(FsmTest):
    """AC-2: отказ любой из четырёх команд merge-последовательности
    по-прежнему пишет «merge FAILED» в журнал и завершает CLI тем же
    текстом."""

    def setUp(self):
        super().setUp()
        self.write_spec("ready")
        self.write_plan("ready")
        self.write_review("approved", 1)
        self.set_state("merge_gate")

    @staticmethod
    def _fail_at(bad_subcommand, stderr="конфликт"):
        """Подмена gitcmd.subprocess.run: отказывает только на одной
        git-подкоманде, остальные отвечают как обычно (rc=0)."""
        def fn(cmd, *args, **kwargs):
            cmd = list(cmd)
            is_bad = (len(cmd) > 1 and cmd[0] == "git"
                      and cmd[1] == bad_subcommand)
            rc = 1 if is_bad else 0
            return subprocess.CompletedProcess(cmd, rc, "",
                                               stderr if is_bad else "")
        return fn

    def _approve_and_capture_exit(self, bad_subcommand) -> str:
        with mock.patch.object(gitcmd.subprocess, "run",
                               self._fail_at(bad_subcommand)):
            with self.assertRaises(SystemExit) as exit_:
                self.capture(fsm.cmd_approve, self.TASK)
        return str(exit_.exception)

    def _assert_merge_failed_journaled_and_gate_held(self):
        rows = store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? AND action=?",
            (self.TASK, "merge FAILED")).fetchall()
        self.assertTrue(rows, "запись «merge FAILED» не найдена в журнале")
        self.assertIn("конфликт", rows[-1]["detail"])
        self.assertEqual(self.state(), "merge_gate",
                         "задача должна остаться на гейте merge")

    def test_ac2_checkout_failure_reports_merge_failed(self):
        message = self._approve_and_capture_exit("checkout")
        self.assertIn("merge упал на git checkout", message)
        self.assertIn("конфликт", message)
        self._assert_merge_failed_journaled_and_gate_held()

    def test_ac2_pull_failure_reports_merge_failed(self):
        message = self._approve_and_capture_exit("pull")
        self.assertIn("merge упал на git pull", message)
        self.assertIn("конфликт", message)
        self._assert_merge_failed_journaled_and_gate_held()

    def test_ac2_merge_failure_reports_merge_failed(self):
        message = self._approve_and_capture_exit("merge")
        self.assertIn("merge упал на git merge", message)
        self.assertIn("конфликт", message)
        self._assert_merge_failed_journaled_and_gate_held()

    def test_ac2_push_failure_reports_merge_failed(self):
        message = self._approve_and_capture_exit("push")
        self.assertIn("merge упал на git push", message)
        self.assertIn("конфликт", message)
        self._assert_merge_failed_journaled_and_gate_held()


class MergeSuccessStillClosesTaskTest(FsmTest):
    """AC-3: успешный путь по-прежнему переводит задачу в `done` с той же
    записью журнала."""

    def setUp(self):
        super().setUp()
        self.write_spec("ready")
        self.write_plan("ready")
        self.write_review("approved", 1)
        self.set_state("merge_gate")

    def test_ac3_success_moves_task_to_done_with_expected_journal(self):
        self.capture(fsm.cmd_approve, self.TASK)

        self.assertEqual(self.state(), "done")
        rows = store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? AND action=?",
            (self.TASK, "state -> done")).fetchall()
        self.assertTrue(rows, "запись перехода в done не найдена в журнале")
        self.assertEqual(rows[-1]["detail"], f"смержено: {self.branch}")


if __name__ == "__main__":
    unittest.main()
