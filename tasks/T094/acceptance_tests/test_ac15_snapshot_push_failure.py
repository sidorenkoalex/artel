"""Приёмочный тест T094 — AC-15 (tasks/T094/SPEC.md, «Критерии приёмки»).

AC-15: «При недоступности push снапшота в origin целевого переход
done/killed всё равно совершается и не удаляет кодовую и артефактную
ветки; повторная попытка push снапшота выполняется при следующей
команде этой задачи и при прогоне doctor.»

Недоступность origin имитируется порчей `remote origin` рабочего клона
целевого (`self.target_workspace`) — тот же remote, на который
указывает `targets.yaml` (`url`, `_sandbox.TARGETS_YAML`) и который уже
сегодня существует как единственная реальная точка выхода в сеть у
клона целевого; сеть по-настоящему не участвует ни в отказе, ни
в восстановлении (`git push` на несуществующий локальный путь отказывает
тем же кодом возврата, что и недоступный форндж).

Красен до реализации: `refs/artifacts/<id>` целевого сегодня не
публикует никто (см. `test_ac13_ac14_snapshot_on_close.py`) — переход
`killed` сегодня безусловно убирает worktree/каталог/ветку, никакого
гейта на успех push нет вовсе.
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import catalog, cleanup, doctor, gitcmd, store  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import ExternalTargetGitSandbox  # noqa: E402


def _snapshot_ref_exists(origin: Path, task_id: str) -> bool:
    res = subprocess.run(
        ["git", "-C", str(origin), "show-ref", "--verify", "--quiet",
         f"refs/artifacts/{task_id}"],
        capture_output=True, text=True)
    return res.returncode == 0


class Ac15SnapshotPushFailureTest(ExternalTargetGitSandbox):

    def _break_origin(self) -> None:
        self.wgit("remote", "set-url", "origin",
                 "/nonexistent/does-not-exist.git")

    def _fix_origin(self) -> None:
        self.wgit("remote", "set-url", "origin", str(self.target_origin))

    def test_ac15_transition_completes_and_keeps_branches_when_push_fails(self):
        task_id = catalog.cmd_new("Задача внешнего target", target=self.TARGET)
        artifact_branches_before = {
            b for b in (gitcmd.list_branches() or [])
            if gitcmd.ls_tree_files(b, f"tasks/{task_id}")
        }
        self.assertTrue(artifact_branches_before, "нет артефактной ветки")

        self._break_origin()
        cleanup.cmd_kill(task_id)

        row = store.get_task(store.db(), task_id)
        self.assertEqual(
            row["state"], "killed",
            "переход в killed обязан совершиться, даже если push "
            "снапшота недоступен (AC-15)")

        artifact_branches_after = {
            b for b in (gitcmd.list_branches() or [])
            if gitcmd.ls_tree_files(b, f"tasks/{task_id}")
        }
        self.assertTrue(
            artifact_branches_before & artifact_branches_after,
            "артефактная ветка удалена, хотя снапшот не подтверждён в "
            "origin целевого (AC-15) — удаление обязано ждать push")

    def test_ac15_retried_on_next_command_after_origin_recovers(self):
        task_id = catalog.cmd_new("Задача внешнего target", target=self.TARGET)
        self._break_origin()
        cleanup.cmd_kill(task_id)
        self.assertFalse(_snapshot_ref_exists(self.target_origin, task_id))

        self._fix_origin()
        cleanup.cmd_kill(task_id)  # «следующая команда этой задачи»

        self.assertTrue(
            _snapshot_ref_exists(self.target_origin, task_id),
            "повторная попытка push снапшота при следующей команде этой "
            "задачи не доставила refs/artifacts (AC-15)")

    def test_ac15_retried_by_doctor_after_origin_recovers(self):
        task_id = catalog.cmd_new("Задача внешнего target", target=self.TARGET)
        self._break_origin()
        cleanup.cmd_kill(task_id)
        self.assertFalse(_snapshot_ref_exists(self.target_origin, task_id))

        self._fix_origin()
        doctor.cmd_doctor()

        self.assertTrue(
            _snapshot_ref_exists(self.target_origin, task_id),
            "прогон doctor не дожал недоставленный снапшот (AC-15)")


if __name__ == "__main__":
    import unittest
    unittest.main()
