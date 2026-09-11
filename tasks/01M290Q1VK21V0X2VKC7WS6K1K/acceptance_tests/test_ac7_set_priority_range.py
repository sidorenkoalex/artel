"""Приёмочный тест AC-7 задачи 01M290Q1VK21V0X2VKC7WS6K1K: `note
--set-priority <ключ> --text <1..4>` заменяет колонку «П» найденной
строки; значение вне диапазона 1..4 отказывает без изменения файла.

Красен до реализации: `orchestrator.notes.cmd_note` ещё не понимает флаг
`--set-priority` — вызов падает до всякой правки колонки.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import notes  # noqa: E402
from _sandbox import NoteSandbox, SECTION_HEADINGS, row_cells, section_rows  # noqa: E402


class SetPriorityReplacesColumnTest(NoteSandbox):

    def test_ac7_set_priority_replaces_p_column_with_valid_value(self):
        """Строка «КЛЮЧПРИОРИТЕТ запись приоритета» несёт «П» = «1» — после
        `--set-priority КЛЮЧПРИОРИТЕТ --text 3` первая колонка («П»)
        строки равна «3», остальные колонки и соседние строки раздела не
        задеты.

        Ловит мутацию: `--set-priority` меняет не ту колонку (например,
        последнюю, как `--append`/`--set-state`) — тест красен на
        `assertEqual` первой ячейки.
        """
        before_rows = section_rows(self.origin_backlog(),
                                   SECTION_HEADINGS["копилка"])

        notes.cmd_note(["--set-priority", "КЛЮЧПРИОРИТЕТ", "--text", "3"])

        after_rows = section_rows(self.origin_backlog(),
                                  SECTION_HEADINGS["копилка"])
        matched = [row for row in after_rows if "КЛЮЧПРИОРИТЕТ" in row]
        self.assertEqual(len(matched), 1, after_rows)
        cells = row_cells(matched[0])
        self.assertEqual(cells[0], "3")
        self.assertEqual(cells[1:], ["01.01", "КЛЮЧПРИОРИТЕТ запись приоритета",
                                     "orchestrator/prio.py"])
        untouched = [row for row in before_rows if "КЛЮЧПРИОРИТЕТ" not in row]
        for row in untouched:
            self.assertIn(row, after_rows)


class SetPriorityOutOfRangeRefusesTest(NoteSandbox):

    def test_ac7_value_above_range_refuses_without_changing_the_file(self):
        """`--set-priority <ключ> --text 5» — значение вне диапазона
        1..4 — именованный отказ `SystemExit`, origin не продвигается,
        `docs/backlog.md` остаётся байт-в-байт прежним.

        Ловит мутацию: проверка диапазона отсутствует (любое числовое
        значение принимается как есть) — тест красен на отсутствующем
        `SystemExit`.
        """
        head_before = self.origin_head()
        text_before = self.origin_backlog()

        with self.assertRaises(SystemExit):
            notes.cmd_note(["--set-priority", "КЛЮЧПРИОРИТЕТ", "--text", "5"])

        self.assertEqual(self.origin_head(), head_before)
        self.assertEqual(self.origin_backlog(), text_before)
        self.assertEqual(notes.pending_notes(), [])

    def test_ac7_value_below_range_refuses_without_changing_the_file(self):
        """`--set-priority <ключ> --text 0» — тоже вне диапазона 1..4 (с
        другой стороны границы) — тот же именованный отказ без изменения
        файла.

        Ловит мутацию: проверка диапазона написана только сверху
        (`<= 4`) без нижней границы (`>= 1`) — тест красен на отсутствующем
        `SystemExit`.
        """
        head_before = self.origin_head()
        text_before = self.origin_backlog()

        with self.assertRaises(SystemExit):
            notes.cmd_note(["--set-priority", "КЛЮЧПРИОРИТЕТ", "--text", "0"])

        self.assertEqual(self.origin_head(), head_before)
        self.assertEqual(self.origin_backlog(), text_before)
        self.assertEqual(notes.pending_notes(), [])


if __name__ == "__main__":
    unittest.main()
