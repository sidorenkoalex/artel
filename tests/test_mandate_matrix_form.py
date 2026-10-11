"""Юнит-тесты формы матрицы неослабления (`mandate.matrix_refusals`) и
разбора `--matrix` CLI `zones-extend` (SPEC 01M4NZ5QRB7MNEYCWGXEWVWFP0) —
свойства, которых не кроет долгоживущий файл задачи
`tests/test_01m4nz5qrb7mneycwgxewvwfp0_mandate_matrix.py`: граница раздела,
нормализация заголовков, короткая строка данных, отказ на `--matrix` без
файла.
"""
import sys
import unittest
from unittest import mock

from orchestrator import answer, artel
from orchestrator.advance_gates import mandate
from tests import mandate_matrix

HEADER_ROW = "| " + " | ".join(mandate_matrix.HEADERS) + " |"
SEPARATOR = "|---|---|---|---|---|"


class MatrixSectionBoundaryTest(unittest.TestCase):

    def test_table_under_next_heading_is_not_the_matrix_table(self):
        """Таблица под следующим заголовком `## …` разделу матрицы не принадлежит — отказ «нет таблицы».

        Ловит мутацию: раздел не обрывается на следующем заголовке уровня
        2 (берётся «до конца файла») — чужая таблица засчитана, отказа нет.
        """
        text = ("## Матрица неослабления\n\nСвёрка ниже.\n\n## Прочее\n\n"
                f"{HEADER_ROW}\n{SEPARATOR}\n"
                "| `docs/a.md` | гейт | да | tests/test_a.py:1 | ок |\n")
        reasons = mandate.matrix_refusals(text, ["docs/a.md"])
        self.assertTrue(reasons)
        self.assertIn("нет таблицы", reasons[0])

    def test_level_three_heading_does_not_end_the_section(self):
        """Подзаголовок `### …` внутри раздела раздел не обрывает — таблица под ним засчитана.

        Ловит мутацию: раздел обрывается на любом заголовке (`#` в начале
        строки) — годная матрица получает отказ «нет таблицы».
        """
        text = ("## Матрица неослабления\n\n### Свёрка\n\n"
                f"{HEADER_ROW}\n{SEPARATOR}\n"
                "| `docs/a.md` | гейт | да | tests/test_a.py:1 | ок |\n")
        self.assertEqual(mandate.matrix_refusals(text, ["docs/a.md"]), [])


class MatrixHeaderNormalizationTest(unittest.TestCase):

    def test_headers_compare_without_emphasis_case_and_yo(self):
        """Заголовки с выделением `**…**`, в другом регистре и с «е» вместо «ё» — канон.

        Ловит мутацию: заголовок сравнивается посимвольно без нормализации
        — «**что меняется**» или «Остается ли…» дают отказ по заголовкам.
        """
        headers = ("**что меняется**", "КАКОЕ СВОЙСТВО СЕЙЧАС ДЕРЖИТ",
                   "Остается ли свойство после изменения",
                   "`Чем покрыто после`", "_Решение_")
        text = ("## Матрица неослабления\n\n"
                "| " + " | ".join(headers) + " |\n" + SEPARATOR + "\n"
                "| `docs/a.md` | гейт | да | tests/test_a.py:1 | ок |\n")
        self.assertEqual(mandate.matrix_refusals(text, ["docs/a.md"]), [])


class ShortDataRowTest(unittest.TestCase):

    def test_row_without_decision_cell_is_checked_as_empty_decision(self):
        """Строка данных без ячейки «Решение» при «да» + «не покрыто» — отказ с номером строки.

        Ловит мутацию: недостающие ячейки строки не дополняются пустыми, а
        строка пропускается (или падает IndexError) — отказа нет.
        """
        text = ("## Матрица неослабления\n\n"
                f"{HEADER_ROW}\n{SEPARATOR}\n"
                "| `docs/a.md` | гейт | да | tests/test_a.py:1 | ок |\n"
                "| `docs/b.md` | гейт | да | не покрыто |\n")
        reasons = mandate.matrix_refusals(text, ["docs/a.md", "docs/b.md"])
        self.assertEqual(len(reasons), 1, reasons)
        self.assertIn("строка данных 2", reasons[0])


class ZonesExtendMatrixFlagTest(unittest.TestCase):

    def test_matrix_flag_without_file_refuses_before_the_command(self):
        """`zones-extend <id> <путь> --matrix` без файла — отказ разбора, `cmd_zones_extend` не зовётся.

        Ловит мутацию: значение после `--matrix` не проверяется — путь
        файла матрицы становится `None`/следующим ключом, и команда
        исполняется с ним.
        """
        argv = ["artel.py", "zones-extend", "T001", "docs/a.md", "--matrix"]
        with mock.patch.object(sys, "argv", argv), \
                mock.patch.object(answer, "cmd_zones_extend") as command, \
                mock.patch.object(artel, "_refuse_if_worktree"), \
                mock.patch.object(artel.runner, "in_role_environment",
                                  return_value=False):
            with self.assertRaises(SystemExit) as ctx:
                artel.main()
        self.assertIn("--matrix", str(ctx.exception))
        command.assert_not_called()

    def test_matrix_flag_before_paths_is_parsed(self):
        """`zones-extend <id> --matrix <файл> <пути>` — флаг в любом месте, пути и файл доходят до команды.

        Ловит мутацию: пути берутся позиционно `rest[1]` без исключения
        пары `--matrix <файл>` — командой получен «--matrix» вместо путей.
        """
        argv = ["artel.py", "zones-extend", "T001", "--matrix", "m.md",
                "docs/a.md, docs/b.md"]
        with mock.patch.object(sys, "argv", argv), \
                mock.patch.object(answer, "cmd_zones_extend") as command, \
                mock.patch.object(artel, "_refuse_if_worktree"), \
                mock.patch.object(artel.runner, "in_role_environment",
                                  return_value=False):
            artel.main()
        command.assert_called_once_with("T001", "docs/a.md, docs/b.md",
                                        matrix_path="m.md")


if __name__ == "__main__":
    unittest.main()
