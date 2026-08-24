"""Тесты doctor: pre-flight, recovery-сверка, сироты, alerts, смоуки
(см. tasks/T022/SPEC.md, критерии приёмки 1–8).

Классы названы по критериям: `DoctorCommandTest` — критерий 1 (здоровый/
сломанный репо, код выхода), `PreflightBlocksMissingTokenTest` —
критерий 2, `IsolationSmokeTest` — критерий 3, `RecoveryCheckTest` —
критерий 4, `ProgramThresholdAlertTest` — критерий 5, `AlertAckTest` —
критерий 6, `OrphansTest` — критерий 7, `LiveSmokeTest` — критерий 8
(с подменённым CLI — живой прогон настоящего CLI мануальный, Оператора).

Песочница — тот же приём, что и в соседних модулях (test_git_fixation.py
`TmpRootTest`): пути `config` подменяются на временный каталог; `claude`
и keychain — подменены, кроме тестов recovery/orphans, которым нужен
настоящий git (тот же приём, что `RealPultGitTest`).
"""
import io
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (alerts, budget, catalog, config, doctor,  # noqa: E402
                          gitcmd, projects, runner, spend, store)

REPO_ROOT = Path(__file__).resolve().parent.parent

TARGETS_YAML_DOGFOOD_ONLY = """targets:
  artel:
    forge: github
    url: https://example.invalid/artel
    base: main
    token_slot: artel-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""

TARGETS_YAML_WITH_SLED = """targets:
  artel:
    forge: github
    url: https://example.invalid/artel
    base: main
    token_slot: artel-token
    no_paths: []
    project_skills: []
    merge_gate: operator
  sled:
    forge: github
    url: https://example.invalid/sled
    base: main
    token_slot: sled-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""


def capture(fn, *args) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        fn(*args)
    return buf.getvalue()


class FakeLiveSmokeProc:
    """Замена `subprocess.Popen` для `doctor.live_smoke`: только `.communicate`."""

    def __init__(self, output: str, returncode: int = 0):
        self.output = output
        self.returncode = returncode

    def communicate(self, timeout=None):
        return self.output, None

    def kill(self) -> None:
        pass

    def wait(self, timeout=None) -> int:
        return self.returncode


class FakeStream:
    """Пайп процесса агента: отдаёт заготовленные строки, помнит своё закрытие."""

    def __init__(self, lines):
        self.lines = iter(lines)

    def __iter__(self):
        return self

    def __next__(self) -> str:
        return next(self.lines)

    def close(self) -> None:
        pass


class FakeAgentProc:
    """Процесс агента для `runner.cmd_run` (не для `doctor.live_smoke`)."""

    def __init__(self, lines, returncode: int = 0):
        self.stdout = FakeStream(lines)
        self.returncode = returncode

    def wait(self, timeout=None) -> int:
        return self.returncode


def result_event(usd: float) -> str:
    return f'{{"type":"result","total_cost_usd":{usd},"usage":{{}}}}\n'


REAL_RUN = subprocess.run
REAL_POPEN = subprocess.Popen


def claude_only_run(claude_stdout: str, claude_returncode: int = 0):
    """`subprocess.run` side_effect: отвечает только на `claude ...`, остальное
    (`git config --get ...` внутри `gitcmd.git`, тот же общий модуль
    `subprocess`) уходит в настоящий `subprocess.run` — та же ловушка, что
    и с `Popen`: подмена атрибута `subprocess.run` глобальна на модуль.
    """
    def run(args, **kwargs):
        if args and args[0] == "claude":
            return subprocess.CompletedProcess(args, claude_returncode,
                                               claude_stdout, "")
        return REAL_RUN(args, **kwargs)
    return run


def claude_only_popen(fake_proc):
    """Аналог `claude_only_run` для `subprocess.Popen` (см. `doctor.live_smoke`)."""
    def popen(cmd, *args, **kwargs):
        if cmd and cmd[0] == "claude":
            return fake_proc
        return REAL_POPEN(cmd, *args, **kwargs)
    return popen


