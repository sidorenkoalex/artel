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
import os
import shutil
import socket
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
from tests.sandbox import (TmpRootTest, capture, claude_only_popen,  # noqa: E402
                           claude_only_run, fake_git)

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


class _DoctorTmpRootTest(TmpRootTest):
    """Песочница doctor: пути `config` — во временном каталоге, keychain подменён."""

    def setUp(self):
        super().setUp()
        shutil.copytree(REPO_ROOT / "skills", self.root / "skills")
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        # T028: бриф роли developer/analyst читает docs/codebase-map.md и
        # CLAUDE.md из config.ROOT — без них шаг developer падает ENOENT
        # ещё до pre-flight-сценариев, которые эта песочница проверяет.
        (self.root / "docs").mkdir()
        (self.root / "docs" / "codebase-map.md").write_text(
            "---\nbuilt_at_sha: 0000000000000000000000000000000000000000\n"
            "---\n\n# Карта\n", encoding="utf-8")
        (self.root / "CLAUDE.md").write_text("# Конвенции\n", encoding="utf-8")

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

        # Эта песочница — про doctor/pre-flight, не про worktree-механику
        # (SPEC T045): `self.root` не настоящий git-репозиторий (никогда
        # им не был — до T045 `role_cwd` для догфуда возвращал `config.ROOT`
        # без единого git-вызова), а часть сценариев (recovery, orphans)
        # заводят СВОЙ настоящий git внешнего target — фейк `gitcmd.git`
        # здесь, на общем уровне, сломал бы их. Классам, которым нужен
        # `cmd_new` (SPEC T048: сам заводит ветку/worktree и коммитит в
        # них через `gitcmd`), фейк ставит их собственный `setUp`.

    def new_task_in_fake_git(self, title: str) -> str:
        """`cmd_new` под фейком `gitcmd.git`, тем же приёмом, что и в
        остальных песочницах без настоящего git; SPEC.md/TZ.md кладёт в
        worktree (требование 2) — эта песочница читает их с диска main
        (`gitcmd.on_foreign_branch` тут всегда False из-за фейка), так
        что то же содержимое дублируется на диск main для брифа роли."""
        git_patcher = mock.patch.object(gitcmd, "git", fake_git)
        git_patcher.start()
        self.addCleanup(git_patcher.stop)
        out = capture(catalog.cmd_new, title)
        task_id = out.split("]")[0].strip("[")
        wt_spec = config.WORKTREES / task_id / "tasks" / task_id / "SPEC.md"
        disk_dir = config.TASKS / task_id
        disk_dir.mkdir(parents=True, exist_ok=True)
        (disk_dir / "SPEC.md").write_text(
            wt_spec.read_text(encoding="utf-8"), encoding="utf-8")
        return out

    def touch_backup(self) -> None:
        config.BACKUP_MARKER.parent.mkdir(parents=True, exist_ok=True)
        config.BACKUP_MARKER.write_text("ok", encoding="utf-8")


