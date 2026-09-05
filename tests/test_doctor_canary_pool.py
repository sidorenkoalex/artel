"""Юнит-тесты `doctor.check_role_log_pool_leak`/`check_token_repo_scope`
(SPEC 01M1NEEWH5K1XPFRDGRMPYSBXJ, требование 13б/13в) — вызовы функций
напрямую, без полного `cmd_doctor` (тот прогон, включая AC-15 с реальным
`config.LOGS`, покрыт приёмочными тестами `tasks/
01M1NEEWH5K1XPFRDGRMPYSBXJ/acceptance_tests/`).

`CanaryPoolDriftCheckTest` — `doctor.check_canary_pool_drift` (SPEC
01M1NSR5M5THYRC0RFWPMVE2DW, требование 3/AC-8) вызовом функции напрямую;
полный сценарий через `doctor` CLI и обе команды восстановления уже
покрыт приёмочными тестами `tasks/01M1NSR5M5THYRC0RFWPMVE2DW/
acceptance_tests/`.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import alerts, config, doctor, store  # noqa: E402


class RoleLogPoolLeakCheckTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        for attr, value in (("ROOT", self.root),
                            ("DB", self.root / ".artel" / "state.db"),
                            ("LOGS", self.root / ".artel" / "logs")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        store.create_schema(store.db())
        self.conn = store.db()

    def test_no_logs_directory_is_ok_and_raises_nothing(self):
        check = doctor.check_role_log_pool_leak(self.conn)
        self.assertEqual(check.status, "ok")
        self.assertEqual(alerts.open_alerts(self.conn, "incident"), [])

    def test_clean_log_is_ok(self):
        config.LOGS.mkdir(parents=True)
        (config.LOGS / "T900-developer-1.log").write_text(
            "Обычный шаг роли: правка кода, коммит, готово.\n",
            encoding="utf-8")
        check = doctor.check_role_log_pool_leak(self.conn)
        self.assertEqual(check.status, "ok")
        self.assertEqual(alerts.open_alerts(self.conn, "incident"), [])

    def test_leaking_log_fails_and_raises_one_incident_alert(self):
        config.LOGS.mkdir(parents=True)
        (config.LOGS / "T900-developer-1.log").write_text(
            f"Agent: гружу шаблон из ~/{config.CANARY_POOL_DIRNAME}/x.md\n",
            encoding="utf-8")
        check = doctor.check_role_log_pool_leak(self.conn)
        self.assertEqual(check.status, "fail")
        incidents = alerts.open_alerts(self.conn, "incident")
        self.assertEqual(len(incidents), 1)
        self.assertIn(config.CANARY_POOL_DIRNAME, incidents[0]["message"])

    def test_two_runs_over_the_same_leaking_log_do_not_duplicate_the_alert(self):
        config.LOGS.mkdir(parents=True)
        (config.LOGS / "T900-developer-1.log").write_text(
            f"~/{config.CANARY_POOL_DIRNAME}/x.md\n", encoding="utf-8")
        doctor.check_role_log_pool_leak(self.conn)
        doctor.check_role_log_pool_leak(self.conn)
        self.assertEqual(len(alerts.open_alerts(self.conn, "incident")), 1)


class TokenRepoScopeCheckTest(unittest.TestCase):

    def test_gh_missing_is_a_skip_without_any_subprocess_call(self):
        with mock.patch.object(doctor.shutil, "which", return_value=None), \
             mock.patch.object(doctor.subprocess, "run") as run_mock:
            checks = doctor.check_token_repo_scope()
        run_mock.assert_not_called()
        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0].status, "skip")

    def test_no_role_token_found_is_a_skip(self):
        with mock.patch.object(doctor.shutil, "which", return_value="/usr/bin/gh"), \
             mock.patch.object(doctor.runner, "role_token", return_value=None):
            checks = doctor.check_token_repo_scope()
        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0].status, "skip")

    def test_token_visible_in_one_repo_is_ok(self):
        result = subprocess.CompletedProcess(
            [], 0, "artel-org/artel\n", "")
        with mock.patch.object(doctor.shutil, "which", return_value="/usr/bin/gh"), \
             mock.patch.object(doctor.runner, "role_token",
                               return_value="tok-shared"), \
             mock.patch.object(doctor.subprocess, "run", return_value=result):
            checks = doctor.check_token_repo_scope()
        statuses = {c.status for c in checks}
        self.assertEqual(statuses, {"ok"})

    def test_token_visible_in_more_than_one_repo_warns(self):
        result = subprocess.CompletedProcess(
            [], 0, "artel-org/artel\nartel-org/other-repo\n", "")
        with mock.patch.object(doctor.shutil, "which", return_value="/usr/bin/gh"), \
             mock.patch.object(doctor.runner, "role_token",
                               return_value="tok-shared"), \
             mock.patch.object(doctor.subprocess, "run", return_value=result):
            checks = doctor.check_token_repo_scope()
        statuses = {c.status for c in checks}
        self.assertIn("warn", statuses)

    def test_same_token_across_roles_is_queried_only_once(self):
        result = subprocess.CompletedProcess([], 0, "artel-org/artel\n", "")
        with mock.patch.object(doctor.shutil, "which", return_value="/usr/bin/gh"), \
             mock.patch.object(doctor.runner, "role_token",
                               return_value="tok-shared"), \
             mock.patch.object(doctor.subprocess, "run",
                               return_value=result) as run_mock:
            doctor.check_token_repo_scope()
        self.assertEqual(run_mock.call_count, 1)


class CanaryPoolDriftCheckTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root_patcher = mock.patch.object(config, "ROOT", Path(tmp.name))
        root_patcher.start()
        self.addCleanup(root_patcher.stop)

        home_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(home_tmp.cleanup)
        self.fake_home = Path(home_tmp.name)
        home_patcher = mock.patch.object(Path, "home",
                                         return_value=self.fake_home)
        home_patcher.start()
        self.addCleanup(home_patcher.stop)

        self.pool_dir = self.fake_home / config.CANARY_POOL_DIRNAME
        self.pool_dir.mkdir()
        (self.pool_dir / "a.md").write_text("тело А\n", encoding="utf-8")

        kc_patcher = mock.patch.object(
            doctor.canary.keychain, "token",
            return_value="unit-test-drift-key")
        kc_patcher.start()
        self.addCleanup(kc_patcher.stop)

    def test_no_sealed_file_is_ok(self):
        self.assertEqual(doctor.check_canary_pool_drift().status, "ok")

    def test_matching_pool_is_ok(self):
        doctor.canary.cmd_pool_seal()
        self.assertEqual(doctor.check_canary_pool_drift().status, "ok")

    def test_diverging_pool_warns(self):
        doctor.canary.cmd_pool_seal()
        (self.pool_dir / "a.md").write_text(
            "тело А, незапечатанная правка\n", encoding="utf-8")
        check = doctor.check_canary_pool_drift()
        self.assertEqual(check.status, "warn")
        self.assertIn("пул", check.detail.lower())


if __name__ == "__main__":
    unittest.main()
