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
                          gitcmd, liveness, projects, runner, spend, store)
from tests import sandbox as sandbox_module  # noqa: E402
from tests.sandbox import (FakeStream, TmpRootTest, capture,  # noqa: E402
                           capture_new_task_id, claude_only_popen,
                           claude_only_run, disk_backed_ls_tree_files,
                           disk_backed_show, fake_git, sync_spec_from_worktree)

REPO_ROOT = Path(__file__).resolve().parent.parent

# Захвачен ДО любого мокинга `shutil.which` в тестах ниже (SPEC
# 01M1RDCEF0JZ4AVQRE43JFH8TN): `orchestrator.runner.role_env` теперь тоже
# резолвит инструменты манифеста через `shutil.which` — стабы doctor'а,
# отвечающие только на `claude`, должны отвечать НАСТОЯЩИМИ путями и на
# `git`/`gh`/`python3`, иначе `role_env` считает их отсутствующими.
_REAL_WHICH = shutil.which

TARGETS_YAML_DOGFOOD_ONLY = """targets:
  artel:
    forge: github
    url: file:///nonexistent/artel
    base: main
    token_slot: artel-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""

TARGETS_YAML_WITH_SLED = """targets:
  artel:
    forge: github
    url: file:///nonexistent/artel
    base: main
    token_slot: artel-token
    no_paths: []
    project_skills: []
    merge_gate: operator
  sled:
    forge: github
    url: file:///nonexistent/sled
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
        остальных песочницах без настоящего git. A7: `cmd_new` коммитит
        SPEC.md в АРТЕФАКТНУЮ ВЕТКУ пульта (`artifact_source.resolve`
        теперь всегда `foreign=True`) — `gitcmd.show`/`ls_tree_files`
        патчены на чтение с диска main (`disk_backed_show`/
        `disk_backed_ls_tree_files`, тот же приём, что и `tests.
        test_invariants.FsmTest`), сюда — тот же шаблон, который реально
        закоммитил бы `cmd_new` (`sync_spec_from_worktree`).

        Возвращает id заведённой задачи (SPEC T094: ULID, не предсказуемая
        строка) — вызывающая песочница обязана взять его отсюда, не
        предполагать литерал."""
        git_patcher = mock.patch.object(gitcmd, "git", fake_git)
        git_patcher.start()
        self.addCleanup(git_patcher.stop)
        show_patcher = mock.patch.object(gitcmd, "show", disk_backed_show)
        show_patcher.start()
        self.addCleanup(show_patcher.stop)
        ls_patcher = mock.patch.object(gitcmd, "ls_tree_files",
                                       disk_backed_ls_tree_files)
        ls_patcher.start()
        self.addCleanup(ls_patcher.stop)
        _, task_id = capture_new_task_id(catalog.cmd_new, title)
        sync_spec_from_worktree(task_id)
        return task_id

    def touch_backup(self) -> None:
        config.BACKUP_MARKER.parent.mkdir(parents=True, exist_ok=True)
        config.BACKUP_MARKER.write_text("ok", encoding="utf-8")


TmpRootTest = _DoctorTmpRootTest


class DoctorCommandTest(TmpRootTest):
    """Критерий 1: здоровый репо — все проверки ок, код 0; сломанный — провалы, код ≠0."""

    def which(self, name):
        if name == "claude":
            return "/usr/bin/claude"
        # git/gh/python3 — реальные пути (SPEC 01M1RDCEF0JZ4AVQRE43JFH8TN,
        # AC-1/AC-6): `role_env` внутри `isolation_smoke`/`live_smoke`
        # обязан находить их, иначе «здоровый репо» перестаёт быть
        # здоровым по причине, не связанной с проверяемым сценарием.
        return _REAL_WHICH(name)

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

    def setUp(self):
        super().setUp()
        self.TASK = self.new_task_in_fake_git("Задача под pre-flight")
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

    def test_mcp_vector_leak_is_caught(self):
        """Мутация четвёртого класса (SPEC T069): `--strict-mcp-config`
        исчез из команды запуска шага — смоук обязан это поймать."""
        leaking_cmd = ["claude", "-p", "--permission-mode", "acceptEdits"]
        with mock.patch.object(doctor.runner, "role_cmd",
                               return_value=leaking_cmd):
            check = doctor.isolation_smoke()

        self.assertEqual(check.status, "fail")
        self.assertIn("MCP", check.detail)


class TargetWrapperCheckTest(unittest.TestCase):
    """SPEC T069, требование 3: инвентаризация обвязки target'а —
    информационная (warn/ok), никогда не блокирует."""

    def test_artel_uses_the_generic_path_not_a_dogfood_skip(self):
        """A7, требование 2 (AC-2): артель (`config.DEFAULT_TARGET`) —
        та же generic-логика, что и любой другой target, не skip по
        имени — «нет workspace» здесь `warn`, тем же основанием, что и
        для `sled` в `test_no_wrapper_is_ok` ниже."""
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(config, "PROJECTS", Path(tmp)):
                check = doctor.check_target_wrapper(config.DEFAULT_TARGET)

        self.assertNotEqual(check.status, "skip")

    def test_no_wrapper_is_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "sled" / "workspace").mkdir(parents=True)
            with mock.patch.object(config, "PROJECTS", Path(tmp)):
                check = doctor.check_target_wrapper("sled")

        self.assertEqual(check.status, "ok")

    def test_wrapper_present_is_warn_and_names_the_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "sled" / "workspace"
            ws.mkdir(parents=True)
            (ws / ".mcp.json").write_text("{}", encoding="utf-8")
            (ws / "CLAUDE.md").write_text("# обвязка\n", encoding="utf-8")
            with mock.patch.object(config, "PROJECTS", Path(tmp)):
                check = doctor.check_target_wrapper("sled")

        self.assertEqual(check.status, "warn")
        self.assertIn(".mcp.json", check.detail)
        self.assertIn("CLAUDE.md", check.detail)

    def test_wrapper_never_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "sled" / "workspace"
            ws.mkdir(parents=True)
            (ws / ".claude").mkdir()
            (ws / ".mcp.json").write_text("{}", encoding="utf-8")
            (ws / "CLAUDE.md").write_text("# обвязка\n", encoding="utf-8")
            (ws / "AGENTS.md").write_text("# обвязка\n", encoding="utf-8")
            with mock.patch.object(config, "PROJECTS", Path(tmp)):
                check = doctor.check_target_wrapper("sled")

        self.assertNotEqual(check.status, "fail")


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

    def test_artel_gets_the_same_recovery_sverka_as_any_target(self):
        """A7, требование 2 (AC-3): артель (`config.DEFAULT_TARGET`) —
        та же логика recovery-сверки, что и `sled` выше (`test_healthy_
        repo_recovery_is_ok`), не skip «вне объёма» по имени target'а.
        Сверка HEAD `config.ROOT` (пин) в этот тест не входит — она
        отдельная забота `check_root_pin` (AC-13)."""
        capture(projects.cmd_target_init, config.DEFAULT_TARGET)
        artel_task = "T900"
        store.insert_task(store.db(), artel_task, "Задача артели", "in_dev",
                          f"task/{artel_task.lower()}", config.DEFAULT_TARGET,
                          25.0)
        tdir = config.PROJECTS / config.DEFAULT_TARGET / "tasks" / artel_task
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "SPEC.md").write_text("артефакт\n", encoding="utf-8")
        repo = config.PROJECTS / config.DEFAULT_TARGET
        gitcmd.in_repo(repo, "add", "-A")
        gitcmd.in_repo(repo, "-c", "user.name=t", "-c", "user.email=t@t.invalid",
                       "commit", "-q", "-m", "фиксация")
        sha = gitcmd.head_sha(repo)
        store.update_task(store.db(), artel_task, fixed_sha=sha)

        checks = doctor.recovery_check(store.db(), config.DEFAULT_TARGET)

        statuses = {c.name: c.status for c in checks}
        self.assertEqual(statuses["recovery-sha"], "ok")
        self.assertEqual(statuses["recovery-clean"], "ok")
        self.assertEqual(alerts.open_alerts(store.db(), "incident"), [])


class BaseBranchCheckTest(unittest.TestCase):
    """tasks/T032/SPEC.md: догфуд-skip и поведение для внешнего target."""

    EXTERNAL_ENTRY = {
        "forge": "github",
        "url": "file:///nonexistent/sled",
        "base": "main",
    }

    def test_artel_uses_the_generic_path_not_a_dogfood_skip(self):
        """A7, требование 2 (AC-2): артель (`config.DEFAULT_TARGET`) —
        та же generic-логика, что и любой другой `forge: github` target
        (сверка с форджем через `gh`, не skip по имени)."""
        entry = {"forge": "github", "url": "file:///nonexistent/artel",
                 "base": "main"}

        def fake_run(args, **kwargs):
            return subprocess.CompletedProcess(args, 0, "main\n", "")

        with mock.patch.object(doctor.shutil, "which",
                               return_value="/usr/bin/gh"), \
             mock.patch.object(doctor.subprocess, "run",
                               side_effect=fake_run) as run:
            check = doctor.check_base_branch(config.DEFAULT_TARGET, entry)

        self.assertEqual(check.status, "ok")
        run.assert_called()

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

    def setUp(self):
        super().setUp()
        self.TASK = self.new_task_in_fake_git("Порог программы")

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


class OrphanArtifactBranchSweepTest(TmpRootTest):
    """SPEC 01M1KVGD18P9H5WR7VM8TGPV1T, требование 4: `doctor --fix`
    удаляет ветки `artifact/<id>` пульта без строки БД — уборка того
    класса утечки, который SPEC «Контекст» описывает (тест, заводящий
    задачу через `cmd_new` без подмены `config.ROOT`, коммитил в
    НАСТОЯЩИЙ репозиторий пульта). Только по явному вызову, ровно один
    incident-алерт на весь прогон, ветки живых задач не трогаются."""

    def test_sweep_deletes_only_branches_without_a_db_row(self):
        """Ловит мутацию: `sweep_orphan_artifact_branches` сверяет
        `list_branches` с БД неверно (например, удаляет ВСЕ ветки
        `artifact/*` без фильтра по известным id, или сравнивает без
        `.lower()` и пропускает ветку живой задачи в другом регистре) —
        тогда `artifact/t001` (живая задача) тоже попал бы в `deleted`
        и был бы удалён `git branch -D`.
        """
        store.insert_task(store.db(), "T001", "Живая задача", "in_dev",
                          "task/t001-zhivaya-zadacha", config.DEFAULT_TARGET, 25.0)
        deleted_via_git = []

        def fake_git(*args):
            if len(args) >= 3 and args[0] == "branch" and args[1] == "-D":
                deleted_via_git.append(args[2])
            return subprocess.CompletedProcess(list(args), 0, "", "")

        with mock.patch.object(
                doctor.gitcmd, "list_branches",
                lambda prefix="": ["artifact/t001", "artifact/t777"]), \
                mock.patch.object(doctor.gitcmd, "git", fake_git):
            deleted = doctor.sweep_orphan_artifact_branches(store.db())

        self.assertEqual(deleted, ["artifact/t777"])
        self.assertEqual(deleted_via_git, ["artifact/t777"])
        incidents = [a for a in alerts.open_alerts(store.db(), "incident")
                    if a["source"] == doctor.ORPHAN_ARTIFACT_BRANCH_SOURCE]
        self.assertEqual(len(incidents), 1)
        self.assertIn("artifact/t777", incidents[0]["message"])
        self.assertNotIn("artifact/t001", incidents[0]["message"])

    def test_failed_deletion_is_not_reported_as_deleted(self):
        """R1-F3 (ANSWER-2 п.3): `git branch -D` неудачный на одной из
        осиротевших веток — она не попадает ни в возвращаемый список, ни
        в алерт как «удалены», только в честную часть «НЕ удалены».

        Ловит мутацию: возврат `gitcmd.git("branch", "-D", ...)` не
        проверяется — тогда ветка с ненулевым кодом возврата всё равно
        попала бы в `deleted` и в алерт как успешно удалённая, хотя
        `git branch -D` физически не удалил её.
        """
        def fake_git(*args):
            if len(args) >= 3 and args[0] == "branch" and args[1] == "-D":
                if args[2] == "artifact/t777":
                    return subprocess.CompletedProcess(
                        list(args), 1, "", "error: branch is checked out")
                return subprocess.CompletedProcess(list(args), 0, "", "")
            return subprocess.CompletedProcess(list(args), 0, "", "")

        with mock.patch.object(
                doctor.gitcmd, "list_branches",
                lambda prefix="": ["artifact/t777", "artifact/t888"]), \
                mock.patch.object(doctor.gitcmd, "git", fake_git):
            deleted = doctor.sweep_orphan_artifact_branches(store.db())

        self.assertEqual(deleted, ["artifact/t888"])
        incidents = [a for a in alerts.open_alerts(store.db(), "incident")
                    if a["source"] == doctor.ORPHAN_ARTIFACT_BRANCH_SOURCE]
        self.assertEqual(len(incidents), 1)
        self.assertIn("удалены: artifact/t888", incidents[0]["message"])
        self.assertIn("НЕ удалены", incidents[0]["message"])
        self.assertIn("artifact/t777", incidents[0]["message"])

    def test_cmd_doctor_fix_reports_found_but_not_removed_honestly(self):
        """R1-F3 (ANSWER-3): сироты найдены, но `git branch -D` провалился
        на всех — `cmd_doctor(fix=True)` не должен печатать «не найдено»
        (расходится с журналом алертов, который `sweep_orphan_artifact_
        branches` уже честно ведёт), а отдельной честной строкой сказать,
        что сироты найдены, но не удалены.

        Ловит мутацию: `cmd_doctor` решает между «не найдено» и «найдены,
        не удалены» только по пустоте возвращённого `sweep_orphan_
        artifact_branches` списка (`removed`), не проверяя, были ли сироты
        на самом деле, — тогда сценарий «найдены, все удаления
        провалились» снова печатал бы обнадёживающее «не найдено».
        """
        def fake_git(*args):
            if len(args) >= 3 and args[0] == "branch" and args[1] == "-D":
                return subprocess.CompletedProcess(
                    list(args), 1, "", "error: branch is checked out")
            return subprocess.CompletedProcess(list(args), 0, "", "")

        with mock.patch.object(doctor, "all_checks", lambda conn: []), \
                mock.patch.object(doctor.gitcmd, "list_branches",
                                  lambda prefix="": ["artifact/t777"]), \
                mock.patch.object(doctor.gitcmd, "git", fake_git):
            out = capture(lambda: doctor.cmd_doctor(fix=True))

        self.assertNotIn("не найдено", out)
        self.assertIn("найдены, но не удалены", out)

    def test_no_orphans_raises_no_alert(self):
        """Ловит мутацию: `sweep_orphan_artifact_branches` заводит
        incident-алерт безусловно (не только `if orphans:`) — тогда
        прогон уборки без единого сироты всё равно оставил бы запись в
        журнале алертов, вводя Оператора в заблуждение о находке, которой
        не было.
        """
        store.insert_task(store.db(), "T001", "Живая задача", "in_dev",
                          "task/t001-zhivaya-zadacha", config.DEFAULT_TARGET, 25.0)

        with mock.patch.object(doctor.gitcmd, "list_branches",
                               lambda prefix="": ["artifact/t001"]), \
                mock.patch.object(doctor.gitcmd, "git",
                                  lambda *a: subprocess.CompletedProcess(
                                      list(a), 0, "", "")):
            deleted = doctor.sweep_orphan_artifact_branches(store.db())

        self.assertEqual(deleted, [])
        self.assertEqual(
            [a for a in alerts.open_alerts(store.db(), "incident")
             if a["source"] == doctor.ORPHAN_ARTIFACT_BRANCH_SOURCE], [])

    def test_cmd_doctor_default_does_not_sweep(self):
        """Ловит мутацию: `cmd_doctor` зовёт уборку сирот безусловно (не
        только под `if fix:`) — тогда `doctor` без флага `--fix` тоже
        удалял бы ветки, нарушая AC-4 («без явного вызова Оператора
        уборка не запускается»).
        """
        with mock.patch.object(doctor, "all_checks", lambda conn: []), \
                mock.patch.object(doctor, "sweep_orphan_artifact_branches") as sweep:
            capture(doctor.cmd_doctor)

        sweep.assert_not_called()

    def test_cmd_doctor_fix_sweeps_once_and_lists_output(self):
        """Ловит мутацию: `cmd_doctor(fix=True)` зовёт уборку сирот более
        одного раза за прогон (например, внутри цикла по target'ам), или
        не печатает имена удалённых веток в вывод — тогда AC-4 («перечень
        удалённого в вывод», «ровно одна запись» уборки) был бы нарушен.
        """
        with mock.patch.object(doctor, "all_checks", lambda conn: []), \
                mock.patch.object(doctor, "sweep_orphan_artifact_branches",
                                  return_value=["artifact/t777"]) as sweep:
            out = capture(lambda: doctor.cmd_doctor(fix=True))

        sweep.assert_called_once()
        self.assertIn("artifact/t777", out)


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


class LeaseFailDetailAndReconciliationTest(TmpRootTest):
    """SPEC 01M1GCHKG8DDK4DCZWCE3DYKWC, требования 4-5 (AC-7..AC-10):
    рекон осиротевшего шага и обогащённая FAIL-строка `check_leases`,
    отдельно от golden path (tasks/T044 acceptance) и от анти-race/полей
    (01M1G... acceptance) — здесь узкие юнит-срезы форм, которых критерию
    не нужно."""

    TASK = "T001"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)

    @staticmethod
    def dead_pid() -> int:
        proc = subprocess.Popen([sys.executable, "-c", "pass"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        proc.wait()
        return proc.pid

    def insert_dead_lease(self, session_id: str = "sess-dead") -> None:
        conn = store.db()
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            (self.TASK, session_id, self.dead_pid(), socket.gethostname(),
             store.now()))
        conn.commit()

    def test_no_orphan_step_leaves_the_journal_untouched(self):
        """Нет «agent run started» без пары — нечего реконить."""
        before = len(store.task_steps(store.db(), self.TASK))
        self.insert_dead_lease()

        doctor.check_leases(store.db())

        after = store.task_steps(store.db(), self.TASK)
        self.assertFalse(
            any("оборван" in (s["action"] or "") for s in after[before:]),
            after[before:])

    def test_orphan_with_a_terminal_pair_is_not_reconciled(self):
        """«agent run started», уже закрытый терминальным событием, — не
        сирота, даже если lease теперь мёртв."""
        conn = store.db()
        conn.execute(
            "INSERT INTO steps (task_id, target, ts, actor, action, detail)"
            " VALUES (?,?,?,?,?,?)",
            (self.TASK, config.DEFAULT_TARGET, store.now(), "developer",
             "agent run started", ""))
        conn.execute(
            "INSERT INTO steps (task_id, target, ts, actor, action, detail)"
            " VALUES (?,?,?,?,?,?)",
            (self.TASK, config.DEFAULT_TARGET, store.now(), "developer",
             "agent run finished", ""))
        conn.commit()
        self.insert_dead_lease()

        doctor.check_leases(store.db())

        steps = store.task_steps(store.db(), self.TASK)
        self.assertFalse(any("оборван" in (s["action"] or "") for s in steps))

    def test_reconciliation_runs_only_once_across_repeated_calls(self):
        """AC-8: три прогона подряд на том же осиротевшем шаге — ровно
        одно терминальное событие обрыва."""
        conn = store.db()
        conn.execute(
            "INSERT INTO steps (task_id, target, ts, actor, action, detail)"
            " VALUES (?,?,?,?,?,?)",
            (self.TASK, config.DEFAULT_TARGET, store.now(), "developer",
             "agent run started", ""))
        conn.commit()
        self.insert_dead_lease("sess-orphan-holder")

        doctor.check_leases(store.db())
        doctor.check_leases(store.db())
        doctor.check_leases(store.db())

        steps = store.task_steps(store.db(), self.TASK)
        orphaned = [s for s in steps if "оборван" in (s["action"] or "")
                   and "sess-orphan-holder" in (s["action"] or "")]
        self.assertEqual(len(orphaned), 1, steps)

    def test_fail_detail_names_role_and_last_journal_event(self):
        conn = store.db()
        conn.execute(
            "INSERT INTO steps (task_id, target, ts, actor, action, detail)"
            " VALUES (?,?,?,?,?,?)",
            (self.TASK, config.DEFAULT_TARGET, "2026-01-02 03:00:00Z",
             "developer", "agent run started", ""))
        conn.execute(
            "INSERT INTO steps (task_id, target, ts, actor, action, detail)"
            " VALUES (?,?,?,?,?,?)",
            (self.TASK, config.DEFAULT_TARGET, "2026-01-02 03:05:00Z",
             "developer", "agent env WARNING", ""))
        conn.commit()
        self.insert_dead_lease("sess-role-holder")

        checks = doctor.check_leases(store.db())

        failed = [c for c in checks if c.status == "fail"]
        self.assertEqual(len(failed), 1, checks)
        detail = failed[0].detail
        self.assertIn("developer", detail)
        self.assertIn("agent env WARNING", detail)
        self.assertRegex(detail, r"шаг\D{0,20}\d")

    def test_fail_detail_names_step_even_when_last_run_already_finished(self):
        """REVIEW.md итерации 1, R1-F1: сессия могла умереть МЕЖДУ шагами —
        последний запуск агента уже штатно закрыт терминальным событием
        (не сирота для рекона), но AC-10 всё равно требует номер и время
        старта ПОСЛЕДНЕГО шага в FAIL-строке, не только оборванного."""
        conn = store.db()
        conn.execute(
            "INSERT INTO steps (task_id, target, ts, actor, action, detail)"
            " VALUES (?,?,?,?,?,?)",
            (self.TASK, config.DEFAULT_TARGET, "2026-01-02 03:00:00Z",
             "developer", "agent run started", ""))
        conn.execute(
            "INSERT INTO steps (task_id, target, ts, actor, action, detail)"
            " VALUES (?,?,?,?,?,?)",
            (self.TASK, config.DEFAULT_TARGET, "2026-01-02 03:05:00Z",
             "developer", "agent run finished", ""))
        conn.commit()
        self.insert_dead_lease("sess-no-orphan")

        checks = doctor.check_leases(store.db())

        failed = [c for c in checks if c.status == "fail"]
        self.assertEqual(len(failed), 1, checks)
        detail = failed[0].detail
        self.assertRegex(
            detail, r"шаг\D{0,20}\d",
            f"FAIL-строка не называет номер шага, когда последний запуск "
            f"агента уже закрыт терминальным событием (R1-F1): {detail!r}")
        self.assertIn(
            "2026-01-02 03:00:00Z", detail,
            f"FAIL-строка не называет время старта последнего шага, когда "
            f"он уже закрыт терминальным событием (R1-F1): {detail!r}")
        self.assertIn("agent run finished", detail)


class LeaseAntiRaceTest(TmpRootTest):
    """SPEC 01M1GCHKG8DDK4DCZWCE3DYKWC, требование 5, AC-9: FAIL по мёртвому
    lease требует ДВА согласных снимка живости pid."""

    TASK = "T001"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача", "in_dev",
                          "task/t001-zadacha", config.DEFAULT_TARGET, 25.0)
        conn = store.db()
        conn.execute(
            "INSERT INTO leases (task_id, session_id, pid, hostname,"
            " heartbeat_ts) VALUES (?,?,?,?,?)",
            (self.TASK, "sess-flaky", 555555, socket.gethostname(), store.now()))
        conn.commit()

    def test_dead_on_both_snapshots_fails(self):
        with mock.patch.object(liveness, "_pid_alive", return_value=False):
            checks = doctor.check_leases(store.db())

        self.assertTrue(any(c.status == "fail" for c in checks), checks)

    def test_dead_then_alive_does_not_fail(self):
        seen = {"n": 0}

        def flaky(pid):
            seen["n"] += 1
            return seen["n"] > 1

        with mock.patch.object(liveness, "_pid_alive", side_effect=flaky):
            checks = doctor.check_leases(store.db())

        self.assertEqual(seen["n"], 2, "анти-race обязан снять второй снимок")
        self.assertFalse(any(c.status == "fail" for c in checks), checks)


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
    """SPEC T094, требование 6 (AC-7) СУПЕРСЕДИРУЕТ SPEC T049 требование 3:
    контур счётчика номеров заморожен как legacy (генератор id — ULID,
    `orchestrator/idgen.py`) — сверка деградирована до информационной,
    никогда не `fail`, алерт `doctor.task_counter` больше не заводится
    ни при каком отставании счётчика. Сквозной путь (посев через
    `cmd_init`, реальный git) — `tasks/T049/acceptance_tests/
    test_ac2_doctor_counter_incident.py` (обновлён этой же задачей);
    здесь `check_task_counters` дёргается напрямую, без git."""

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)

    def test_counter_behind_observed_max_is_informational_only(self):
        (config.TASKS / "T010").mkdir(parents=True)
        conn = store.db()
        conn.execute("UPDATE task_counters SET next_number=3 WHERE target=?",
                     (config.DEFAULT_TARGET,))
        conn.commit()

        check = doctor.check_task_counters(conn)

        self.assertEqual(check.status, "ok")
        self.assertIn("не движется", check.detail)
        incidents = [a for a in alerts.open_alerts(conn, "incident")
                    if a["source"] == "doctor.task_counter"]
        self.assertEqual(incidents, [])

    def test_counter_behind_observed_max_raises_an_incident(self):
        """Имя сохранено байт-в-байт с main (tasks/T031/acceptance_tests/
        test_branch_correct_reads.py::ExistingTestsNotWeakenedTest, AC-7 —
        никакой тестовый метод не исчезает без ADR, ADR-0002): SPEC T094,
        требование 6 меняет само поведение — счётчик больше НЕ поднимает
        incident ни при каком отставании (см. `test_counter_behind_
        observed_max_is_informational_only` выше, актуальная формулировка
        под честным именем). Тело — то же исполнение под старым именем."""
        self.test_counter_behind_observed_max_is_informational_only()

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

    def test_preexisting_incident_is_auto_acked_once_check_stops_raising_it(self):
        """Прогон до SPEC T094 мог оставить открытый incident этого
        source — авто-ack безусловно его закрывает (условие «ещё живо»
        теперь всегда `False`, требование 6)."""
        conn = store.db()
        alerts.raise_alert(conn, config.DEFAULT_TARGET, "incident",
                          "doctor.task_counter", "legacy incident")

        doctor.check_task_counters(conn)

        incidents = [a for a in alerts.open_alerts(conn, "incident")
                    if a["source"] == "doctor.task_counter"]
        self.assertEqual(incidents, [])

    def test_catching_up_target_is_auto_acked_without_touching_a_lagging_target(self):
        """Имя сохранено байт-в-байт с main (та же регресс-защита T031
        AC-7, см. докстринг `test_counter_behind_observed_max_raises_an_
        incident` выше): сценарий «один target догнал, другой ещё
        отстаёт» перестал существовать вместе с самой блокирующей сверкой
        (SPEC T094, требование 6 — сверка теперь ok для любого target
        безусловно, отставание не заводит incident ни для кого). Тело —
        то же исполнение, что и актуальный тест авто-ack под честным
        именем (`test_preexisting_incident_is_auto_acked_once_check_
        stops_raising_it`)."""
        self.test_preexisting_incident_is_auto_acked_once_check_stops_raising_it()


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


class AutoAckGoneTargetFilterTest(TmpRootTest):
    """tasks/T088/SPEC.md, требование 6: параметр `target` `_auto_ack_gone`
    изолированно от прогона `recovery_check`/`check_task_counters` — свежий
    источник, у которого несколько target держат открытый алерт того же
    `source` одновременно, ack'ается только по своему target; старое
    поведение (без `target`, как у сирот/leases/merge_lock/backup_age)
    не меняется."""

    def test_target_filter_leaves_other_targets_alone(self):
        alerts.raise_alert(store.db(), "sled", "incident",
                           "doctor.recovery.sha", "sled разошёлся")
        alerts.raise_alert(store.db(), "crate", "incident",
                           "doctor.recovery.sha", "crate разошёлся")
        sled_id = [a for a in alerts.open_alerts(store.db(), "incident")
                  if a["target"] == "sled"][0]["id"]
        crate_id = [a for a in alerts.open_alerts(store.db(), "incident")
                   if a["target"] == "crate"][0]["id"]

        doctor._auto_ack_gone(store.db(), "doctor.recovery.sha",
                              lambda _msg: False, target="crate")

        self.assertIsNone(store.get_alert(store.db(), sled_id)["ack_ts"],
                          "фильтр по target='crate' не должен задевать sled")
        self.assertIsNotNone(store.get_alert(store.db(), crate_id)["ack_ts"])

    def test_no_target_argument_keeps_matching_across_targets(self):
        """Совместимость: вызовы без `target` (сироты/leases/merge_lock/
        backup_age) продолжают ack'ать по всем target сразу."""
        alerts.raise_alert(store.db(), "sled", "incident",
                           "doctor.orphans.branch", "T001 (done): ветка t не убрана")
        alerts.raise_alert(store.db(), "crate", "incident",
                           "doctor.orphans.branch", "T002 (done): ветка t2 не убрана")

        doctor._auto_ack_gone(store.db(), "doctor.orphans.branch", lambda _msg: False)

        self.assertEqual(alerts.open_alerts(store.db(), "incident"), [],
                         "без фильтра target ack обязан закрыть оба алерта источника")


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


class _RoleHomeReferenceTmpRootTest(sandbox_module.TmpRootTest):
    """Сужение `TmpRootTest`: только `ROLE_HOME`/`ROLE_CONFIG_DIR` во
    временном каталоге — `ROOT` остаётся настоящим деревом репозитория,
    тот же приём, что и в приёмочном тесте AC-13 этой же задачи
    (`tasks/01M1RDCEF0JZ4AVQRE43JFH8TN/acceptance_tests/
    test_ac13_doctor_role_home_reference_diff.py`)."""

    PATCHED_ATTRS = ("ROLE_HOME", "ROLE_CONFIG_DIR")

    def setUp(self):
        super().setUp()
        self.reference = (config.ROOT / "docs" / "reference" / "role-home"
                          / "claude")
        shutil.copytree(self.reference, config.ROLE_CONFIG_DIR)


class RoleHomeReferenceExtraFilesTest(_RoleHomeReferenceTmpRootTest):
    """Регресс REVIEW.md 01M1RDCEF0JZ4AVQRE43JFH8TN итерации 1, R1-F1:
    сравнение симметрической разностью деревьев файлов давало WARN на
    ЛЮБОМ файле развёрнутого слоя, которого нет в референсе — а такое
    разрастание легитимно (docs/reference/role-home.md, «Курирование»;
    рантайм-файлы `claude` CLI внутри `CLAUDE_CONFIG_DIR`)."""

    def test_extra_file_absent_from_reference_is_not_a_warn(self):
        """Ловит мутацию: возврат к сравнению `ref_files ^ dep_files`
        (симметрическая разность) вместо сверки только файлов
        референса — та регрессия завела бы WARN на лишнем файле ниже."""
        (config.ROLE_CONFIG_DIR / "session-cache.json").write_text(
            "{}", encoding="utf-8")

        check = doctor.check_role_home_reference()

        self.assertNotEqual(check.status, "warn",
                            f"лишний файл развёрнутого слоя не должен "
                            f"давать WARN: {check.detail}")

    def test_extra_subdirectory_is_not_a_warn(self):
        """То же самое для целого поддерева, а не одного файла —
        например, MCP-конфиг, добавленный Оператором вручную."""
        extra_dir = config.ROLE_CONFIG_DIR / "mcp"
        extra_dir.mkdir()
        (extra_dir / "config.json").write_text("{}", encoding="utf-8")

        check = doctor.check_role_home_reference()

        self.assertNotEqual(check.status, "warn",
                            f"лишнее поддерево не должно давать WARN: "
                            f"{check.detail}")


if __name__ == "__main__":
    unittest.main()