TmpRootTest = _DoctorTmpRootTest


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
        self.new_task_in_fake_git("Задача под pre-flight")
        store.update_task(store.db(), self.TASK, state="in_dev")
        # CLI на машине прогона может отсутствовать (CI-раннер) — проверки
        # токена/идентичности не должны зависеть от cli-found: он тестируется
        # отдельно, здесь всегда ok.
        cli_patcher = mock.patch.object(
            doctor, "check_cli_found",
            lambda: doctor.Check("cli-found", "ok", "/stub/claude"))
        cli_patcher.start()
        self.addCleanup(cli_patcher.stop)

    def test_missing_token_blocks_the_step_with_a_named_reason_and_no_retries(self):
        with mock.patch.object(runner.keychain, "token", lambda slot: None), \
                mock.patch.object(runner, "spawn_agent") as popen:
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
                mock.patch.object(runner, "spawn_agent"):
            capture(runner.cmd_run, self.TASK)

        self.assertEqual(store.get_task(store.db(), self.TASK)["state"], "in_dev")

    def test_token_present_lets_the_step_start(self):
        """Контроль: сам pre-flight не мешает обычному запуску."""
        with mock.patch.object(runner, "spawn_agent",
                               side_effect=claude_only_popen(
                                   FakeAgentProc(["готово\n"]))) as popen:
            capture(runner.cmd_run, self.TASK)

        claude_calls = [c for c in popen.call_args_list
                       if c.args and c.args[0] and c.args[0][0] == "claude"]
        self.assertEqual(len(claude_calls), 1, "агент стартовал ровно один раз")

    def test_git_identity_is_part_of_preflight(self):
        """Требование 2: git-идентичность — тоже пункт pre-flight, не только doctor."""
        checks = doctor.preflight_checks("developer", config.DEFAULT_TARGET)

        self.assertIn("git-identity", [c.name for c in checks])

    def test_broken_identity_warns_but_does_not_block_the_step(self):
        def no_identity(*args):
            # Только запросы идентичности отвечают отказом — остальное
            # (в частности `workspace.ensure` внутри `role_cwd`, SPEC
            # T045/T048) идёт тем же фейком, что и в `setUp`, иначе
            # рабочий каталог роли не готовится вовсе и шаг не стартует
            # по совсем другой причине, не той, что проверяет этот тест.
            if args[:2] == ("config", "--get"):
                return subprocess.CompletedProcess(args, 1, "", "")
            return fake_git(*args)

        # Гасим ambient GIT_AUTHOR_*/GIT_COMMITTER_* машины, где гоняются
        # тесты — иначе `env.setdefault` в `role_env` подставляет реальную
        # идентичность машины раньше замоканного `gitcmd.git` (тот же приём,
        # что и в `TmpRootTest.setUp` для CLAUDE_CODE_OAUTH_TOKEN).
        no_env = {"GIT_AUTHOR_NAME": "", "GIT_AUTHOR_EMAIL": "",
                  "GIT_COMMITTER_NAME": "", "GIT_COMMITTER_EMAIL": ""}
        with mock.patch.object(runner.gitcmd, "git", no_identity), \
                mock.patch.dict("os.environ", no_env), \
                mock.patch.object(runner, "spawn_agent",
                                  side_effect=claude_only_popen(
                                      FakeAgentProc(["готово\n"]))) as popen:
            out = capture(runner.cmd_run, self.TASK)

        self.assertIn("git-identity", out)
        claude_calls = [c for c in popen.call_args_list
                       if c.args and c.args[0] and c.args[0][0] == "claude"]
        self.assertEqual(len(claude_calls), 1, "предупреждение не блокирует шаг")

    def test_blocking_failure_makes_no_subprocess_calls_at_all(self):
        """Регресс: провал по токену не должен тянуть за собой git-идентичность
        (а с ней — subprocess) — блок уже решён, платить нечем за доп. warn."""
        with mock.patch.object(runner.keychain, "token", lambda slot: None), \
                mock.patch.object(runner, "spawn_agent") as popen:
            capture(runner.cmd_run, self.TASK)

        popen.assert_not_called()


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

    def test_project_hook_setting_source_leak_is_caught(self):
        """Мутация третьего класса (SPEC T058): `--setting-sources` шага
        роли перестал исключать project-/local-слой (в т.ч. хуки, инцидент
        T046) — смоук обязан это поймать."""
        with mock.patch.object(doctor.config, "AGENT_SETTING_SOURCES",
                               "user,project"):
            check = doctor.isolation_smoke()

        self.assertEqual(check.status, "fail")
        self.assertIn("project-хук", check.detail)

    def test_local_setting_source_leak_is_also_caught(self):
        with mock.patch.object(doctor.config, "AGENT_SETTING_SOURCES",
                               "local"):
            check = doctor.isolation_smoke()

        self.assertEqual(check.status, "fail")
        self.assertIn("project-хук", check.detail)


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


