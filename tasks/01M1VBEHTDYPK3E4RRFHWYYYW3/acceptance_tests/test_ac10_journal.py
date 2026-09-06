"""Приёмочный тест AC-10 задачи 01M1VBEHTDYPK3E4RRFHWYYYW3: успешная
запись (вставка либо `--append`) добавляет в журнал пульта запись без
`task_id`, actor `operator`, вида «заметка: <раздел> <sha>».

Формат SPEC называет только СОДЕРЖАНИЕ записи, не то, в какое именно
поле схемы `steps` (`action`/`detail`) оно попадает — тест поэтому
сверяет объединённый текст `action + " " + detail`, а не одно
конкретное поле.

Красен до реализации: `orchestrator.notes` ещё не существует — импорт
падает `ModuleNotFoundError`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import notes, store  # noqa: E402
from _sandbox import NoteSandbox  # noqa: E402


def _last_operator_note_step(conn):
    rows = conn.execute(
        "SELECT * FROM steps WHERE task_id IS NULL AND actor='operator' "
        "ORDER BY id").fetchall()
    return rows[-1] if rows else None


class JournalOnInsertTest(NoteSandbox):

    def test_ac10_insert_journals_note_without_task_id(self):
        """Успешная вставка пишет в журнал пульта запись БЕЗ `task_id`,
        actor `operator`, чей текст содержит «заметка: копилка» и sha
        нового коммита origin.

        Ловит мутацию: журнал не пишется вовсе для успешной вставки
        (падает на `assertIsNotNone`), либо пишется с actor, отличным от
        `operator`, либо привязан к какому-то `task_id`.
        """
        notes.cmd_note(["копилка", "--text",
                        "9 | 09.09 | заметка в журнал | orchestrator/j.py"])
        sha = self.origin_head()

        row = _last_operator_note_step(store.db())
        self.assertIsNotNone(row, "запись журнала не найдена")
        combined = f"{row['action']} {row['detail'] or ''}"
        self.assertIn("заметка: копилка", combined)
        self.assertIn(sha, combined)


class JournalOnAppendTest(NoteSandbox):

    def test_ac10_append_journals_note_without_task_id(self):
        """Тот же критерий для `--append`: раздел в записи журнала —
        раздел, где реально найдена и изменена строка («копилка»), не
        произвольное значение.

        Ловит мутацию: журнал `--append` называет раздел неверно
        (например, всегда «копилка» независимо от факта совпадения) —
        безопасно проверяется здесь, потому что единственное совпадение
        в этой песочнице лежит именно в «Копилке».
        """
        notes.cmd_note(["--append", "УНИКАЛЬНЫЙКЛЮЧ", "--text", "доп. текст"])
        sha = self.origin_head()

        row = _last_operator_note_step(store.db())
        self.assertIsNotNone(row)
        combined = f"{row['action']} {row['detail'] or ''}"
        self.assertIn("заметка: копилка", combined)
        self.assertIn(sha, combined)


if __name__ == "__main__":
    unittest.main()
