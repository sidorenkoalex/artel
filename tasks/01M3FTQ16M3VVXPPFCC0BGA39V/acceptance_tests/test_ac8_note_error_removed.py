"""AC-8 — 01M3FTQ16M3VVXPPFCC0BGA39V: рудимент `NoteError` удалён вместе
с докстрингом, ссылок на имя в дереве нет.

Источник — SPEC.md, «Критерии приёмки»:

AC-8. В `orchestrator/notes.py` нет ни `class NoteError`, ни его
докстринга; поиск по имени `NoteError` во всём дереве репозитория не даёт
совпадений.

Поиск по дереву — по отслеживаемым git файлам, за вычетом двух зон,
которые задача по SPEC не правит и править не вправе: `tasks/` (артефакты
задач — в том числе SPEC этой задачи и эта планка, обе обязаны называть
удаляемое имя, чтобы вообще говорить о нём) и `docs/audits/` (отчёт
седьмой ревизии, где находка CR-2026-09-26-12 зафиксирована историей;
SPEC «Не входит»: только чтение). Вне этих двух зон совпадений быть не
должно ни одного — именно это и проверяется.

Красен до реализации: `orchestrator/notes.py`:96 несёт
`class NoteError(Exception)` с докстрингом — падают оба теста.
"""
import ast
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _util  # noqa: E402

NOTES_REL = "orchestrator/notes.py"
RUDIMENT = "NoteError"
# Фрагмент докстринга рудимента (orchestrator/notes.py:97-98 на базе) —
# он обязан уйти вместе с классом, а не остаться комментарием рядом.
DOCSTRING_FRAGMENT = "Не используется наружу"
EXCLUDED_ZONES = (":(exclude)tasks/", ":(exclude)docs/audits/")


class NoteErrorRemovedTest(unittest.TestCase):

    def test_ac8_notes_module_has_no_rudiment_class_nor_its_docstring(self):
        """В `orchestrator/notes.py` нет объявления класса-рудимента (ни
        текстом, ни в разборе `ast` — на случай нестандартных пробелов) и
        нет его докстринга.

        Ловит мутацию: класс убран, а его докстринг оставлен рядом
        висячей строкой/комментарием («здесь только для внутренней
        читаемости») — проверка фрагмента докстринга покраснеет, хотя
        проверка `ast` уже прошла.
        """
        text = (_util.REPO_ROOT / NOTES_REL).read_text(encoding="utf-8")
        classes = [node.name for node in ast.parse(text).body
                   if isinstance(node, ast.ClassDef)]
        self.assertNotIn(RUDIMENT, classes,
                         f"класс {RUDIMENT} обязан быть удалён из "
                         f"{NOTES_REL} (AC-8); классы модуля: {classes}")
        self.assertNotIn(RUDIMENT, text,
                         f"имя {RUDIMENT} не должно встречаться в "
                         f"{NOTES_REL} вовсе (AC-8)")
        self.assertNotIn(DOCSTRING_FRAGMENT, text,
                         f"докстринг рудимента ('{DOCSTRING_FRAGMENT}…') "
                         f"обязан уйти вместе с классом (AC-8)")

    def test_ac8_no_references_to_the_rudiment_anywhere_in_the_tree(self):
        """Поиск по отслеживаемым файлам дерева (кроме артефактов задач и
        отчётов ревизий, которые задача не правит) не даёт ни одного
        совпадения с именем рудимента.

        Ловит мутацию: класс удалён из `notes.py`, но имя осталось в
        другом месте кодовой базы — например, в `except NoteError:` или в
        экспортном списке фасада, — и команда `note` упадёт на первом же
        вызове; `git grep` найдёт строку, и тест покраснеет, назвав её.
        """
        found = _util.git("grep", "-I", "-F", "-n", RUDIMENT, "--", ".",
                          *EXCLUDED_ZONES, check=False)
        self.assertIn(
            found.returncode, (0, 1),
            f"git grep не отработал (код {found.returncode}): {found.stderr}")
        self.assertEqual(
            "", found.stdout,
            f"имя {RUDIMENT} не должно встречаться в дереве (AC-8), а "
            f"найдено:\n{found.stdout}")


if __name__ == "__main__":
    unittest.main()
