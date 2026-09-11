"""Общая песочница приёмочных тестов задачи 01M1RA0R9AH9RBAHD4A2Z5SEWQ
(не test_*.py — не подхватывается `unittest discover` напрямую, только
импортом из test_ac*.py).

Предмет — `orchestrator/fsm.py::_pull_main_or_escalate` ДО вызова `git
merge`: очистка незакоммиченной `docs/codebase-map.md` и прочего WIP
worktree'а (SPEC, требования 1-4). Тот же приём лёгкой FSM-песочницы без
реального git (мок `gitcmd.in_repo`/`gitcmd.git`/`fsm._origin_main_sha`),
каким уже пользуются `tests/test_fsm_map_conflict_autoresolve.py` и
`tests/test_branch_freshness_gate.py` (оба явно названы в AC-8 как
существующее поведение, которое эта задача не имеет права ослабить) —
не копия РЕАЛЬНОГО git из `tasks/T051`/`tasks/T067`: та песочница не
заводит `origin`-remote, которого требует текущая архитектура сверки
свежести (SPEC 01M1NBWPKNBXP9ZXXQDJM7AXPJ, `fsm._origin_main_sha` реально
фетчит `origin`) — без него `_origin_main_sha` вырождается и подтяжка
вообще не срабатывает (проверено прогоном исходного `tasks/T051`
дерева — оно красное уже сегодня, до этой задачи, по не связанной с ней
причине). Мок той же функции — тот же приём, каким обходят это
расхождение оба файла-образца выше.

Тесты не переоткрывают саму логику очистки (её ещё нет — эту задачу
впервые пишет developer после test_author) — только наблюдаемое поведение
`fsm.cmd_advance` на переходе `in_dev -> review` (роль `developer`,
`config.STATE_ROLE["in_dev"]`, тот же мандат кода, что несёт worktree
задачи на ВСЕХ трёх точках вызова `_pull_main_or_escalate`, SPEC
требование 2 — «мандат кода в этом worktree всегда у developer»).
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import (acceptance, alerts, catalog, config, fsm,  # noqa: E402
                          gitcmd, store, workspace)
from tests.sandbox import (SpyRun, capture, capture_new_task_id,  # noqa: E402
                           disk_backed_ls_tree_files, disk_backed_show,
                           fake_git)

REPO_ROOT = Path(__file__).resolve().parents[3]

MAP_REL = "docs/codebase-map.md"

PLAN_READY = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 1
---

# PLAN: очистка worktree перед подтяжкой main

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""


class PullCleanupSandbox(unittest.TestCase):
    """Задача в лёгкой песочнице без реального git (`fake_git` + мок
    `gitcmd.in_repo`) — тот же фикстур-код, что `tests/
    test_fsm_map_conflict_autoresolve.py::MapConflictAutoResolveTest`."""

    MAP_REL = MAP_REL

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
        # `fake_git` без REVIEW.md R1-F1 (01M1NBWPKNBXP9ZXXQDJM7AXPJ,
        # итерация 1) отвечает на "rev-parse FETCH_HEAD" пустой строкой —
        # `_pull_main_or_escalate` деградировала бы на "fresh" немедленно
        # и ни разу не позвала бы merge; truthy-заглушка держит прежний
        # путь исполнения (тот же приём, что оба файла-образца).
        origin_sha_patcher = mock.patch.object(
            fsm, "_origin_main_sha", return_value="deadbeefcafefeed")
        origin_sha_patcher.start()
        self.addCleanup(origin_sha_patcher.stop)
        # A7 (generic-путь заведения, AC-5): `cmd_new` коммитит артефакты
        # плотницки (`artifact_branch.write_commit`) — та функция зовёт
        # `subprocess.run` НАПРЯМУЮ, минуя `gitcmd.git`/фейк выше.
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

        self.capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(
            catalog.cmd_new, "Очистка worktree перед подтяжкой main")
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

    def journal_rows(self) -> list:
        return store.task_steps(store.db(), self.TASK)

    def journal_details(self) -> list[str]:
        return [r["detail"] or "" for r in self.journal_rows()]

    def write_plan_ready(self) -> None:
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / "PLAN.md").write_text(
            PLAN_READY.format(task=self.TASK), encoding="utf-8")

    def write_acceptance_plank(self) -> None:
        """Правка планки Оператором 06.09 (amend-tests): SPEC.md со
        `schema_version: 2` без `skip_tests` + непустой `acceptance_tests/`
        обязаны лежать на диске `self.tdir` ДО перехода — в лёгкой песочнице
        `disk_backed_show`/`disk_backed_ls_tree_files` читают «ветку» с
        диска, и без планки `_pull_main_or_escalate` честно отказывает
        («планка не найдена в источнике», SPEC 01M1R9YEK08XEQWBFX0929WFVJ).
        Тот же приём, что `tests/test_fsm_map_conflict_autoresolve.py::
        write_acceptance_plank` и `tests/test_branch_freshness_gate.py`."""
        self.tdir.mkdir(parents=True, exist_ok=True)
        (self.tdir / "SPEC.md").write_text(
            "---\n"
            f"task: {self.TASK}\n"
            "type: spec\n"
            "author_role: analyst\n"
            "status: ready\n"
            "schema_version: 2\n"
            "---\n\n"
            "# SPEC: планка\n\n"
            "## Критерии приёмки\n\nAC-1. ...\n",
            encoding="utf-8")
        tests_dir = self.tdir / "acceptance_tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / "test_stub.py").write_text(
            "import unittest\n\n\n"
            "class StubTest(unittest.TestCase):\n\n"
            "    def test_stub(self):\n        pass\n",
            encoding="utf-8")

    def advance_from_in_dev(self) -> str:
        self.write_plan_ready()
        self.write_acceptance_plank()
        self.set_state("in_dev")
        return self.capture(fsm.cmd_advance, self.TASK)

    @staticmethod
    def _ok(repo, *args) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(("git", "-C", str(repo), *args), 0, "", "")

    def _fixation_response(self, repo, *args):
        """Ответ на вызовы фиксации (`fixation._fix_external`,
        `config.PROJECTS/<target>`) — идут на ДРУГОМ repo, не на
        `self.wt_path`, и не имеют отношения к предмету этих тестов
        (тот же довод, что уже несёт docstring `_fixation_response` в
        `tests/test_branch_freshness_gate.py`): «чисто, нечего коммитить»
        безусловно, независимо от того, что симулирует WIP-сценарий
        конкретного теста для `self.wt_path`."""
        if args == ("rev-parse", "HEAD"):
            return subprocess.CompletedProcess(
                ("git", "-C", str(repo), *args), 0, "f" * 40 + "\n", "")
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
        if "commit" in args:
            return self._ok(repo, *args)
        return None


if __name__ == "__main__":
    unittest.main()