class BaseBranchCheckTest(unittest.TestCase):
    """tasks/T032/SPEC.md: догфуд-skip и поведение для внешнего target."""

    EXTERNAL_ENTRY = {
        "forge": "github",
        "url": "https://example.invalid/sled",
        "base": "main",
    }

    def test_dogfood_target_is_skipped_without_calling_gh(self):
        entry = {"forge": "github", "url": "https://example.invalid/artel",
                 "base": "main"}

        with mock.patch.object(doctor.shutil, "which",
                               return_value="/usr/bin/gh"), \
             mock.patch.object(doctor.subprocess, "run") as run:
            check = doctor.check_base_branch(config.DEFAULT_TARGET, entry)

        self.assertEqual(check.status, "skip")
        run.assert_not_called()
        self.assertIn("догфуд", check.detail.lower())

    def test_non_github_forge_is_skipped(self):
        entry = dict(self.EXTERNAL_ENTRY, forge="gitlab")

        check = doctor.check_base_branch("sled", entry)

        self.assertEqual(check.status, "skip")

    def test_missing_gh_cli_is_skipped(self):
        with mock.patch.object(doctor.shutil, "which", return_value=None):
            check = doctor.check_base_branch("sled", self.EXTERNAL_ENTRY)

        self.assertEqual(check.status, "skip")

    def test_matching_base_branch_is_ok(self):
        def fake_run(args, **kwargs):
            return subprocess.CompletedProcess(args, 0, "main\n", "")

        with mock.patch.object(doctor.shutil, "which",
                               return_value="/usr/bin/gh"), \
             mock.patch.object(doctor.subprocess, "run",
                               side_effect=fake_run):
            check = doctor.check_base_branch("sled", self.EXTERNAL_ENTRY)

        self.assertEqual(check.status, "ok")

    def test_diverging_base_branch_is_warn(self):
        def fake_run(args, **kwargs):
            return subprocess.CompletedProcess(args, 0, "develop\n", "")

        with mock.patch.object(doctor.shutil, "which",
                               return_value="/usr/bin/gh"), \
             mock.patch.object(doctor.subprocess, "run",
                               side_effect=fake_run):
            check = doctor.check_base_branch("sled", self.EXTERNAL_ENTRY)

        self.assertEqual(check.status, "warn")


class ProgramThresholdAlertTest(TmpRootTest):
    """Критерий 5: пороги 70/90% программы — alerts kind=threshold, без дублей."""

    TASK = "T001"

    def setUp(self):
        super().setUp()
        self.new_task_in_fake_git("Порог программы")

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


