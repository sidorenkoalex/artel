"""Приёмочный тест AC-9 задачи 01M1VBEHTDYPK3E4RRFHWYYYW3: `note --append
<подстрока-ключ> --text "<текст>"` меняет ровно одну существующую строку
раздела (дописывает текст в последнюю колонку); ноль или более одного
совпадения подстроки — отказ без изменения файла.

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


class AppendUniqueMatchTest(NoteSandbox):

    def test_ac9_append_updates_only_the_matching_row_last_column(self):
        """Ключ, встречающийся ровно в одной строке («УНИКАЛЬНЫЙКЛЮЧ»,
        строка №1 «Копилки»), — дописанный текст оказывается в ПОСЛЕДНЕЙ
        колонке именно этой строки (вместе со старым содержимым), а
        остальные строки раздела остаются байт-в-байт прежними.

        Ловит мутацию: текст дописывается не в последнюю, а в какую-то
        другую колонку (например, вставляется отдельной строкой) — тест
        красен на `assertIn` содержимого последней ячейки.
        """
        head_before = self.origin_head()

        notes.cmd_note(["--append", "УНИКАЛЬНЫЙКЛЮЧ", "--text", "доп. текст"])

        head_after = self.origin_head()
        self.assertNotEqual(head_before, head_after)
        self.assertEqual(self.origin_changed_files(head_before, head_after),
                         ["docs/backlog.md"])

        rows = section_rows(self.origin_backlog(), SECTION_HEADINGS["копилка"])
        matched = row_cells(rows[2])
        self.assertIn("orchestrator/x.py", matched[-1])
        self.assertIn("доп. текст", matched[-1])
        # Соседние строки раздела не задеты.
        self.assertEqual(row_cells(rows[3]),
                         ["2", "01.01", "наблюдение ПОВТОРКЛЮЧ один",
                          "orchestrator/y.py"])
        self.assertEqual(row_cells(rows[4]),
                         ["2", "01.01", "наблюдение ПОВТОРКЛЮЧ два",
                          "orchestrator/z.py"])


class AppendZeroMatchesTest(NoteSandbox):

    def test_ac9_zero_matches_refuses_without_changing_the_file(self):
        """Подстрока, не встречающаяся ни в одной строке файла, —
        именованный отказ, origin не продвигается, содержимое
        `docs/backlog.md` в origin остаётся байт-в-байт прежним.

        Ловит мутацию: отсутствие совпадения трактуется как «нечего
        менять — тихий успех» вместо отказа — тест красен на
        `assertRaises(SystemExit)`.
        """
        head_before = self.origin_head()
        text_before = self.origin_backlog()

        with self.assertRaises(SystemExit):
            notes.cmd_note(["--append", "НЕТТАКОГОКЛЮЧА", "--text", "текст"])

        self.assertEqual(self.origin_head(), head_before)
        self.assertEqual(self.origin_backlog(), text_before)


class AppendMultipleMatchesTest(NoteSandbox):

    def test_ac9_multiple_matches_refuses_without_changing_the_file(self):
        """Подстрока, встречающаяся в НЕСКОЛЬКИХ строках («ПОВТОРКЛЮЧ» —
        строки №2 и №3 «Копилки»), — именованный отказ, файл не меняется:
        неоднозначность не разрешается автоматическим выбором первой
        строки.

        Ловит мутацию: реализация при нескольких совпадениях молча берёт
        ПЕРВОЕ — тест красен и на отсутствии `SystemExit`, и на
        изменившемся содержимом origin.
        """
        head_before = self.origin_head()
        text_before = self.origin_backlog()

        with self.assertRaises(SystemExit):
            notes.cmd_note(["--append", "ПОВТОРКЛЮЧ", "--text", "текст"])

        self.assertEqual(self.origin_head(), head_before)
        self.assertEqual(self.origin_backlog(), text_before)


if __name__ == "__main__":
    unittest.main()
