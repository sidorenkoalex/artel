"""AC-1/AC-2 (tasks/01M290PVYG2VJK6442H5BAX9MA/SPEC.md): WIP-чекпоинты
пульта (`_commit_worktree_change`/её вызыватели) коммитят после `git add
-A` только пути внутри зон задачи (`tasks.zones`/`zones_extension` +
`config.COMMON_ZONES`) либо `tasks/<свой id>/`; посторонние пути (вне
зон, вне tasks/<id>/) не попадают в коммит и пишут ровно одну запись
журнала «посторонние файлы в worktree: <список>» на шаг, не по записи
на файл.

Красен до реализации: `_commit_worktree_change` (orchestrator/
checkpoint.py) сегодня коммитит ЛЮБОЙ путь worktree (кроме `tasks/<id>/`
для developer) без сверки с зонами задачи вовсе — `grep -n "посторонние
файлы в worktree" orchestrator/checkpoint.py` пуст, файл вне зоны
попадает в кодовый коммит наравне с заявленным.

Песочница — `_WorktreeCheckpointTest` (tests/test_timeout_checkpoint.py,
импорт, не копия): реальный `git add`/`git diff`/`git commit` в
worktree ветки задачи — фильтрацию по зонам заглушкой `gitcmd.git` не
проверить, тем же доводом, что уже несёт докстринг того файла.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import checkpoint, store  # noqa: E402
from tests.test_timeout_checkpoint import _WorktreeCheckpointTest  # noqa: E402


class CheckpointZoneFilterTest(_WorktreeCheckpointTest):
    """Красен до реализации: см. докстринг модуля — фильтр по зонам ещё
    не существует, оба теста ниже падают на сегодняшнем безусловном
    `git add -A`."""

    ZONE = "orchestrator/allowed_module.py"

    def enter_in_dev(self):
        # `zones` объявляется ПОСЛЕ `enter_in_dev()`: сам переход к
        # approve (`fsm.cmd_approve`) перечитывает `zones` из SPEC.md
        # фикстуры (пустое поле по умолчанию) и сбрасывает ручную
        # предустановку до этого момента.
        sha = super().enter_in_dev()
        store.update_task(store.db(), self.TASK, zones=self.ZONE)
        return sha

    def test_ac1_file_outside_declared_zone_is_excluded_from_the_commit(self):
        """Правка в заявленной зоне и правка вне зоны/вне `tasks/<id>/`
        одновременно на чекпоинте таймаута — в кодовый коммит попадает
        только первая, вторая остаётся на диске непровреждённой.

        Ловит мутацию: сверка со списком зон убрана (или подменена на
        безусловное «всё в зоне») из фильтра после `git add -A` —
        `docs/stray_note.md` доехал бы до кодового коммита наравне с
        `orchestrator/allowed_module.py`, и `assertNotIn` ниже покраснеет."""
        self.enter_in_dev()
        self.write_code_file(self.ZONE, "# в зоне задачи\n")
        self.write_code_file("docs/stray_note.md", "рабочая заметка роли\n")

        checkpoint.commit_timeout_checkpoint(store.db(), self.TASK, "developer")

        after = self.worktree_head()
        committed = self.worktree_git("show", "--name-only", "--format=", after)
        committed_paths = [p for p in committed.splitlines() if p]
        self.assertIn(self.ZONE, committed_paths)
        self.assertNotIn("docs/stray_note.md", committed_paths)
        self.assertTrue((self.wt / "docs" / "stray_note.md").exists(),
                        "файл вне зоны остаётся на диске, не пропадает "
                        "без следа")

    def test_ac2_multiple_stray_files_write_exactly_one_journal_entry(self):
        """Два посторонних файла разом на одном чекпоинте — ровно одна
        запись журнала о посторонних файлах worktree, не по записи на
        файл, и она называет оба пути.

        Ловит мутацию: журнал пишется внутри цикла по посторонним файлам
        (по записи на каждый) вместо одного вызова после цикла — записей
        действия «посторонние файлы в worktree» выйдет 2, не 1, и
        `assertEqual(len(entries), 1)` покраснеет."""
        self.enter_in_dev()
        self.write_code_file(self.ZONE, "# в зоне задачи\n")
        self.write_code_file("docs/stray_a.md", "заметка A\n")
        self.write_code_file("docs/stray_b.md", "заметка B\n")

        checkpoint.commit_timeout_checkpoint(store.db(), self.TASK, "developer")

        rows = store.task_steps(store.db(), self.TASK)
        entries = [r for r in rows
                  if "посторонние файлы в worktree" in f"{r['action']} {r['detail']}"]
        self.assertEqual(len(entries), 1)
        self.assertIn("stray_a.md", entries[0]["detail"])
        self.assertIn("stray_b.md", entries[0]["detail"])


if __name__ == "__main__":
    unittest.main()
