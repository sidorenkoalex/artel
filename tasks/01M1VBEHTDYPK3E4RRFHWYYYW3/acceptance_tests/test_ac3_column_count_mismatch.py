"""Приёмочный тест AC-3 задачи 01M1VBEHTDYPK3E4RRFHWYYYW3: число колонок
`--text` сверяется с числом колонок шапки таблицы раздела; при
несовпадении — отказ с указанием ожидаемого числа колонок, коммит не
создаётся (мутация: снятие проверки — отказ на 4 колонках пропадает —
тест красный).

Числа колонок синтетического `docs/backlog.md` этой песочницы (4 у
«Копилки», 7 у «Бэклога» — `_sandbox.HEADER_COLUMNS`) НАМЕРЕННО не
совпадают с боевыми (5/6) — тест ловит и жёстко закодированный список
{"копилка": 5, "бэклог": 6, ...}, не только отсутствие проверки вовсе.

Красен до реализации: `orchestrator.notes` ещё не существует — импорт
падает `ModuleNotFoundError`.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import notes  # noqa: E402
from _sandbox import NoteSandbox  # noqa: E402


class ColumnCountMismatchTest(NoteSandbox):

    def test_ac3_kopilka_wrong_column_count_refuses_naming_four(self):
        """`--text` с тремя ячейками против шапки «Копилки» (4 ячейки в
        этой песочнице) отказывает именованно, называя ожидаемое число
        4, и не создаёт коммита в origin.

        Ловит мутацию: проверка снята вовсе (отказ пропадает — падает на
        `assertRaises`) либо число колонок зашито литералом «5» (боевое
        значение) вместо чтения фактической шапки — падает на
        `assertIn("4", ...)`.
        """
        head_before = self.origin_head()

        with self.assertRaises(SystemExit) as cm:
            notes.cmd_note(["копилка", "--text", "1 | 2 | 3"])

        self.assertIn("4", str(cm.exception))
        self.assertEqual(self.origin_head(), head_before,
                         "коммит создан несмотря на несовпадение колонок")

    def test_ac3_backlog_wrong_column_count_refuses_naming_seven(self):
        """Тот же критерий для раздела «Бэклог» (7 ячеек в шапке этой
        песочницы) другим числом — подтверждает, что число читается из
        КОНКРЕТНОГО раздела, не одно захардкоженное значение на все.

        Ловит мутацию: реализация всегда сверяет с числом колонок ПЕРВОЙ
        встреченной таблицы файла («Копилка», 4) вместо таблицы
        выбранного раздела — тест красен на `assertIn("7", ...)`.
        """
        head_before = self.origin_head()

        with self.assertRaises(SystemExit) as cm:
            notes.cmd_note(["бэклог", "--text", "1 | 2 | 3 | 4 | 5"])

        self.assertIn("7", str(cm.exception))
        self.assertEqual(self.origin_head(), head_before)


if __name__ == "__main__":
    unittest.main()