class TmpRootTest(unittest.TestCase):
    """Песочница doctor: пути `config` — во временном каталоге, keychain подменён."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        shutil.copytree(REPO_ROOT / "skills", self.root / "skills")
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")

        for attr, value in (("ROOT", self.root),
                            ("DB", self.root / ".artel" / "state.db"),
                            ("TASKS", self.root / "tasks"),
                            ("LOGS", self.root / ".artel" / "logs"),
                            ("PROJECTS", self.root / ".artel" / "projects"),
                            ("ROLE_HOME", self.root / ".artel" / "home"),
                            ("ROLE_CONFIG_DIR",
                             self.root / ".artel" / "home" / ".claude"),
                            ("TARGETS", self.root / "targets.yaml"),
                            ("BACKUP_MARKER", self.root / ".artel" / "backup-marker")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        kc_patcher = mock.patch.object(runner.keychain, "token",
                                       lambda slot: "tok-test")
        kc_patcher.start()
        self.addCleanup(kc_patcher.stop)

        # `check_token` смотрит ambient-переменные раньше keychain — не
        # даём реальному окружению машины, где гоняются тесты, тихо решить
        # исход проверки за подложенный keychain.
        env_patcher = mock.patch.dict(
            "os.environ",
            {"CLAUDE_CODE_OAUTH_TOKEN": "", "ANTHROPIC_API_KEY": ""})
        env_patcher.start()
        self.addCleanup(env_patcher.stop)

        config.TARGETS.write_text(TARGETS_YAML_DOGFOOD_ONLY, encoding="utf-8")
        capture(catalog.cmd_init)

    def touch_backup(self) -> None:
        config.BACKUP_MARKER.parent.mkdir(parents=True, exist_ok=True)
        config.BACKUP_MARKER.write_text("ok", encoding="utf-8")


class DoctorCommandTest(TmpRootTest):
    """Критерий 1: здоровый репо — все проверки ок, код 0; сломанный — провалы, код ≠0."""

    def which(self, name):
        return "/usr/bin/claude" if name == "claude" else None

    def healthy_mocks(self):
        """Контекст-менеджер, под которым все проверки doctor проходят чисто."""
        self.touch_backup()
        return (
            mock.patch.object(doctor.shutil, "which", side_effect=self.which),
            mock.patch.object(doctor.subprocess, "run", side_effect=claude_only_run(
                f"{config.CLI_VERSION_PIN} (Claude Code)\n")),
            mock.patch.object(doctor.subprocess, "Popen", side_effect=claude_only_popen(
                FakeLiveSmokeProc(result_event(0.01)))),
        )

    def test_healthy_repo_prints_ok_and_does_not_exit(self):
        p1, p2, p3 = self.healthy_mocks()
        with p1, p2, p3:
            buf = io.StringIO()
            with redirect_stdout(buf):
                doctor.cmd_doctor()  # не должен поднять SystemExit
        out = buf.getvalue()
        self.assertIn("DOCTOR: ок", out)
        self.assertNotIn("[FAIL]", out)

    def test_broken_repo_named_failures_and_nonzero_exit(self):
        """Нет токена, версия CLI ≠ пин, сирота-каталог — провалы, код ≠0."""
        self.touch_backup()
        (config.TASKS / "T999-orphan").mkdir(parents=True)

        with mock.patch.object(doctor.shutil, "which", side_effect=self.which), \
                mock.patch.object(doctor.subprocess, "run",
                                  side_effect=claude_only_run("0.0.1 (stub)\n")), \
                mock.patch.object(doctor.subprocess, "Popen",
                                  side_effect=claude_only_popen(
                                      FakeLiveSmokeProc(result_event(0.01)))), \
                mock.patch.object(runner.keychain, "token", lambda slot: None):
            with self.assertRaises(SystemExit) as exit_ctx:
                capture(doctor.cmd_doctor)

        self.assertEqual(exit_ctx.exception.code, 1)

    def test_broken_repo_output_names_the_reasons(self):
        """Именованные причины провала — тем же набором проверок, что печатает `doctor`."""
        (config.TASKS / "T999-orphan").mkdir(parents=True)

        conn = store.db()
        with mock.patch.object(doctor.shutil, "which", side_effect=self.which), \
                mock.patch.object(doctor.subprocess, "run",
                                  side_effect=claude_only_run("0.0.1 (stub)\n")), \
                mock.patch.object(doctor.subprocess, "Popen",
                                  side_effect=claude_only_popen(
                                      FakeLiveSmokeProc(result_event(0.01)))), \
                mock.patch.object(runner.keychain, "token", lambda slot: None):
            checks = doctor.all_checks(conn)

        by_name = {c.name: c for c in checks if c.name in
                  ("token", "cli-version", "orphans-dirs")}
        self.assertEqual(by_name["token"].status, "fail")
        self.assertIn("keychain", by_name["token"].detail)
        self.assertEqual(by_name["cli-version"].status, "warn")
        self.assertIn("0.0.1", by_name["cli-version"].detail)
        self.assertEqual(by_name["orphans-dirs"].status, "fail")
        self.assertIn("T999-orphan", by_name["orphans-dirs"].detail)


class PreflightBlocksMissingTokenTest(TmpRootTest):
    """Критерий 2: pre-flight ловит отсутствие токена до запуска агента."""

    TASK = "T001"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_new, "Задача под pre-flight")
        store.update_task(store.db(), self.TASK, state="in_dev")

    def test_missing_token_blocks_the_step_with_a_named_reason_and_no_retries(self):
        with mock.patch.object(runner.keychain, "token", lambda slot: None), \
                mock.patch.object(runner.subprocess, "Popen") as popen:
            out = capture(runner.cmd_run, self.TASK)

        popen.assert_not_called()
        self.assertIn("pre-flight провален", out)
        self.assertIn("token", out)

        actions = [(r["action"], r["detail"])
                  for r in store.task_steps(store.db(), self.TASK)]
        failed = [d for a, d in actions if a == "pre-flight FAILED"]
        self.assertEqual(len(failed), 1, "ровно одна запись — без ретраев")
        self.assertIn("claude setup-token", failed[0], "причина несёт починку")
        self.assertNotIn("agent run started", [a for a, _ in actions],
                         "агент не стартовал вовсе")

    def test_task_state_is_untouched_by_a_preflight_failure(self):
        """Провал pre-flight — не эскалация: шаг просто не начат."""
        with mock.patch.object(runner.keychain, "token", lambda slot: None), \
                mock.patch.object(runner.subprocess, "Popen"):
            capture(runner.cmd_run, self.TASK)

        self.assertEqual(store.get_task(store.db(), self.TASK)["state"], "in_dev")

    def test_token_present_lets_the_step_start(self):
        """Контроль: сам pre-flight не мешает обычному запуску."""
        with mock.patch.object(runner.subprocess, "Popen",
                               side_effect=claude_only_popen(
                                   FakeAgentProc(["готово\n"]))) as popen:
            capture(runner.cmd_run, self.TASK)

        claude_calls = [c for c in popen.call_args_list
                       if c.args and c.args[0] and c.args[0][0] == "claude"]
        self.assertEqual(len(claude_calls), 1, "агент стартовал ровно один раз")


class IsolationSmokeTest(TmpRootTest):
    """Критерий 3: маркеры project-/user-слоя не достигают env/промпта роли."""

    def test_clean_isolation_passes(self):
        check = doctor.isolation_smoke()

        self.assertEqual(check.status, "ok", check.detail)

    def test_broken_isolation_is_caught(self):
        """Мутация: `role_env` «протекает» маркером — смоук обязан это поймать."""
        leaking_env = {"HOME": "/tmp/leaked", "LEAK": doctor.ISOLATION_MARKER}
        with mock.patch.object(doctor.runner, "role_env",
                               return_value=leaking_env):
            check = doctor.isolation_smoke()

        self.assertEqual(check.status, "fail")
        self.assertIn("user-слой", check.detail)

    def test_project_layer_marker_leak_is_caught(self):
        """Мутация другого класса: промпт роли «прочитал» CLAUDE.md рабочего каталога."""
        real_read_text = Path.read_text

        def leaking_read_text(self_path, *args, **kwargs):
            text = real_read_text(self_path, *args, **kwargs)
            if self_path.name == "conventions-core.md":
                return text + doctor.ISOLATION_MARKER
            return text

        with mock.patch.object(Path, "read_text", leaking_read_text):
            check = doctor.isolation_smoke()

        self.assertEqual(check.status, "fail")
        self.assertIn("промпт роли", check.detail)


class RecoveryCheckTest(TmpRootTest):
    """Критерий 4: recovery-сверка ловит расхождение sha и грязный репо."""

    TASK = "SLED-T001"

    def setUp(self):
        super().setUp()
        config.TARGETS.write_text(TARGETS_YAML_WITH_SLED, encoding="utf-8")
        capture(projects.cmd_target_init, "sled")
        store.insert_task(store.db(), self.TASK, "Задача sled", "in_dev",
                          f"task/{self.TASK.lower()}", "sled", 25.0)

    def repo(self) -> Path:
        return config.PROJECTS / "sled"

    def commit_artifact(self, name: str = "SPEC.md") -> str:
        tdir = self.repo() / "tasks" / self.TASK
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / name).write_text("артефакт\n", encoding="utf-8")
        gitcmd.in_repo(self.repo(), "add", "-A")
        gitcmd.in_repo(self.repo(), "-c", "user.name=t", "-c",
                       "user.email=t@t.invalid", "commit", "-q", "-m", "фиксация")
        return gitcmd.head_sha(self.repo())

    def test_healthy_repo_recovery_is_ok(self):
        sha = self.commit_artifact()
        store.update_task(store.db(), self.TASK, fixed_sha=sha)

        checks = doctor.recovery_check(store.db(), "sled")

        statuses = {c.name: c.status for c in checks}
        self.assertEqual(statuses["recovery-sha"], "ok")
        self.assertEqual(statuses["recovery-clean"], "ok")
        self.assertEqual(alerts.open_alerts(store.db(), "incident"), [])

    def test_sha_mismatch_raises_an_incident_alert(self):
        self.commit_artifact()
        store.update_task(store.db(), self.TASK, fixed_sha="0" * 40)

        checks = doctor.recovery_check(store.db(), "sled")

        by_name = {c.name: c for c in checks}
        self.assertEqual(by_name["recovery-sha"].status, "fail")
        incidents = alerts.open_alerts(store.db(), "incident")
        self.assertEqual(len(incidents), 1)
        self.assertEqual(incidents[0]["target"], "sled")
        self.assertIn("sha", incidents[0]["message"])

    def test_dirty_working_copy_raises_an_incident_alert(self):
        sha = self.commit_artifact()
        store.update_task(store.db(), self.TASK, fixed_sha=sha)
        (self.repo() / "tasks" / self.TASK / "SPEC.md").write_text(
            "незакоммиченная правка\n", encoding="utf-8")

        checks = doctor.recovery_check(store.db(), "sled")

        by_name = {c.name: c for c in checks}
        self.assertEqual(by_name["recovery-clean"].status, "fail")
        incidents = alerts.open_alerts(store.db(), "incident")
        self.assertTrue(any("грязный" in a["message"] for a in incidents))

    def test_dogfood_is_out_of_scope(self):
        checks = doctor.recovery_check(store.db(), config.DEFAULT_TARGET)

        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0].status, "skip")


class ProgramThresholdAlertTest(TmpRootTest):
    """Критерий 5: пороги 70/90% программы — alerts kind=threshold, без дублей."""

    TASK = "T001"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_new, "Порог программы")

    def test_crossing_seventy_percent_creates_a_threshold_alert(self):
        store.update_task(store.db(), self.TASK,
                          spent_usd=config.PROGRAM_STOP_LOSS_USD * 0.7 - 1)
        cost = {"usd": 2.0, "tokens": None}
        conn = store.db()
        # Тот же порядок, что и в `runner.run_agent_once`: стоимость
        # учитывается в spent_usd ДО проверки порога, порог считает уже
        # пересечённую сумму (tests/test_multitarget.py::ProgramSpendTest).
        spend.charge_step(conn, self.TASK, "developer", cost, "1/1")

        budget.check_program_spend(conn, self.TASK, cost)

        thresholds = alerts.open_alerts(store.db(), "threshold")
        self.assertEqual(len(thresholds), 1)
        self.assertIn("70%", thresholds[0]["message"])

    def test_repeated_alert_is_not_duplicated(self):
        ok1 = alerts.raise_alert(store.db(), None, "threshold",
                                 "budget.program_spend", "порог 70%")
        ok2 = alerts.raise_alert(store.db(), None, "threshold",
                                 "budget.program_spend", "порог 70%")

        self.assertTrue(ok1)
        self.assertFalse(ok2)
        self.assertEqual(len(alerts.open_alerts(store.db(), "threshold")), 1)

    def test_after_ack_the_same_condition_can_alert_again(self):
        alerts.raise_alert(store.db(), None, "threshold", "src", "снова")
        row = alerts.open_alerts(store.db(), "threshold")[0]
        alerts.ack(store.db(), row["id"], "operator", "")

        again = alerts.raise_alert(store.db(), None, "threshold", "src", "снова")

        self.assertTrue(again)
        self.assertEqual(len(alerts.open_alerts(store.db(), "threshold")), 1)


class AlertAckTest(TmpRootTest):
    """Критерий 6: ack триггера без решения — отказ."""

    def test_trigger_ack_without_resolution_is_refused(self):
        alerts.raise_alert(store.db(), None, "trigger", "docs/triggers.md#1",
                           "SQLITE_BUSY замечен")
        alert_id = alerts.open_alerts(store.db(), "trigger")[0]["id"]

        error = alerts.ack(store.db(), alert_id, "operator", "")

        self.assertIsNotNone(error)
        self.assertIn("решение", error)
        self.assertEqual(len(alerts.open_alerts(store.db(), "trigger")), 1,
                         "алерт остался неподтверждённым")

    def test_trigger_ack_with_resolution_succeeds(self):
        alerts.raise_alert(store.db(), None, "trigger", "docs/triggers.md#1",
                           "SQLITE_BUSY замечен")
        alert_id = alerts.open_alerts(store.db(), "trigger")[0]["id"]

        error = alerts.ack(store.db(), alert_id, "operator", "отложено до C0")

        self.assertIsNone(error)
        self.assertEqual(alerts.open_alerts(store.db(), "trigger"), [])

    def test_incident_ack_without_resolution_is_allowed(self):
        alerts.raise_alert(store.db(), "sled", "incident", "doctor.orphans.dir",
                           "каталог без строки БД")
        alert_id = alerts.open_alerts(store.db(), "incident")[0]["id"]

        error = alerts.ack(store.db(), alert_id, "operator", "")

        self.assertIsNone(error)

    def test_cli_ack_without_resolution_refuses_a_trigger(self):
        alerts.raise_alert(store.db(), None, "trigger", "docs/triggers.md#2",
                           "поток задач высокий")
        alert_id = alerts.open_alerts(store.db(), "trigger")[0]["id"]

        with self.assertRaises(SystemExit):
            capture(doctor.cmd_alert_ack, str(alert_id), "")

        self.assertEqual(len(alerts.open_alerts(store.db(), "trigger")), 1)

    def test_cli_ack_with_resolution_succeeds(self):
        alerts.raise_alert(store.db(), None, "trigger", "docs/triggers.md#2",
                           "поток задач высокий")
        alert_id = alerts.open_alerts(store.db(), "trigger")[0]["id"]

        out = capture(doctor.cmd_alert_ack, str(alert_id), "внедряем — задача N")

        self.assertIn("подтверждён", out)
        self.assertEqual(alerts.open_alerts(store.db(), "trigger"), [])


class OrphansTest(TmpRootTest):
    """Критерий 7: каталог без строки БД, ветка done-задачи, worktree без
    задачи — три алерта kind=incident."""

    def test_orphan_task_dir_without_a_db_row(self):
        (config.TASKS / "T777").mkdir(parents=True)

        checks = doctor.check_orphans(store.db())

        by_name = {c.name: c for c in checks}
        self.assertEqual(by_name["orphans-dirs"].status, "fail")
        incidents = [a for a in alerts.open_alerts(store.db(), "incident")
                    if a["source"] == "doctor.orphans.dir"]
        self.assertEqual(len(incidents), 1)
        self.assertIn("T777", incidents[0]["message"])

    def test_done_task_branch_not_cleaned_up(self):
        capture(catalog.cmd_init)
        store.insert_task(store.db(), "T001", "Готова", "done",
                          "task/t001-gotova", config.DEFAULT_TARGET, 25.0)
        with mock.patch.object(doctor.gitcmd, "branch_exists",
                               lambda b: b == "task/t001-gotova"):
            checks = doctor.check_orphans(store.db())

        by_name = {c.name: c for c in checks}
        self.assertEqual(by_name["orphans-branches"].status, "fail")
        incidents = [a for a in alerts.open_alerts(store.db(), "incident")
                    if a["source"] == "doctor.orphans.branch"]
        self.assertEqual(len(incidents), 1)
        self.assertIn("task/t001-gotova", incidents[0]["message"])

    def test_worktree_without_a_task_is_an_orphan(self):
        porcelain = ("worktree /main\nHEAD abc\n\n"
                    "worktree /some/other/worktree\nHEAD def\n\n")
        with mock.patch.object(doctor.gitcmd, "git",
                               lambda *a: subprocess.CompletedProcess(
                                   list(a), 0, porcelain, "")):
            checks = doctor.check_orphans(store.db())

        by_name = {c.name: c for c in checks}
        self.assertEqual(by_name["orphans-worktrees"].status, "fail")
        incidents = [a for a in alerts.open_alerts(store.db(), "incident")
                    if a["source"] == "doctor.orphans.worktree"]
        self.assertEqual(len(incidents), 1)
        self.assertIn("/some/other/worktree", incidents[0]["message"])

    def test_all_three_orphan_kinds_at_once(self):
        (config.TASKS / "T777").mkdir(parents=True)
        store.insert_task(store.db(), "T001", "Готова", "done",
                          "task/t001-gotova", config.DEFAULT_TARGET, 25.0)
        porcelain = "worktree /main\nHEAD abc\n\nworktree /extra\nHEAD def\n\n"

        with mock.patch.object(doctor.gitcmd, "branch_exists",
                               lambda b: b == "task/t001-gotova"), \
                mock.patch.object(doctor.gitcmd, "git",
                                  lambda *a: subprocess.CompletedProcess(
                                      list(a), 0, porcelain, "")
                                  if a[:2] == ("worktree", "list")
                                  else subprocess.CompletedProcess(list(a), 1, "", "")):
            checks = doctor.check_orphans(store.db())

        failed = {c.name for c in checks if c.status == "fail"}
        self.assertEqual(failed,
                         {"orphans-dirs", "orphans-branches", "orphans-worktrees"})
        self.assertEqual(len(alerts.open_alerts(store.db(), "incident")), 3)

    def test_clean_repo_has_no_orphans(self):
        checks = doctor.check_orphans(store.db())

        self.assertTrue(all(c.status == "ok" for c in checks))
        self.assertEqual(alerts.open_alerts(store.db(), "incident"), [])


class LiveSmokeTest(TmpRootTest):
    """Критерий 8: команда есть; тест — с подменённым CLI (реальный прогон — manual)."""

    def test_success_reports_ok_with_cost(self):
        with mock.patch.object(doctor.subprocess, "Popen", side_effect=claude_only_popen(
                FakeLiveSmokeProc(result_event(0.0123)))):
            check = doctor.live_smoke()

        self.assertEqual(check.status, "ok")
        self.assertIn("0.0123", check.detail)

    def test_nonzero_return_code_fails(self):
        with mock.patch.object(doctor.subprocess, "Popen", side_effect=claude_only_popen(
                FakeLiveSmokeProc("упал\n", returncode=1))):
            check = doctor.live_smoke()

        self.assertEqual(check.status, "fail")
        self.assertIn("rc=1", check.detail)

    def test_missing_cost_event_fails(self):
        with mock.patch.object(doctor.subprocess, "Popen", side_effect=claude_only_popen(
                FakeLiveSmokeProc("готово, без cost\n"))):
            check = doctor.live_smoke()

        self.assertEqual(check.status, "fail")
        self.assertIn("стоимост", check.detail)

    def test_cli_not_found_fails(self):
        def popen(cmd, *args, **kwargs):
            if cmd and cmd[0] == "claude":
                raise FileNotFoundError()
            return REAL_POPEN(cmd, *args, **kwargs)

        with mock.patch.object(doctor.subprocess, "Popen", side_effect=popen):
            check = doctor.live_smoke()

        self.assertEqual(check.status, "fail")
        self.assertIn("не найден", check.detail)

    def test_command_exists_and_is_wired_into_doctor(self):
        self.assertTrue(callable(doctor.live_smoke))
        self.assertTrue(callable(doctor.cmd_doctor))


if __name__ == "__main__":
    unittest.main()
