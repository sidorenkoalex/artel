"""AC-5 — 01M2CN465WEDCF6D77V37FJ82E: ассерты существующих тестов не
изменены.

Источник — SPEC.md, «Критерии приёмки»:

AC-5. Ассерты существующих тестов (кроме диффа AC-4, который не входит в
код ветки задачи) не изменены.

Требование 5 SPEC формулирует то же самое: правка ограничена
`PATCHED_ATTRS` (кортежи имён строк) — она НЕ добавляет, не убирает и не
переписывает ни одной строки вида `assert...`/`self.assert...` в
СУЩЕСТВУЮЩИХ файлах `tests/`. `tests/test_invariants.py` из этой сверки
исключён явно: по AC-4 он вообще не входит в код ветки задачи (правка
приходит диффом к PLAN.md, который применяет Оператор), поэтому его
здесь сравнивать не с чем.

Красен до реализации: не должен быть красным — задача НЕ ДОЛЖНА трогать
ни одного ассерта, поэтому уже сейчас (до единой правки веткой) диф
пуст и тест зелёный. Зелёный с рождения: пока разработчик не менял
`tests/`, сравнивать нечего — красным этот тест должен стать РОВНО
тогда, когда чей-то диф случайно тронет строку ассерта, что и есть его
единственная работа.
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402

# Строка добавлена(+)/убрана(-) диффом и матчит вызов ассерта unittest
# (`self.assertEqual(...)`, `assertTrue(...)`) либо голый `assert`.
_ASSERT_LINE_RE = re.compile(r"^[+-](?!\+\+|--)\s*(self\.)?assert[A-Za-z_]*\s*\(|^[+-](?!\+\+|--)\s*assert\s")


class ExistingAssertionsUnchangedTest(unittest.TestCase):

    def test_ac5_no_assertion_lines_changed_in_modified_test_files(self):
        """Ни одна строка вида `assert...`/`self.assert...` не входит в
        добавленные или удалённые строки диффа `tests/` (файлы, УЖЕ
        существовавшие на `main` — новые файлы, если появятся, не
        являются «существующими тестами» из формулировки AC-5),
        исключая `tests/test_invariants.py` (AC-4).

        Ловит мутацию: правка "заодно" меняет условие существующего
        `self.assertEqual(x, y)` на `self.assertEqual(x, y + 1)` (или
        любую другую строку с `assert`) в уже существующем файле — диф
        покажет и `-`, и `+` строку с `assert`, regex найдёт совпадение,
        и `assertEqual([], offending)` покраснеет.
        """
        modified_files = _util.changed_paths_since_main(
            "tests/", ":(exclude)tests/test_invariants.py",
            diff_filter="M")
        if not modified_files:
            return

        diff_text = _util.diff_since_main(
            "tests/", ":(exclude)tests/test_invariants.py",
            unified=0, diff_filter="M")

        offending = [line for line in diff_text.splitlines()
                    if _ASSERT_LINE_RE.match(line)]

        self.assertEqual(
            [], offending,
            "диф tests/ меняет строку(и) с ассертом в существующем "
            "файле — AC-5 запрещает менять ассерты существующих тестов: "
            + " | ".join(offending))


if __name__ == "__main__":
    unittest.main()
