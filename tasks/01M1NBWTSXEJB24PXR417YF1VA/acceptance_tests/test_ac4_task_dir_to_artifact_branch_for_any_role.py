"""Приёмочный тест AC-4 — 01M1NBWTSXEJB24PXR417YF1VA: `tasks/<id>/`
рабочего каталога при таймауте — в артефактную ветку, для любой роли.

Источник — tasks/01M1NBWTSXEJB24PXR417YF1VA/SPEC.md, «Критерии приёмки»:

AC-4. Содержимое `tasks/<id>/` рабочего каталога при таймауте переносится
в артефактную ветку тем же автокоммитом, что и при штатном завершении
шага (`_commit_external_step_artifacts`), для любой роли — и не попадает
в кодовую ветку.

Роли `developer` (мандат кода — «всё, кроме tasks/<id>/») и `test_author`
(мандат кода — «ничего») — оба конца таблицы мандата ANSWER-1: критерий
требует ОДИНАКОВОГО поведения `tasks/<id>/` для обеих, независимо от
мандата кода.

Красен до реализации: до этой задачи `commit_timeout_checkpoint` вообще
не зовёт `_commit_external_step_artifacts` — `tasks/<TASK>/wip.md`
остаётся либо в кодовом коммите (безусловный `git add -A`), либо, для
роли без кода, просто оседает как незакоммиченный WIP. В обоих случаях
`artifact_branch_task_files()` для этой роли пуст — тест ниже ловит
именно это.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import MandateCheckpointTest  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from orchestrator import checkpoint, store  # noqa: E402


class TaskDirToArtifactBranchForAnyRoleTest(MandateCheckpointTest):

    def _assert_task_dir_moved_to_artifact_branch(self, role: str):
        self.enter_in_dev()
        self.worktree_task_dir().joinpath("wip.md").write_text(
            f"недописанный артефакт роли {role}\n", encoding="utf-8")
        before = self.worktree_head()

        checkpoint.commit_timeout_checkpoint(store.db(), self.TASK, role)

        files = self.artifact_branch_task_files()
        self.assertIn(
            f"tasks/{self.TASK}/wip.md", files,
            f"AC-4: артефакт роли {role} обязан оказаться в артефактной "
            f"ветке — фактически там: {files}")
        after = self.worktree_head()
        if after != before:
            committed = self.code_branch_committed_paths(after)
            task_paths = [p for p in committed
                         if p.startswith(f"tasks/{self.TASK}/")]
            self.assertEqual(
                task_paths, [],
                f"AC-4: tasks/<id>/ не попадает в кодовую ветку ни для "
                f"какой роли — фактически найдено в коммите {after}: "
                f"{task_paths}")

    def test_ac4_developer_timeout_moves_task_dir_to_artifact_branch(self):
        """Таймаут шага `developer` — единственный незакоммиченный
        артефакт (`tasks/<id>/wip.md`, кода нет) оказывается в
        артефактной ветке, не в кодовой.

        Ловит мутацию: `_commit_external_step_artifacts` вызывается
        только для успешного завершения шага (`commit_step_artifacts`),
        не для таймаута — тогда `tasks/{self.TASK}/wip.md` не появился
        бы в артефактной ветке вовсе.
        """
        self._assert_task_dir_moved_to_artifact_branch("developer")

    def test_ac4_test_author_timeout_moves_task_dir_to_artifact_branch(self):
        """Таймаут шага `test_author` (мандат кода — «ничего», AC-2) —
        `tasks/<id>/wip.md` всё равно оказывается в артефактной ветке:
        AC-4 не зависит от мандата кода роли.

        Ловит мутацию: перенос `tasks/<id>/` в артефактную ветку по
        ошибке подключён только к мандатным ролям (`developer`) — тогда
        для `test_author` артефакт роли молча терялся бы (не в кодовой
        ветке И не в артефактной).
        """
        self._assert_task_dir_moved_to_artifact_branch("test_author")


if __name__ == "__main__":
    import unittest
    unittest.main()