class LeasesCheckTest(TmpRootTest):
    """SPEC T044, требование 11: lease с мёртвым pid на этом host — incident.

    AC-6 (tasks/T044/acceptance_tests) уже кроет golden path одного
    мёртвого и одного живого lease; здесь — форма результата и края,
    которые критерию не нужны (несколько мёртвых, чужой host, пустая
    таблица), по образцу `OrphansTest`.
    """

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        for task_id in ("T001", "T002"):
            store.insert_task(store.db(), task_id, "Задача", "in_dev",
                              f"task/{task_id.lower()}-zadacha",
                              config.DEFAULT_TARGET, 25.0)

    @staticmethod
    def dead_pid() -> int:
        proc = subprocess.Popen([sys.executable, "-c", "pass"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
        return proc.pid

    def test_empty_leases_table_is_ok(self):
        checks = doctor.check_leases(store.db())

        self.assertTrue(all(c.status == "ok" for c in checks))
        self.assertEqual(alerts.open_alerts(store.db(), "incident"), [])

    def test_foreign_host_dead_pid_is_not_flagged(self):
        """Чужой host: pid из чужой процессной таблицы нельзя ни
        подтвердить мёртвым, ни живым — не проверяется вовсе."""
        conn = store.db()
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            ("T001", "sess", self.dead_pid(), "other-host.invalid", store.now()))
        conn.commit()

        checks = doctor.check_leases(store.db())

        self.assertTrue(all(c.status != "fail" for c in checks))
        self.assertEqual(alerts.open_alerts(store.db(), "incident"), [])

    def test_multiple_dead_leases_each_raise_their_own_incident(self):
        conn = store.db()
        host = socket.gethostname()
        for task_id in ("T001", "T002"):
            conn.execute(
                "INSERT INTO leases (task_id, session_id, pid, hostname,"
                " heartbeat_ts) VALUES (?,?,?,?,?)",
                (task_id, f"sess-{task_id}", self.dead_pid(), host, store.now()))
        conn.commit()

        checks = doctor.check_leases(store.db())

        failed = [c for c in checks if c.status == "fail"]
        self.assertEqual(len(failed), 2)
        incidents = [a for a in alerts.open_alerts(store.db(), "incident")
                    if a["source"] == "doctor.leases"]
        self.assertEqual(len(incidents), 2)
        messages = [i["message"] for i in incidents]
        self.assertTrue(any("T001" in m for m in messages))
        self.assertTrue(any("T002" in m for m in messages))

    def test_repeated_run_does_not_duplicate_the_incident(self):
        """Дедуп — по тому же ключу (target, kind, source, message), что и
        остальные incident-алерты doctor (`alerts.raise_alert`)."""
        conn = store.db()
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            ("T001", "sess", self.dead_pid(), socket.gethostname(), store.now()))
        conn.commit()

        doctor.check_leases(store.db())
        doctor.check_leases(store.db())

        incidents = [a for a in alerts.open_alerts(store.db(), "incident")
                    if a["source"] == "doctor.leases"]
        self.assertEqual(len(incidents), 1)

    def test_row_removed_is_auto_acked_on_next_run(self):
        """SPEC T054, требование 1 (AC-1): строка снята -> auto-ack."""
        conn = store.db()
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            ("T001", "sess", self.dead_pid(), socket.gethostname(), store.now()))
        conn.commit()
        doctor.check_leases(conn)
        alert_id = [a for a in alerts.open_alerts(conn, "incident")
                   if a["source"] == "doctor.leases"][0]["id"]

        store.release_lease(conn, "T001", "sess")
        doctor.check_leases(conn)

        self.assertIsNotNone(store.get_alert(conn, alert_id)["ack_ts"])

    def test_pid_becomes_alive_is_auto_acked_on_next_run(self):
        """SPEC T054, требование 1 (AC-1): pid жив -> auto-ack."""
        conn = store.db()
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            ("T001", "sess", self.dead_pid(), socket.gethostname(), store.now()))
        conn.commit()
        doctor.check_leases(conn)
        alert_id = [a for a in alerts.open_alerts(conn, "incident")
                   if a["source"] == "doctor.leases"][0]["id"]

        store.update_lease(conn, "T001", "sess", os.getpid(),
                           socket.gethostname(), store.now())
        doctor.check_leases(conn)

        self.assertIsNotNone(store.get_alert(conn, alert_id)["ack_ts"])

    def test_dead_pid_still_present_is_not_auto_acked(self):
        """SPEC T054, требование 1 (AC-1): условие в силе -> не auto-ack."""
        conn = store.db()
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            ("T001", "sess", self.dead_pid(), socket.gethostname(), store.now()))
        conn.commit()
        doctor.check_leases(conn)
        alert_id = [a for a in alerts.open_alerts(conn, "incident")
                   if a["source"] == "doctor.leases"][0]["id"]

        doctor.check_leases(conn)

        self.assertIsNone(store.get_alert(conn, alert_id)["ack_ts"])


