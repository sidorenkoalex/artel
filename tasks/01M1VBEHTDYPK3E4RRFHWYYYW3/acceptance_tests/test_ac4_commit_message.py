"""Приёмочный тест AC-4 задачи 01M1VBEHTDYPK3E4RRFHWYYYW3: коммит несёт
сообщение `оператор: <раздел> — <первые 80 символов текста>`.

Красен до реализации: `orchestrator.notes` ещё не существует — импорт
падает `ModuleNotFoundError`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import notes  # noqa: E402
from _sandbox import NoteSandbox  # noqa: E402


class CommitMessageTest(NoteSandbox):

    def test_ac4_message_truncates_text_to_first_80_chars(self):
        """Текст длиннее 80 символов обрезается в сообщении коммита
        РОВНО по 80-му символу целой строки `--text` (не по ячейке), с
        префиксом `оператор: копилка — `.

        Ловит мутацию: неверная граница среза (79/81 символ вместо 80)
        либо префикс без раздела/тире — падает на точном
        `assertEqual` полного сообщения.
        """
        text = ("9 | 09.09 | " + "х" * 90 + " | orchestrator/long.py")
        head_before = self.origin_head()

        notes.cmd_note(["копилка", "--text", text])

        head_after = self.origin_head()
        self.assertNotEqual(head_before, head_after)
        message = self.origin_commit_message(head_after)
        self.assertEqual(message, f"оператор: копилка — {text[:80]}")

    def test_ac4_message_keeps_short_text_verbatim(self):
        """Текст короче 80 символов входит в сообщение коммита ЦЕЛИКОМ,
        без обрезки и без добавления многоточия/иных маркеров.

        Ловит мутацию: реализация всегда дописывает суффикс усечения
        (например «…») даже когда текст короче лимита.
        """
        text = "1 | 01.01 | короткая заметка | orchestrator/short.py"

        notes.cmd_note(["копилка", "--text", text])

        message = self.origin_commit_message(self.origin_head())
        self.assertEqual(message, f"оператор: копилка — {text}")


if __name__ == "__main__":
    unittest.main()
