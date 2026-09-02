"""Общая песочница приёмочных тестов задачи (не test_*.py — не подхватывается
`unittest discover` напрямую, только импортом из test_ac*.py).

Позаимствована у `tests/test_git_fixation.py::RealPultGitTest` (ROOT —
настоящий git-репозиторий на main, `catalog.cmd_new` (SPEC T048) сам
заводит настоящую ветку/worktree задачи, артефакты пишутся и коммитятся
В WORKTREE) и `tasks/T087/acceptance_tests/_sandbox.py` (настоящий
bare-origin remote без сети): предмет проверки этой задачи — присутствие
головы ветки задачи в РЕАЛЬНОМ origin — заглушкой `gitcmd.git` этого не
изобразить (тот же довод, что у обоих источников). Опрос CI (`ci.
verifying_status`) подменяется отдельно (`set_ci_green`) — сеть `gh`
здесь ни при чём, предмет проверки только push/origin.

Флоу до `review` нарочно короткий: SPEC.md несёт `schema_version: 1`
(без AC-разметки) — `tests_writing` пропускается (`fsm.py::_cmd_approve`,
ветка `spec_gate`), PLAN.md — минимальный `ready`, REVIEW.md — approved
без реестра замечаний (`schema_version: 2` — `guard.requires_registry`
требует ровно >=3). Это решения теста, не факты SPEC — если разработчик
собьёт эту цепочку (например, потребует AC-разметку и на schema_version
1), сама эта песочница откажет явным `assert`, а не тихо разойдётся с
реализацией.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import catalog, ci, config, fsm, gitcmd, store, workspace  # noqa: E402
from tests.sandbox import capture, capture_new_task_id, resilient_tmp_cleanup  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]

SPEC_SCHEMA1 = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 1
---

# SPEC: маркер песочницы (голова в origin)

## Контекст
Маркер.

## Требования
1. Маркер.

## Критерии приёмки
AC-1. Маркер.

## Не входит
"""

PLAN_READY = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 1
---

# PLAN: маркер песочницы

## Подход
Маркер.

## Шаги
1. Маркер.

## Покрытие требований
| Требование | Шаг |
|---|---|
| 1 | 1 |

## Влияние на систему
Нет.
"""

REVIEW_APPROVED = """---
task: {task}
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 2
---

# REVIEW: маркер песочницы

## Соответствие SPEC
| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | |

## Замечания
- ...

## Вердикт
approved

