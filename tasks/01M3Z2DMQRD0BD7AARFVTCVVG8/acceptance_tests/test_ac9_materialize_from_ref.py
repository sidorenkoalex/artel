"""AC-9: документы выкладываются перед шагом роли из головы `refs/artifacts/<id>`.

Группа: разовый
Красен до реализации: сегодня выкладка читает голову ветки `artifact/<id>`, а `refs/artifacts/<id>` нет — предусловие о голове ссылки падает раньше сверки диска.

Файл разовый: место выкладки «прежнее» — факт этой части этапа 1 (часть
(б) его меняет), и проверка идёт через настоящий git.

Выкладку делает `runner.role_cwd` — вход, которым шаг роли получает свой
рабочий каталог; прежнее место — `tasks/<id>/` в worktree задачи
(`workspace.path`).
"""
import unittest
from pathlib import Path

from _sandbox import RefSandbox, ref_name
from orchestrator import checkpoint, runner, store, workspace


class Ac9MaterializeTest(RefSandbox):
    """AC-9."""

    def disk_tree(self, root: Path, task_id: str) -> dict:
        base = root / "tasks" / task_id
        return {p.relative_to(root).as_posix(): p.read_text(encoding="utf-8")
                for p in sorted(base.rglob("*")) if p.is_file()}

    def ref_tree(self, sha: str, task_id: str) -> dict:
        return {rel: self.file_at(sha, rel) for rel in self.tree_paths(sha)
                if rel.startswith(f"tasks/{task_id}/")}

    def test_ac9_role_cwd_lays_out_ref_head_in_place(self):
        """Выложенный `tasks/<id>/` совпадает с деревом головы ссылки.

        Вторая выкладка после нового коммита в ссылку приносит новый файл
        и убирает файл, которого в ссылке нет.

        Ловит мутацию: выкладка читает голову прежней ветки — после второго
        коммита в ссылку диск не получает `acceptance_tests/test_x.py`.
        """
        task_id = self.new_task()
        target = self.row(task_id)["target"]
        self.assertTrue(self.local_head(task_id),
                        f"предусловие: после new есть {ref_name(task_id)}")
        cwd = runner.role_cwd(self.conn, task_id, target)
        self.assertEqual(Path(cwd).resolve(),
                         Path(workspace.path(task_id)).resolve(),
                         "документы выложены не на прежнее место")
        stale = Path(cwd) / "tasks" / task_id / "STALE.md"
        stale.write_text("осевший файл\n", encoding="utf-8")
        head = self.seed_docs(task_id, {
            "acceptance_tests/test_x.py": "# тест x\n",
            "NOTE.md": "заметка\n"}, "второй коммит")

        cwd = runner.role_cwd(self.conn, task_id, target)

        self.assertEqual(self.local_head(task_id), head)
        self.assertEqual(self.disk_tree(Path(cwd), task_id),
                         self.ref_tree(head, task_id),
                         "выложенный tasks/<id>/ не совпадает с головой ссылки")
        self.assertFalse(stale.exists(), "файл вне ссылки не убран")

    def test_ac9_role_edit_goes_to_ref_by_autocommit(self):
        """Правка роли в выложенном каталоге — новый коммит ссылки поверх головы.

        Ловит мутацию: автокоммит переносит правку в прежнюю ветку — голова
        ссылки не меняется, правки в ней нет.
        """
        task_id = self.new_task()
        before = self.local_head(task_id)
        self.assertTrue(before, f"предусловие: после new есть {ref_name(task_id)}")
        cwd = runner.role_cwd(self.conn, task_id, self.row(task_id)["target"])
        (Path(cwd) / "tasks" / task_id / "QUESTIONS.md").write_text(
            "Вопрос роли ВОПРОС-AC9.\n", encoding="utf-8")

        checkpoint.commit_step_artifacts(store.db(), task_id, "analyst")

        head = self.assert_ref_advanced(task_id, before, "автокоммит шага")
        self.assertEqual(self.parents(head), [before],
                         "автокоммит не поверх выложенной головы")
        self.assertIn("ВОПРОС-AC9",
                      self.file_at(head, f"tasks/{task_id}/QUESTIONS.md") or "")


if __name__ == "__main__":
    unittest.main()
