"""Приёмочный тест AC-1 задачи 01M1VBEHTDYPK3E4RRFHWYYYW3: вызов
`note <раздел> --text "<строка>"` в песочнице с локальным `origin`
создаёт ровно один коммит, меняющий только `docs/backlog.md`; строка на
месте.

Красен до реализации: `orchestrator.notes` ещё не существует — импорт
падает `ModuleNotFoundError`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import notes  # noqa: E402
from _sandbox import NoteSandbox, row_cells  # noqa: E402


class InsertSingleCommitTest(NoteSandbox):

    def test_ac1_insert_creates_one_commit_touching_only_backlog(self):
        """Успешный `note копилка --text ...` добавляет РОВНО один коммит
        поверх головы `origin/main`, трогающий только `docs/backlog.md`,
        а сама строка оказывается в итоговом содержимом файла.

        Ловит мутацию: реализация коммитит правку прямо в рабочую копию
        `config.ROOT` (лишний файл индекса/маркер) либо делает отдельный
        служебный коммит (например, коммит самого fetch/merge) в
        дополнение к содержательному — тест красен на `commit_count != 1`
        или на непустом списке файлов сверх `docs/backlog.md`.
        """
        head_before = self.origin_head()

        notes.cmd_note(["копилка", "--text",
                        "3 | 02.02 | новое наблюдение | orchestrator/new.py"])

        head_after = self.origin_head()
        self.assertNotEqual(head_before, head_after,
                            "origin/main не продвинулся — коммит не дошёл")
        self.assertEqual(self.origin_commit_count(head_before, head_after), 1)
        self.assertEqual(self.origin_changed_files(head_before, head_after),
                         ["docs/backlog.md"])

        text = self.origin_backlog()
        rows = [row_cells(ln) for ln in text.splitlines()
               if ln.strip().startswith("|")]
        self.assertIn(["3", "02.02", "новое наблюдение", "orchestrator/new.py"],
                     rows)


if __name__ == "__main__":
    unittest.main()