class MergeLockCheckTest(TmpRootTest):
    """SPEC T053, требование 4: мёртвый держатель мьютекса merge —
    incident-алерт; SPEC T054, требование 2 (AC-2): тот же алерт закрывается
    авто-ack'ом, когда условие исчезло."""

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        for task_id in ("T001", "T002"):
            store.insert_task(store.db(), task_id, "Задача", "in_dev",
                              f"task/{task_id.lower()}-zadacha",
                              config.DEFAULT_TARGET, 25.0)

    @staticmethod
    def dead_pid() -> int:
        proc = subprocess.Popen([sys.executable, "-c", "pass"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
        return proc.pid

    def test_empty_lock_is_ok(self):
        checks = doctor.check_merge_lock(store.db())

        self.assertTrue(all(c.status == "ok" for c in checks))
        self.assertEqual(alerts.open_alerts(store.db(), "incident"), [])

    def test_foreign_host_dead_pid_is_not_flagged(self):
        conn = store.db()
        store.set_merge_lock(conn, "T001", "sess", self.dead_pid(),
                             "other-host.invalid", store.now())

        checks = doctor.check_merge_lock(conn)

        self.assertTrue(all(c.status != "fail" for c in checks))
        self.assertEqual(alerts.open_alerts(conn, "incident"), [])

    def test_dead_holder_on_this_host_raises_an_incident(self):
        conn = store.db()
        store.set_merge_lock(conn, "T001", "sess", self.dead_pid(),
                             socket.gethostname(), store.now())

        checks = doctor.check_merge_lock(conn)

        self.assertTrue(any(c.status == "fail" for c in checks))
        incidents = [a for a in alerts.open_alerts(conn, "incident")
                    if a["source"] == "doctor.merge_lock"]
        self.assertEqual(len(incidents), 1)
        self.assertIn("T001", incidents[0]["message"])

    def test_repeated_run_does_not_duplicate_the_incident(self):
        conn = store.db()
        store.set_merge_lock(conn, "T001", "sess", self.dead_pid(),
                             socket.gethostname(), store.now())

        doctor.check_merge_lock(conn)
        doctor.check_merge_lock(conn)

        incidents = [a for a in alerts.open_alerts(conn, "incident")
                    if a["source"] == "doctor.merge_lock"]
        self.assertEqual(len(incidents), 1)

    def test_lock_cleared_is_auto_acked_on_next_run(self):
        conn = store.db()
        store.set_merge_lock(conn, "T001", "sess", self.dead_pid(),
                             socket.gethostname(), store.now())
        doctor.check_merge_lock(conn)
        alert_id = [a for a in alerts.open_alerts(conn, "incident")
                   if a["source"] == "doctor.merge_lock"][0]["id"]

        store.release_merge_lock(conn, "sess")
        doctor.check_merge_lock(conn)

        self.assertIsNotNone(store.get_alert(conn, alert_id)["ack_ts"])

    def test_holder_changed_is_auto_acked_on_next_run(self):
        conn = store.db()
        store.set_merge_lock(conn, "T001", "sess-1", self.dead_pid(),
                             socket.gethostname(), store.now())
        doctor.check_merge_lock(conn)
        alert_id = [a for a in alerts.open_alerts(conn, "incident")
                   if a["source"] == "doctor.merge_lock"][0]["id"]

        store.set_merge_lock(conn, "T002", "sess-2", self.dead_pid(),
                             socket.gethostname(), store.now())
        doctor.check_merge_lock(conn)

        self.assertIsNotNone(store.get_alert(conn, alert_id)["ack_ts"])

    def test_holder_pid_becomes_alive_is_auto_acked_on_next_run(self):
        conn = store.db()
        store.set_merge_lock(conn, "T001", "sess", self.dead_pid(),
                             socket.gethostname(), store.now())
        doctor.check_merge_lock(conn)
        alert_id = [a for a in alerts.open_alerts(conn, "incident")
                   if a["source"] == "doctor.merge_lock"][0]["id"]

        store.set_merge_lock(conn, "T001", "sess", os.getpid(),
                             socket.gethostname(), store.now())
        doctor.check_merge_lock(conn)

        self.assertIsNotNone(store.get_alert(conn, alert_id)["ack_ts"])

    def test_dead_holder_remains_is_not_auto_acked(self):
        conn = store.db()
        store.set_merge_lock(conn, "T001", "sess", self.dead_pid(),
                             socket.gethostname(), store.now())
        doctor.check_merge_lock(conn)
        alert_id = [a for a in alerts.open_alerts(conn, "incident")
                   if a["source"] == "doctor.merge_lock"][0]["id"]

        doctor.check_merge_lock(conn)

        self.assertIsNone(store.get_alert(conn, alert_id)["ack_ts"])


class BranchFreshnessCheckTest(TmpRootTest):
    """SPEC T051, требование 8 (AC-5): активная задача с веткой, отставшей
    от `config.MAIN_BRANCH` больше чем на `config.STALE_BRANCH_WARN_COMMITS`
    коммитов, — warn, не incident (см. PLAN «Подход»); требование 9 (AC-6)
    — git не отвечающий осмысленно пропускается молча, по образцу
    `LeasesCheckTest`/`OrphansTest`.
    """

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)

    def test_stale_active_task_warns(self):
        store.insert_task(store.db(), "T001", "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)
        with mock.patch.object(doctor.gitcmd, "commits_behind",
                               lambda b: config.STALE_BRANCH_WARN_COMMITS + 1):
            checks = doctor.check_branch_freshness(store.db())

        self.assertTrue(any(c.status == "warn" for c in checks))
        self.assertIn("T001", checks[0].detail)
        self.assertEqual(alerts.open_alerts(store.db(), "incident"), [],
                         "отставание ветки — не incident (не ack-целевой)")

    def test_exactly_at_the_threshold_is_ok(self):
        store.insert_task(store.db(), "T001", "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)
        with mock.patch.object(doctor.gitcmd, "commits_behind",
                               lambda b: config.STALE_BRANCH_WARN_COMMITS):
            checks = doctor.check_branch_freshness(store.db())

        self.assertTrue(all(c.status == "ok" for c in checks))

    def test_terminal_tasks_are_not_checked(self):
        store.insert_task(store.db(), "T001", "Готова", "done",
                          "task/t001-gotova", config.DEFAULT_TARGET, 25.0)
        checked_branches = []
        with mock.patch.object(
                doctor.gitcmd, "commits_behind",
                lambda b: checked_branches.append(b) or 999):
            checks = doctor.check_branch_freshness(store.db())

        self.assertEqual(checked_branches, [])
        self.assertTrue(all(c.status == "ok" for c in checks))

    def test_unresponsive_git_is_silently_skipped(self):
        store.insert_task(store.db(), "T001", "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)
        with mock.patch.object(doctor.gitcmd, "commits_behind",
                               lambda b: None):
            checks = doctor.check_branch_freshness(store.db())

        self.assertTrue(all(c.status == "ok" for c in checks))

    def test_no_active_tasks_is_ok(self):
        checks = doctor.check_branch_freshness(store.db())

        self.assertTrue(all(c.status == "ok" for c in checks))
        self.assertEqual(alerts.open_alerts(store.db(), "incident"), [])


class TaskCounterCheckTest(TmpRootTest):
    """SPEC T049, требование 3 (AC-2): счётчик номеров target'а ниже
    наблюдаемого max — incident; на уровне или выше — здоровое состояние.

    Сквозной путь (посев через `cmd_init`, реальный git) уже покрыт
    `tasks/T049/acceptance_tests/test_ac2_doctor_counter_incident.py` —
    здесь `check_task_counters` дёргается напрямую, без git (наблюдаемый
    max в этой песочнице приходит только от каталогов `tasks/T*`)."""

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)

    def test_counter_behind_observed_max_raises_an_incident(self):
        (config.TASKS / "T010").mkdir(parents=True)
        conn = store.db()
        conn.execute("UPDATE task_counters SET next_number=3 WHERE target=?",
                     (config.DEFAULT_TARGET,))
        conn.commit()

        check = doctor.check_task_counters(conn)

        self.assertEqual(check.status, "fail")
        incidents = [a for a in alerts.open_alerts(conn, "incident")
                    if a["source"] == "doctor.task_counter"]
        self.assertEqual(len(incidents), 1)
        self.assertIn(config.DEFAULT_TARGET, incidents[0]["message"])

    def test_counter_equal_to_observed_max_is_ok(self):
        conn = store.db()
        (config.TASKS / "T001").mkdir(parents=True)
        conn.execute("UPDATE task_counters SET next_number=1 WHERE target=?",
                     (config.DEFAULT_TARGET,))
        conn.commit()

        check = doctor.check_task_counters(conn)

        self.assertEqual(check.status, "ok")
        self.assertEqual(alerts.open_alerts(conn, "incident"), [])

    def test_counter_above_observed_max_is_ok(self):
        check = doctor.check_task_counters(store.db())

        self.assertEqual(check.status, "ok")
        self.assertEqual(alerts.open_alerts(store.db(), "incident"), [])

    def test_repeated_run_does_not_duplicate_the_incident(self):
        (config.TASKS / "T010").mkdir(parents=True)
        conn = store.db()
        conn.execute("UPDATE task_counters SET next_number=3 WHERE target=?",
                     (config.DEFAULT_TARGET,))
        conn.commit()

        doctor.check_task_counters(conn)
        doctor.check_task_counters(conn)

        incidents = [a for a in alerts.open_alerts(conn, "incident")
                    if a["source"] == "doctor.task_counter"]
        self.assertEqual(len(incidents), 1)


class BackupAgeDegradedCheckTest(TmpRootTest):
    """SPEC T049, требование 6 (AC-4): `check_backup_age` больше не заводит
    `incident` — ни при отсутствии маркера, ни при просроченном. До этой
    задачи (tasks/T022) отсутствие/просрочка маркера были гейтом; здесь —
    регресс-тест на то, что деградация действительно снята, а не только
    задокументирована."""

    def test_missing_marker_is_ok_without_an_incident(self):
        self.assertFalse(config.BACKUP_MARKER.exists())

        check = doctor.check_backup_age(store.db())

        self.assertEqual(check.status, "ok")
        self.assertEqual(alerts.open_alerts(store.db(), "incident"), [])

    def test_stale_marker_is_still_ok_without_an_incident(self):
        """Раньше просроченный (по мотивам T022) маркер заводил бы incident
        — здесь маркер искусственно состарен, а прогон остаётся `ok`."""
        self.touch_backup()
        old = time.time() - 999 * 86400
        os.utime(config.BACKUP_MARKER, (old, old))

        check = doctor.check_backup_age(store.db())

        self.assertEqual(check.status, "ok")
        self.assertEqual(alerts.open_alerts(store.db(), "incident"), [])

    def test_fresh_marker_reports_informational_ok(self):
        self.touch_backup()

        check = doctor.check_backup_age(store.db())

        self.assertEqual(check.status, "ok")
        self.assertIn("информационно", check.detail)


class AutoAckTest(TmpRootTest):
    """tasks/T035/SPEC.md, требования 1-7: авто-ack закрывает алерт, только
    когда его условие фактически исчезло; нераспознанный формат сообщения
    (дрейф формата разбора сущности) — безопасный отказ, не ack; авто-ack
    одного source не задевает открытые алерты другого.

    Пары AC-1/2, AC-3/4, AC-5/6, AC-7/8 (ack при исчезновении условия /
    не-ack, пока условие в силе) уже покрыты приёмочными тестами
    (tasks/T035/acceptance_tests/test_auto_ack.py) — здесь только то, чего
    там нет."""

    def test_auto_ack_records_actor_and_resolution(self):
        alerts.raise_alert(store.db(), config.DEFAULT_TARGET, "incident",
                           "doctor.orphans.dir", "T555 без строки БД")
        alert_id = alerts.open_alerts(store.db(), "incident")[0]["id"]

        alerts.auto_ack(store.db(), alert_id)

        row = store.get_alert(store.db(), alert_id)
        self.assertEqual(row["ack_by"], "doctor")
        self.assertIn("условие ушло, прогон doctor", row["ack_resolution"])

    def test_unrecognised_messages_are_left_open_on_next_run(self):
        cases = (
            ("doctor.orphans.branch", "ветка потерялась без стандартного текста"),
            ("doctor.orphans.dir", "каталог пропал без стандартного текста"),
            ("doctor.orphans.worktree", "worktree пропал без стандартного текста"),
        )
        for source, message in cases:
            with self.subTest(source=source):
                alerts.raise_alert(store.db(), config.DEFAULT_TARGET, "incident",
                                   source, message)
                alert_id = [a for a in alerts.open_alerts(store.db(), "incident")
                           if a["source"] == source][0]["id"]

                with mock.patch.object(
                        doctor.gitcmd, "git",
                        lambda *a: subprocess.CompletedProcess(list(a), 1, "", "")), \
                        mock.patch.object(doctor.gitcmd, "branch_exists",
                                          return_value=False):
                    doctor.check_orphans(store.db())

                self.assertIsNone(store.get_alert(store.db(), alert_id)["ack_ts"],
                                  "нераспознанное сообщение не должно закрываться")

    def test_backup_age_auto_ack_does_not_touch_orphan_sources(self):
        store.insert_task(store.db(), "T001", "чужой", "done",
                          "task/t001-x", config.DEFAULT_TARGET, 25.0)
        with mock.patch.object(doctor.gitcmd, "branch_exists", return_value=True):
            doctor.check_orphans(store.db())
        branch_alert = [a for a in alerts.open_alerts(store.db(), "incident")
                        if a["source"] == "doctor.orphans.branch"][0]

        config.BACKUP_MARKER.parent.mkdir(parents=True, exist_ok=True)
        config.BACKUP_MARKER.write_text("ok", encoding="utf-8")
        doctor.check_backup_age(store.db())

        self.assertIsNone(store.get_alert(store.db(), branch_alert["id"])["ack_ts"],
                          "авто-ack backup_age не должен трогать чужой source")


class LiveSmokeTest(TmpRootTest):
    """Критерий 8: команда есть; тест — с подменённым CLI (реальный прогон — manual)."""

    def test_success_reports_ok_with_cost(self):
        with mock.patch.object(doctor.subprocess, "Popen", side_effect=claude_only_popen(
                FakeLiveSmokeProc(result_event(0.0123)))):
            check = doctor.live_smoke(store.db())

        self.assertEqual(check.status, "ok")
        self.assertIn("0.0123", check.detail)
        self.assertEqual(alerts.open_alerts(store.db(), "incident"), [],
                         "успех не заводит алерт")

    def test_nonzero_return_code_fails(self):
        with mock.patch.object(doctor.subprocess, "Popen", side_effect=claude_only_popen(
                FakeLiveSmokeProc("упал\n", returncode=1))):
            check = doctor.live_smoke(store.db())

        self.assertEqual(check.status, "fail")
        self.assertIn("rc=1", check.detail)

    def test_missing_cost_event_fails(self):
        with mock.patch.object(doctor.subprocess, "Popen", side_effect=claude_only_popen(
                FakeLiveSmokeProc("готово, без cost\n"))):
            check = doctor.live_smoke(store.db())

        self.assertEqual(check.status, "fail")
        self.assertIn("стоимост", check.detail)

    def test_cli_not_found_fails(self):
        real_popen = subprocess.Popen

        def popen(cmd, *args, **kwargs):
            if cmd and cmd[0] == "claude":
                raise FileNotFoundError()
            return real_popen(cmd, *args, **kwargs)

        with mock.patch.object(doctor.subprocess, "Popen", side_effect=popen):
            check = doctor.live_smoke(store.db())

        self.assertEqual(check.status, "fail")
        self.assertIn("не найден", check.detail)

    def test_failure_result_is_journalled_as_an_incident_alert(self):
        """Требование 3: «результат в журнал» — провал не теряется вместе с stdout."""
        with mock.patch.object(doctor.subprocess, "Popen", side_effect=claude_only_popen(
                FakeLiveSmokeProc("упал\n", returncode=1))):
            check = doctor.live_smoke(store.db())

        incidents = alerts.open_alerts(store.db(), "incident")
        self.assertEqual(len(incidents), 1)
        self.assertEqual(incidents[0]["source"], "doctor.live_smoke")
        self.assertIn("rc=1", incidents[0]["message"])
        self.assertEqual(incidents[0]["message"], check.detail)

    def test_repeated_failure_does_not_duplicate_the_alert(self):
        with mock.patch.object(doctor.subprocess, "Popen", side_effect=claude_only_popen(
                FakeLiveSmokeProc("упал\n", returncode=1))):
            doctor.live_smoke(store.db())
            doctor.live_smoke(store.db())

        self.assertEqual(len(alerts.open_alerts(store.db(), "incident")), 1)

    def test_command_exists_and_is_wired_into_doctor(self):
        self.assertTrue(callable(doctor.live_smoke))
        self.assertTrue(callable(doctor.cmd_doctor))


if __name__ == "__main__":
    unittest.main()
