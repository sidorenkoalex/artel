"""Приёмочный тест AC-2 задачи 01M290Q1VK21V0X2VKC7WS6K1K: `--drop` при
отсутствии совпадений или более чем одном совпадении отказывает
именованным сообщением; `docs/backlog.md` в origin не изменён.

Красен до реализации: `orchestrator.notes.cmd_note` ещё не понимает флаг
`--drop` — вызов падает до момента, который проверяет этот тест.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import notes  # noqa: E402
from _sandbox import NoteSandbox  # noqa: E402


class DropZeroMatchesTest(NoteSandbox):

    def test_ac2_zero_matches_refuses_without_changing_the_file(self):
        """Подстрока, не встречающаяся ни в одной строке файла, — отказ
        `SystemExit` с именованным сообщением (упоминающим ключ), origin
        не продвигается, содержимое `docs/backlog.md` остаётся
        байт-в-байт прежним.

        Ловит мутацию: отсутствие совпадения трактуется как «нечего
        снимать — тихий успех» вместо отказа — тест красен на
        `assertRaises(SystemExit)`.
        """
        head_before = self.origin_head()
        text_before = self.origin_backlog()

        with self.assertRaises(SystemExit) as cm:
            notes.cmd_note(["--drop", "НЕТТАКОГОКЛЮЧА"])
        self.assertIn("НЕТТАКОГОКЛЮЧА", str(cm.exception))

        self.assertEqual(self.origin_head(), head_before)
        self.assertEqual(self.origin_backlog(), text_before)
        self.assertEqual(notes.pending_notes(), [],
                         "отказ валидации до push не должен удерживать заметку")


class DropMultipleMatchesTest(NoteSandbox):

    def test_ac2_multiple_matches_refuses_without_changing_the_file(self):
        """Подстрока, встречающаяся в НЕСКОЛЬКИХ строках («ПОВТОРКЛЮЧ» —
        обе строки раздела «Копилка»), — именованный отказ, файл не
        меняется: неоднозначность не разрешается автоматическим снятием
        первой найденной строки.

        Ловит мутацию: при нескольких совпадениях реализация молча снимает
        ПЕРВУЮ найденную строку — тест красен и на отсутствии
        `SystemExit`, и на изменившемся содержимом origin.
        """
        head_before = self.origin_head()
        text_before = self.origin_backlog()

        with self.assertRaises(SystemExit):
            notes.cmd_note(["--drop", "ПОВТОРКЛЮЧ"])

        self.assertEqual(self.origin_head(), head_before)
        self.assertEqual(self.origin_backlog(), text_before)
        self.assertEqual(notes.pending_notes(), [])


if __name__ == "__main__":
    unittest.main()
