"""Приёмочный тест AC-1 задачи 01M290Q1VK21V0X2VKC7WS6K1K: `note --drop
<ключ>` снимает РОВНО ОДНУ строку таблицы раздела, найденную тем же
поиском по подстроке ключа, что `--append` (`_iter_matching_rows`), и не
меняет остальные строки файла — ни в том же разделе, ни в других.

Красен до реализации: `orchestrator.notes.cmd_note` ещё не понимает флаг
`--drop` (`argparse` отказывает неизвестным аргументом) — импорт модуля
проходит, но сам вызов падает `SystemExit`/`ArgumentError` до всякого
git, а не по причине, которую проверяет этот тест.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from orchestrator import notes  # noqa: E402
from _sandbox import NoteSandbox, SECTION_HEADINGS, row_cells, section_rows  # noqa: E402


class DropRemovesOnlyMatchedRowTest(NoteSandbox):

    def test_ac1_drop_removes_matched_row_and_keeps_neighbours_intact(self):
        """Ключ «КЛЮЧСНЯТЬ» встречается ровно в одной строке раздела
        «Копилка» — после `--drop` эта строка пропадает, а соседние строки
        («КЛЮЧСОСТОЯНИЕ», «КЛЮЧПРИОРИТЕТ» и обе «ПОВТОРКЛЮЧ») остаются
        байт-в-байт прежними и в прежнем порядке; другие разделы файла не
        затронуты вовсе.

        Ловит мутацию: снятие строки по индексу совпадения (например,
        первой строки раздела) вместо найденной по ключу — сосед со
        строкой «КЛЮЧСОСТОЯНИЕ» окажется снят или искажён вместо
        «КЛЮЧСНЯТЬ», тест красен на `assertEqual` соседних строк.
        """
        before_text = self.origin_backlog()
        before_rows = section_rows(before_text, SECTION_HEADINGS["копилка"])
        head_before = self.origin_head()

        notes.cmd_note(["--drop", "КЛЮЧСНЯТЬ"])

        head_after = self.origin_head()
        self.assertNotEqual(head_before, head_after)
        self.assertEqual(self.origin_changed_files(head_before, head_after),
                         ["docs/backlog.md"])

        after_text = self.origin_backlog()
        after_rows = section_rows(after_text, SECTION_HEADINGS["копилка"])

        self.assertEqual(len(after_rows), len(before_rows) - 1)
        self.assertFalse(any("КЛЮЧСНЯТЬ" in row for row in after_rows))

        # Остальные строки раздела «Копилка» — байт-в-байт прежние и в
        # прежнем относительном порядке (сравнение множеств, т.к. одна
        # строка исчезла из середины).
        expected_remaining = [row for row in before_rows
                              if "КЛЮЧСНЯТЬ" not in row]
        self.assertEqual(after_rows, expected_remaining)

        # Другие разделы файла не затронуты.
        for section_key in ("бэклог", "очередь"):
            heading = SECTION_HEADINGS[section_key]
            self.assertEqual(section_rows(after_text, heading),
                             section_rows(before_text, heading))

    def test_ac1_drop_from_last_row_of_section_keeps_earlier_rows(self):
        """Снятие строки, находящейся в КОНЦЕ раздела («КЛЮЧДЛИННЫЙ …
        ХВОСТМАРКЕР»), не задевает строки, идущие раньше неё, включая
        соседнюю «КЛЮЧПРИОРИТЕТ» непосредственно перед ней.

        Ловит мутацию: реализация ошибочно снимает строку ПОСЛЕ найденной
        (сдвиг индекса на единицу) — при снятии последней строки раздела
        это привело бы либо к `IndexError`, либо к порче предыдущей строки
        «КЛЮЧПРИОРИТЕТ», тест красен на `assertIn` этого ключа в
        результате.
        """
        notes.cmd_note(["--drop", "ХВОСТМАРКЕР"])

        after_rows = section_rows(self.origin_backlog(),
                                  SECTION_HEADINGS["копилка"])
        self.assertFalse(any("ХВОСТМАРКЕР" in row for row in after_rows))
        self.assertTrue(any("КЛЮЧПРИОРИТЕТ" in row for row in after_rows))
        matched = [row for row in after_rows if "КЛЮЧПРИОРИТЕТ" in row][0]
        self.assertEqual(row_cells(matched),
                         ["1", "01.01", "КЛЮЧПРИОРИТЕТ запись приоритета",
                          "orchestrator/prio.py"])


if __name__ == "__main__":
    unittest.main()
