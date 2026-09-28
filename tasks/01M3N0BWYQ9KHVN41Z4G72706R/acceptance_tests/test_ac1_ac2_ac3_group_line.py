"""AC-1, AC-2, AC-3 — строка группы в докстринге модуля `test_*.py` на
выходе из `tests_writing` задачи target `artel`.

Группа: разовый
Красен до реализации: строки группы выход из `tests_writing` сейчас не проверяет — файл без неё или с неизвестным значением проходит в `in_dev`, записи отказа нет.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _sandbox  # noqa: E402

HELPER = '"""Помощник вложенной планки без строки группы."""\nVALUE = 1\n'


class GroupLineRequiredTest(_sandbox.GroupPlankSandbox):

    def test_ac1_file_without_group_line_refuses_naming_file(self):
        """Вложенная задача target `artel`: единственный `test_*.py` без
        строки группы (всё остальное в порядке) — `advance` из
        `tests_writing` отклонён, задача осталась в `tests_writing`, запись
        отказа называет файл.

        Ловит мутацию: проверку строки группы подключили только к
        `amend-tests`, а на выход из `tests_writing` — нет (или её ошибки
        не добавили к списку ошибок перехода): задача уходит в `in_dev`,
        записи отказа с именем `test_no_group.py` нет.
        """
        self.assert_refused_naming(
            {"test_no_group.py": _sandbox.plank_source(group=None)},
            "test_no_group.py", why="файл без строки группы")

    def test_ac2_unknown_group_value_refuses_naming_file(self):
        """Строка `Группа: временный` (значение вне перечня) — отказ
        перехода, запись отказа называет файл.

        Ловит мутацию: регулярное выражение строки группы принимает любое
        слово после «Группа:» (`\\S+` вместо перечня двух значений) —
        файл с неизвестным значением проходит в `in_dev`.
        """
        self.assert_refused_naming(
            {"test_bad_group.py": _sandbox.plank_source(
                raw_group_line="Группа: временный")},
            "test_bad_group.py", why="неизвестное значение группы")

    def test_ac3_helpers_without_group_line_do_not_refuse(self):
        """Каталог планки: корректный долгоживущий `test_*.py`, корректный
        разовый `test_*.py`, а также `_helper.py`, `markers.py`,
        `__init__.py`, `README.md` и `notes.txt` без строки группы —
        переход проходит в `in_dev` без отказа.

        Ловит мутацию: проверка строки группы обходит все `*.py` каталога
        (как `scan_id_format_samples`), а не только `test_*.py` — у
        `_helper.py`/`markers.py`/`__init__.py` строки нет, переход
        отклонён.
        """
        self.assert_passes({
            "test_long.py": _sandbox.plank_source(group=_sandbox.GROUP_LONG),
            "test_once.py": _sandbox.plank_source(group=_sandbox.GROUP_ONCE),
            "_helper.py": HELPER,
            "markers.py": HELPER,
            "__init__.py": "",
            "README.md": "# вложенная планка\n",
            "notes.txt": "заметки\n",
        }, why="разрешённые файлы без строки группы")

    def test_ac3_each_group_alone_passes_but_missing_line_still_refuses(self):
        """Каждая из двух групп по отдельности проходит переход; тот же
        каталог, где у одного файла строки нет, — отклонён (контроль, что
        проверка вообще работает в этом сценарии).

        Ловит мутацию: разбор значения сравнивает с `долгоживущий`
        буквой «е» вместо «ё» (или только с одним значением перечня) —
        корректный файл одной из групп отклоняется, `self.state()` не
        `in_dev`.
        """
        for group in (_sandbox.GROUP_LONG, _sandbox.GROUP_ONCE):
            with self.subTest(group=group):
                self.assert_passes(
                    {"test_one.py": _sandbox.plank_source(group=group)},
                    why=f"файл группы «{group}»")
        self.assert_refused_naming(
            {"test_one.py": _sandbox.plank_source(group=_sandbox.GROUP_ONCE),
             "test_two.py": _sandbox.plank_source(group=None)},
            "test_two.py", why="второй файл без строки группы")


if __name__ == "__main__":
    unittest.main()
