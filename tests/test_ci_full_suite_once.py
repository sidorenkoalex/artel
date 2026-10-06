"""Полный набор CI исполняется один раз на голову ветки задачи."""
import json
import re
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import ci


SHA = "a" * 40
PYTHON = "Синтаксис и тесты оркестратора"
PYTHON_MIN = "Инварианты на минимальной версии Python"


def check(name: str, conclusion: str, run_id: int, suite_id: int,
          status: str = "completed") -> dict:
    return {"name": name, "conclusion": conclusion, "status": status,
            "check_suite": {"id": suite_id},
            "details_url": f"https://github.com/o/r/actions/runs/{run_id}/job/1"}


def workflow(run_id: int, suite_id: int, event: str,
             conclusion: str = "success") -> dict:
    return {"id": run_id, "check_suite_id": suite_id, "event": event,
            "status": "completed", "conclusion": conclusion}


class FullSuiteStatusTest(unittest.TestCase):
    def setUp(self):
        head = mock.patch.object(ci, "head_sha", lambda branch, **kw: (SHA, ""))
        head.start()
        self.addCleanup(head.stop)

    def serve(self, checks: list[dict], workflows: list[dict] | None):
        def gh(*args, **kwargs):
            if "check-runs" in " ".join(args):
                payload = {"check_runs": checks, "total_count": len(checks)}
            elif workflows is None:
                return subprocess.CompletedProcess(args, 1, "", "нет индекса")
            else:
                payload = {"workflow_runs": workflows}
            return subprocess.CompletedProcess(args, 0, json.dumps(payload), "")

        patcher = mock.patch.object(ci, "gh", gh)
        patcher.start()
        self.addCleanup(patcher.stop)

    def outcomes(self, repo=None):
        return (ci.verifying_status("task/x", repo=repo),
                ci.branch_status("task/x", repo=repo))

    def test_skipped_push_waits_for_pr_execution(self):
        """Ловит мутацию: skipped полного набора вновь засчитан зелёным без PR."""
        self.serve([check(PYTHON, "skipped", 10, 1),
                    check(PYTHON_MIN, "skipped", 10, 1)],
                   [workflow(10, 1, "push")])

        verifying, branch = self.outcomes()

        self.assertEqual(verifying[0], ci.VERIFYING_RUNNING)
        self.assertFalse(branch[0])
        self.assertIn(PYTHON, verifying[1])

    def test_unfinished_pr_does_not_complete_skipped_push(self):
        """Ловит мутацию: наличие PR засчитано как исполнение незавершённого job."""
        self.serve([check(PYTHON, "skipped", 10, 1),
                    check(PYTHON, None, 20, 2, "in_progress")],
                   [workflow(10, 1, "push"), workflow(20, 2, "pull_request")])

        verifying, branch = self.outcomes()

        self.assertEqual(verifying[0], ci.VERIFYING_RUNNING)
        self.assertFalse(branch[0])

    def test_successful_pr_completes_skipped_push(self):
        """Ловит мутацию: исполненный успех PR игнорируется и гейт висит."""
        self.serve([check(PYTHON, "skipped", 10, 1),
                    check(PYTHON_MIN, "skipped", 10, 1),
                    check(PYTHON, "success", 20, 2),
                    check(PYTHON_MIN, "success", 20, 2),
                    check("Карта кодовой базы генерируется и свежа",
                          "skipped", 20, 2)],
                   [workflow(10, 1, "push"), workflow(20, 2, "pull_request")])

        verifying, branch = self.outcomes()

        self.assertEqual(verifying[0], ci.VERIFYING_GREEN)
        self.assertTrue(branch[0])

    def test_unknown_event_of_skipped_full_suite_is_not_green(self):
        """Ловит мутацию: сбой индекса событий трактуется как подтверждённый PR."""
        self.serve([check(PYTHON, "skipped", 10, 1),
                    check(PYTHON, "success", 20, 2)], None)

        verifying, branch = self.outcomes()

        self.assertNotEqual(verifying[0], ci.VERIFYING_GREEN)
        self.assertFalse(branch[0])

    def test_push_without_pr_needs_and_accepts_executed_suite(self):
        """Ловит мутацию: первый push без PR пропускает полный набор или висит после успеха."""
        self.serve([check(PYTHON, "success", 10, 1),
                    check(PYTHON_MIN, "success", 10, 1)],
                   [workflow(10, 1, "push")])

        verifying, branch = self.outcomes()

        self.assertEqual(verifying[0], ci.VERIFYING_GREEN)
        self.assertTrue(branch[0])

    def test_unrelated_skipped_check_and_external_project_keep_old_rule(self):
        """Ловит мутацию: новое правило распространено на карту или внешний target."""
        checks = [check(PYTHON, "skipped", 10, 1),
                  check("Карта кодовой базы генерируется и свежа",
                        "skipped", 10, 1)]
        self.serve(checks, [workflow(10, 1, "push")])
        with mock.patch.object(ci.repo_context, "is_artel", return_value=False):
            verifying, branch = self.outcomes(Path("/tmp/external"))

        self.assertEqual(verifying[0], ci.VERIFYING_GREEN)
        self.assertTrue(branch[0])

    def test_declared_checks_match_workflow_job_names(self):
        """Ловит мутацию: задание полного набора в ci.yml переименовано без перечня."""
        content = Path(".github/workflows/ci.yml").read_text()
        names = []
        for job in ("python", "python-min"):
            found = re.search(rf"(?m)^  {re.escape(job)}:\n    name: (.+)$",
                              content)
            self.assertIsNotNone(found, job)
            names.append(found.group(1))

        self.assertEqual(ci.FULL_SUITE_CHECKS, frozenset(names))


class FullSuiteRerunTest(unittest.TestCase):
    def test_failed_pull_request_is_selected_over_failed_push(self):
        """Ловит мутацию: ре-ран уходит в push со skipped вместо полного PR."""
        calls = []
        runs = [workflow(10, 1, "push", "failure"),
                workflow(20, 2, "pull_request", "failure")]

        def gh(*args, **kwargs):
            calls.append(args)
            if args and args[0] == "api" and "check-runs" in args[1]:
                payload = json.dumps({"check_runs": [
                    check(PYTHON, "skipped", 10, 1),
                    check(PYTHON, "failure", 20, 2)],
                    "total_count": 2})
            elif args[:2] == ("api", f"repos/{{owner}}/{{repo}}/actions/runs"
                              f"?head_sha={SHA}&per_page={ci.config.CI_RUNS_PER_PAGE}"):
                payload = json.dumps({"workflow_runs": runs})
            else:
                payload = ""
            return subprocess.CompletedProcess(args, 0, payload, "")

        with mock.patch.object(ci, "gh", gh), mock.patch.object(
                ci, "head_sha", return_value=(SHA, "")):
            self.assertEqual(ci.find_run_id(SHA)[0], "20")
            ci.trigger_rerun("task/x")

        self.assertIn(("run", "rerun", "20", "--failed"), calls)


if __name__ == "__main__":
    unittest.main()
