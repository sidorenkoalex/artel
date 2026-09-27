"""AC-1, AC-2 — 01M3HST4SGX0SPKAGNHVY7DWHM: обе формы строки `note` дают
одну строку таблицы; сверка числа ячеек считает их после снятия
обрамления.

Источник — SPEC.md, «Критерии приёмки»:

AC-1. `note копилка --text "| 1 | 27.09 | текст | где | состояние |"` и
`note копилка --text "1 | 27.09 | текст | где | состояние"` дают в
`docs/backlog.md` байт-в-байт одинаковую строку таблицы.

AC-2. Строка, число ячеек которой после снятия обрамления не совпадает с
числом колонок шапки раздела, по-прежнему отказ, называющий ожидаемое
число колонок; содержимое документа не меняется.

Проверяется сквозь `notes.cmd_note` против настоящего git (bare origin
стенда), а не вызовом `notes._apply_insert`: критерий говорит о строке В
`docs/backlog.md`, а снятие обрамления может лечь в любую точку пути
команды — планка не вправе фиксировать, в какую именно.

Красен до реализации: `_apply_insert` (:181) делит `--text` своим
`text.split("|")`, поэтому обрамлённая форма даёт на две ячейки больше и
отказывает по числу колонок (AC-1 падает на `SystemExit`), а «| 1 | 2 | 3 |»
даёт ровно пять ячеек с двумя пустыми и молча вставляется (AC-2 падает на
отсутствии отказа).
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _sandbox  # noqa: E402
from orchestrator import notes  # noqa: E402

ROW_CELLS = ("1", "27.09", "текст", "где", "состояние")
FRAMED = "| " + " | ".join(ROW_CELLS) + " |"
BARE = " | ".join(ROW_CELLS)
EXPECTED_ROW = FRAMED


class RowFormsTest(_sandbox.NoteSandbox):

    def test_ac1_framed_and_bare_text_give_the_same_row(self):
        """Две вставки в «Копилку» одного и того же содержимого — сперва с
        обрамляющими чертами, затем без них — дают в документе origin две
        строки таблицы, равные друг другу байт-в-байт (и обе — в форме
        `| ячейка | ячейка | … |`, которую документ несёт сегодня).

        Ловит мутацию: обрамление снимается не «только когда текст и
        начинается, и заканчивается чертой» (приёмом `_row_cells`), а
        безусловным `text.strip("|")` либо не снимается вовсе — тогда
        обрамлённая форма или отказывает по числу колонок, или даёт строку
        с пустыми крайними ячейками, и равенство двух строк ломается.
        """
        self.note("копилка", "--text", FRAMED)
        self.note("копилка", "--text", BARE)

        rows = self.backlog_rows("| текст |")
        self.assertEqual(len(rows), 2, self.origin_backlog())
        self.assertEqual(rows[0], rows[1])
        self.assertEqual(rows[0], EXPECTED_ROW)

    def test_ac2_cell_count_mismatch_after_unframing_refuses(self):
        """Обрамлённая строка из трёх ячеек против пятиколоночной шапки
        «Копилки» — отказ, называющий ожидаемое число колонок; документ в
        origin остаётся байт-в-байт прежним, удержанной записи нет.

        Ловит мутацию: обрамление снимается, но число ячеек сверяется с
        шапкой ДО снятия — три ячейки плюс два пустых обрамляющих поля
        дают ровно пять, строка молча вставляется, и тест красен на
        отсутствии `SystemExit` и изменившемся документе.
        """
        before = self.origin_head()

        message = self.refusal(notes.cmd_note, "копилка", "--text",
                               "| 1 | 2 | 3 |")

        self.assertIn(str(_sandbox.KOPILKA_COLUMNS), message, message)
        self.assertEqual(before, self.origin_head())
        self.assertEqual(self.origin_backlog(), _sandbox.BACKLOG_TEXT)
        self.assertEqual(notes.pending_notes(), [])


if __name__ == "__main__":
    unittest.main()
