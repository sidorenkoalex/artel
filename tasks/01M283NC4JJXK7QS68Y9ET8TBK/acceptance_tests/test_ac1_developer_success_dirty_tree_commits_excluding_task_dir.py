"""Приёмочный тест AC-1 — 01M283NC4JJXK7QS68Y9ET8TBK.

Источник — tasks/01M283NC4JJXK7QS68Y9ET8TBK/SPEC.md, «Критерии приёмки»:

AC-1. Шаг роли `developer` завершился с `rc=0` в обычном успешном пути
(не таймаут, не `rc≠0`, не отсутствие обязательного артефакта, не обрыв
stdout-пайпа) и рабочее дерево несёт незакоммиченные изменения вне
`tasks/<id>/` → оркестратор коммитит эти изменения тем же приёмом и с
теми же фильтрами мандата, что `commit_timeout_checkpoint`: только роль
`developer`, только догфуд-target, только если реально есть что
коммитить, тихая деградация без записи при отказе git.

Догфуд-target и мандат `developer` — уже условия сценария:
`RealPultGitTest.enter_in_dev()` (см. `_sandbox.py`) заводит задачу
именно на `config.DEFAULT_TARGET` (единственный target, объявленный
`targets.yaml` этой песочницы) в состоянии `in_dev` (роль `developer`,
`config.STATE_ROLE`) — отдельного сценария на «не догфуд»/«не developer»
эта задача не требует форматом самого AC-1 (он называет фильтры единым
перечислением, не отдельными критериями); негативная сторона мандата
(роль БЕЗ мандата кода) — предмет AC-5, отдельный файл.

Красен до реализации: до этой задачи `orchestrator/runner.py` в ветке
`rc=0` без `pump.error` зовёт только `checkpoint.commit_step_artifacts`
(переносит исключительно `tasks/<id>/` в артефактную ветку) — код роли
`developer` вне `tasks/<id>/` остаётся незакоммиченным в рабочем дереве
кодовой ветки, `worktree_head()` не сдвигается, и тест ниже покраснеет
именно на этом сравнении (`after == before`), не на импорте или опечатке.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import DeveloperWipCommitSandbox  # noqa: E402


class DeveloperSuccessDirtyTreeCommitTest(DeveloperWipCommitSandbox):

    def test_ac1_developer_step_rc0_dirty_tree_outside_task_dir_gets_committed(self):
        """Шаг `developer` завершается `rc=0` (подложный агент `run_faked()`
        всегда отвечает нулевым кодом возврата), в рабочем дереве кодовой
        ветки заранее оставлена незакоммиченная правка вне `tasks/<id>/` —
        после шага рабочее дерево кодовой ветки чистое, HEAD сдвинут, а
        коммит несёт правку роли, но НЕ несёт `tasks/<id>/` (мандат
        `developer` исключает его, как и `commit_timeout_checkpoint`).

        Ловит мутацию: новый чекпоинт вызывается БЕЗ `exclude=tasks/<id>`
        (или вызывается `git add -A` без последующего `git reset -- tasks/
        <id>`) — материализованные `role_cwd` артефакты (`PLAN.md`/
        `REVIEW.md`) попали бы в код-коммит `developer` наравне с
        `orchestrator/new_module.py`, и `task_paths` внизу теста был бы не
        пуст.
        """
        self.enter_in_dev()
        self.write_code_file("orchestrator/new_module.py",
                             "# правка разработчика без коммита\n")
        before = self.worktree_head()

        self.run_faked()

        after = self.worktree_head()
        self.assertNotEqual(
            after, before,
            "AC-1: пульт обязан закоммитить незакоммиченный код роли "
            "developer после успешного (rc=0) завершения шага")
        self.assertEqual(
            self.worktree_status().strip(), "",
            "AC-1: рабочее дерево кодовой ветки обязано стать чистым "
            "после коммита пульта")

        committed = self.worktree_git("show", "--name-only", "--format=", after)
        committed_paths = [p for p in committed.splitlines() if p]
        self.assertIn("orchestrator/new_module.py", committed_paths,
                      f"AC-1: коммит обязан нести правку роли — "
                      f"фактически закоммичено: {committed_paths}")
        task_paths = [p for p in committed_paths
                     if p.startswith(f"tasks/{self.TASK}/")]
        self.assertEqual(
            task_paths, [],
            f"AC-1: tasks/<id>/ не входит в мандат кода developer — "
            f"фактически закоммичено: {task_paths}")


if __name__ == "__main__":
    import unittest
    unittest.main()
