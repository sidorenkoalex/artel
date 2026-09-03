"""Регресс-тесты систематического бага разрешения префикса id (REVIEW.md
T094, итерация 1, замечание 1 — blocker).

`store.resolve_task_id` (SPEC T094, требование 3, AC-3) резолвился только
в точке `store.get_task`, а вызывающий код CLI-команд продолжал использовать
НЕразрешённый (возможно-префиксный) `task_id` для CAS-перехода, путей на
диске и журнала — единственный существующий тест AC-3 (`catalog.cmd_show`)
этот класс не ловил, потому что резолв в одной точке не значит, что он
распространяется на остальную функцию/на другие команды.

Правка: каждая id-принимающая CLI-команда резолвит `task_id` ОДИН РАЗ на
самом верху, до lease/CAS/путей/журнала — файлы ниже проверяют именно
результат этой правки на пяти командах, названных ревью явно (kill/log/
advance/reject) плюс workspace; `cmd_show` уже покрыт
`tasks/T094/acceptance_tests/test_ac3_prefix_resolution.py`.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (catalog, cleanup, config, fsm,  # noqa: E402
                          gitcmd, store, workspace)
from tests.sandbox import (SpyRun, TmpRootTest, capture,  # noqa: E402
                           capture_new_task_id, disk_backed_ls_tree_files,
                           disk_backed_show, fake_git, resilient_tmp_cleanup,
                           sync_spec_from_worktree)

REPO_ROOT = Path(__file__).resolve().parent.parent


class PrefixLogTest(TmpRootTest):
    """`log <префикс>` (REVIEW T094 итерация 1: `cmd_log` не резолвил
    вовсе — печатал 0 строк на непустом журнале под полным id)."""

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        conn = store.db()
        store.insert_task(conn, "BBBBSOLO9", "Задача-одиночка", "in_dev",
                          "task/bbbbsolo9-x", config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        store.journal(conn, "BBBBSOLO9", "operator", "created", "тест")

    def test_log_with_unique_prefix_prints_the_same_journal_as_full_id(self):
        full = capture(catalog.cmd_log, "BBBBSOLO9")
        prefix = capture(catalog.cmd_log, "BBBB")

        self.assertEqual(full, prefix)
        self.assertIn("created", prefix)


class PrefixKillTest(unittest.TestCase):
    """`kill <префикс>` (REVIEW T094 итерация 1: `_cmd_kill` брал lease по
    несуществующему префиксному ключу и зацикливался на вечно
    проигрывающем CAS — живой репро ревью: `cmd_kill('AAAA')` зависал
    >8с на задаче `AAAAUNIQ1XYZ`)."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, tmp)
        self.root = Path(tmp.name).resolve()

        self.git("init", "-q", "-b", config.MAIN_BRANCH)
        self.git("config", "user.email", "artel@example.invalid")
        self.git("config", "user.name", "artel tests")
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        shutil.copy(REPO_ROOT / ".gitignore", self.root / ".gitignore")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")

        for attr, value in (("ROOT", self.root),
                            ("DB", self.root / ".artel" / "state.db"),
                            ("TASKS", self.root / "tasks"),
                            ("LOGS", self.root / ".artel" / "logs"),
                            ("WORKTREES", self.root / ".artel" / "worktrees")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(catalog.cmd_new, "Убить префиксом")

    def git(self, *args: str) -> str:
        res = subprocess.run(["git", *args], cwd=self.root,
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0,
                         f"git {' '.join(args)} упал: {res.stderr}")
        return res.stdout

    def test_kill_with_unique_prefix_resolves_and_does_not_hang(self):
        prefix = self.TASK[:8]
        self.assertNotEqual(prefix, self.TASK, "префикс обязан быть короче id")

        out = capture(cleanup.cmd_kill, prefix)

        row = store.db().execute(
            "SELECT state FROM tasks WHERE id=?", (self.TASK,)).fetchone()
        self.assertEqual(row["state"], "killed")
        self.assertIn(self.TASK, out)


class PrefixAdvanceRejectTest(unittest.TestCase):
    """`advance`/`reject <префикс>` (REVIEW T094 итерация 1: `_cmd_advance`
    строила `tdir` из НЕразрешённого префикса — живой репро ревью:
    `cmd_advance('AAAA')` ложно печатал «PLAN.md не ready» на задаче с
    реально готовым PLAN.md; `_cmd_reject` на `merge_gate` кидала
    необработанный `CasConflict` сквозь `lease.run_locked`)."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, tmp)
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
        wt_patcher = mock.patch.object(
            workspace, "ensure", lambda task_id, branch: (root, None))
        wt_patcher.start()
        self.addCleanup(wt_patcher.stop)
        # A7 (generic-путь заведения, AC-5): `cmd_new` коммитит артефакты
        # плотницки, минуя `gitcmd.git` (фейк выше) — без этого патча
        # `cmd_new` падает `sys.exit` («git не ответил»).
        spy_patcher = mock.patch.object(gitcmd.subprocess, "run", SpyRun())
        spy_patcher.start()
        self.addCleanup(spy_patcher.stop)
        # `artifact_source.resolve` теперь ВСЕГДА `foreign=True` — FSM
        # читает SPEC.md через `gitcmd.show`/`ls_tree_files`; эта
        # песочница без настоящего git ведёт диск `config.TASKS` как
        # единственный источник истины.
        show_patcher = mock.patch.object(gitcmd, "show", disk_backed_show)
        show_patcher.start()
        self.addCleanup(show_patcher.stop)
        ls_patcher = mock.patch.object(gitcmd, "ls_tree_files",
                                       disk_backed_ls_tree_files)
        ls_patcher.start()
        self.addCleanup(ls_patcher.stop)

        capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(catalog.cmd_new, "Advance префиксом")
        # `cmd_new` (A7) коммитит SPEC.md в артефактную ветку пульта
        # плотницки, не на диск — эта песочница без настоящего git читает
        # диск `config.TASKS` как единственный источник истины, значит
        # содержимое кладётся сюда же явно (тем же приёмом, что и
        # `tests.test_agent_prompt.PromptChannelTest`).
        sync_spec_from_worktree(self.TASK)
        self.tdir = config.TASKS / self.TASK
        self.prefix = self.TASK[:8]
        self.assertNotEqual(self.prefix, self.TASK,
                            "префикс обязан быть короче id")

    def set_state(self, state: str) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, self.TASK))
        conn.commit()

    def state(self) -> str:
        return store.db().execute("SELECT state FROM tasks WHERE id=?",
                                  (self.TASK,)).fetchone()[0]

    def test_advance_with_unique_prefix_reads_the_real_task_dir(self):
        # `cmd_new` уже завела SPEC.md в tdir полного id — advance с
        # префиксом обязан найти именно этот каталог, не
        # `tasks/<префикс>/`, которого не существует вовсе. Шаблонный
        # status по умолчанию `draft` — доводим до `ready` руками, как
        # сделал бы analyst.
        spec_path = self.tdir / "SPEC.md"
        self.assertTrue(spec_path.exists())
        spec_path.write_text(
            spec_path.read_text(encoding="utf-8").replace(
                "status: draft", "status: ready", 1),
            encoding="utf-8")

        out = capture(fsm.cmd_advance, self.prefix)

        self.assertEqual(self.state(), "spec_gate",
                         f"advance с префиксом не сдвинул задачу: {out}")

    def test_reject_with_unique_prefix_on_merge_gate_does_not_raise(self):
        self.set_state("merge_gate")

        capture(fsm.cmd_reject, self.prefix, "не готово")

        self.assertEqual(self.state(), "in_dev")


class PrefixWorkspaceTest(unittest.TestCase):
    """`workspace <префикс>` (REVIEW T094 итерация 1: `_cmd_workspace`
    заводила/искала worktree по несовпадающему с остальной системой
    ключу)."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, tmp)
        self.root = Path(tmp.name).resolve()

        self.git("init", "-q", "-b", config.MAIN_BRANCH)
        self.git("config", "user.email", "artel@example.invalid")
        self.git("config", "user.name", "artel tests")
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        shutil.copy(REPO_ROOT / ".gitignore", self.root / ".gitignore")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")

        for attr, value in (("ROOT", self.root),
                            ("DB", self.root / ".artel" / "state.db"),
                            ("TASKS", self.root / "tasks"),
                            ("LOGS", self.root / ".artel" / "logs"),
                            ("WORKTREES", self.root / ".artel" / "worktrees")):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(catalog.cmd_new, "Workspace префиксом")

    def git(self, *args: str) -> str:
        res = subprocess.run(["git", *args], cwd=self.root,
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0,
                         f"git {' '.join(args)} упал: {res.stderr}")
        return res.stdout

    def test_workspace_with_unique_prefix_finds_the_existing_worktree(self):
        real_wt_path = workspace.path(self.TASK)
        prefix = self.TASK[:8]

        out = capture(workspace.cmd_workspace, prefix)

        self.assertIn(str(real_wt_path), out)
        self.assertNotIn("не создан", out)


if __name__ == "__main__":
    unittest.main()
