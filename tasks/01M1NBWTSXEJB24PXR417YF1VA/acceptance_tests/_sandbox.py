"""Общая песочница приёмочных тестов 01M1NBWTSXEJB24PXR417YF1VA — мандат
роли в WIP-чекпоинте после таймаута шага (SPEC.md).

Чекпоинт (`orchestrator/checkpoint.py::commit_timeout_checkpoint`) коммитит
РЕАЛЬНОЕ рабочее дерево ветки задачи (`git add`/`git diff`/`git commit`) и
читает/пишет РЕАЛЬНУЮ артефактную ветку пульта (`orchestrator/
artifact_branch.py`) — заглушкой `gitcmd.git` эту механику не проверить и
не отличить от отсутствия коммита вовсе (тот же довод, что у
`tests/test_timeout_checkpoint.py` и
`tasks/T041/acceptance_tests/test_checkpoint_after_timeout.py`, откуда и
позаимствован приём песочницы: `RealPultGitTest`,
`tests/test_git_fixation.py`).

`TimeoutThenKilledProc` — тот же приём, что у
`tasks/T041/acceptance_tests/test_checkpoint_after_timeout.py`: таймаут
коротко замыкает `proc.wait()` без реального 30-минутного ожидания;
`leaves_wip` пишет WIP ВНУТРИ `wait()`, а не до запуска шага — иначе он
испортил бы дерево ещё на входной сверке `fixation.check_integrity`
следующего запуска, а не на итоге ЭТОГО шага (тот же класс дефекта, что
модульный докстринг `tasks/T041/acceptance_tests/
test_checkpoint_after_timeout.py` объясняет для своего сценария).

`commit_timeout_checkpoint` работает только для self/артели
(`config.DEFAULT_TARGET`, докстринг функции — «Только догфуд») — все
сценарии этой песочницы заводятся через generic self-путь
`RealPultGitTest`, тем же приёмом, что и её собственные тесты.
"""
import subprocess
import sys
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import artifact_branch, fsm, gitcmd, runner, store, workspace  # noqa: E402
from tests.sandbox import FakeStream  # noqa: E402
from tests.test_git_fixation import RealPultGitTest  # noqa: E402

# SPEC валиден по guard (schema_version 2, AC-разметка, без skip_tests) —
# нужен только чтобы `fsm.cmd_approve` из `spec_gate` увёл задачу в
# `tests_writing` (`orchestrator/fsm.py`, требует `guard.requires_ac_markup`),
# а не в `in_dev` напрямую (образец — `SPEC_V2` в
# `tests/test_acceptance_tests_flow.py`). Содержательная сторона критерия
# этой заглушки не проверяется — сценарии AC-7 нужен только сам факт
# состояния `tests_writing`, откуда `runner.cmd_run` запускает роль
# `test_author` (`orchestrator/config.py::STATE_ROLE`).
SPEC_V2_STUB = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: песочница мандата WIP-чекпоинта

## Контекст

## Требования

1. ...

## Критерии приёмки

AC-1. Критерий-заглушка для песочницы приёмочных тестов.

