"""Приёмочные тесты T059 — автокоммит артефактов роли и
worktree-чекпоинт.

Источник — tasks/T059/SPEC.md, «Критерии приёмки» (AC-1..AC-5).

Песочница — `RealPultGitTest` (tests/test_git_fixation.py), тот же приём,
что и у `tasks/T041/acceptance_tests/test_checkpoint_after_timeout.py`:
автокоммит и чекпоинт коммитят РЕАЛЬНОЕ рабочее дерево worktree'а задачи
(`git add`/`git commit`) — заглушкой `gitcmd.git` эту механику не
проверить и не отличить от отсутствия коммита вовсе. Процесс агента
шага — подложный (`SuccessProc`/`TimeoutThenKilledProc`/`FailedProc`
ниже), тот же приём, что у T041: побочный эффект (WIP-файл, свой
коммит роли) происходит ВНУТРИ `wait()`, не до запуска шага — иначе он
испортил бы дерево ещё на входной сверке `fixation.check_integrity`, а
не на итоге ЭТОГО шага.

WIP пишется по адресу `tasks/<id>/PLAN.md` ВНУТРИ worktree задачи
(`self.task_dir()`, метод `RealPultGitTest`), не по устаревшему адресу
главной копии (`config.TASKS`) — именно этот перепутанный адрес и есть
дефект, из-за которого приёмочный тест T041 падает на текущем коде
(SPEC T059, «Контекст»); здесь адрес верный с самого начала. Файл —
валидный ready PLAN.md (шаблон `PLAN_READY` из `tests/test_git_fixation.py`,
уже проверенный на прохождение guard'а в `ExternalTargetAdvanceIgnoresDirtyCheckTest`
того же модуля), чтобы AC-1 могло дойти до реального `advance` в
`review`, а не только до факта коммита.
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config, fsm, gitcmd, runner, store, workspace  # noqa: E402
from tests.test_git_fixation import (FakeStream, PLAN_READY,  # noqa: E402
                                     RealPultGitTest)


class SuccessProc:
    """Успешный шаг роли (rc=0): опциональный побочный эффект
    (`on_wait` — WIP-файл, свой коммит роли) происходит внутри `wait()`,
    тот же приём, что у `TimeoutThenKilledProc`/`FailedProc` ниже и у
    tasks/T041/acceptance_tests."""

    def __init__(self, lines, on_wait=None):
        self.stdout = FakeStream(lines)
        self._on_wait = on_wait

    def wait(self, timeout=None) -> int:
        if self._on_wait:
            self._on_wait()
        return 0

    def kill(self) -> None:
        pass


class TimeoutThenKilledProc:
    """Таймаут шага: `wait()` сначала бросает `TimeoutExpired` (после
    опционального `leaves_wip`), затем отдаёт код убитого процесса —
    тот же приём, что `tasks/T041/acceptance_tests`."""

    def __init__(self, lines, leaves_wip=None):
        self.stdout = FakeStream(lines)
        self._calls = 0
        self._leaves_wip = leaves_wip

    def wait(self, timeout=None) -> int:
        self._calls += 1
        if self._calls == 1:
            if self._leaves_wip:
                self._leaves_wip()
            raise subprocess.TimeoutExpired(cmd="claude",
                                            timeout=config.AGENT_TIMEOUT_SEC)
        return -9

    def kill(self) -> None:
        pass


class FailedProc:
    """Провал по коду возврата — НЕ таймаут: `wait()` сразу отдаёт
    `returncode`, опционально оставив WIP до этого."""

    def __init__(self, lines, returncode, leaves_wip=None):
        self.stdout = FakeStream(lines)
        self.returncode = returncode
        self._leaves_wip = leaves_wip

    def wait(self, timeout=None) -> int:
        if self._leaves_wip:
            self._leaves_wip()
        return self.returncode

    def kill(self) -> None:
        pass


class AutocommitAndCheckpointTest(RealPultGitTest):
    """AC-1..AC-4: автокоммит артефактов шага и worktree-чекпоинт таймаута."""

    def run_agent(self, proc) -> str:
        """Тот же приём, что `RealPultGitTest.run_faked`, но с заданным
        подложным процессом агента вместо всегда успешного `FakeProc`."""
        real_popen = subprocess.Popen

        def side_effect(cmd, *args, **kwargs):
            if cmd and cmd[0] == "claude":
                return proc
            return real_popen(cmd, *args, **kwargs)

        with mock.patch.object(runner, "spawn_agent", side_effect=side_effect):
            return self.capture(runner.cmd_run, self.TASK)

    def write_plan(self) -> Path:
        """PLAN.md ready, валидный по guard — ПО АДРЕСУ WORKTREE задачи
        (`task_dir()`), не главной копии пульта."""
        path = self.task_dir() / "PLAN.md"
        path.write_text(PLAN_READY.format(task=self.TASK), encoding="utf-8")
        return path

    def leave_uncommitted_plan(self) -> None:
        """То, что реально оставляет роль, не успевшая закоммитить
        собственный артефакт до конца шага (AC-1)."""
        self.write_plan()

    def commit_plan_itself(self) -> None:
        """То, что реально делает роль, которая сама коммитит свой
        артефакт до конца шага (AC-2) — конвенция conventions-core."""
        self.write_plan()
        self.git_in_worktree("add", f"tasks/{self.TASK}")
        self.git_in_worktree("commit", "-q", "-m", "developer: PLAN.md")

    def orchestrator_steps(self) -> list:
        return [r for r in store.task_steps(store.db(), self.TASK)
               if r["actor"] == "orchestrator"]

    def autocommit_journal_entries(self) -> list:
        return [r for r in self.orchestrator_steps()
               if "автокоммит" in f"{r['action']} {r['detail']}".lower()]

    def test_ac1_successful_step_with_uncommitted_changes_autocommits(self):
        self.enter_in_dev()

        self.run_agent(SuccessProc(["готово\n"],
                                   on_wait=self.leave_uncommitted_plan))

        self.assertTrue(
            gitcmd.is_clean(repo=workspace.path(self.TASK)),
            "AC-1: автокоммит коммитит незакоммиченные изменения шага — "
            "worktree обязан стать снова чистым")
        subject = self.git_in_worktree("log", "-1", "--format=%s").strip()
        self.assertEqual(
            subject,
            f"{self.TASK}: артефакты шага developer (автокоммит оркестратора)",
            f"AC-1: сообщение служебного коммита — фактическое: {subject!r}")

        entries = self.autocommit_journal_entries()
        self.assertEqual(
            len(entries), 1,
            f"AC-1: журнал обязан нести ровно одну запись actor=orchestrator "
            f"по факту автокоммита — найдено записей actor=orchestrator: "
            f"{[dict(r) for r in self.orchestrator_steps()]}")

        out = self.capture(fsm.cmd_advance, self.TASK)

        self.assertNotIn(
            "не закоммичен", out,
            f"AC-1: advance не отказывает по грязной копии после "
            f"автокоммита — вывод:\n{out}")
        self.assertEqual(
            store.get_task(store.db(), self.TASK)["state"], "review",
            f"AC-1: advance проходит без инцидента целостности — "
            f"вывод:\n{out}")

    def test_ac2_role_committed_changes_itself_no_empty_autocommit(self):
        self.enter_in_dev()
        before = self.head()

        self.run_agent(SuccessProc(["готово\n"],
                                   on_wait=self.commit_plan_itself))

        after_role_commit = self.head()
        self.assertNotEqual(
            after_role_commit, before,
            "предусловие теста: роль сама закоммитила свой PLAN.md")
        self.assertEqual(
            self.autocommit_journal_entries(), [],
            "AC-2: нечего коммитить — автокоммит не пишет запись в журнал")
        self.assertEqual(
            self.head(), after_role_commit,
            "AC-2: нечего коммитить — автокоммит не создаёт пустой коммит "
            "поверх коммита роли")

    def test_ac3_timeout_checkpoint_stays_in_task_worktree(self):
        self.enter_in_dev()
        main_before = self.git("rev-parse", "HEAD").strip()
        foreign = self.root / "chuzhaya-sessiya-pulta.md"
        foreign.write_text("мусор чужой сессии пульта (инцидент T048)\n",
                           encoding="utf-8")

        out = self.run_agent(TimeoutThenKilledProc(
            ["агент работает, потом молчит\n"],
            leaves_wip=self.leave_uncommitted_plan))

        self.assertIn("таймаут", out)
        self.assertTrue(
            gitcmd.is_clean(repo=workspace.path(self.TASK)),
            "AC-3: чекпоинт коммитится В worktree задачи — тот снова чист")
        self.assertEqual(
            self.git("rev-parse", "HEAD").strip(), main_before,
            "AC-3: рабочее дерево пульта не получает ни коммита")
        root_status = self.git("status", "--porcelain")
        self.assertIn(
            foreign.name, root_status,
            "AC-3: рабочее дерево пульта не получает `add` — посторонний "
            "файл остаётся untracked")
        sha = gitcmd.head_sha(workspace.path(self.TASK))
        shown = self.git_in_worktree("show", "--stat", sha)
        self.assertNotIn(
            foreign.name, shown,
            "AC-3: посторонний файл вне worktree задачи не попадает в "
            "коммит-чекпоинт")

    def test_ac4_return_code_failure_creates_no_checkpoint(self):
        self.enter_in_dev()
        before = self.head()

        with mock.patch.object(config, "AGENT_ATTEMPTS", 1), \
                mock.patch.object(runner.time, "sleep", lambda _: None):
            self.run_agent(FailedProc(
                ["падаю с кодом возврата\n"], returncode=1,
                leaves_wip=self.leave_uncommitted_plan))

        self.assertEqual(
            self.head(), before,
            "AC-4: провал шага по коду возврата (не таймаут) не создаёт "
            "коммит-чекпоинт (инвариант 30)")
        self.assertFalse(
            gitcmd.is_clean(repo=workspace.path(self.TASK)),
            "AC-4: рабочее дерево worktree остаётся незакоммиченным, как "
            "до этой задачи")


# AC-5: manual — «все существующие тесты зелёные» и «допустимые правки
# тестов — только адрес дерева чекпоинта (T041) и пути патчей» проверяются
# полным прогоном `tests/` (CI, `.github/workflows/ci.yml`) и обзором
# ДИФФА веток `tests/test_timeout_checkpoint.py`/`tasks/T041/acceptance_tests`
# на приёмке Оператором/ревьювером — это утверждение о СОСТАВЕ правки чужих
# файлов вне tasks/T059/, не поведение, которое можно закодировать unittest
# внутри этого каталога (тот же довод, что у AC-5 в
# tasks/T041/acceptance_tests, и AC-4 в tasks/T040/acceptance_tests).


if __name__ == "__main__":
    unittest.main()
