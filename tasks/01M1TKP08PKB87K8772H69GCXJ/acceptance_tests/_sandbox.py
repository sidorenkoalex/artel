"""Общая песочница приёмочных тестов задачи 01M1TKP08PKB87K8772H69GCXJ
(R3 — `orchestrator/pull.py` + таблица `orchestrator/fsm._cmd_approve`,
не `test_*.py` — не подхватывается `unittest discover` напрямую, только
импортом из `test_ac*.py`).

`PullNodeSandbox` — лёгкая FSM-песочница БЕЗ реального git (тот же
приём, что `tests/test_branch_freshness_gate.py`/`tests/test_fsm_map_
conflict_autoresolve.py`, на которые прямо ссылается требование 5
SPEC), но зовёт `fsm._pull_main_or_escalate` НАПРЯМУЮ, минуя
`cmd_advance`/`cmd_approve` целиком: предмет проверки AC-1..AC-3, AC-5,
AC-7, AC-9 — ровно один узел подтяжки, не вся цепочка гейтов вокруг
него (PLAN.md/guard и т.п., не тронутые этой задачей). Задача заводится
напрямую `store.insert_task` (тем же приёмом, что `tests/test_fsm_
draft_mr_reentry.py`) — `catalog.cmd_new` со всей плотницкой запиской
артефактной ветки здесь не нужен.

`ApproveTableSandbox` — тот же приём для сценариев таблицы `_cmd_approve`
(AC-4/AC-8): подтяжка (`_pull_main_or_escalate`) на состоянии `acceptance`
и цикл `merge_gate` (`fsm_merge_gate._cmd_approve_merge_gate_cycle`)
замокана целиком — предмет проверки здесь ДИСПЕТЧЕРИЗАЦИЯ approve по
состоянию, не сама подтяжка/merge_gate (у них свои песочницы).
"""
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, fsm, gitcmd, store, workspace  # noqa: E402
from tests.sandbox import (TmpRootTest, capture, disk_backed_ls_tree_files,  # noqa: E402
                           disk_backed_show)

MAP_REL = "docs/codebase-map.md"

SPEC_WITH_AC_MARKUP = """---
task: {task}
type: spec
author_role: analyst
status: ready
schema_version: 2
---

# SPEC: планка (фикстура песочницы R3)

## Критерии приёмки

AC-1. Фикстура.
"""