## Не входит
"""


class TimeoutThenKilledProc:
    """Таймаут шага: `wait()` сначала бросает `TimeoutExpired` (после
    опционального побочного эффекта `leaves_wip` — WIP, который агент
    успел оставить до того, как замолчал), затем отдаёт код убитого
    процесса."""

    def __init__(self, lines, leaves_wip=None):
        self.stdout = FakeStream(lines)
        self._calls = 0
        self._leaves_wip = leaves_wip

    def wait(self, timeout=None) -> int:
        self._calls += 1
        if self._calls == 1:
            if self._leaves_wip:
                self._leaves_wip()
            raise subprocess.TimeoutExpired(cmd="claude", timeout=60)
        return -9

    def kill(self) -> None:
        pass


class MandateCheckpointTest(RealPultGitTest):
    """Мандат-фикстура: worktree кодовой ветки задачи (`self.wt`, то же
    место, что `runner.role_cwd` возвращает ЛЮБОЙ роли self/артели —
    `orchestrator/runner.py::role_cwd`, докстринг: «этот worktree, не
    внешний артефактный каталог») + чтение артефактной ветки пульта того
    же task_id.
    """

    def setUp(self):
        super().setUp()
        # До A7 `cmd_new` заводил worktree кодовой ветки сам; generic-путь
        # (AC-5) его больше не создаёт — песочница заводит его явно, тем
        # же приёмом, что `tests/test_timeout_checkpoint.py::
        # _WorktreeCheckpointTest.setUp`.
        branch = store.get_task(store.db(), self.TASK)["branch"]
        wt_path, error = workspace.ensure(self.TASK, branch)
        self.assertIsNone(error, f"worktree не создан: {error}")
        self.wt = wt_path
        self.addCleanup(self._remove_worktree)

    def _remove_worktree(self) -> None:
        """`workspace.ensure` заводит worktree ПО РЕАЛЬНОМУ пути
        (`config.WORKTREES` не патчится этой песочницей, см. докстринг
        модуля) — без явной уборки он переживёт `TmpRootTest.tearDown`
        и останется сиротой в РЕАЛЬНОМ дереве репозитория."""
        workspace.remove(self.TASK)

    def worktree_task_dir(self) -> Path:
        d = self.wt / "tasks" / self.TASK
        d.mkdir(parents=True, exist_ok=True)
        return d

    def write_code_file(self, rel: str, text: str) -> Path:
        """Файл кодовой ветки ВНЕ `tasks/<id>/` — путь мандата developer."""
        path = self.wt / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def worktree_git(self, *args: str) -> str:
        res = subprocess.run(["git", "-C", str(self.wt), *args],
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"git {' '.join(args)}: {res.stderr}")
        return res.stdout

    def worktree_head(self) -> str:
        return gitcmd.head_sha(self.wt)

    def code_branch_committed_paths(self, sha: str) -> list:
        """Пути, реально попавшие в коммит `sha` кодовой ветки — то, что
        покажет `git show --name-only` для этого коммита."""
        out = self.worktree_git("show", "--name-only", "--format=", sha)
        return [line for line in out.splitlines() if line]

    def orchestrator_checkpoint_steps(self) -> list:
        return [r for r in store.task_steps(store.db(), self.TASK)
               if r["actor"] == "orchestrator"
               and r["action"].startswith("WIP-чекпоинт")]

    def artifact_branch(self) -> str:
        return artifact_branch.branch_name(self.TASK)

    def artifact_branch_task_files(self) -> list:
        return gitcmd.ls_tree_files(self.artifact_branch(),
                                    f"tasks/{self.TASK}") or []

    def artifact_branch_subject(self) -> str:
        res = gitcmd.git("log", "-1", "--format=%s", self.artifact_branch())
        self.assertEqual(res.returncode, 0, res.stderr)
        return res.stdout.strip()

    def run_agent(self, proc) -> str:
        """Тот же приём, что `RealPultGitTest.run_faked`, но с заданным
        подложным процессом агента вместо всегда успешного `FakeProc`
        (`tasks/T041/acceptance_tests/test_checkpoint_after_timeout.py`)."""
        real_popen = subprocess.Popen

        def side_effect(cmd, *args, **kwargs):
            if cmd and cmd[0] == "claude":
                return proc
            return real_popen(cmd, *args, **kwargs)

        with mock.patch.object(runner, "spawn_agent", side_effect=side_effect):
            return self.capture(runner.cmd_run, self.TASK)

    def enter_tests_writing(self) -> None:
        """spec_gate -> tests_writing: SPEC.md версии 2 с AC-разметкой,
        без `skip_tests` (`orchestrator/fsm.py::cmd_approve`) — та же
        механика, что `RealPultGitTest.enter_spec_gate`/`enter_in_dev`,
        только версия SPEC другая, чтобы не срезать `tests_writing`."""
        self.task_dir().mkdir(parents=True, exist_ok=True)
        spec_text = SPEC_V2_STUB.format(task=self.TASK)
        (self.task_dir() / "SPEC.md").write_text(spec_text, encoding="utf-8")
        self._seed_artifact_branch(f"tasks/{self.TASK}/SPEC.md", spec_text,
                                   f"{self.TASK}: SPEC готов")
        self.capture(fsm.cmd_advance, self.TASK)
        sha = self.head()
        self.capture(fsm.cmd_approve, self.TASK, sha)
        self.assertEqual(store.get_task(store.db(), self.TASK)["state"],
                         "tests_writing")
