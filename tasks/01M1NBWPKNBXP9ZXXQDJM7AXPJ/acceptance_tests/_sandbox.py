"""Общая песочница приёмочных тестов задачи (не test_*.py — не
подхватывается `unittest discover` напрямую, только импортом из
test_ac*.py).

Два разных предмета проверки этой SPEC несут два разных класса
песочниц:

`OriginDivergedSandbox` — НАСТОЯЩИЙ git-репозиторий (`self.root`,
локальный пин `config.MAIN_BRANCH`) с НАСТОЯЩИМ bare `origin` remote
(`self.origin`), способный по-настоящему РАСХОДИТЬСЯ с пином
(`advance_origin_only`): предмет проверки AC-1/AC-2/AC-3/AC-4/AC-8 —
сравнение и merge относительно РЕАЛЬНОГО состояния origin, заглушкой
`gitcmd.git` это не изобразить (тот же довод, что у `tests/
test_gitcmd_branch_reads.py::RemoteBranchShaTest` и `tasks/
01M1GS5HZ1JXFGKVR95HEW0AEZ/acceptance_tests/_sandbox.py::
HeadInOriginSandbox`, откуда позаимствован приём bare-origin без сети).
Задача заводится generic-путём (`catalog.cmd_new`, A7): `tasks/<id>/`
коммитится артефактной веткой пульта плотницки (`artifact_branch.
commit_files`, тем же механизмом, что и сам `cmd_new`), без единого
worktree артефактной ветки — только кодовая ветка задачи (`t["branch"]`,
предмет самой сверки свежести) заводится здесь явно (`git branch`,
не `checkout`: рабочая копия песочницы остаётся на `config.MAIN_BRANCH`,
тем же приёмом, каким роль-разработчик заводит код-ветку первым шагом,
ADR-0005 п.9/T045/T048).

`MergeGateFreshCiWaitSandbox` — лёгкая песочница БЕЗ настоящего git
(тот же приём, что `tests/test_merge_gate_ci_wait.py::
MergeGateCiWaitUnitTest`): предмет проверки AC-5/AC-6/AC-7 —
ветвление ПОСЛЕ статуса CI на пути «fresh после push» гейта
`merge_gate` (ждать циклом или отказать немедленно), не сам git —
`time.sleep`/`time.monotonic` заглушены `FakeClock`, `ci.branch_status`
и сверка свежести (`fsm._pull_main_or_escalate`, замокана на `"fresh"`
намеренно — предмет ЭТИХ тестов начинается ПОСЛЕ неё, сама сверка
свежести отдельно покрыта `OriginDivergedSandbox` выше) — прямыми
моками.
"""
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import (acceptance, artifact_branch, catalog, ci, config,
                          fsm, fsm_merge_gate, github_adapter, gitcmd, store,
                          workspace)
from tests.sandbox import (capture, capture_new_task_id,  # noqa: E402
                           resilient_tmp_cleanup)

REPO_ROOT = Path(__file__).resolve().parents[3]

PLAN_READY = """---
task: {task}
type: plan
author_role: developer
status: ready
schema_version: 1
---

# PLAN: сверка свежести

## Подход

## Шаги

## Покрытие требований

## Влияние на систему
"""

UPSTREAM_MARKER_REL = "upstream-only.txt"
UPSTREAM_MARKER_CONTENT = "коммит, существующий только в main артели на origin\n"


# ---------------------------------------------------------------------------
# AC-1/AC-2/AC-3/AC-4/AC-8: настоящий git, настоящее расхождение с origin
# ---------------------------------------------------------------------------

