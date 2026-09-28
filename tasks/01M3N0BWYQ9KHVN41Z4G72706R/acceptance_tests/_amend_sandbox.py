"""Песочница настоящего git для `amend-tests` (AC-4, AC-9) — надстройка
`RealGitSandbox` (tests/sandbox.py) тем же рецептом, что
`tests/test_amend.py::AmendThenReviewGateTest`: артефактная ветка,
worktree задачи и лок `tests_locked_sha` — настоящие, `amend-tests`
зовётся как команда Оператора.

Два способа завести задачу в `in_dev` с зафиксированной планкой:

- `enter_in_dev_through_gate` — штатный выход из `tests_writing`
  настоящим `advance` (планка зафиксирована кодом, в котором уже есть эта
  задача: «после мержа»);
- `enter_in_dev_legacy` — планка без строк группы закоммичена на
  артефактную ветку и зафиксирована прямой записью `tests_locked_sha`
  в БД, минуя новый выход из `tests_writing`, с датой создания задачи
  задолго до этой задачи и без единой записи журнала о переходе — так
  выглядит в БД задача, чья планка зафиксирована до мержа этой задачи.
"""
import io
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import (amend, artifact_branch, catalog, config,  # noqa: E402
                          fsm, gitcmd, store, workspace)
from tests.sandbox import (RealGitSandbox, capture,  # noqa: E402
                           capture_new_task_id)

SPEC_TWO_AC = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: вложенная песочница amend-tests

## Контекст

## Требования

1. ...

## Критерии приёмки

AC-1. Первый критерий, проверяемый тестом.
AC-2. Второй критерий, проверяемый пометкой.

## Не входит
"""

PLAN_MD = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 2
---

# PLAN: вложенная песочница amend-tests

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""


def plank_file(group_line: str | None, variant: str = "исходный") -> str:
    """Файл планки вложенной задачи: AC-1 — тестом, AC-2 — пометкой
    manual; `group_line` — строка группы целиком (`None` — строки нет),
    `variant` — отличие текста, чтобы правка была правкой."""
    group = f"\n{group_line}" if group_line else ""
    return f'''"""Фикстура планки вложенной задачи ({variant}).{group}
Красен до реализации: фикстура песочницы amend-tests, покрывает оба критерия.
"""
import unittest


class AcceptanceTest(unittest.TestCase):
    def test_ac1_first_criterion(self):
        """Фикстурный критерий ({variant}).

        Ловит мутацию: фикстура вложенной песочницы.
        """
        self.assertTrue(True)


# AC-2: manual — фикстура вложенной песочницы
'''


class AmendSandbox(RealGitSandbox):

    TASK_TITLE = "amend-tests и строка группы"

    def setUp(self):
        super().setUp()
        self.add_synced_origin()
        capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(catalog.cmd_new, self.TASK_TITLE)
        self.branch = artifact_branch.branch_name(self.TASK)
        self.code_branch = self.row()["branch"]
        wt_path, error = workspace.ensure(self.TASK, self.code_branch)
        self.assertIsNone(error, f"worktree не создан: {error}")
        self.wt_path = wt_path
        self.tdir = wt_path / "tasks" / self.TASK
        (self.wt_path / "feature.txt").write_text("код фичи\n", encoding="utf-8")
        self.git_wt("add", "feature.txt")
        self.git_wt("commit", "-q", "-m", f"{self.TASK}: код фичи")

    def row(self):
        return store.db().execute("SELECT * FROM tasks WHERE id=?",
                                  (self.TASK,)).fetchone()

    def state(self) -> str:
        return self.row()["state"]

    def git_wt(self, *args: str) -> str:
        res = subprocess.run(["git", "-C", str(self.wt_path), *args],
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0,
                         f"git -C {self.wt_path} {' '.join(args)}: {res.stderr}")
        return res.stdout

    def artifact_commit(self, files: dict, message: str) -> str:
        sha = artifact_branch.commit_files(self.TASK, files,
                                           f"{self.TASK}: {message}")
        self.assertTrue(sha, f"коммит {message!r} на артефактную ветку не удался")
        return sha

    def plank_rel(self, name: str = "test_ac.py") -> str:
        return f"tasks/{self.TASK}/acceptance_tests/{name}"

    def _enter_tests_writing(self) -> None:
        self.artifact_commit(
            {f"tasks/{self.TASK}/SPEC.md": SPEC_TWO_AC.format(task=self.TASK),
             f"tasks/{self.TASK}/PLAN.md": PLAN_MD.format(task=self.TASK)},
            "SPEC")
        capture(fsm.cmd_advance, self.TASK)  # spec_writing -> spec_gate
        sha = gitcmd.head_sha(config.PROJECTS / config.DEFAULT_TARGET)
        capture(fsm.cmd_approve, self.TASK, sha)  # -> tests_writing
        self.assertEqual(self.state(), "tests_writing")

    def enter_in_dev_through_gate(self) -> None:
        """Штатный путь: планка со строкой группы проходит новый выход из
        `tests_writing`, лок ставит сам переход."""
        self._enter_tests_writing()
        self.artifact_commit(
            {self.plank_rel(): plank_file("Группа: разовый")},
            "acceptance_tests")
        out = capture(fsm.cmd_advance, self.TASK)  # tests_writing -> in_dev
        self.assertEqual(self.state(), "in_dev",
                         f"штатный выход из tests_writing не прошёл: {out}")
        self.assertTrue(self.row()["tests_locked_sha"])

    def enter_in_dev_legacy(self) -> None:
        """Планка без строк группы, зафиксированная до мержа этой задачи:
        лок записан прямо в БД, новый выход из `tests_writing` не
        исполнялся, задача заведена задолго до этой."""
        self._enter_tests_writing()
        locked = self.artifact_commit(
            {self.plank_rel(): plank_file(None)}, "acceptance_tests")
        conn = store.db()
        conn.execute(
            "UPDATE tasks SET state='in_dev', tests_locked_sha=?, "
            "created_at='2026-08-01T00:00:00+00:00' WHERE id=?",
            (locked, self.TASK))
        conn.commit()

    def write_worktree_plank(self, content: str, name: str = "test_ac.py") -> None:
        tests_dir = self.tdir / "acceptance_tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / name).write_text(content, encoding="utf-8")

    def amend(self, reason: str = "правка планки в песочнице") -> tuple[bool, str]:
        """(отказ, весь текст исхода) `amend-tests`: отказ — `SystemExit`
        команды; текст — её вывод, сообщение выхода и записи журнала
        задачи, появившиеся за этот вызов."""
        before = len(store.task_steps(store.db(), self.TASK))
        buf = io.StringIO()
        refused = False
        message = ""
        try:
            with redirect_stdout(buf):
                amend.cmd_amend_tests(self.TASK, reason)
        except SystemExit as exc:
            refused = True
            message = str(exc.code)
        journal = "\n".join(
            f"{r['action']} {r['detail'] or ''}"
            for r in store.task_steps(store.db(), self.TASK)[before:])
        return refused, "\n".join((buf.getvalue(), message, journal))
