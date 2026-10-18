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
        row = self.row(CHECKS_OK, RATE_LIMIT)
        self.assertEqual(row.status, "skip", row.detail)

    def test_both_rate_limited_is_skip(self):
        """Оба эндпоинта ответили 403 лимита — `skip` (ANSWER-1).

        Ловит мутацию: `_GhProbe.forbidden` признаёт отказом прав любой
        403 — лимит запросов у обоих эндпоинтов давал бы `fail`.
        """
        row = self.row(RATE_LIMIT, RATE_LIMIT)
        self.assertEqual(row.status, "skip", row.detail)

    def test_actions_non_permission_refusal_is_skip(self):
        """Actions 5xx или неразобранный ответ — `skip`; 401/404/403 прав — `fail` (ANSWER-1).

        Ловит мутацию: любой отказ Actions объявляется «Actions недоступны»
        (`fail`) — 502 у Actions давал бы `fail` вместо `skip`; либо отказ
        правами 401 читается временным — `skip` вместо `fail`.
        """
        for actions in (completed("", 1, "gh: Bad Gateway (HTTP 502)\n"),
                        completed("не json")):
            self.assertEqual(self.row(CHECKS_OK, actions).status, "skip")
        for actions in (completed("", 1, "gh: Bad credentials (HTTP 401)\n"),
                        completed("", 1, "gh: Not Found (HTTP 404)\n"),
                        completed("", 1, "gh: Resource not accessible by "
                                         "personal access token (HTTP 403)\n")):
            self.assertEqual(self.row(CHECKS_OK, actions).status, "fail")

    @staticmethod
    def row(checks, actions):
        def fake_run(cmd, **kwargs):
            return checks if "check-runs" in cmd[2] else actions

        doctor = project_checks.doctor
        with mock.patch.object(doctor.shutil, "which",
                               lambda name: "/usr/local/bin/gh"), \
                mock.patch.object(doctor, "gh_env",
                                  lambda name, entry: (None, None)), \
                mock.patch.object(doctor.subprocess, "run", fake_run):
            return project_checks.check_ci_token(
                "project-ci-token-p", "p",
                {"url": "https://localhost/o/p", "base": "main"})


CHECKS_OK = completed(json.dumps({"total_count": 0, "check_runs": []}))
RATE_LIMIT = completed(json.dumps({"message": "API rate limit"}), 1,
                       "gh: API rate limit exceeded (HTTP 403)\n")


if __name__ == "__main__":
    unittest.main()
