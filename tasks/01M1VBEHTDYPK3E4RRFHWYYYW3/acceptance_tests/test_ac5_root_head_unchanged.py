"""Приёмочный тест AC-5 задачи 01M1VBEHTDYPK3E4RRFHWYYYW3: HEAD «главной
копии» песочницы не меняется в ходе выполнения `note` при успешном
исходе.

Красен до реализации: `orchestrator.notes` ещё не существует — импорт
падает `ModuleNotFoundError`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import notes  # noqa: E402
from _sandbox import BACKLOG_TEXT, NoteSandbox  # noqa: E402


class RootHeadUnchangedTest(NoteSandbox):

    def test_ac5_root_head_branch_and_worktree_stay_untouched(self):
        """После успешного `note` HEAD, текущая ветка и содержимое
        `docs/backlog.md` НА ДИСКЕ главной копии (`self.root`) остаются
        теми же, что были до вызова — правка происходит в эфемерном
        git-окружении (worktree/клоне), не в рабочей копии пульта.

        Ловит мутацию: реализация редактирует и коммитит прямо в
        рабочее дерево `config.ROOT` (проще, чем заводить эфемерный
        worktree/клон) — тест красен на несовпадении HEAD до/после или
        на изменившемся содержимом файла на диске главной копии.
        """
        head_before = self.git("rev-parse", "HEAD").strip()
        branch_before = self.git("rev-parse", "--abbrev-ref", "HEAD").strip()
        disk_before = (self.root / "docs" / "backlog.md").read_text(encoding="utf-8")
        self.assertEqual(disk_before, BACKLOG_TEXT, "предусловие фикстуры")

        notes.cmd_note(["копилка", "--text",
                        "9 | 09.09 | новое | orchestrator/new.py"])

        self.assertEqual(self.git("rev-parse", "HEAD").strip(), head_before)
        self.assertEqual(self.git("rev-parse", "--abbrev-ref", "HEAD").strip(),
                         branch_before)
        disk_after = (self.root / "docs" / "backlog.md").read_text(encoding="utf-8")
        self.assertEqual(disk_after, disk_before,
                         "docs/backlog.md на диске главной копии изменился")
        # Сама вставка тем не менее должна была дойти до origin — иначе
        # тест ложно зеленел бы на команде, которая просто ничего не
        # делает.
        self.assertIn("новое", self.origin_backlog())


if __name__ == "__main__":
    unittest.main()