class OriginDivergedSandbox(unittest.TestCase):
    """Задача заведена в настоящем git-репозитории с настоящим bare
    `origin`; на выходе из `setUp` origin ещё СИНХРОНЕН с локальным
    пином и с кодовой веткой задачи — расхождение заводит сам тест
    вызовом `advance_origin_only`."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, tmp)
        self.root = Path(tmp.name).resolve()

        self.git("init", "-q", "-b", config.MAIN_BRANCH)
        self.git("config", "user.email", "artel-tests@example.invalid")
        self.git("config", "user.name", "artel tests")
        (self.root / "marker.txt").write_text("main\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")

        bare = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, bare, ignore_errors=True)
        self.git("init", "-q", "--bare", bare)
        self.git("remote", "add", "origin", bare)
        self.git("push", "-q", "-u", "origin", config.MAIN_BRANCH)
        self.origin = Path(bare)

        for attr, value in (
            ("ROOT", self.root),
            ("DB", self.root / ".artel" / "state.db"),
            ("TASKS", self.root / "tasks"),
            ("LOGS", self.root / ".artel" / "logs"),
            ("PROJECTS", self.root / ".artel" / "projects"),
            ("TARGETS", self.root / "targets.yaml"),
            ("ROLE_HOME", self.root / ".artel" / "home"),
            ("ROLE_CONFIG_DIR", self.root / ".artel" / "home" / ".claude"),
            ("BACKUP_MARKER", self.root / ".artel" / "backup-marker"),
            ("WORKTREES", self.root / ".artel" / "worktrees"),
        ):
            patcher = mock.patch.object(config, attr, value)
            patcher.start()
            self.addCleanup(patcher.stop)

        store.create_schema(store.db())
        self.capture(catalog.cmd_init)
        _, self.TASK = capture_new_task_id(catalog.cmd_new, "Сверка свежести")
        self.branch = store.get_task(store.db(), self.TASK)["branch"]
        # Кодовая ветка задачи — заводит её разработчик, не `cmd_new`
        # (A7, генерик-путь: артефакты идут отдельной артефактной веткой
        # пульта). Плотницкий `git branch` (не `checkout`) эквивалентен
        # первому шагу роли-разработчика (ADR-0005 п.9) и не трогает
        # чекаут песочницы (остаётся на `config.MAIN_BRANCH`).
        self.git("branch", self.branch)

    capture = staticmethod(capture)

    # ------------------------------------------------------------ git-утилиты

    def git(self, *args: str, cwd=None) -> str:
        res = subprocess.run(["git", *args], cwd=cwd or self.root,
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0,
                         f"git {' '.join(args)} упал: {res.stderr}")
        return res.stdout

    def local_pin_sha(self) -> str:
        return self.git("rev-parse", config.MAIN_BRANCH).strip()

    def origin_main_sha(self) -> str:
        out = self.git("ls-remote", str(self.origin),
                       f"refs/heads/{config.MAIN_BRANCH}")
        return out.split()[0] if out.strip() else ""

    def advance_origin_only(self, filename: str = UPSTREAM_MARKER_REL,
                            content: str = UPSTREAM_MARKER_CONTENT) -> str:
        """Двигает main артели на `origin` вперёд БЕЗ единого касания
        локального пина `self.root` — ровно разрыв из «Контекста» SPEC
        (main мержит другая задача, локальный пин узнаёт об этом только
        следующим `pin-update`): коммит идёт отдельным клоном `origin`,
        не `self.root`, и пушится обратно. Возвращает sha нового HEAD
        main артели на origin.
        """
        clone_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, clone_dir, ignore_errors=True)
        subprocess.run(["git", "clone", "-q", str(self.origin), clone_dir],
                       check=True, capture_output=True)
        (Path(clone_dir) / filename).write_text(content, encoding="utf-8")
        subprocess.run(["git", "-C", clone_dir, "add", "-A"],
                       check=True, capture_output=True)
        subprocess.run(
            ["git", "-C", clone_dir,
             "-c", "user.email=artel-tests@example.invalid",
             "-c", "user.name=artel tests",
             "commit", "-q", "-m", "main артели ушёл вперёд"],
            check=True, capture_output=True)
        subprocess.run(["git", "-C", clone_dir, "push", "-q", "origin",
                       config.MAIN_BRANCH], check=True, capture_output=True)
        return self.origin_main_sha()

    # ------------------------------------------------------------ задача/FSM

    def task_row(self):
        return store.get_task(store.db(), self.TASK)

    def state(self) -> str:
        return self.task_row()["state"]

    def set_state(self, state: str) -> None:
        conn = store.db()
        conn.execute("UPDATE tasks SET state=? WHERE id=?", (state, self.TASK))
        conn.commit()

    def journal_details(self) -> list[str]:
        return [r["detail"] for r in store.db().execute(
            "SELECT detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,))]

    def write_plan_ready(self) -> str:
        """Коммитит PLAN.md ready в артефактную ветку пульта плотницки
        (`artifact_branch.commit_files`) — тем же механизмом, каким
        `catalog.cmd_new` уже коммитит SPEC.md/ТЗ (A7): реального
        worktree артефактной ветки эта песочница не заводит."""
        text = PLAN_READY.format(task=self.TASK)
        sha = artifact_branch.commit_files(
            self.TASK, {f"tasks/{self.TASK}/PLAN.md": text}, "PLAN ready")
        self.assertTrue(sha, "artifact_branch.commit_files не сработал")
        return sha

    def approve(self) -> str:
        """Двухшаговое подтверждение sha (`confirm_fixation`), тем же
        приёмом, что `tasks/01M1GS5HZ1JXFGKVR95HEW0AEZ/acceptance_tests/
        _sandbox.py::HeadInOriginSandbox.approve` — здесь на практике
        фиксации ещё нет (свежая задача), и первый заход проходит сразу,
        но приём остаётся общим на случай, если это когда-то изменится."""
        first = self.capture(fsm.cmd_approve, self.TASK)
        match = re.search(r"зафиксирован (\S+)", first)
        if match is None:
            return first
        second = self.capture(fsm.cmd_approve, self.TASK, match.group(1))
        return first + second

    def pull(self, state: str = "in_dev"):
        """Прямой вызов предмета проверки — `fsm._pull_main_or_escalate`
        — в обход диспетчеров `cmd_advance`/`cmd_approve` (те покрыты
        отдельно, AC-3): AC-1/AC-2/AC-4/AC-8 проверяют сам узел
        сверки/подтяжки, не конкретную точку входа."""
        t = store.get_task(store.db(), self.TASK)
        with mock.patch.object(acceptance, "run", return_value=(True, "ok")):
            return fsm._pull_main_or_escalate(store.db(), self.TASK, t, state)

    def worktree_file(self, rel: str) -> Path:
        return workspace.path(self.TASK) / rel


# ---------------------------------------------------------------------------
# AC-5/AC-6/AC-7: путь «fresh после push» гейта merge_gate, лёгкая песочница
# ---------------------------------------------------------------------------

class FakeClock:
    """Тот же приём, что `tests/test_merge_gate_ci_wait.py::FakeClock`:
    `sleep(s)` продвигает `monotonic()` на `s` вместо настоящего ожидания."""

    def __init__(self, start: float = 0.0):
        self.value = start
        self.sleep_calls: list[float] = []

    def monotonic(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.sleep_calls.append(seconds)
        self.value += seconds


NOCHECKS = (False, "у коммита abc12345 нет ни одной проверки CI — статус неизвестен")
GREEN = (True, "CI коммита abc12345 зелёный (1 проверок)")


class MergeGateFreshCiWaitSandbox(unittest.TestCase):
    """Лёгкая песочница без настоящего git — гейт CI-ожидания не зависит
    от git вовсе, предмет проверки начинается ПОСЛЕ push головы (тем же
    приёмом, что `tests/test_merge_gate_ci_wait.py::
    MergeGateCiWaitUnitTest`)."""

    TASK = "T001"
    BRANCH = "task/t001-zadacha"

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, tmp)
        root = Path(tmp.name)

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

        capture(catalog.cmd_init)
        store.insert_task(store.db(), self.TASK, "Задача", "merge_gate",
                          self.BRANCH, config.DEFAULT_TARGET, 25.0)

        self.clock = FakeClock()
        sleep_patcher = mock.patch.object(time, "sleep", self.clock.sleep)
        sleep_patcher.start()
        self.addCleanup(sleep_patcher.stop)
        monotonic_patcher = mock.patch.object(time, "monotonic",
                                              self.clock.monotonic)
        monotonic_patcher.start()
        self.addCleanup(monotonic_patcher.stop)

        # Сверка свежести уже пройдена ("fresh") — предмет проверки этой
        # группы тестов начинается ПОСЛЕ неё (обработка отсутствия
        # CI-проверок), не сама сверка (AC-1..AC-4/AC-8,
        # OriginDivergedSandbox выше).
        pull_patcher = mock.patch.object(fsm, "_pull_main_or_escalate",
                                         return_value="fresh")
        pull_patcher.start()
        self.addCleanup(pull_patcher.stop)

        push_patcher = mock.patch.object(github_adapter, "ensure_head_in_origin",
                                         return_value=(True, ""))
        self.ensure_head_in_origin = push_patcher.start()
        self.addCleanup(push_patcher.stop)

    def patch_branch_status(self, fn) -> None:
        patcher = mock.patch.object(ci, "branch_status", fn)
        patcher.start()
        self.addCleanup(patcher.stop)

    def patch_origin_main_sha(self, fn) -> None:
        patcher = mock.patch.object(fsm_merge_gate, "_origin_main_sha", fn)
        patcher.start()
        self.addCleanup(patcher.stop)

    def run_cycle(self) -> None:
        t = {"branch": self.BRANCH}
        fsm_merge_gate._cmd_approve_merge_gate_cycle(
            store.db(), self.TASK, "sess-1", t, "merge_gate")

    def journal_blob(self) -> str:
        rows = store.db().execute(
            "SELECT action, detail FROM steps WHERE task_id=? ORDER BY id",
            (self.TASK,)).fetchall()
        return "\n".join(f"{r['action']} | {r['detail']}" for r in rows).lower()
