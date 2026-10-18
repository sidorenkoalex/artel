"""Узлы пути Actions статуса CI внешнего проекта и строки doctor
`project-ci-token-<проект>` (SPEC 01M574A6YQHAPASS9716Z11G4Q), не
покрытые долгоживущими файлами задачи: распознавание 403 прав, ответ
Actions без `total_count`, временный 403 у Actions в doctor.

Ни git, ни `gh` не запускаются: вызовы подменены.
"""
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import ci  # noqa: E402
from orchestrator.doctor import project_checks  # noqa: E402


def completed(stdout: str, code: int = 0, stderr: str = ""):
    return subprocess.CompletedProcess(["gh"], code, stdout, stderr)


class ChecksForbiddenTest(unittest.TestCase):

    def test_only_403_with_not_accessible_text(self):
        """«Resource not accessible …» — переход на Actions только при HTTP 403.

        Ловит мутацию: сверка кода 403 убрана из `ci.checks_forbidden` —
        тот же текст в отказе 404 переводил бы статус на Actions.
        """
        for text in ci.CHECKS_FORBIDDEN_TEXTS:
            self.assertTrue(ci.checks_forbidden(
                f"gh не ответил: gh: {text} (HTTP 403)"))
            self.assertFalse(ci.checks_forbidden(
                f"gh не ответил: gh: {text} (HTTP 404)"))
        self.assertFalse(ci.checks_forbidden(
            "gh не ответил: gh: API rate limit exceeded (HTTP 403)"))


class ActionsPagesTest(unittest.TestCase):

    def test_missing_total_count_is_unknown(self):
        """Ответ Actions без `total_count` — «неизвестен», не полный список.

        Ловит мутацию: ответ без `total_count` читается полным по короткой
        странице, как у `check_runs` — полноту запусков сверить не с чем, и
        неполный список дал бы зелёный исход.
        """
        payload = json.dumps({"workflow_runs": [{"id": 1}]})
        with mock.patch.object(ci, "_gh_at",
                               lambda repo, *args, **kw: completed(payload)):
            items, why = ci._actions_pages(None, "repos/o/r/actions/runs",
                                           "workflow_runs")
        self.assertIsNone(items)
        self.assertIn("total_count", why)


class DoctorActionsThrottledTest(unittest.TestCase):

    def test_actions_rate_limit_is_skip_not_fail(self):
        """403 лимита запросов у Actions при читаемых check-runs — `skip`, не `fail`.

        Ловит мутацию: временный 403 распознаётся только у check-runs —
        лимит запросов на чтении Actions объявлялся бы «Actions
        недоступны» (`fail`).
        """
        def fake_run(cmd, **kwargs):
            if "check-runs" in cmd[2]:
                return completed(json.dumps({"total_count": 0,
                                             "check_runs": []}))
            return completed(json.dumps({"message": "API rate limit"}), 1,
                             "gh: API rate limit exceeded (HTTP 403)\n")

        doctor = project_checks.doctor
        with mock.patch.object(doctor.shutil, "which",
                               lambda name: "/usr/local/bin/gh"), \
                mock.patch.object(doctor, "gh_env",
                                  lambda name, entry: (None, None)), \
                mock.patch.object(doctor.subprocess, "run", fake_run):
            row = project_checks.check_ci_token(
                "project-ci-token-p", "p",
                {"url": "https://localhost/o/p", "base": "main"})
        self.assertEqual(row.status, "skip", row.detail)


if __name__ == "__main__":
    unittest.main()
