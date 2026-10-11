"""Общая песочница приёмочных тестов задачи 01M1GCN1FPSC1A6WK9WD1Q1V8X
(«Лимиты пакетов контекста и гейт ёмкости диффа ревью»).

Не сканируется guard'ом на AC-маркеры/тест-методы (только test_*.py,
SPEC T081) — файлы test_ac*.py этого каталога делят с ним фикстуры.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import (brief, catalog, config, fsm, gitcmd,  # noqa: E402
                          review, store, workspace)
from tests.sandbox import (TmpRootTest, capture, capture_new_task_id,  # noqa: E402
                           fake_git)

TASK = "T001"

# --------------------------------------------------------------- brief.py

MAP_FRESH = ("---\nbuilt_at_sha: aaaa000011112222333344445555666677778888\n"
            "---\n\n# Карта\n")
SPEC_SMALL = "# SPEC\n\nМаркер-текста-SPEC.\n"
CONVENTIONS_SMALL = "# Конвенции проекта\n"


class BriefSandbox(TmpRootTest):
    """docs/codebase-map.md + CLAUDE.md + tasks/<TASK>/SPEC.md на диске —
    тот же минимум, что tests/test_brief.py::BriefUnitTest."""

    def setUp(self):
        super().setUp()
        (self.root / "docs").mkdir(parents=True)
        (self.root / "docs" / "codebase-map.md").write_text(
            MAP_FRESH, encoding="utf-8")
        (self.root / "CLAUDE.md").write_text(
            CONVENTIONS_SMALL, encoding="utf-8")
        (config.TASKS / TASK).mkdir(parents=True)
        (config.TASKS / TASK / "SPEC.md").write_text(
            SPEC_SMALL, encoding="utf-8")
        store.create_schema(store.db())
        self.conn = store.db()

    def build_brief(self, git=fake_git) -> str:
        with mock.patch.object(gitcmd, "git", git):
            return brief.developer_brief(self.conn, TASK)


# ------------------------------------------------------------- review.py

SPEC_MD = """---
task: {task}
type: spec
author_role: analyst
status: approved
---

# SPEC: тест лимитов пакета

## Требования
1. Пакет собирает оркестратор.
"""

PLAN_MD = """---
task: {task}
type: plan
author_role: developer
status: ready
---

# PLAN: тест лимитов пакета

## Подход
Реализация.
"""

REVIEW_MD = """---
task: {task}
type: review
author_role: reviewer
status: changes_requested
iteration: 1
---

# REVIEW: тест лимитов пакета

## Замечания
major — прошлая итерация.
"""

FORM_MD = """---
task: T000
type: review
author_role: reviewer
status: draft
---

# REVIEW: <заголовок>

