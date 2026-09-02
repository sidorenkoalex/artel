"""AC-7: Полный сценарий одной новой задачи артели (заведение ->
артефактная ветка пульта при жизни -> Draft-MR -> verifying -> merge_gate
-> done) проходит без единой записи `tasks/<её id>/` в код-ветках или main
пульта — артефакты живут только в артефактной ветке пульта и, после
закрытия, в `refs/artifacts/<id>` артели.

Сценарий проведён напрямую по значимым узлам (`cmd_new` ->
`github_adapter.ensure_draft_mr` -> роль пишет артефакты шага ->
`store.set_state` в промежуточные состояния -> `fsm_merge_gate.
_cmd_approve_merge_gate`), тем же приёмом прямого вызова тела перехода,
каким уже пользуется `tests/test_fsm_merge_gate_done_snapshot.py` (минуя
lease/мьютекс — те не касаются предмета этой проверки, гейт-логика
инвариантов 12/19 покрыта отдельно, AC-15). Сеть — только локальный bare
`self.origin`, `gh`/CI замоканы.

Красен до реализации: сегодня `cmd_new` без `target=` заводит `tasks/<id>/`
прямо в НОВОЙ КОДОВОЙ ветке (AC-5 ещё не выполнен) — уже на первом шаге
сценария утверждение «ни одной записи tasks/<id>/ в код-ветках» нарушено;
тест падает на самой ранней проверке, не доходя до merge_gate.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import (artifact_branch, catalog, checkpoint, ci,  # noqa: E402
                          config, fsm_merge_gate, gitcmd, github_adapter,
                          store)
from tests.sandbox import RealGitSandbox, resilient_tmp_cleanup  # noqa: E402

ARTEL_TARGETS_YAML = """targets:
  artel:
    forge: github
    url: https://example.invalid/artel
    base: main
    token_slot: artel-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""


