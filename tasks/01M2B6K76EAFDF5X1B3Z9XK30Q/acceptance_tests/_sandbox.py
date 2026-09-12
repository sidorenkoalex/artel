"""Общая песочница приёмочных тестов задачи 01M2B6K76EAFDF5X1B3Z9XK30Q
(AC-1..AC-9): «приёмка: что проверит approve» — единая запись
журнала/печать на входе в `acceptance`, вычисленная из
`fsm_autogate._autogate_conditions` и `scripts.guard.scan_ac_content`
(SPEC требования 1-2).

Точка входа задачи — `fsm_autogate._maybe_autogate_acceptance`: она уже
зовётся РОВНО один раз на входе в `acceptance`, единым местом что для
ручного `advance`, что для цикла `auto` (вызывающий код —
`orchestrator/fsm_advance.py::_review_approved`, вне зон этой задачи,
SPEC «Зоны») — тестировать саму эту функцию напрямую значит покрыть
обе ветки AC-1 («остановка auto на acceptance» и «advance без auto»)
одним и тем же вызовом, без надобности гонять `fsm.cmd_advance`/
`auto.cmd_auto` целиком (тот же довод, что уже несёт `tasks/
01M1NBWWPJMHKJMYXRDCM0W0C5/acceptance_tests/_sandbox.py::
AutogateBranchSandbox`, чью структуру этот файл повторяет).

Реальный git-репозиторий (тот же приём) — планка коммитится плотницки
в артефактную ветку (`artifact_branch.commit_files`), а КОДОВАЯ ветка
задачи (`t["branch"]`) для сценария «родители подтяжек» (AC-3) заводится
по-настоящему (`git checkout -b`/`git merge --no-ff`) — этот факт живёт
только в реальной истории git, ни один мок его не изобразит достоверно.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import (acceptance, artifact_branch, budget, catalog,  # noqa: E402
                          config, fsm_autogate, gates, store, workspace)

REPO_ROOT = Path(__file__).resolve().parents[3]

TASK = "T001"

# Действие журнала, которое обязана заводить эта задача (SPEC AC-1) —
# буквальная строка из требования 1, не пересказ.
ACTION = "приёмка: что проверит approve"


class AcceptanceEntryReportSandbox(unittest.TestCase):
    """Задача T001 в свежем временном git-репозитории; строка БД без
    `catalog.cmd_new` — планка коммитится прямо в артефактную ветку,
    кодовая ветка задачи (`self.branch`) заводится по-настоящему в том
    же репозитории (нужна тестам «родители подтяжек», AC-3)."""

    TASK = TASK

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        # resolve(): на macOS /var — симлинк на /private/var.
        self.root = Path(tmp.name).resolve()

        self.git("init", "-q", "-b", config.MAIN_BRANCH)
        self.git("config", "user.email", "artel-tests@example.invalid")
        self.git("config", "user.name", "artel tests")
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        shutil.copy(REPO_ROOT / ".gitignore", self.root / ".gitignore")
        (self.root / "shared.txt").write_text("base\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")

        for attr, value in (
            ("ROOT", self.root),
            ("DB", self.root / ".artel" / "state.db"),
            ("TASKS", self.root / "tasks"),
            ("LOGS", self.root / ".artel" / "logs"),
            ("WORKTREES", self.root / ".artel" / "worktrees"),
            ("PROJECTS", self.root / ".artel" / "projects"),
            ("TARGETS", self.root / "targets.yaml"),
            ("ROLE_HOME", self.root / ".artel" / "home"),
            ("ROLE_CONFIG_DIR", self.root / ".artel" / "home" / ".claude"),
            ("BACKUP_MARKER", self.root / ".artel" / "backup-marker"),
        ):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.capture(catalog.cmd_init)
        self.branch = f"task/{self.TASK.lower()}-priyomka-otchet"
        store.insert_task(store.db(), self.TASK,
                          "Приёмка: печать того, что проверит approve",
                          "acceptance", self.branch, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        self.artifact_branch = artifact_branch.branch_name(self.TASK)

    # ------------------------------------------------------------ утилиты

    def git(self, *args: str, cwd=None, check: bool = True):
        res = subprocess.run(["git", *args], cwd=cwd or self.root,
                             capture_output=True, text=True)
        if check:
            self.assertEqual(res.returncode, 0,
                             f"git {' '.join(args)} упал: {res.stderr}")
        return res

    @staticmethod
    def capture(fn, *args):
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            fn(*args)
        return buf.getvalue()

    def journal_rows(self) -> list:
        """(actor, action, detail) журнала задачи по порядку записи."""
        return [(r["actor"], r["action"], r["detail"]) for r in store.db().execute(
            "SELECT actor, action, detail FROM steps WHERE task_id=? "
            "ORDER BY id", (self.TASK,))]

    def task_row(self):
        return store.get_task(store.db(), self.TASK)

    def state(self) -> str:
        return self.task_row()["state"]

    def seed_planka(self, content: str, filename: str = "test_marker.py") -> str:
        """Коммитит `content` в `acceptance_tests/` артефактной ветки
        задачи — плотницки, минуя диск (`artifact_branch.commit_files`)."""
        rel = f"tasks/{self.TASK}/acceptance_tests/{filename}"
        sha = artifact_branch.commit_files(
            self.TASK, {rel: content}, "тест: планка песочницы")
        self.assertTrue(sha, "commit_files не вернул sha")
        return sha

    def stale_disk_dir(self) -> Path:
        """Путь `acc_tdir`, каким его после A7 видит вызывающий код —
        `_autogate_conditions` условие «а» его больше не читает вовсе
        (см. докстринг `fsm_autogate._autogate_conditions`), значение
        только пробрасывается сигнатурой."""
        return self.root / "tasks" / self.TASK

    def checkout_code_branch(self) -> None:
        """Заводит КОДОВУЮ ветку задачи (`self.branch`) по-настоящему —
        история подтяжек (AC-3) живёт только в реальном git."""
        self.git("checkout", "-q", "-b", self.branch, config.MAIN_BRANCH)

    def commit_on_code_branch(self, filename: str, content: str,
                              message: str) -> str:
        self.git("checkout", "-q", self.branch)
        (self.root / filename).write_text(content, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD").stdout.strip()

    def commit_on_main(self, filename: str, content: str, message: str) -> str:
        self.git("checkout", "-q", config.MAIN_BRANCH)
        (self.root / filename).write_text(content, encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        sha = self.git("rev-parse", "HEAD").stdout.strip()
        self.git("checkout", "-q", self.branch)
        return sha

    def merge_main_into_code_branch(self) -> str:
        """Настоящий merge-коммит main в кодовую ветку задачи — родитель,
        который группа «остаётся человеку» (AC-3) обязана назвать."""
        self.git("checkout", "-q", self.branch)
        self.git("merge", "-q", "--no-ff", "-m",
                 "merge main into task branch", config.MAIN_BRANCH)
        return self.git("rev-parse", "HEAD").stdout.strip()

    def entry_report(self, acc_tdir=None, iteration: int = 1) -> tuple:
        """Вызывает `_maybe_autogate_acceptance` — единую точку входа в
        `acceptance` (SPEC AC-1) — с условиями б/в/г заглушенными на
        «выполнено» (предмет ЭТОЙ задачи — печать/журнал, не сами условия
        автогейта, SPEC «Не входит»: ADR-0007 их не меняет).

        Возвращает `(stdout, detail)` — `detail` уже проверен как
        РОВНО одна запись журнала с action == ACTION (SPEC AC-1)."""
        conn = store.db()
        t = store.get_task(conn, self.TASK)
        acc_tdir = acc_tdir if acc_tdir is not None else self.stale_disk_dir()
        with mock.patch.object(gates, "policy", return_value=gates.AUTO), \
             mock.patch.object(workspace, "on_task_branch", return_value=True), \
             mock.patch.object(workspace, "path", return_value=self.root), \
             mock.patch.object(acceptance, "run_full_suite",
                               return_value=(True, "")), \
             mock.patch.object(budget, "budget_block", return_value=None):
            out = self.capture(fsm_autogate._maybe_autogate_acceptance,
                               conn, self.TASK, t, acc_tdir, iteration)
        details = [d for _, a, d in self.journal_rows() if a == ACTION]
        self.assertEqual(len(details), 1,
                         f"записей «{ACTION}»: {len(details)} — {details}")
        return out, details[0]
