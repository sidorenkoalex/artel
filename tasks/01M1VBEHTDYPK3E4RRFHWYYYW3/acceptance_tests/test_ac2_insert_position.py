"""Приёмочный тест AC-2 задачи 01M1VBEHTDYPK3E4RRFHWYYYW3: вставленная
строка располагается первой сразу после строки-разделителя таблицы
выбранного раздела.

Красен до реализации: `orchestrator.notes` ещё не существует — импорт
падает `ModuleNotFoundError`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import notes  # noqa: E402
from _sandbox import NoteSandbox, SECTION_HEADINGS, row_cells, section_rows  # noqa: E402


class InsertPositionTest(NoteSandbox):

    def test_ac2_new_row_lands_right_after_separator_before_old_rows(self):
        """Новая строка становится ПЕРВОЙ строкой данных таблицы «Копилка»
        (сразу после `|---|...|`), а прежняя первая строка данных
        сдвигается на второе место, не теряясь и не меняясь.

        Ловит мутацию: вставка в конец таблицы (`append`-подобная
        реализация вместо вставки сразу после разделителя) — тест
        красен, потому что новая строка окажется НЕ на позиции `rows[2]`.
        """
        notes.cmd_note(["копилка", "--text",
                        "9 | 09.09 | самая новая | orchestrator/fresh.py"])

        rows = section_rows(self.origin_backlog(), SECTION_HEADINGS["копилка"])
        # rows[0] — шапка, rows[1] — разделитель, rows[2:] — данные.
        self.assertEqual(row_cells(rows[2]),
                         ["9", "09.09", "самая новая", "orchestrator/fresh.py"])
        self.assertEqual(row_cells(rows[3]),
                         ["1", "01.01", "старое наблюдение УНИКАЛЬНЫЙКЛЮЧ",
                          "orchestrator/x.py"])

    def test_ac2_insert_into_another_section_does_not_touch_kopilka(self):
        """Вставка в «Очередь Оператора» не трогает позицию строк данных
        раздела «Копилка» — раздел выбирается позиционным аргументом, не
        как побочный эффект первой найденной таблицы файла.

        Ловит мутацию: реализация всегда вставляет в ПЕРВУЮ таблицу
        файла независимо от переданного раздела — тест красен, потому
        что строка данных «Копилки» окажется другой.
        """
        notes.cmd_note(["очередь", "--text", "9 | новое действие"])

        text = self.origin_backlog()
        kopilka_rows = section_rows(text, SECTION_HEADINGS["копилка"])
        self.assertEqual(row_cells(kopilka_rows[2]),
                         ["1", "01.01", "старое наблюдение УНИКАЛЬНЫЙКЛЮЧ",
                          "orchestrator/x.py"])
        queue_rows = section_rows(text, SECTION_HEADINGS["очередь"])
        self.assertEqual(row_cells(queue_rows[2]), ["9", "новое действие"])


if __name__ == "__main__":
    unittest.main()
