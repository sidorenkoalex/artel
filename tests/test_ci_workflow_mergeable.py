"""Выбор единственного полного прогона CI при открытом PR ветки задачи."""

import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


WORKFLOW = Path(os.environ.get(
    "ARTEL_TEST_WORKFLOW",
    Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml",
))


def open_pr_script(workflow: str) -> str:
    """Тело шага `open-pr` из workflow с наложенным приложением PLAN."""
    lines = workflow.splitlines()
    start = lines.index("      - id: open-pr")
    run = lines.index("        run: |", start)
    body = []
    for line in lines[run + 1:]:
        if line and not line.startswith("          "):
            break
        body.append(line[10:] if line else "")
    return "\n".join(body) + "\n"


class WorkflowMergeabilityTest(unittest.TestCase):
    def test_open_pr_requires_explicit_mergeability(self):
        """Ловит мутацию: пропуск GET карточки PR или проверки mergeable
        снимает полный набор с push при конфликте, null или сбое API.
        """
        script = open_pr_script(WORKFLOW.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            timeout = root / "timeout"
            timeout.write_text(
                "#!" + sys.executable + "\n"
                "import json, os, sys\n"
                "from pathlib import Path\n"
                "args = sys.argv[1:]\n"
                "assert args[:3] == ['30s', 'gh', 'api'], args\n"
                "case = json.loads(os.environ['FAKE_PR_CASE'])\n"
                "endpoint = next(arg for arg in args if arg.startswith('repos/'))\n"
                "with Path(os.environ['FAKE_PR_CALLS']).open('a') as log:\n"
                "    log.write(endpoint + '\\n')\n"
                "if '/pulls?' in endpoint:\n"
                "    if case.get('list_error'):\n"
                "        sys.exit(124)\n"
                "    print('\\n'.join(str(n) for n in case.get('numbers', [])))\n"
                "else:\n"
                "    if case.get('detail_error'):\n"
                "        sys.exit(124)\n"
                "    number = int(endpoint.rsplit('/', 1)[1])\n"
                "    if '.mergeable == true' in args[-1]:\n"
                "        if case.get('state') == 'open' and case.get('mergeable') is True:\n"
                "            print(number)\n"
                "    else:\n"
                "        print(number)\n",
                encoding="utf-8",
            )
            timeout.chmod(0o755)
            cases = (
                ({"numbers": [42], "state": "open", "mergeable": True}, True, 2),
                ({"numbers": [42], "state": "open", "mergeable": False}, False, 2),
                ({"numbers": [42], "state": "open", "mergeable": None}, False, 2),
                ({"numbers": [42], "state": "closed", "mergeable": True}, False, 2),
                ({"numbers": []}, False, 1),
                ({"list_error": True}, False, 1),
                ({"numbers": [42], "detail_error": True}, False, 2),
            )
            for case, expected, call_count in cases:
                with self.subTest(case=case):
                    output = root / "output"
                    calls = root / "calls"
                    output.write_text("", encoding="utf-8")
                    calls.write_text("", encoding="utf-8")
                    env = dict(os.environ, PATH=f"{root}:{os.environ['PATH']}",
                               GITHUB_REPOSITORY="owner/repo",
                               GITHUB_REF_NAME="task/example",
                               GITHUB_OUTPUT=str(output), FAKE_PR_CALLS=str(calls),
                               FAKE_PR_CASE=json.dumps(case))
                    result = subprocess.run(["/bin/bash", "-e", "-o", "pipefail", "-c", script],
                                            env=env, capture_output=True, text=True,
                                            timeout=10)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual("value=true" in output.read_text(encoding="utf-8"),
                                     expected)
                    self.assertEqual(len(calls.read_text(encoding="utf-8").splitlines()),
                                     call_count)

    def test_full_suite_jobs_use_open_pr_only_on_task_push(self):
        """Ловит мутацию: условие полного набора снимает push main или
        pull_request, либо использует open_pr без ограничения веткой task/.
        """
        workflow = WORKFLOW.read_text(encoding="utf-8")
        step = workflow.split("      - id: open-pr", 1)[1].split("\n  python:", 1)[0]
        step_condition = re.search(r"^        if: (.+)$", step, re.MULTILINE)
        self.assertIsNotNone(step_condition)
        self.assertEqual(step_condition.group(1),
                         "github.event_name == 'push' && "
                         "startsWith(github.ref, 'refs/heads/task/')")
        jobs = re.findall(r"^  (python|python-min):\n(.*?)(?=^  [\w-]+:|\Z)",
                          workflow, re.MULTILINE | re.DOTALL)
        self.assertEqual({name for name, _ in jobs}, {"python", "python-min"})
        for name, body in jobs:
            with self.subTest(job=name):
                condition = re.search(r"^    if: (.+)$", body, re.MULTILINE)
                self.assertIsNotNone(condition)
                self.assertEqual(
                    condition.group(1),
                    "${{ !cancelled() && needs.changes.outputs.code != 'false' && "
                    "(github.event_name == 'pull_request' || "
                    "needs.changes.outputs.open_pr != 'true') }}",
                )


if __name__ == "__main__":
    unittest.main()
