"""AC-6 (tasks/T051/SPEC.md): в песочницах тестов без реального git
(`fake_git` и аналогичные заглушки) сверка свежести молча пропускается;
существующие тесты остаются зелёными без ослабления существующих тестов,
гейтов, лимитов, guard-проверок и инвариантов (ADR-0002).

Песочница здесь — лёгкая (без реального git), тем же приёмом, что
`tests/test_review_freshness.py::ReviewFreshnessScenarioTest`: `gitcmd.git`
подменён заглушкой, отвечающей на любой вызов, не обращаясь к
репозиторию. Переход `in_dev -> review` обязан пройти как и до этой
задачи — свежесть здесь физически нечем сверить (веток нет), и это не
повод ни падать, ни отказывать переходу.
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from _sandbox import PLAN_READY_MD, fake_git  # noqa: E402
from orchestrator import catalog, config, fsm, gitcmd, store  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]


class FakeGitSandboxSkipsFreshnessTest(unittest.TestCase):
    TASK = "T001"

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

        git_patcher = mock.patch.object(gitcmd, "git", fake_git)
        git_patcher.start()
        self.addCleanup(git_patcher.stop)

        conn = store.db()
        store.create_schema(conn)
        branch = f"task/{self.TASK.lower()}-fakegit"
        store.insert_task(conn, self.TASK, "Песочница без git", "in_dev",
                          branch, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

        self.tdir = config.TASKS / self.TASK
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / "PLAN.md").write_text(
            PLAN_READY_MD.format(task=self.TASK), encoding="utf-8")

    def task_row(self):
        return store.db().execute(
            "SELECT * FROM tasks WHERE id=?", (self.TASK,)).fetchone()

    def test_ac6_indev_to_review_advances_normally_without_a_real_git_branch(self):
        fsm.cmd_advance(self.TASK)

        self.assertEqual(
            self.task_row()["state"], "review",
            "без реального git сверка свежести обязана молча пропускаться "
            "— переход выполняется как и до этой задачи, не отказывает и "
            "не роняет исключение")


if __name__ == "__main__":
    unittest.main()
