"""Проводка уборки ветки задачи в `origin` через тело гейта мержа (SPEC
01M5FGJW4RBN9C9P48Q8MDHJX1, требования 1, 4; REVIEW итерация 1, R1-F1).

Свойства самой уборки (исходы, подсказки, сбои git) держит долгоживущий
файл задачи, зовущий `cleanup.cleanup_merged_remote` напрямую; здесь —
только то, что тело гейта зовёт её после `done` и не зовёт на исходе
push «moved». Тело `_cmd_approve_merge_gate` зовётся напрямую тем же
приёмом, что `tests/test_fsm_merge_gate_done_snapshot.py`; ветка задачи
публикуется в bare-`origin` проекта до вызова гейта, чтобы «ветки нет»
после `done` было следствием уборки, а не отсутствия публикации.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import (acceptance, artifact_branch, catalog, ci,  # noqa: E402
                          config, fsm_merge_gate, keychain, store)
from tests.sandbox import (RealGitSandbox, artel_target_entry,  # noqa: E402
                           capture, init_bare_origin, resilient_tmp_cleanup)

TARGET = "extproj"
CLEANUP_ACTION = "уборка"


class _GateWiringCases:
    """Сценарии — у внешнего проекта и у артели одним набором."""

    TASK = ""

    def patch(self, target, attr, replacement) -> None:
        patcher = mock.patch.object(target, attr, replacement)
        patcher.start()
        self.addCleanup(patcher.stop)

    def approve(self):
        t = store.get_task(store.db(), self.TASK)
        box = {}

        def body():
            box["result"] = fsm_merge_gate._cmd_approve_merge_gate(
                store.db(), self.TASK, "merge_gate", t,
                confirmed_ci_note="зелёный (тест)")
        out = capture(body)
        return box["result"], out

    def origin_has_branch(self) -> bool:
        res = subprocess.run(
            ["git", "--git-dir", str(self.bare_origin), "for-each-ref",
             f"refs/heads/{self.branch}"], capture_output=True, text=True)
        return bool(res.stdout.strip())

    def cleanup_notes(self) -> list:
        return [row["detail"] or "" for row in
                store.task_steps(store.db(), self.TASK)
                if row["action"] == CLEANUP_ACTION]

    def test_done_removes_task_branch_from_origin(self):
        """После `("done",)` ветки задачи в bare-`origin` проекта нет, у
        задачи одна запись «уборка» — «ветка origin <ветка>: удалена».

        Ловит мутацию: вызов `cleanup.cleanup_merged_remote` удалён из
        `_cleanup_merged_task` (или зовётся только для одного вида
        проекта) — ветка остаётся в `origin`, записи «уборка» нет.
        """
        self.assertTrue(self.origin_has_branch(), "фикстура: ветки нет")

        result, out = self.approve()

        self.assertEqual(result, ("done",), out)
        self.assertEqual(store.task_state(store.db(), self.TASK), "done")
        self.assertFalse(self.origin_has_branch(),
                         f"ветка задачи осталась в origin:\n{out}")
        self.assertEqual(self.cleanup_notes(),
                         [f"ветка origin {self.branch}: удалена"], out)

    def test_moved_keeps_task_branch_in_origin(self):
        """Исход push мержа «moved»: ветка задачи в `origin` на месте,
        записи «уборка» нет.

        Ловит мутацию: уборка перенесена до проверки исхода
        `_push_merged_main` (зовётся без условия `"ok"`) — на «moved»
        ветка удалена, запись «уборка» есть.
        """
        self.patch(fsm_merge_gate, "_push_merged_main",
                   lambda *a, **k: "moved")

        result, out = self.approve()

        self.assertEqual(result, ("moved", self.branch), out)
        self.assertTrue(self.origin_has_branch(), out)
        self.assertEqual(self.cleanup_notes(), [], out)


class ExternalGateWiringTest(_GateWiringCases, RealGitSandbox):
    """Задача внешнего проекта: `origin` — bare-`origin` клона проекта."""

    TASK = "01MRGWIREEXT0000000001"

    def setUp(self):
        super().setUp()
        capture(catalog.cmd_init)
        pult_origin = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, pult_origin, ignore_errors=True)
        init_bare_origin(pult_origin, self.git)
        self.git("remote", "add", "origin", str(pult_origin))
        self.git("push", "-q", "-u", "origin", config.MAIN_BRANCH)
        self.branch = f"task/{self.TASK.lower()}-x"
        config.TARGETS.write_text(
            "targets:\n"
            f"  {TARGET}:\n"
            "    forge: github\n"
            f"    url: http://localhost/{TARGET}\n"
            f"    base: {config.MAIN_BRANCH}\n"
            f"    token_slot: {TARGET}-token\n"
            "    no_paths: []\n"
            "    project_skills: []\n"
            "    merge_gate: operator\n",
            encoding="utf-8")
        store.insert_task(store.db(), self.TASK, "Задача внешнего проекта",
                          "merge_gate", self.branch, TARGET,
                          config.DEFAULT_BUDGET_USD)
        bare_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, bare_tmp)
        self.bare_origin = Path(bare_tmp.name) / "origin.git"
        init_bare_origin(self.bare_origin)
        self.clone = config.PROJECTS / TARGET / "repo"
        self.clone.mkdir(parents=True)
        self.wgit("init", "-q", "-b", config.MAIN_BRANCH)
        self.wgit("remote", "add", "origin", str(self.bare_origin))
        self.wgit("config", "user.email", "artel@example.invalid")
        self.wgit("config", "user.name", "artel tests")
        (self.clone / "marker.txt").write_text("main\n", encoding="utf-8")
        self.wgit("add", "-A")
        self.wgit("commit", "-q", "-m", "init")
        self.wgit("push", "-q", "origin", config.MAIN_BRANCH)
        artifact_branch.commit_files(
            self.TASK, {f"tasks/{self.TASK}/PLAN.md": "план\n"},
            f"{self.TASK}: план")
        self.wgit("checkout", "-q", "-b", self.branch)
        (self.clone / "feature.txt").write_text("код фичи\n", encoding="utf-8")
        self.wgit("add", "feature.txt")
        self.wgit("commit", "-q", "-m", f"{self.TASK}: код фичи")
        self.wgit("push", "-q", "origin", self.branch)
        self.patch(ci, "branch_status", lambda branch: (True, "зелёный (тест)"))
        self.patch(keychain, "token", lambda slot: f"tok-{slot}")

    def wgit(self, *args: str) -> str:
        res = subprocess.run(["git", *args], cwd=self.clone,
                             capture_output=True, text=True)
        self.assertEqual(res.returncode, 0,
                         f"git {' '.join(args)}: {res.stderr}")
        return res.stdout


class ArtelGateWiringTest(_GateWiringCases, RealGitSandbox):
    """Задача артели: `origin` — bare-`origin` пульта."""

    TASK = "01MRGWIREART0000000001"

    def setUp(self):
        super().setUp()
        config.TARGETS.write_text(
            "targets:\n" + artel_target_entry(base=config.MAIN_BRANCH,
                                              url="http://localhost/artel"),
            encoding="utf-8")
        self.bare_origin = self.add_synced_origin()
        capture(catalog.cmd_init)
        self.branch = f"task/{self.TASK.lower()}-x"
        self.checkout(self.branch, create=True)
        (self.root / "feature.txt").write_text("код задачи\n", encoding="utf-8")
        self.git("add", "feature.txt")
        self.git("commit", "-q", "-m", f"{self.TASK}: код задачи")
        self.git("push", "-q", "origin", self.branch)
        self.checkout(config.MAIN_BRANCH)
        store.insert_task(store.db(), self.TASK, "Задача артели",
                          "merge_gate", self.branch, config.DEFAULT_TARGET,
                          config.DEFAULT_BUDGET_USD)
        text = (f"---\ntask: {self.TASK}\ntype: plan\nauthor_role: developer\n"
                f"status: ready\nschema_version: 2\n---\n\n# PLAN\n\n"
                f"## Подход\n\nФикстура.\n")
        artifact_branch.commit_files(
            self.TASK, {f"tasks/{self.TASK}/PLAN.md": text},
            f"{self.TASK}: PLAN.md")
        self.patch(acceptance, "run_full_suite",
                   lambda root: (True, "42 passed (тест)"))
        self.patch(ci, "branch_status", lambda branch: (True, "зелёный (тест)"))
        self.patch(ci, "main_line_status", lambda sha, repo=None:
                   ci.MainLineStatus(ci.MAIN_GREEN, sha, [], [], "",
                                     "зелёный (тест)"))


if __name__ == "__main__":
    unittest.main()
