"""Приёмочный тест AC-5 задачи 01M290Q1VK21V0X2VKC7WS6K1K: `note
--set-state <ключ> --text "<новое состояние>"` заменяет колонку
состояния найденной строки ЦЕЛИКОМ (не дописывает); `--append` для той
же колонки по-прежнему дописывает.

Красен до реализации: `orchestrator.notes.cmd_note` ещё не понимает флаг
`--set-state` — вызов падает до всякой правки колонки.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import notes  # noqa: E402
from _sandbox import NoteSandbox, SECTION_HEADINGS, row_cells, section_rows  # noqa: E402


class SetStateReplacesColumnTest(NoteSandbox):

    def test_ac5_set_state_replaces_last_column_entirely(self):
        """Строка «КЛЮЧСОСТОЯНИЕ запись | старое-состояние-маркер» — та же
        последняя колонка, что дописывает `--append` (`_apply_append`
        меняет `cells[-1]`) — после `--set-state <ключ> --text "новое
        состояние"` равна РОВНО новому тексту, прежний маркер
        («старое-состояние-маркер») в ней не остаётся ни целиком, ни
        частично; остальные колонки строки и соседние строки раздела не
        задеты.

        Ловит мутацию: `--set-state` по ошибке использует ту же логику,
        что `--append` (дописывает вместо замены) — тест красен на
        `assertNotIn` старого маркера в итоговой ячейке.
        """
        before_rows = section_rows(self.origin_backlog(),
                                   SECTION_HEADINGS["копилка"])

        notes.cmd_note(["--set-state", "КЛЮЧСОСТОЯНИЕ",
                        "--text", "новое состояние"])

        after_rows = section_rows(self.origin_backlog(),
                                  SECTION_HEADINGS["копилка"])
        matched = [row for row in after_rows if "КЛЮЧСОСТОЯНИЕ" in row]
        self.assertEqual(len(matched), 1, after_rows)
        cells = row_cells(matched[0])
        self.assertEqual(cells[-1], "новое состояние")
        self.assertNotIn("старое-состояние-маркер", cells[-1])
        # Остальные колонки строки не задеты заменой последней.
        self.assertEqual(cells[:-1], ["3", "01.01", "КЛЮЧСОСТОЯНИЕ запись"])
        # Соседние строки раздела не задеты.
        untouched = [row for row in before_rows if "КЛЮЧСОСТОЯНИЕ" not in row]
        for row in untouched:
            self.assertIn(row, after_rows)


class AppendStillAppendsSameColumnTest(NoteSandbox):

    def test_ac5_append_still_appends_to_the_same_column(self):
        """Тот же ключ строки («КЛЮЧАППЕНД дополняемая запись», последняя
        колонка «orchestrator/append.py») через `--append` дописывает
        новый текст К ТЕКУЩЕМУ содержимому последней колонки (старое
        содержимое остаётся, новое добавляется рядом) — в отличие от
        `--set-state`, поведение `--append` не меняется этой задачей.

        Ловит мутацию: правка `--set-state` случайно затронула общий
        код `--append` и та тоже начала заменять колонку целиком — тест
        красен на `assertIn` старого содержимого ячейки.
        """
        notes.cmd_note(["--append", "КЛЮЧАППЕНД", "--text", "доп. текст"])

        rows = section_rows(self.origin_backlog(), SECTION_HEADINGS["копилка"])
        matched = [row for row in rows if "КЛЮЧАППЕНД" in row]
        self.assertEqual(len(matched), 1, rows)
        cells = row_cells(matched[0])
        self.assertIn("orchestrator/append.py", cells[-1])
        self.assertIn("доп. текст", cells[-1])


if __name__ == "__main__":
    unittest.main()