## Проверено исполнением
`python3 -m unittest discover -s tests` — зелёный.
"""


class HeadInOriginSandbox(unittest.TestCase):
    """Задача доведена до `review` в настоящем git-репозитории с настоящим
    bare-origin — тест сам решает, пушить ли голову ветки до вызова
    `fsm.cmd_advance`/`fsm.cmd_approve`, и сверяет результат по РЕАЛЬНОМУ
    содержимому `self.origin`.
    """

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, tmp)
        self.root = Path(tmp.name).resolve()

        self.git("init", "-q", "-b", config.MAIN_BRANCH)
        self.git("config", "user.email", "artel-tests@example.invalid")
        self.git("config", "user.name", "artel tests")
        shutil.copytree(REPO_ROOT / "templates", self.root / "templates")
        shutil.copytree(REPO_ROOT / "skills", self.root / "skills")
        shutil.copy(REPO_ROOT / ".gitignore", self.root / ".gitignore")
        (self.root / "docs").mkdir()
        (self.root / "docs" / "codebase-map.md").write_text(
            "---\nbuilt_at_sha: 0000000000000000000000000000000000000000\n"
            "---\n\n# Карта\n", encoding="utf-8")
        (self.root / "CLAUDE.md").write_text("# Конвенции\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")

        bare = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, bare, ignore_errors=True)
        self.git("init", "-q", "--bare", str(bare))
        self.git("remote", "add", "origin", str(bare))
        self.git("push", "-q", "-u", "origin", config.MAIN_BRANCH)
        self.origin = bare

        for attr, value in (
            ("ROOT", self.root),
            ("DB", self.root / ".artel" / "state.db"),
            ("TASKS", self.root / "tasks"),
            ("LOGS", self.root / ".artel" / "logs"),
            ("ROLE_HOME", self.root / ".artel" / "home"),
            ("ROLE_CONFIG_DIR", self.root / ".artel" / "home" / ".claude"),
            ("WORKTREES", self.root / ".artel" / "worktrees"),
        ):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        self.capture(catalog.cmd_init)
        # SPEC T094: id — ULID, не предсказуемый "T001".
        _, self.TASK = capture_new_task_id(catalog.cmd_new, "Голова в origin")
        self.branch = store.get_task(store.db(), self.TASK)["branch"]

        self.set_ci_green()

    # ------------------------------------------------------------ утилиты

    def git(self, *args: str, cwd=None,
           check: bool = True) -> subprocess.CompletedProcess:
        res = subprocess.run(["git", *args], cwd=cwd or self.root,
                             capture_output=True, text=True)
        if check:
            self.assertEqual(res.returncode, 0,
                             f"git {' '.join(args)} упал: {res.stderr}")
        return res

    capture = staticmethod(capture)

    def task_dir(self) -> Path:
        """Каталог артефактов задачи — в её worktree (SPEC T048)."""
        return workspace.path(self.TASK) / "tasks" / self.TASK

    def git_in_worktree(self, *args: str,
                        check: bool = True) -> subprocess.CompletedProcess:
        wt = workspace.path(self.TASK)
        return self.git(*args, cwd=wt, check=check)

    def commit_task_dir(self, message: str = "артефакт") -> str:
        self.git_in_worktree("add", f"tasks/{self.TASK}")
        self.git_in_worktree("commit", "-q", "-m", message)
        return self.branch_head()

    def branch_head(self) -> str:
        """Голова ветки задачи — общий для всех worktree ref, читается
        с main (тот же приём, что `RealPultGitTest.head`)."""
        return gitcmd.branch_head_sha(self.branch)

    def origin_branch_sha(self) -> str:
        res = self.git("rev-parse", "--verify", "--quiet",
                       f"refs/heads/{self.branch}", cwd=self.origin,
                       check=False)
        return res.stdout.strip() if res.returncode == 0 else ""

    def push_branch_to_origin(self) -> None:
        """Публикует ТЕКУЩУЮ голову ветки задачи в origin — штатным
        `git push -u origin <branch>` (тот же вызов, что
        `github_adapter.ensure_draft_mr`)."""
        self.git_in_worktree("push", "-q", "-u", "origin", self.branch)

    def break_origin_remote(self) -> None:
        """origin указывает на несуществующий путь — любой push обязан
        упасть по-настоящему (не заглушкой)."""
        self.git_in_worktree("remote", "set-url", "origin",
                             str(self.root / "no-such-remote-here"))

    def restore_origin_remote(self) -> None:
        self.git_in_worktree("remote", "set-url", "origin", str(self.origin))

    def set_ci_green(self) -> None:
        """И `verifying` (`ci.verifying_status`, review->verifying->
        acceptance), И `merge_gate` (`ci.branch_status`, `_cmd_approve_
        merge_gate`) читают CI по-разному (SPEC T079 vs T017/T053) —
        обе точки замокан зелёными: предмет проверки этой задачи — push/
        origin, не сеть `gh`."""
        for target, value in (
            ("verifying_status", lambda branch: (
                ci.VERIFYING_GREEN, "CI коммита aaaaaaaa зелёный (1 проверок)")),
            ("branch_status", lambda branch: (
                True, "CI коммита aaaaaaaa зелёный (1 проверок)")),
        ):
            patcher = mock.patch.object(ci, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def state(self) -> str:
        return store.get_task(store.db(), self.TASK)["state"]

    def task_row(self):
        return store.get_task(store.db(), self.TASK)

    def steps(self) -> list:
        return store.task_steps(store.db(), self.TASK)

    def journal_tail(self, since: int) -> str:
        return "\n".join(f"{r['action']} | {r['detail']}"
                         for r in self.steps()[since:]).lower()

    # ------------------------------------------------------------ флоу FSM

    def enter_spec_gate(self) -> None:
        (self.task_dir() / "SPEC.md").write_text(
            SPEC_SCHEMA1.format(task=self.TASK), encoding="utf-8")
        self.commit_task_dir()
        self.capture(fsm.cmd_advance, self.TASK)
        assert self.state() == "spec_gate", (
            f"предпосылка песочницы: SPEC.md ready обязан завести "
            f"spec_gate, состояние {self.state()!r}")

    def enter_in_dev(self) -> None:
        self.enter_spec_gate()
        sha = self.branch_head()
        self.capture(fsm.cmd_approve, self.TASK, sha)
        assert self.state() == "in_dev", (
            f"предпосылка песочницы: approve на spec_gate со "
            f"schema_version 1 обязан пропустить tests_writing "
            f"(без AC-разметки) и завести in_dev напрямую, состояние "
            f"{self.state()!r}")

    def enter_review(self) -> None:
        """Доводит задачу до `review`; REVIEW.md ещё не написан."""
        self.enter_in_dev()
        (self.task_dir() / "PLAN.md").write_text(
            PLAN_READY.format(task=self.TASK), encoding="utf-8")
        self.commit_task_dir()
        self.capture(fsm.cmd_advance, self.TASK)
        assert self.state() == "review", (
            f"предпосылка песочницы: PLAN.md ready обязан завести "
            f"review, состояние {self.state()!r}")

    def write_review_approved(self) -> str:
        """Пишет и коммитит REVIEW.md approved — голова ветки после
        этого коммита ЕЩЁ НЕ обязана быть в origin (решает сам тест)."""
        (self.task_dir() / "REVIEW.md").write_text(
            REVIEW_APPROVED.format(task=self.TASK), encoding="utf-8")
        return self.commit_task_dir()

    def approve(self) -> str:
        """Двухшаговое подтверждение sha (`confirm_fixation`/
        `APPROVE_NEEDS_SHA`), тем же приёмом, что
        `tasks/T087/acceptance_tests/_sandbox.py::approve` /
        `tasks/T053/acceptance_tests/_sandbox.py::approve`."""
        import re
        first = self.capture(fsm.cmd_approve, self.TASK)
        match = re.search(r"зафиксирован (\S+)", first)
        if match is None:
            return first
        second = self.capture(fsm.cmd_approve, self.TASK, match.group(1))
        return first + second

    def enter_merge_gate(self) -> None:
        """Доводит задачу до `merge_gate`: review approved и запушен,
        `verifying` зелёный (CI замокан), `acceptance` пройден approve'ом.
        Голова ветки задачи в origin синхронна на выходе — тесты AC-8/AC-9
        сами решают, расходиться ли с ней дальше."""
        self.enter_review()
        self.write_review_approved()
        self.push_branch_to_origin()
        self.capture(fsm.cmd_advance, self.TASK)  # review -> verifying
        assert self.state() == "verifying", self.state()
        self.capture(fsm.cmd_advance, self.TASK)  # verifying -> acceptance (CI зелёный)
        assert self.state() == "acceptance", self.state()
        self.approve()  # acceptance -> merge_gate
        assert self.state() == "merge_gate", (
            f"предпосылка песочницы: approve на acceptance обязан "
            f"завести merge_gate, состояние {self.state()!r}")
