"""AC-7 (tasks/T067/SPEC.md): в песочницах тестов без реального git
(`fake_git` и аналогичные заглушки) сверка/авторазрешение молча
пропускается — тот же вырожденный случай деградации, что у остальной
части `_pull_main_or_escalate` (SPEC T051).

Зелёный с рождения: `gitcmd.commits_behind` под `fake_git` отвечает
`None` (git не отвечает осмысленно) — `_pull_main_or_escalate` возвращает
`"fresh"` до какой-либо попытки merge/разбора списка конфликтующих
файлов (`if not behind: return "fresh"`, `orchestrator/fsm.py`, ветка
существует с T051). Новый код T067 живёт строго ПОСЛЕ этой ранней точки
выхода — сценарий её физически не достигает, значит T067 никаким образом
эту ветку не задевает, и переход обязан пройти как и до задачи (тот же
приём, что `tasks/T051/acceptance_tests/test_ac6_fake_git_skips_freshness_silently.py`).
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, fsm, gitcmd, store  # noqa: E402
from tests.sandbox import fake_git  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]

PLAN_READY_MD = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 1
---

# PLAN: авторазрешение конфликта карты

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""


class FakeGitSandboxSkipsAutoResolutionTest(unittest.TestCase):
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
        branch = f"task/{self.TASK.lower()}-fakegit-mapconflict"
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

    def test_ac7_indev_to_review_advances_normally_without_a_real_git_branch(self):
        fsm.cmd_advance(self.TASK)

        self.assertEqual(
            self.task_row()["state"], "review",
            "без реального git сверка/авторазрешение обязаны молча "
            "пропускаться — переход выполняется как и до этой задачи, не "
            "отказывает и не роняет исключение")


if __name__ == "__main__":
    unittest.main()