class PullNodeSandbox(TmpRootTest):
    """Задача `self.TASK` в состоянии `in_dev`, ветка `self.BRANCH` —
    узел подтяжки вызывается напрямую через `self.pull(state)`."""

    TASK = "01PULLNODESANDBOXTASK1"
    BRANCH = f"task/{TASK.lower()}-x"

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        store.insert_task(store.db(), self.TASK, "Песочница подтяжки",
                          "in_dev", self.BRANCH, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)

        # `_read_branch_text_or_refuse`/`acceptance.materialize_from_branch`
        # читают SPEC.md/`acceptance_tests/` артефактной ветки через эти два
        # примитива (`artifact_source.resolve` — всегда `foreign=True`,
        # SPEC «Материалы») — без подмены оба чтения ушли бы в `gitcmd.git`
        # против несуществующего репозитория (тот же приём, что `tests/
        # test_branch_freshness_gate.py`).
        show_patcher = mock.patch.object(gitcmd, "show", disk_backed_show)
        show_patcher.start()
        self.addCleanup(show_patcher.stop)
        ls_patcher = mock.patch.object(gitcmd, "ls_tree_files",
                                       disk_backed_ls_tree_files)
        ls_patcher.start()
        self.addCleanup(ls_patcher.stop)

        self.wt_path = self.root / "wt"
        wt_patcher = mock.patch.object(
            workspace, "ensure", lambda task_id, branch: (self.wt_path, None))
        wt_patcher.start()
        self.addCleanup(wt_patcher.stop)

        # Sha origin main фиксирован — сценарии, которым важен реальный
        # merge, получают предсказуемый truthy `base` без обращения к
        # настоящему git (тот же приём, что и оба файла-образца выше);
        # AC-5 переопределяет этот патч своим маркерным значением.
        origin_sha_patcher = mock.patch.object(
            fsm, "_origin_main_sha", return_value="deadbeefcafefeed")
        origin_sha_patcher.start()
        self.addCleanup(origin_sha_patcher.stop)

    # ------------------------------------------------------------ утилиты

    def task_row(self):
        return store.get_task(store.db(), self.TASK)

    def state(self) -> str:
        return self.task_row()["state"]

    def journal_rows(self) -> list:
        return store.task_steps(store.db(), self.TASK)

    def journal_details(self) -> list[str]:
        return [r["detail"] for r in self.journal_rows()]

    def pull(self, state: str = "in_dev") -> str:
        conn = store.db()
        t = self.task_row()
        return fsm._pull_main_or_escalate(conn, self.TASK, t, state)

    def write_spec(self, text: str) -> None:
        tdir = config.TASKS / self.TASK
        tdir.mkdir(parents=True, exist_ok=True)
        (tdir / "SPEC.md").write_text(text, encoding="utf-8")

    def write_acceptance_plank(self) -> None:
        """SPEC.md с AC-разметкой (`requires_ac_markup` — `True`) и
        непустой `acceptance_tests/` — планка «найдена в источнике»."""
        self.write_spec(SPEC_WITH_AC_MARKUP.format(task=self.TASK))
        tests_dir = config.TASKS / self.TASK / "acceptance_tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / "test_stub.py").write_text(
            "import unittest\n\n\nclass StubTest(unittest.TestCase):\n\n"
            "    def test_stub(self):\n        pass\n", encoding="utf-8")

    def write_spec_requiring_ac_without_plank(self) -> None:
        """SPEC.md с AC-разметкой, но БЕЗ `acceptance_tests/` — планка «не
        найдена в источнике» (AC-3 «именованный отказ», не «pulled»)."""
        self.write_spec(SPEC_WITH_AC_MARKUP.format(task=self.TASK))

    # ------------------------------------------------ фейковый `gitcmd.in_repo`

    @staticmethod
    def _ok(repo, *args) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(
            ("git", "-C", str(repo), *args), 0, "", "")

    def in_repo_side_effect(self, *, conflict_files: list | None = None,
                            merge_stdout: str = "", merge_stderr: str = "",
                            overwrite_stderr: str | None = None):
        """Универсальный `gitcmd.in_repo` side_effect, параметризуемый
        исходом `merge` — успех / конфликт содержимого / инцидент «would
        be overwritten by merge» — и списком конфликтующих файлов для
        `diff --name-only --diff-filter=U`. Остальные вызовы (WIP-
        чекпоинт `checkpoint.commit_pull_checkpoint`, авторазрешение
        карты `_auto_resolve_map_conflict`: `checkout`/`add`/`commit`/
        `status --porcelain`/`diff --cached`/`reset`/`rev-parse HEAD`/
        `init`) — безобидный no-op успех, тем же приёмом, что
        `_fixation_response` в `tests/test_branch_freshness_gate.py`:
        предмет проверки этой задачи — ветвление ПОСЛЕ merge/конфликта,
        не сама фиксация/чекпоинт.

        Записывает вызовы `merge`/`merge --abort` в `self.merge_calls`/
        `self.abort_calls` — сценарии AC-9 сверяют их число.
        """
        self.merge_calls: list = []
        self.abort_calls: list = []

        def side_effect(repo, *args) -> subprocess.CompletedProcess:
            if args[:1] == ("merge",) and "--abort" in args:
                self.abort_calls.append((repo, args))
                return self._ok(repo, *args)
            if args[:1] == ("merge",):
                self.merge_calls.append((repo, args))
                if overwrite_stderr is not None:
                    return subprocess.CompletedProcess(
                        ("git", "-C", str(repo), *args), 1, "",
                        overwrite_stderr)
                if conflict_files:
                    return subprocess.CompletedProcess(
                        ("git", "-C", str(repo), *args), 1, merge_stdout,
                        merge_stderr)
                return self._ok(repo, *args)
            if args[:2] == ("diff", "--name-only"):
                files = conflict_files or []
                return subprocess.CompletedProcess(
                    ("git", "-C", str(repo), *args), 0,
                    "\n".join(files) + ("\n" if files else ""), "")
            return self._ok(repo, *args)

        return side_effect


class ApproveTableSandbox(TmpRootTest):
    """Задача `self.TASK` — заводится напрямую `self.insert(state, ...)`
    в нужном состоянии; `self.approve(sha)` зовёт `fsm._cmd_approve`
    напрямую (мимо lease, тем же приёмом, что `tests/test_fsm_draft_mr_
    reentry.py`). `confirm_fixation` и `github_adapter.ensure_draft_mr`
    замокана безусловно — сверка фиксации и Draft MR не относятся к
    предмету проверки этих тестов (диспетчеризация `_cmd_approve` по
    состоянию), тем же приёмом, что и упомянутый файл-образец."""

    TASK = "01APPROVETABLESANDBOX1"
    BRANCH = f"task/{TASK.lower()}-x"

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())

        confirm_patcher = mock.patch.object(
            fsm, "confirm_fixation", lambda *a: True)
        confirm_patcher.start()
        self.addCleanup(confirm_patcher.stop)

        draft_patcher = mock.patch.object(fsm.github_adapter, "ensure_draft_mr")
        self.ensure_draft_mr = draft_patcher.start()
        self.addCleanup(draft_patcher.stop)

    def insert(self, state: str, **overrides) -> None:
        store.insert_task(store.db(), self.TASK, "Песочница таблицы approve",
                          state, self.BRANCH, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        if overrides:
            store.update_task(store.db(), self.TASK, **overrides)

    def task_row(self):
        return store.get_task(store.db(), self.TASK)

    def state(self) -> str:
        return self.task_row()["state"]

    def approve(self, sha: str | None = None) -> str:
        return capture(fsm._cmd_approve, store.db(), self.TASK, sha, "sid")


if __name__ == "__main__":
    unittest.main()
