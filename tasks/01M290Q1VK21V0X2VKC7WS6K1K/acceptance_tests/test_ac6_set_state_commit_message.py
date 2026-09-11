"""Приёмочный тест AC-6 задачи 01M290Q1VK21V0X2VKC7WS6K1K: коммит
`--set-state` несёт сообщение вида «оператор: <раздел> — состояние: …».

В отличие от `--drop` (нет `--text` пользователя, AC-3), у `--set-state`
текст сообщения — буквально то же значение, что пришло через `--text`:
сообщение проверяется точным `assertEqual`, тем же приёмом, что и
`insert`/`append` в предыдущей задаче `note` (усечение до 80 символов).

Красен до реализации: `orchestrator.notes.cmd_note` ещё не понимает флаг
`--set-state` — вызов падает до создания коммита.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import notes  # noqa: E402
from _sandbox import NoteSandbox  # noqa: E402


class SetStateCommitMessageTest(NoteSandbox):

    def test_ac6_message_keeps_short_text_verbatim_with_state_prefix(self):
        """Текст короче 80 символов входит в сообщение коммита ЦЕЛИКОМ, с
        префиксом «оператор: копилка — состояние: » (не «снята: », не
        голый префикс `insert`/`append`).

        Ловит мутацию: сообщение `--set-state` использует общий с
        `insert`/`append` формат без маркера «состояние: » — тест красен
        на точном `assertEqual`.
        """
        text = "готово к проверке"

        notes.cmd_note(["--set-state", "КЛЮЧСОСТОЯНИЕ", "--text", text])

        message = self.origin_commit_message(self.origin_head())
        self.assertEqual(message, f"оператор: копилка — состояние: {text}")

    def test_ac6_message_truncates_text_to_first_80_chars(self):
        """Текст длиннее 80 символов обрезается в сообщении коммита ровно
        по 80-му символу целой строки `--text`.

        Ловит мутацию: неверная граница среза (например, обрезка по всему
        сообщению вместе с префиксом, а не только по тексту состояния) —
        падает на точном `assertEqual` полного сообщения.
        """
        text = "х" * 90

        notes.cmd_note(["--set-state", "КЛЮЧСОСТОЯНИЕ", "--text", text])

        message = self.origin_commit_message(self.origin_head())
        self.assertEqual(message, f"оператор: копилка — состояние: {text[:80]}")


if __name__ == "__main__":
    unittest.main()