class FullArtelTaskScenarioTest(RealGitSandbox):

    def setUp(self):
        super().setUp()
        config.TARGETS.write_text(ARTEL_TARGETS_YAML, encoding="utf-8")
        bare_tmp = tempfile.TemporaryDirectory()
        self.addCleanup(resilient_tmp_cleanup, bare_tmp)
        self.origin = Path(bare_tmp.name) / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b",
                        config.MAIN_BRANCH, str(self.origin)],
                       check=True, capture_output=True, text=True)
        self.git("remote", "add", "origin", str(self.origin))
        self.git("push", "-q", "-u", "origin", config.MAIN_BRANCH)

    def code_branch_tree_files(self, branch: str, task_id: str) -> list:
        return gitcmd.ls_tree_files(branch, f"tasks/{task_id}") or []

    def main_tree_files(self, task_id: str) -> list:
        return gitcmd.ls_tree_files(config.MAIN_BRANCH, f"tasks/{task_id}") or []

    def origin_ref_files(self, ref: str, task_id: str) -> list:
        res = subprocess.run(
            ["git", "-C", str(self.origin), "ls-tree", "-r", "--name-only", ref],
            capture_output=True, text=True)
        return [p for p in res.stdout.splitlines() if p] if res.returncode == 0 else []

    def snapshot_ref_exists(self, task_id: str) -> bool:
        res = subprocess.run(
            ["git", "-C", str(self.origin), "show-ref", "--verify", "--quiet",
             f"refs/artifacts/{task_id}"], capture_output=True, text=True)
        return res.returncode == 0

    def test_ac7_full_lifecycle_never_writes_task_dir_to_code_or_main(self):
        # 1. Заведение (AC-5): tasks/<id>/ обязан родиться в артефактной
        # ветке пульта, не в новой кодовой ветке.
        task_id = catalog.cmd_new("Полный сценарий артели")
        t = store.get_task(store.db(), task_id)
        code_branch = t["branch"]
        self.assertEqual(
            self.code_branch_tree_files(code_branch, task_id)
            if gitcmd.branch_exists(code_branch) else [],
            [], "tasks/<id>/ не должен появиться в кодовой ветке при заведении")
        self.assertTrue(
            gitcmd.ls_tree_files(artifact_branch.branch_name(task_id),
                                 f"tasks/{task_id}"),
            "SPEC.md обязан быть в артефактной ветке пульта сразу после cmd_new")

        # Кодовая ветка задачи — своим коммитом (роль-разработчик пишет код
        # ПУЛЬТА напрямую в config.ROOT, т.к. до собственной семантики
        # мержа внешнего кода на его фордже A7 ещё не доходит — «Не
        # входит» SPEC; тот же приём, что и `test_fsm_merge_gate_done_
        # snapshot.py`).
        self.git("checkout", "-b", code_branch)
        (self.root / "feature.txt").write_text("код фичи\n", encoding="utf-8")
        self.git("add", "feature.txt")
        self.git("commit", "-q", "-m", f"{task_id}: код фичи")
        self.git("checkout", config.MAIN_BRANCH)
        self.git("push", "-q", "-u", "origin", code_branch)

        # 2. Draft-MR (github_adapter.ensure_draft_mr) — не пишет
        # tasks/<id>/ никуда, только push кодовой ветки + `gh pr create`.
        with mock.patch.object(
                ci, "gh",
                lambda *a, **kw: subprocess.CompletedProcess(
                    list(a), 0, "https://example.invalid/pr/1", "")):
            github_adapter.ensure_draft_mr(store.db(), task_id, t)
        t = store.get_task(store.db(), task_id)
        self.assertEqual(t["draft_mr_created"], 1)
        self.assertEqual(self.code_branch_tree_files(code_branch, task_id), [])

        # 3. Роль пишет артефакты шага (например PLAN.md) в свой рабочий
        # каталог `.artel/projects/artel/workspace/tasks/<id>/` (AC-6) —
        # `commit_step_artifacts` обязан перенести их в артефактную ветку,
        # не в кодовую.
        role_task_dir = config.PROJECTS / config.DEFAULT_TARGET / "workspace" / "tasks" / task_id
        role_task_dir.mkdir(parents=True)
        (role_task_dir / "PLAN.md").write_text("план\n", encoding="utf-8")
        checkpoint.commit_step_artifacts(store.db(), task_id, "developer")
        self.assertIn(f"tasks/{task_id}/PLAN.md",
                      gitcmd.ls_tree_files(artifact_branch.branch_name(task_id),
                                          f"tasks/{task_id}") or [])
        self.assertEqual(self.code_branch_tree_files(code_branch, task_id), [])

        # 4. verifying -> merge_gate (переходы состояния сами — забота
        # других инвариантов/AC, здесь важна только неприкосновенность
        # tasks/<id>/ в код-ветках/main на всём пути).
        store.set_state(store.db(), task_id, "verifying", "operator",
                        expected_state=t["state"])
        store.set_state(store.db(), task_id, "merge_gate", "operator",
                        expected_state="verifying")
        self.assertEqual(self.code_branch_tree_files(code_branch, task_id), [])
        self.assertEqual(self.main_tree_files(task_id), [])

        # 5. merge_gate -> done: `_cmd_approve_merge_gate` напрямую (минуя
        # lease/мьютекс — не предмет этой проверки).
        t = store.get_task(store.db(), task_id)
        with mock.patch.object(ci, "branch_status",
                               lambda branch: (True, "зелёный (тест)")):
            result = fsm_merge_gate._cmd_approve_merge_gate(
                store.db(), task_id, "merge_gate", t)

        self.assertEqual(result, ("done",))
        row = store.get_task(store.db(), task_id)
        self.assertEqual(row["state"], "done")

        # tasks/<id>/ по-прежнему нигде в main пульта — ни при жизни, ни
        # после done код фичи (без tasks/<id>/) смержен, артефакты — нет.
        self.assertEqual(self.main_tree_files(task_id), [])
        self.assertIn("feature.txt",
                      gitcmd.ls_tree_files(config.MAIN_BRANCH, "") or [])

        # После закрытия — снапшот в refs/artifacts/<id> артели (origin),
        # артефактная ветка пульта убрана.
        self.assertTrue(self.snapshot_ref_exists(task_id),
                        f"refs/artifacts/{task_id} не появился в origin "
                        f"артели после done")
        snapshot_files = self.origin_ref_files(f"refs/artifacts/{task_id}", task_id)
        self.assertTrue(any(f.startswith(f"tasks/{task_id}/")
                            for f in snapshot_files),
                        f"снапшот не несёт tasks/{task_id}/: {snapshot_files}")
        self.assertFalse(gitcmd.branch_exists(artifact_branch.branch_name(task_id)),
                         "артефактная ветка пульта обязана быть убрана после done")


if __name__ == "__main__":
    unittest.main()
