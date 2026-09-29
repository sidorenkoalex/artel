"""AC-19 — на `in_dev -> verifying` долгоживущие файлы перечня
исполняются в том же прогоне `acceptance.run`, что и приёмочные тесты;
итог называет число тестов разовой и долгоживущей групп.

`acceptance.run` не подменяется — только оборачивается шпионом
(`wraps`), чтобы сосчитать вызовы: прогон настоящий, pytest в worktree
кодовой ветки.

Группа: разовый
Красен до реализации: прогон на `in_dev -> verifying` сегодня исполняет только каталог приёмочных тестов — падающий долгоживущий файл перечня не исполняется, переход проходит, а итог называет одно число тестов планки.
"""
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _sandbox  # noqa: E402
from orchestrator import acceptance  # noqa: E402


def near(word_root: str, number: int) -> re.Pattern:
    """Число рядом с названием группы (в пределах фразы, в любом порядке)."""
    return re.compile(
        rf"{word_root}\w*[^\d\n]{{0,40}}?(?<!\d){number}(?!\d)"
        rf"|(?<!\d){number}(?!\d)[^\d\n]{{0,40}}?{word_root}", re.I)


class OneRunTest(_sandbox.LongLivedSandbox):

    def advance_in_dev_spied(self):
        with mock.patch.object(acceptance, "run", wraps=acceptance.run) as spy:
            out, entries = self.advance_in_dev()
        return out, entries, spy

    def test_ac19_failing_long_lived_test_reddens_the_single_run(self):
        """Долгоживущий файл перечня несёт падающий метод (файл зафиксирован
        перечнем как есть, сверка сумм проходит). `in_dev -> verifying`
        отклонён красным прогоном приёмки; `acceptance.run` вызван ровно
        один раз, и текст отказа называет долгоживущий файл.

        Ловит мутацию: долгоживущие файлы гоняются отдельным вторым
        прогоном после зелёной планки (или не гоняются вовсе) —
        `acceptance.run` вызван дважды либо переход прошёл.
        """
        rel = self.ll_path("red")
        self.lock_with({rel: _sandbox.long_lived_source(
            methods=("test_ac1_green", "test_ac1_red"), failing=("test_ac1_red",))})
        out, entries, spy = self.advance_in_dev_spied()
        text = "\n".join(entries + [out])
        self.assertEqual(self.state(), "in_dev",
                         f"падающий долгоживущий тест не остановил переход: {text}")
        self.assertEqual(spy.call_count, 1,
                         f"прогонов acceptance.run: {spy.call_count}")
        self.assertIn(Path(rel).name, text,
                      "отказ прогона не называет долгоживущий файл")

    def test_ac19_summary_names_counts_of_both_groups(self):
        """Планка — три метода, долгоживущий файл — два, все зелёные:
        переход проходит в `verifying`, `acceptance.run` вызван один раз, а
        итог (записи журнала за переход и вывод) называет «разов…» рядом
        с 3 и «долгожив…» рядом с 2.

        Ловит мутацию: итог по-прежнему считает только планку
        (`acceptance.summary` по `acceptance_tests/`) — числа
        долгоживущей группы в нём нет.
        """
        self.artifact_commit(
            {"acceptance_tests/test_ac1_plank.py": _sandbox.plank_source(
                methods=("test_ac1_a", "test_ac1_b", "test_ac1_c"))},
            "планка из трёх методов")
        self.lock_with({self.ll_path("pair"): _sandbox.long_lived_source(
            methods=("test_ac1_first", "test_ac1_second"))})
        out, entries, spy = self.advance_in_dev_spied()
        text = "\n".join(entries + [out])
        self.assertEqual(self.state(), "verifying",
                         f"зелёный прогон обеих групп не прошёл: {text}")
        self.assertEqual(spy.call_count, 1)
        self.assertRegex(text, near("разов", 3),
                         "итог не называет число тестов разовой группы")
        self.assertRegex(text, near("долгожив", 2),
                         "итог не называет число тестов долгоживущей группы")


if __name__ == "__main__":
    unittest.main()
