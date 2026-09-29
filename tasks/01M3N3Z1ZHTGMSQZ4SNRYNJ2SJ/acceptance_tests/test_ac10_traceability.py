"""AC-10 — трассируемость на выходе из `tests_writing` засчитывает метод
`test_ac<n>_…` долгоживущего файла `tests/` кодовой ветки ЭТОЙ задачи
(файл с её префиксом), но не одноимённый метод файла `tests/` без её
префикса.

База ветки песочницы уже несёт два одноимённых метода `test_ac1_…`:
`tests/test_existing.py::test_ac1_legacy` (файл без префикса) и
`tests/test_<id чужой задачи>_legacy.py` (долгоживущий файл «уже
смерженной» задачи). SPEC вложенной задачи — AC-1 и AC-2, планка
покрывает только AC-2.

Группа: разовый
Красен до реализации: трассируемость сегодня читает только каталог приёмочных тестов ветки документов — AC-1, покрытый лишь долгоживущим файлом `tests/` задачи, числится непокрытым, и переход отклонён.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _sandbox  # noqa: E402


class LongLivedTraceabilityTest(_sandbox.LongLivedSandbox):

    CRITERIA = ("AC-1. Первый критерий вложенной песочницы.\n\n"
                "AC-2. Второй критерий вложенной песочницы.")

    def setUp(self):
        super().setUp()
        self.artifact_commit(
            {"acceptance_tests/test_ac1_plank.py":
             _sandbox.plank_source(methods=("test_ac2_plank_fixture",))},
            "планка покрывает только AC-2")

    def test_ac10_long_lived_method_of_this_task_covers_criterion(self):
        """Кодовая ветка добавила `tests/test_<префикс>_cover.py` с методом
        `test_ac1_…` — выход из `tests_writing` проходит, записи отказа
        трассируемости нет.

        Ловит мутацию: трассируемость собирает методы только из
        `acceptance_tests/` ветки документов — AC-1 остаётся непокрытым,
        переход отклонён «трассируемость AC».
        """
        self.wt_commit({self.ll_path("cover"): _sandbox.long_lived_source()})
        out, entries = self.exit_tests_writing()
        self.assertEqual(self.state(), "in_dev",
                         f"AC-1 покрыт долгоживущим файлом задачи, но переход "
                         f"не прошёл: {entries!r}\n{out}")

    def test_ac10_same_named_method_outside_task_prefix_does_not_cover(self):
        """Долгоживущего файла задачи нет; одноимённые методы `test_ac1_…`
        есть только в файлах `tests/` базы без префикса этой задачи.
        Выход отклонён, и отказ называет непокрытый AC-1.

        Ловит мутацию: трассируемость собирает `test_ac<n>_…` из всего
        каталога `tests/` кодовой ветки, а не из файлов с префиксом задачи
        — `test_ac1_legacy` базы засчитывается, переход проходит.
        """
        out, entries = self.exit_tests_writing()
        text = "\n".join(entries + [out])
        self.assertEqual(self.state(), "tests_writing",
                         f"AC-1 засчитан чужим методом: {text}")
        self.assertIn("AC-1", text)


if __name__ == "__main__":
    unittest.main()