## Замечания
"""

BRANCH = "task/t001-limity-paketov"


def standard_files(task: str = TASK) -> dict:
    return {
        f"tasks/{task}/SPEC.md": SPEC_MD.format(task=task),
        f"tasks/{task}/PLAN.md": PLAN_MD.format(task=task),
        "templates/REVIEW.md": FORM_MD,
    }


class FakeGitDiff:
    """Заглушка `gitcmd.git` для `review.review_package`: `show` — по
    словарю `files`, `diff`/`diff --stat` — по заготовленным строкам,
    остальное — «чисто» (rc=0, пусто)."""

    def __init__(self, files=None, diff="diff --git a b", stat="a.py | 1 +"):
        self.files = dict(files or {})
        self.diff = diff
        self.stat = stat
        self.calls: list[list[str]] = []

    def __call__(self, *args: str) -> subprocess.CompletedProcess:
        self.calls.append(list(args))
        if args and args[0] == "show":
            _, rel = args[1].split(":", 1)
            if rel not in self.files:
                return subprocess.CompletedProcess(
                    list(args), 128, "",
                    f"fatal: path '{rel}' does not exist")
            return subprocess.CompletedProcess(list(args), 0, self.files[rel], "")
        if args and args[0] == "rev-parse" and "--verify" in args:
            return subprocess.CompletedProcess(list(args), 1, "", "")
        if args and args[0] == "diff" and "--stat" in args:
            return subprocess.CompletedProcess(list(args), 0, self.stat, "")
        if args and args[0] == "diff":
            return subprocess.CompletedProcess(list(args), 0, self.diff, "")
        return subprocess.CompletedProcess(list(args), 0, "", "")


def build_review_package(git, task: str = TASK, branch: str = BRANCH,
                         title: str = "Лимиты пакетов", **kw) -> dict:
    """`review.review_package` под фейковым git — `config.ROOT` подменён
    на пустой временный каталог на время вызова.

    `review.artifact_text` при неудачном `git show` откатывается на
    чтение `config.ROOT / rel` с диска (рабочее дерево). Без подмены
    ROOT это читает НАСТОЯЩИЙ репозиторий пульта — `tasks/T001/REVIEW.md`
    реальной (исторической) задачи T001 в этом же дереве утекал бы в
    пакет как «прошлая итерация», когда `files` не содержит этот путь
    (обнаружено прогоном этого же файла — реальный REVIEW T001 оказался
    в тексте пакета вместо ожидаемого «не показан»)."""
    with tempfile.TemporaryDirectory() as tmp:
        with mock.patch.object(gitcmd, "git", git), \
                mock.patch.object(config, "ROOT", Path(tmp)):
            return review.review_package(task, title, branch, **kw)


# ------------------------------------------------------------ fsm_advance

PLAN_READY = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 1
---

# PLAN: гейт ёмкости

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""


class GateSandbox(TmpRootTest):
    """Задача в `in_dev` с готовым PLAN.md — переход `in_dev -> review`
    через `fsm.cmd_advance` (тот же каркас настройки, что
    `tests/test_branch_freshness_gate.py::BranchFreshnessGateTest`)."""

    def setUp(self):
        super().setUp()
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")

        self.wt_path = self.root / "wt"
        wt_patcher = mock.patch.object(
            workspace, "ensure", lambda task_id, branch: (self.wt_path, None))
        wt_patcher.start()
        self.addCleanup(wt_patcher.stop)

        with mock.patch.object(gitcmd, "git", fake_git):
            self.capture(catalog.cmd_init)
            _, self.TASK = capture_new_task_id(catalog.cmd_new, "Гейт ёмкости диффа")
        self.tdir = config.TASKS / self.TASK
        self.branch = self.task_row()["branch"]

    def task_row(self):
        return store.db().execute("SELECT * FROM tasks WHERE id=?",
                                  (self.TASK,)).fetchone()

    def state(self) -> str:
        return self.task_row()["state"]

    def journal_details(self) -> list[str]:
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,))]

    def write_plan_ready(self) -> None:
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / "PLAN.md").write_text(
            PLAN_READY.format(task=self.TASK), encoding="utf-8")

    def _set_state(self, state: str) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, self.TASK))
        conn.commit()

    def advance_with_snapshot_diff(self, diff_text: str) -> str:
        """Прогон `advance` из `in_dev` с заданным содержимым полного diff
        снимка (`git diff config.MAIN_BRANCH...<ветка>`); ветка не отстала
        от main (`commits_behind` = 0) — подтяжка не звонится, гейт ёмкости
        считается по единственному нужному git-вызову."""
        self.write_plan_ready()
        self._set_state("in_dev")

        def git_stub(*args):
            if (args and args[0] == "diff"
                    and args[-1] == f"{config.MAIN_BRANCH}...{self.branch}"):
                return subprocess.CompletedProcess(list(args), 0, diff_text, "")
            return fake_git(*args)

        with mock.patch.object(gitcmd, "git", git_stub), \
                mock.patch.object(gitcmd, "commits_behind", return_value=0):
            return capture(fsm.cmd_advance, self.TASK)
