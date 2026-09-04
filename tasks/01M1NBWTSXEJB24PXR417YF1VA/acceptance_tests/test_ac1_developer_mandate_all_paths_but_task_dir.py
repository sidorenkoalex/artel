"""Приёмочный тест AC-1 — 01M1NBWTSXEJB24PXR417YF1VA: мандат `developer`
в WIP-чекпоинте после таймаута шага.

Источник — tasks/01M1NBWTSXEJB24PXR417YF1VA/SPEC.md, «Критерии приёмки»:

AC-1. При таймауте шага роли `developer` WIP-чекпоинт коммитит в кодовую
ветку задачи изменения по всем путям worktree, кроме `tasks/<id>/`.

Красен до реализации: `checkpoint.commit_timeout_checkpoint` сегодня (до
этой задачи) коммитит ВСЁ рабочее дерево безусловным `git add -A` без
разбора мандата роли (SPEC, «Контекст») — `tasks/<TASK>/wip.md` попадает
в ТОТ ЖЕ коммит кодовой ветки, что и правки кода, и тест ниже ловит это:
`code_branch_committed_paths` содержит путь `tasks/<TASK>/wip.md`,
которого там по AC-1 быть не должно.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _sandbox import MandateCheckpointTest  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from orchestrator import checkpoint, store  # noqa: E402


class DeveloperMandateCommitsAllButTaskDirTest(MandateCheckpointTest):

    def test_ac1_developer_timeout_commits_every_path_except_task_dir(self):
        """Таймаут шага `developer` с одновременной правкой ВНЕ
        `tasks/<id>/` (файл, отслеживаемый кодовой веткой, и новый файл)
        и ВНУТРИ `tasks/<id>/` — код-коммит кодовой ветки несёт оба пути
        вне `tasks/<id>/` и НИ ОДНОГО пути `tasks/<id>/*`.

        Ловит мутацию: возврат к безусловному `git add -A` всего дерева
        (сегодняшнее поведение `commit_timeout_checkpoint`) — тогда
        `tasks/<TASK>/wip.md` попал бы в тот же коммит кодовой ветки,
        что и правки кода, и проверка `task_paths == []` покраснела бы.
        """
        self.enter_in_dev()
        claude_md = self.wt / "CLAUDE.md"
        claude_md.write_text(
            claude_md.read_text(encoding="utf-8") + "правка разработчика\n",
            encoding="utf-8")
        self.write_code_file("orchestrator/new_module.py",
                             "# правка разработчика\n")
        self.worktree_task_dir().joinpath("wip.md").write_text(
            "недописанный артефакт роли\n", encoding="utf-8")
        before = self.worktree_head()

        detail = checkpoint.commit_timeout_checkpoint(
            store.db(), self.TASK, "developer")

        self.assertNotEqual(
            detail, "",
            "AC-1: чекпоинт обязан закоммитить непустой diff по путям "
            "мандата developer")
        after = self.worktree_head()
        self.assertNotEqual(
            after, before,
            "AC-1: код-коммит обязан сдвинуть HEAD кодовой ветки")
        committed = self.code_branch_committed_paths(after)
        self.assertIn("CLAUDE.md", committed,
                      f"AC-1: отслеживаемый путь кодовой ветки обязан "
                      f"попасть в коммит — фактически закоммичено: "
                      f"{committed}")
        self.assertIn("orchestrator/new_module.py", committed,
                      f"AC-1: новый путь кодовой ветки обязан попасть в "
                      f"коммит — фактически закоммичено: {committed}")
        task_paths = [p for p in committed
                     if p.startswith(f"tasks/{self.TASK}/")]
        self.assertEqual(
            task_paths, [],
            f"AC-1: tasks/<id>/ не входит в мандат кода developer в "
            f"ЭТОМ коммите (переносится в артефактную ветку отдельно, "
            f"AC-4) — фактически найдено: {task_paths}")


if __name__ == "__main__":
    import unittest
    unittest.main()
