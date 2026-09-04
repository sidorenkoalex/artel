"""Юнит-тесты сверки свежести ветки на входе в гейт (SPEC T051, требования
1, 3-7, 10) — orchestrator/fsm.py::_pull_main_or_escalate и её подключение
в обеих точках (`in_dev -> review` через `cmd_advance`, `acceptance ->
merge_gate` через `cmd_approve`).

Полный прогон РЕАЛЬНОГО git (merge, конфликт, `git merge --abort`, счёт
коммитов) — приёмочные тесты `tasks/T051/acceptance_tests/`
(`_sandbox.py::RealGitFreshnessTest`); здесь — ветвление самой логики
через мок трёх точек механизма (`gitcmd.commits_behind`, `gitcmd.in_repo`,
`orchestrator.acceptance.run`), тем же приёмом лёгкой FSM-песочницы без
реального git, что и `tests/test_advance_guard.py`.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (acceptance, catalog, config, fsm, gitcmd,  # noqa: E402
                          store, workspace)
from tests.sandbox import (SpyRun, capture, capture_new_task_id,  # noqa: E402
                           disk_backed_ls_tree_files, disk_backed_show,
                           fake_git)

REPO_ROOT = Path(__file__).resolve().parent.parent

PLAN_READY = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 1
---

# PLAN: сверка свежести

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""


class BranchFreshnessGateTest(unittest.TestCase):

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        shutil.copytree(REPO_ROOT / "templates", root / "templates")

        for attr, value in (("DB", root / ".artel" / "state.db"),
                            ("TASKS", root / "tasks"),
                            ("LOGS", root / ".artel" / "logs"),
                            ("ROOT", root),
                            ("PROJECTS", root / ".artel" / "projects"),
                            ("TARGETS", root / "targets.yaml"),
                            ("ROLE_HOME", root / ".artel" / "home"),
                            ("ROLE_CONFIG_DIR",
                             root / ".artel" / "home" / ".claude"),
                            ("BACKUP_MARKER", root / ".artel" / "backup-marker"),
                            ("WORKTREES", root / ".artel" / "worktrees")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        patcher = mock.patch.object(gitcmd, "git", fake_git)
        patcher.start()
        self.addCleanup(patcher.stop)
        # `fake_git` отвечает на "rev-parse FETCH_HEAD" пустой строкой
        # (нет настоящего git) — с REVIEW.md R1-F1 (итерация 1) вырожденный
        # `_origin_main_sha` обязана деградировать на "fresh" немедленно,
        # не на литерал "FETCH_HEAD". Тесты этого файла, которые кроют
        # ветку "ветка отстала" (`commits_behind` замокан на ненулевое
        # значение отдельно), нуждаются в настоящем truthy `base` — тем же
        # приёмом стаба, что и `gitcmd.commits_behind` ниже по каждому
        # тесту; `test_advance_treats_origin_fetch_failure_as_fresh`
        # переопределяет этот патч на `None` для проверки самой
        # деградации.
        origin_sha_patcher = mock.patch.object(
            fsm, "_origin_main_sha", return_value="deadbeefcafefeed")
        origin_sha_patcher.start()
        self.addCleanup(origin_sha_patcher.stop)
        # A7 (generic-путь заведения, AC-5): `cmd_new` коммитит артефакты
        # плотницки (`artifact_branch.write_commit`) — та функция зовёт
        # `subprocess.run` НАПРЯМУЮ, минуя `gitcmd.git`/фейк выше; `root`
        # здесь не настоящий git-репозиторий — без этого патча `cmd_new`
        # падает `sys.exit` («git не ответил») ещё до сценария, который
        # тест проверяет (тот же приём, что `tests.sandbox.TmpRootTest.
        # setUp`).
        spy_patcher = mock.patch.object(gitcmd.subprocess, "run", SpyRun())
        spy_patcher.start()
        self.addCleanup(spy_patcher.stop)
        # `artifact_source.resolve` теперь ВСЕГДА возвращает `foreign=True`
        # — FSM читает PLAN/SPEC через `gitcmd.show`/`ls_tree_files`, не с
        # диска напрямую; эта песочница без настоящего git ведёт один
        # источник истины — диск `self.tdir` (тот же приём, что
        # `tests.test_invariants.FsmTest`).
        show_patcher = mock.patch.object(gitcmd, "show", disk_backed_show)
        show_patcher.start()
        self.addCleanup(show_patcher.stop)
        ls_patcher = mock.patch.object(gitcmd, "ls_tree_files",
                                       disk_backed_ls_tree_files)
        ls_patcher.start()
        self.addCleanup(ls_patcher.stop)

        self.wt_path = root / "wt"
        wt_patcher = mock.patch.object(
            workspace, "ensure", lambda task_id, branch: (self.wt_path, None))
        wt_patcher.start()
        self.addCleanup(wt_patcher.stop)

        self.capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(catalog.cmd_new, "Сверка свежести")
        self.tdir = config.TASKS / self.TASK
        self.branch = self.task_row()["branch"]

    # ------------------------------------------------------------ утилиты

    capture = staticmethod(capture)

    def task_row(self):
        return store.db().execute("SELECT * FROM tasks WHERE id=?",
                                  (self.TASK,)).fetchone()

    def state(self) -> str:
        return self.task_row()["state"]

    def set_state(self, state: str) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, self.TASK))
        conn.commit()

    def journal_details(self) -> list[str]:
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,))]

    def write_plan_ready(self) -> None:
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / "PLAN.md").write_text(
            PLAN_READY.format(task=self.TASK), encoding="utf-8")

    def advance_from_in_dev(self) -> str:
        self.write_plan_ready()
        self.set_state("in_dev")
        return self.capture(fsm.cmd_advance, self.TASK)

    def approve_from_acceptance(self) -> str:
        self.set_state("acceptance")
        return self.capture(fsm.cmd_approve, self.TASK)

    @staticmethod
    def _ok(repo, *args) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(("git", "-C", str(repo), *args), 0, "", "")

    def _fixation_response(self, repo, *args) -> subprocess.CompletedProcess | None:
        """Ответ на вызовы `fixation.read`/`fix` (A7: self/артель фиксируется
        тем же кодом, что и любой target, — `confirm_fixation`/`record_
        fixation` зовут `gitcmd.in_repo` на КАЖДОМ approve/advance, до и
        независимо от предмета этого файла, подтяжки свежести) — `None`,
        если `args` не про фиксацию (вызывающий код решает дальше сам).
        Эти вызовы НЕ считаются `merge_calls`/`abort_calls` — те про
        предмет теста, не про фиксацию."""
        if args == ("rev-parse", "HEAD"):
            # Пустой sha (не фейковый непустой) — `confirm_fixation`
            # деградирует «сверять не с чем» (тот же вырожденный случай,
            # что и до A7: этот файл — не про фиксацию, approve без `sha`
            # обязан продолжать работать).
            return subprocess.CompletedProcess(
                ("git", "-C", str(repo), *args), 0, "", "")
        if args[:2] == ("status", "--porcelain"):
            return subprocess.CompletedProcess(
                ("git", "-C", str(repo), *args), 0, "", "")
        if args[:1] == ("init",):
            return self._ok(repo, *args)
        if args[:2] == ("diff", "--cached"):
            return subprocess.CompletedProcess(
                ("git", "-C", str(repo), *args), 0, "", "")  # нечего коммитить
        if args[:1] == ("add",):
            return self._ok(repo, *args)
        return None

    def _conflict_then_abort_ok(self, repo, *args) -> subprocess.CompletedProcess:
        fixation_response = self._fixation_response(repo, *args)
        if fixation_response is not None:
            return fixation_response
        if args[:1] == ("merge",) and "--abort" in args:
            self.abort_calls.append((repo, args))
            return self._ok(repo, *args)
        if args[:1] == ("merge",):
            self.merge_calls.append((repo, args))
            return subprocess.CompletedProcess(
                ("git", "-C", str(repo), *args), 1, "",
                "CONFLICT (content): Merge conflict in shared.txt")
        if args[:2] == ("diff", "--name-only"):
            # Конфликт не сводится к «только карта» (SPEC T067,
            # требование 4) — список конфликтующих файлов называет
            # посторонний файл, авторазрешение не применимо, прежний
            # abort+escalate.
            return subprocess.CompletedProcess(
                ("git", "-C", str(repo), *args), 0, "shared.txt\n", "")
        raise AssertionError(f"неожиданный gitcmd.in_repo вызов: {args}")

    def _recording_ok(self, repo, *args) -> subprocess.CompletedProcess:
        fixation_response = self._fixation_response(repo, *args)
        if fixation_response is not None:
            return fixation_response
        self.merge_calls.append((repo, args))
        return self._ok(repo, *args)

    def setup_recording(self) -> None:
        self.merge_calls: list = []
        self.abort_calls: list = []

    # ----------------------------------------------------- ветка не отстала

    def test_advance_skips_pull_when_branch_not_behind(self):
        self.setup_recording()
        with mock.patch.object(gitcmd, "commits_behind", return_value=0), \
             mock.patch.object(gitcmd, "in_repo",
                               side_effect=self._recording_ok), \
             mock.patch.object(acceptance, "run") as acc_run:
            self.advance_from_in_dev()

        self.assertEqual(self.state(), "review",
                         "переход обязан пройти как и до T051 (требование 7)")
        self.assertEqual(self.merge_calls, [], "не отставшая ветка — merge не звонится")
        acc_run.assert_not_called()

    def test_approve_skips_pull_when_branch_not_behind(self):
        self.setup_recording()
        with mock.patch.object(gitcmd, "commits_behind", return_value=None), \
             mock.patch.object(gitcmd, "in_repo",
                               side_effect=self._recording_ok), \
             mock.patch.object(acceptance, "run") as acc_run:
            self.approve_from_acceptance()

        self.assertEqual(self.state(), "merge_gate",
                         "None (git не ответил) — тот же вырожденный случай, "
                         "что и 0 коммитов (требование 9)")
        self.assertEqual(self.merge_calls, [])
        acc_run.assert_not_called()

    # ------------------------------------------------- успешная подтяжка

    def test_advance_pulls_main_and_advances_when_acceptance_green(self):
        self.setup_recording()
        with mock.patch.object(gitcmd, "commits_behind", return_value=3), \
             mock.patch.object(gitcmd, "in_repo",
                               side_effect=self._recording_ok), \
             mock.patch.object(acceptance, "run",
                               return_value=(True, "ok")) as acc_run:
            self.advance_from_in_dev()

        self.assertEqual(self.state(), "review",
                         "переход обязан состояться после успешной подтяжки")
        self.assertEqual(len(self.merge_calls), 1)
        repo, args = self.merge_calls[0]
        self.assertEqual(repo, self.wt_path, "merge — в worktree ЗАДАЧИ, "
                         "не в рабочей копии пульта (ADR-0006 п.2)")
        self.assertEqual(args[0], "merge")
        self.assertIn("--no-ff", args, "подтяжка не rebase (требование 3)")
        # SPEC 01M1NBWPKNBXP9ZXXQDJM7AXPJ, AC-2: источник merge — sha,
        # зафетченный с origin (здесь замокан `fsm._origin_main_sha` ->
        # "deadbeefcafefeed", REVIEW.md R1-F1 итерация 1: литерал
        # "FETCH_HEAD" больше не подставляется НИКОГДА, даже когда
        # `_origin_main_sha` вырождена — см.
        # `test_advance_treats_origin_fetch_failure_as_fresh`), НЕ
        # локальный `config.MAIN_BRANCH` буквальным аргументом merge.
        self.assertNotIn(config.MAIN_BRANCH, args,
                         "AC-2: config.MAIN_BRANCH (локальный пин) не "
                         "имеет права быть источником merge")
        self.assertIn("deadbeefcafefeed", args)
        self.assertNotIn("FETCH_HEAD", args,
                         "R1-F1: литерал FETCH_HEAD не подставляется — не "
                         "честный no-op ни в config.ROOT (чужой предыдущий "
                         "фетч), ни в приватном FETCH_HEAD worktree'а")
        self.assertNotIn(self.branch, args,
                         "ветка задачи не упоминается в аргументах merge")
        acc_run.assert_called_once_with(self.wt_path / "tasks" / self.TASK)

    def test_approve_pulls_main_and_advances_when_acceptance_green(self):
        self.setup_recording()
        with mock.patch.object(gitcmd, "commits_behind", return_value=1), \
             mock.patch.object(gitcmd, "in_repo",
                               side_effect=self._recording_ok), \
             mock.patch.object(acceptance, "run",
                               return_value=(True, "ok")) as acc_run:
            self.approve_from_acceptance()

        self.assertEqual(self.state(), "merge_gate")
        self.assertEqual(len(self.merge_calls), 1)
        acc_run.assert_called_once_with(self.wt_path / "tasks" / self.TASK)

    # --------------------------- AC-4 (эквивалент лёгкой песочницы) ---

    def test_freshness_check_never_defaults_base_to_local_pin(self):
        """SPEC 01M1NBWPKNBXP9ZXXQDJM7AXPJ, AC-4 — эквивалент в стиле
        этого файла (лёгкая песочница без реального git не может честно
        развести «ветка отстаёт от origin, но совпадает с локальным
        пином» — тот сценарий кроют приёмочные тесты задачи,
        `_sandbox.py::OriginDivergedSandbox::test_ac4_*`): узел сверки
        обязан звать `gitcmd.commits_behind` с явным `base`, полученным
        из fetch, а не оставлять параметр пустым — иначе `commits_behind`
        сама подставила бы `config.MAIN_BRANCH` (локальный пин), ровно
        дефект инцидента 04.09 из «Контекста» SPEC.
        """
        self.setup_recording()
        behind_calls = []

        def spying_commits_behind(branch, base=None):
            behind_calls.append((branch, base))
            return 3

        with mock.patch.object(gitcmd, "commits_behind",
                               side_effect=spying_commits_behind), \
             mock.patch.object(gitcmd, "in_repo",
                               side_effect=self._recording_ok), \
             mock.patch.object(acceptance, "run", return_value=(True, "ok")):
            self.advance_from_in_dev()

        self.assertEqual(len(behind_calls), 1)
        _, base = behind_calls[0]
        self.assertTrue(
            base, "AC-4: base обязан быть передан явно из origin-fetch, "
            "не оставлен пустым/None (иначе commits_behind сама "
            "подставит config.MAIN_BRANCH — локальный пин)")
        self.assertNotEqual(
            base, config.MAIN_BRANCH,
            "AC-4: base не имеет права совпасть с локальным config.MAIN_BRANCH")

    # ------------------------------- R1-F1 (REVIEW.md итерация 1, major)

    def test_advance_treats_origin_fetch_failure_as_fresh(self):
        """REVIEW.md 01M1NBWPKNBXP9ZXXQDJM7AXPJ итерация 1, замечание
        R1-F1 (major): `_origin_main_sha` вырождена (git fetch/rev-parse
        не ответили, либо конфигурация target'а неисправна) — переход
        обязан деградировать на "fresh" немедленно, НЕ подставляя литерал
        "FETCH_HEAD" ни в `commits_behind`, ни в `merge`. Прежде такая
        подстановка сравнивала/мержила ветку задачи против постороннего
        состояния `config.ROOT`/приватного `FETCH_HEAD` worktree'а — не
        «ничего не делала», как заявляла деградация.
        """
        self.setup_recording()
        with mock.patch.object(fsm, "_origin_main_sha", return_value=None), \
             mock.patch.object(gitcmd, "commits_behind") as behind, \
             mock.patch.object(gitcmd, "in_repo",
                               side_effect=self._recording_ok), \
             mock.patch.object(acceptance, "run") as acc_run:
            self.advance_from_in_dev()

        self.assertEqual(self.state(), "review",
                         "вырожденная _origin_main_sha — тот же исход, что "
                         "и «ветка не отстала» (требование 7)")
        behind.assert_not_called()
        self.assertEqual(self.merge_calls, [],
                         "R1-F1: merge не имеет права звонить против "
                         "постороннего FETCH_HEAD")
        acc_run.assert_not_called()

    # --------------------------------------------------- конфликт подтяжки

    def test_advance_escalates_on_pull_conflict_and_aborts(self):
        self.setup_recording()
        self.write_plan_ready()
        self.set_state("in_dev")
        with mock.patch.object(gitcmd, "commits_behind", return_value=5), \
             mock.patch.object(gitcmd, "in_repo",
                               side_effect=self._conflict_then_abort_ok), \
             mock.patch.object(acceptance, "run") as acc_run:
            out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "escalated",
                         "конфликт подтяжки обязан эскалировать (требование 5)")
        combined = out + "\n".join(self.journal_details())
        self.assertIn("конфликт", combined.lower())
        self.assertEqual(len(self.merge_calls), 1)
        self.assertEqual(len(self.abort_calls), 1,
                         "конфликт обязан откатываться git merge --abort")
        acc_run.assert_not_called()

    def test_approve_escalates_on_pull_conflict_and_aborts(self):
        self.setup_recording()
        self.set_state("acceptance")
        with mock.patch.object(gitcmd, "commits_behind", return_value=2), \
             mock.patch.object(gitcmd, "in_repo",
                               side_effect=self._conflict_then_abort_ok), \
             mock.patch.object(acceptance, "run") as acc_run:
            out = self.capture(fsm.cmd_approve, self.TASK)

        self.assertEqual(self.state(), "escalated")
        combined = out + "\n".join(self.journal_details())
        self.assertIn("конфликт", combined.lower())
        self.assertEqual(len(self.abort_calls), 1)
        acc_run.assert_not_called()

    # --------------------------------------- красные приёмочные после пула

    def test_advance_escalates_on_red_acceptance_after_pull_keeps_merge(self):
        self.setup_recording()
        self.write_plan_ready()
        self.set_state("in_dev")
        with mock.patch.object(gitcmd, "commits_behind", return_value=4), \
             mock.patch.object(gitcmd, "in_repo",
                               side_effect=self._recording_ok), \
             mock.patch.object(acceptance, "run",
                               return_value=(False, "MARKER-RED")):
            out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "escalated",
                         "красные приёмочные после подтяжки эскалируют "
                         "(требование 6)")
        combined = out + "\n".join(self.journal_details())
        self.assertIn("MARKER-RED", combined)
        self.assertEqual(len(self.merge_calls), 1,
                         "слияние остаётся — откат не выполняется")
        self.assertEqual(self.abort_calls, [])

    def test_approve_escalates_on_red_acceptance_after_pull_keeps_merge(self):
        self.setup_recording()
        self.set_state("acceptance")
        with mock.patch.object(gitcmd, "commits_behind", return_value=7), \
             mock.patch.object(gitcmd, "in_repo",
                               side_effect=self._recording_ok), \
             mock.patch.object(acceptance, "run",
                               return_value=(False, "MARKER-RED")):
            out = self.capture(fsm.cmd_approve, self.TASK)

        self.assertEqual(self.state(), "escalated")
        combined = out + "\n".join(self.journal_details())
        self.assertIn("MARKER-RED", combined)
        self.assertEqual(len(self.merge_calls), 1)
        self.assertEqual(self.abort_calls, [])

    # ------------------------------------------------ worktree недоступен

    def test_advance_escalates_when_worktree_not_available(self):
        with mock.patch.object(gitcmd, "commits_behind", return_value=9), \
             mock.patch.object(workspace, "ensure",
                               return_value=(self.wt_path, "worktree add упал")):
            self.write_plan_ready()
            self.set_state("in_dev")
            out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertEqual(self.state(), "escalated")
        combined = out + "\n".join(self.journal_details())
        self.assertIn("worktree", combined)


# --------------------------------------------------------------------- AC-10


class TargetSourcedRemoteTest(unittest.TestCase):
    """SPEC 01M1NBWPKNBXP9ZXXQDJM7AXPJ, требование 5/AC-10 (ANSWER-1,
    добавлено после лока приёмочной планки — юнит-тест здесь, не в
    `tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/acceptance_tests/`).

    Источник сверки/подтяжки — конфигурация target'а задачи
    (`targets.yaml`/`store.task_target`), не хардкод `origin` пульта:
    задача с не-self target'ом фетчит `url` её записи, не литерал
    `"origin"`. Self-target уже покрыт `BranchFreshnessGateTest` выше
    (там `config.TARGETS` намеренно не заводится — AC-9); здесь отдельная
    песочница ИМЕННО потому, что этот сценарий обязан завести файл.
    """

    TARGETS_YAML = """targets:
  acme:
    forge: github
    url: https://example.invalid/acme-target.git
    base: trunk
    token_slot: artel-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        shutil.copytree(REPO_ROOT / "templates", root / "templates")

        for attr, value in (("DB", root / ".artel" / "state.db"),
                            ("TASKS", root / "tasks"),
                            ("LOGS", root / ".artel" / "logs"),
                            ("ROOT", root),
                            ("PROJECTS", root / ".artel" / "projects"),
                            ("TARGETS", root / "targets.yaml"),
                            ("ROLE_HOME", root / ".artel" / "home"),
                            ("ROLE_CONFIG_DIR",
                             root / ".artel" / "home" / ".claude"),
                            ("BACKUP_MARKER", root / ".artel" / "backup-marker"),
                            ("WORKTREES", root / ".artel" / "worktrees")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        config.TARGETS.write_text(self.TARGETS_YAML, encoding="utf-8")

        self.calls: list = []

        def spying_git(*args):
            self.calls.append(args)
            return fake_git(*args)

        patcher = mock.patch.object(gitcmd, "git", spying_git)
        patcher.start()
        self.addCleanup(patcher.stop)
        spy_patcher = mock.patch.object(gitcmd.subprocess, "run", SpyRun())
        spy_patcher.start()
        self.addCleanup(spy_patcher.stop)
        show_patcher = mock.patch.object(gitcmd, "show", disk_backed_show)
        show_patcher.start()
        self.addCleanup(show_patcher.stop)
        ls_patcher = mock.patch.object(gitcmd, "ls_tree_files",
                                       disk_backed_ls_tree_files)
        ls_patcher.start()
        self.addCleanup(ls_patcher.stop)

        self.wt_path = root / "wt"
        wt_patcher = mock.patch.object(
            workspace, "ensure", lambda task_id, branch: (self.wt_path, None))
        wt_patcher.start()
        self.addCleanup(wt_patcher.stop)

        self.capture = capture
        self.capture(catalog.cmd_init)
        self.TASK = catalog.cmd_new("Внешний target", target="acme")
        self.tdir = config.TASKS / self.TASK
        self.branch = store.db().execute(
            "SELECT branch FROM tasks WHERE id=?",
            (self.TASK,)).fetchone()["branch"]

    def test_pull_freshness_fetches_target_url_not_pult_origin(self):
        """Ветка не отстала (`commits_behind` -> 0) — сверке этого
        достаточно, чтобы проявить свой источник: fetch обязан случиться
        ДО самого сравнения (AC-1 для self-target, тот же порядок здесь),
        и его remote — `url` записи `acme`, не `"origin"`; ветка фетча —
        её `base` (`trunk`), не `config.MAIN_BRANCH` (`main`).
        """
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / "PLAN.md").write_text(
            PLAN_READY.format(task=self.TASK), encoding="utf-8")
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?",
                     ("in_dev", self.TASK))
        conn.commit()

        with mock.patch.object(gitcmd, "commits_behind", return_value=0):
            self.capture(fsm.cmd_advance, self.TASK)

        fetch_calls = [c for c in self.calls if c and c[0] == "fetch"]
        self.assertTrue(fetch_calls, "AC-10: сверка обязана фетчить "
                        "источник target'а перед сравнением")
        remote_args = fetch_calls[0]
        self.assertNotIn("origin", remote_args,
                         "AC-10: remote внешнего target — из его "
                         "конфигурации, не хардкод origin пульта")
        self.assertIn("https://example.invalid/acme-target.git", remote_args,
                     "AC-10: remote — url записи target'а из targets.yaml")
        self.assertIn("trunk", remote_args,
                     "AC-10: ветка фетча — base записи target'а, не "
                     "config.MAIN_BRANCH")
        self.assertNotIn(config.MAIN_BRANCH, remote_args,
                         "AC-10: config.MAIN_BRANCH — имя ветки self-"
                         "target'а, не этого target'а")


if __name__ == "__main__":
    unittest.main()
