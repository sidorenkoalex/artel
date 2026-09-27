"""AC-3, AC-4 — 01M3HST4SGX0SPKAGNHVY7DWHM: приоритет нормализуется к
цифре на двух путях; нераспознанный приоритет — именованный отказ.

Источник — SPEC.md, «Критерии приёмки»:

AC-3. Вставка строки с ячейкой приоритета «П2» и вставка той же строки с
ячейкой «2» дают в документе ячейку «2»; `note --set-priority <ключ>
--text "П2"` и `--text "2"` тоже дают «2».

AC-4. Приоритет «высокий», «5» или «П7» — отказ, текст которого несёт
пример допустимой формы; документ не изменён, коммита нет.

Колонка приоритета «Копилки» — первая по шапке (`| П | …`), поэтому
проверяется нулевая ячейка строки; разбор строки — собственный
(`_sandbox.cells`), не `notes._row_cells`.

Красен до реализации: нормализации приоритета сегодня нет вовсе —
`_apply_insert` (:181) кладёт ячейку как есть («П2» остаётся «П2»), а
`_apply_set_priority` (:250) требует `int(text)` и потому отказывает форме
«П2» вместо того, чтобы записать «2»; путь вставки любой мусор в колонке
приоритета принимает молча. Три теста файла из четырёх поэтому красные.

Четвёртый — `test_ac4_unrecognized_priority_in_set_priority_refuses` —
зелёный с рождения, и это ожидаемо: сегодняшний `_apply_set_priority`
отказывает всем трём значениям, а его текст («вне диапазона 1..4») уже
несёт пример допустимой формы. Тест охраняет это от ослабления на шаге,
где к разбору добавляют форму «П<цифра>»: снятая вместе с `int(text)`
сверка границ — правдоподобная мутация именно этого шага.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _sandbox  # noqa: E402
from orchestrator import notes  # noqa: E402

# Пример допустимой формы в тексте отказа (требование 4): цифра
# разрешённого диапазона. Конкретную формулировку планка не фиксирует.
VALID_FORM_EXAMPLE = re.compile(r"[1-4]")

UNRECOGNIZED = ("высокий", "5", "П7")


class InsertedPriorityTest(_sandbox.NoteSandbox):

    def test_ac3_inserted_priority_cell_normalizes_to_digit(self):
        """Две вставки в «Копилку» с ячейкой приоритета «П2» и «2» — обе
        дают в документе origin ячейку приоритета «2».

        Ловит мутацию: нормализация применена только к пути
        `--set-priority` и забыта у вставки строки — ячейка «П2» приезжает
        в документ буквой, и тест красен на первой из двух строк.
        """
        self.note("копилка", "--text",
                  "П2 | 27.09 | ПРИОРИТЕТБУКВОЙ | где | состояние")
        self.note("копилка", "--text",
                  "2 | 27.09 | ПРИОРИТЕТЦИФРОЙ | где | состояние")

        for key in ("ПРИОРИТЕТБУКВОЙ", "ПРИОРИТЕТЦИФРОЙ"):
            row = self.backlog_row(key)
            self.assertEqual(_sandbox.cells(row)[0], "2", row)

    def test_ac4_unrecognized_priority_in_inserted_row_refuses(self):
        """Вставка строки с ячейкой приоритета «высокий», «5» и «П7» — три
        отказа, каждый несёт пример допустимой формы (цифру диапазона);
        документ в origin после всех трёх попыток байт-в-байт прежний,
        удержанной записи нет.

        Ловит мутацию: нераспознанный приоритет вставки молча пропускается
        как есть (проверка стоит только на пути `--set-priority`) — тест
        красен на отсутствии `SystemExit` и изменившемся документе.
        """
        before = self.origin_head()

        for value in UNRECOGNIZED:
            message = self.refusal(
                notes.cmd_note, "копилка", "--text",
                f"{value} | 27.09 | ОТКАЗПРИОРИТЕТА | где | состояние")
            self.assertRegex(message, VALID_FORM_EXAMPLE, message)

        self.assertEqual(before, self.origin_head())
        self.assertEqual(self.origin_backlog(), _sandbox.BACKLOG_TEXT)
        self.assertEqual(notes.pending_notes(), [])


class SetPriorityTest(_sandbox.NoteSandbox):

    def test_ac3_set_priority_normalizes_both_forms(self):
        """`note --set-priority <ключ> --text "П2"` и тот же вызов с
        `--text "2"` (по второму ключу, чтобы правка не оказалась пустой)
        — обе строки получают в документе origin ячейку приоритета «2».

        Ловит мутацию: ведущая «П» снимается, но в файл пишется исходный
        текст ячейки (`cells[0] = text` вместо нормализованного значения)
        — тест красен на ячейке «П2» первой строки.
        """
        self.note("--set-priority", "ПРИОРИТЕТКЛЮЧ", "--text", "П2")
        self.note("--set-priority", "ПРИОРИТЕТВТОРОЙ", "--text", "2")

        for key in ("ПРИОРИТЕТКЛЮЧ", "ПРИОРИТЕТВТОРОЙ"):
            row = self.backlog_row(key)
            self.assertEqual(_sandbox.cells(row)[0], "2", row)

    def test_ac4_unrecognized_priority_in_set_priority_refuses(self):
        """`--set-priority` с «высокий», «5» и «П7» — три отказа, каждый
        несёт пример допустимой формы; документ в origin прежний,
        удержанной записи нет.

        Ловит мутацию: диапазон расширен вместе с приёмом формы «П<цифра>»
        (разбор стал `int(text.lstrip("Пп"))` без сверки границ) — «5» и
        «П7» проходят, и тест красен на отсутствии `SystemExit`.
        """
        before = self.origin_head()

        for value in UNRECOGNIZED:
            message = self.refusal(notes.cmd_note, "--set-priority",
                                   "ПРИОРИТЕТКЛЮЧ", "--text", value)
            self.assertRegex(message, VALID_FORM_EXAMPLE, message)

        self.assertEqual(before, self.origin_head())
        self.assertEqual(self.origin_backlog(), _sandbox.BACKLOG_TEXT)
        self.assertEqual(notes.pending_notes(), [])


if __name__ == "__main__":
    unittest.main()
