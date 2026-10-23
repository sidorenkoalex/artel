"""Блок «самые медленные» `suite_durations.slowest_block` меньше среза."""
import tempfile
import unittest
from pathlib import Path

from orchestrator import suite_durations


class SlowestBlockBelowCutTest(unittest.TestCase):

    def test_fewer_than_cut_lists_all_and_skips_broken_lines(self):
        """Тестов и файлов меньше среза — в блоке все, строки файла не по форме пропущены.

        Ловит мутацию: срез применён без учёта меньшего числа (отдаётся
        пусто или с пропуском) — строк в блоке меньше трёх тестов и двух
        файлов; строка файла времени не из четырёх полей или с нечисловыми
        секундами роняет разбор или попадает в блок.
        """
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "t-suiterun-3.log"
            suite_durations.path_for(log).write_text(
                "tests/test_a.py::test_x\tgw0\tPASSED\t1.500\n"
                "tests/test_a.py::test_y\tgw1\tFAILED\t0.250\n"
                "битая строка\n"
                "tests/test_c.py::test_z\tgw0\tPASSED\tnan?\n"
                "tests/test_b.py::test_z\tgw0\tPASSED\t3.000\n",
                encoding="utf-8")
            block = suite_durations.slowest_block(log)
        entries = [line for line in block.splitlines() if line.startswith("  ")]
        self.assertEqual(entries, [
            "  3.00 с  tests/test_b.py::test_z",
            "  1.50 с  tests/test_a.py::test_x",
            "  0.25 с  tests/test_a.py::test_y",
            "  3.00 с  tests/test_b.py",
            "  1.75 с  tests/test_a.py",
        ])
        self.assertNotIn("test_c", block)

    def test_write_slowest_puts_block_beside_log_only_when_rows(self):
        """Блок пишется в `<лог>.slowest.txt`; без файла времени и с пустым — файла блока нет.

        Ловит мутацию: файл блока не пишется или пишется под другим именем
        (под шаблоном `*.log`) — пути и содержимого нет; пустой файл времени
        даёт файл с одним заголовком — функция отдаёт путь вместо `None`.
        """
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "t-suiterun-4.log"
            self.assertIsNone(suite_durations.write_slowest(log))
            suite_durations.path_for(log).write_text("", encoding="utf-8")
            self.assertIsNone(suite_durations.write_slowest(log))
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()),
                             ["t-suiterun-4.durations.tsv"])
            suite_durations.path_for(log).write_text(
                "tests/test_a.py::test_x\tgw0\tPASSED\t1.500\n",
                encoding="utf-8")
            path = suite_durations.write_slowest(log)
            self.assertEqual(path, Path(tmp) / "t-suiterun-4.slowest.txt")
            self.assertEqual(path.read_text(encoding="utf-8"),
                             suite_durations.slowest_block(log) + "\n")


if __name__ == "__main__":
    unittest.main()
