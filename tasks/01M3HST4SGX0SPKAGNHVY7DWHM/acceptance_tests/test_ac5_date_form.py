"""AC-5 — 01M3HST4SGX0SPKAGNHVY7DWHM: дата вставляемой строки приводится
к краткой форме «ДД.ММ», уже краткая не меняется.

Источник — SPEC.md, «Критерии приёмки»:

AC-5. Вставка строки с ячейкой даты «22.09.2026» даёт в документе
«22.09»; вставка с «27.09» оставляет «27.09».

Колонка даты «Копилки» — вторая по шапке (`| П | Дата | …`), поэтому
проверяется ячейка с индексом 1; разбор строки — собственный
(`_sandbox.cells`), не `notes._row_cells`.

Красен до реализации: нормализации даты сегодня нет — `_apply_insert`
(:181) кладёт ячейку как есть, и «22.09.2026» приезжает в документ с
годом.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _sandbox  # noqa: E402

DATE_CELL_INDEX = 1


class DateFormTest(_sandbox.NoteSandbox):

    def test_ac5_long_date_loses_year_short_date_survives(self):
        """Две вставки в «Копилку»: с ячейкой даты «22.09.2026» и с
        «27.09». В документе origin первая несёт «22.09», вторая — «27.09»
        без изменений.

        Ловит мутацию: ячейка даты разбирается строго как «ДД.ММ.ГГГГ»
        (`datetime.strptime` без ветки краткой формы, `cell.split(".")`
        с обращением к третьему элементу) — уже краткая «27.09» тогда
        теряет содержимое либо роняет команду, и тест красен на второй
        строке; нормализация, вовсе не доехавшая до пути вставки, красит
        первую.
        """
        self.note("копилка", "--text",
                  "1 | 22.09.2026 | ДАТАСГОДОМ | где | состояние")
        self.note("копилка", "--text",
                  "1 | 27.09 | ДАТАКРАТКАЯ | где | состояние")

        long_row = self.backlog_row("ДАТАСГОДОМ")
        short_row = self.backlog_row("ДАТАКРАТКАЯ")

        self.assertEqual(_sandbox.cells(long_row)[DATE_CELL_INDEX], "22.09",
                         long_row)
        self.assertEqual(_sandbox.cells(short_row)[DATE_CELL_INDEX], "27.09",
                         short_row)


if __name__ == "__main__":
    unittest.main()
