"""Приёмочный тест AC-3 задачи 01M290Q1VK21V0X2VKC7WS6K1K: коммит
`--drop` несёт сообщение вида «оператор: <раздел> — снята: <первые 80
символов наблюдения>».

`--drop` не принимает `--text` (снимаемая строка уже есть в файле) —
«наблюдение» здесь может относиться только к содержимому НАЙДЕННОЙ
строки, точный формат его сериализации (сырая строка с `|`, ячейки без
внешних `|` и т.п.) SPEC не фиксирует. Тест поэтому проверяет то, что
однозначно следует из формулировки критерия и не зависит от выбора
представления: префикс сообщения, срез по 80 символам (маркер сразу
после ключа входит в сообщение короткой строки целиком; хвостовой
маркер строки длиннее 80 символов в сообщение не попадает).

Красен до реализации: `orchestrator.notes.cmd_note` ещё не понимает флаг
`--drop` — вызов падает до создания коммита, сообщение проверить нечем.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import notes  # noqa: E402
from _sandbox import (LONG_ROW_HEAD_KEY, LONG_ROW_TAIL_MARKER,  # noqa: E402
                      NoteSandbox)


class DropCommitMessageShortRowTest(NoteSandbox):

    def test_ac3_short_row_message_carries_prefix_and_full_row_content(self):
        """Снятие короткой строки (ключ «КЛЮЧСНЯТЬ», вся строка короче 80
        символов при любом разумном представлении) — сообщение коммита
        начинается с «оператор: копилка — снята: » и целиком несёт
        содержимое снятой строки (ключ и путь из последней колонки), без
        обрезки.

        Ловит мутацию: сообщение коммита `--drop` собрано с тем же
        префиксом, что `--append`/insert (без «снята: »), либо не
        привязано к содержимому найденной строки вовсе (например, всегда
        пустой хвост) — тест красен на `assertTrue(startswith(...))` или
        на отсутствующих `assertIn`.
        """
        notes.cmd_note(["--drop", "КЛЮЧСНЯТЬ"])

        message = self.origin_commit_message(self.origin_head())
        self.assertTrue(message.startswith("оператор: копилка — снята: "),
                        message)
        self.assertIn("КЛЮЧСНЯТЬ", message)
        self.assertIn("orchestrator/drop.py", message)


class DropCommitMessageLongRowTruncationTest(NoteSandbox):

    def test_ac3_long_row_message_truncates_at_80_chars_of_observation(self):
        """Снятие строки, чьё представление (в любом разумном формате)
        длиннее 80 символов — хвостовой маркер строки, гарантированно
        оказывающийся за пределами первых 80 символов «наблюдения» в
        ЛЮБОМ разумном представлении (сырая строка, ячейки без `|`, текст
        одной ячейки), в сообщение коммита не попадает; при этом ключ у
        самого начала строки — попадает.

        Ловит мутацию: срез по 80 символам не применяется вовсе (в
        сообщение попадает всё «наблюдение» целиком, включая хвостовой
        маркер) — тест красен на `assertNotIn` хвостового маркера.
        """
        notes.cmd_note(["--drop", LONG_ROW_HEAD_KEY])

        message = self.origin_commit_message(self.origin_head())
        self.assertTrue(message.startswith("оператор: копилка — снята: "),
                        message)
        self.assertIn(LONG_ROW_HEAD_KEY, message)
        self.assertNotIn(LONG_ROW_TAIL_MARKER, message)


if __name__ == "__main__":
    unittest.main()
