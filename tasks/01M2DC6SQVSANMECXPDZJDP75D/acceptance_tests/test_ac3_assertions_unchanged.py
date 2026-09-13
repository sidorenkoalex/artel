"""AC-3 — 01M2DC6SQVSANMECXPDZJDP75D: диф `tests/` не меняет ни одной
строки `assert...`/`self.assert...` в уже существующих файлах.

Источник — SPEC.md, «Критерии приёмки»:

AC-3. Ассерты и сценарии существующих тестов не изменены (допустимы
только правки импортов, путей патчей и переход на наследование); полный
набор `tests/` зелёный.

Этот файл механически проверяет ИМЕННО часть про ассерты — тот же приём,
что и прецедент `tasks/01M2CN465WEDCF6D77V37FJ82E/acceptance_tests/
test_ac5_existing_test_assertions_unchanged.py` для соседней задачи того
же класса «рефакторинг ≠ фикс»: правка ограничена импортами/путями
патчей/переходом на наследование — она НЕ добавляет, не убирает и не
переписывает ни одной строки вида `assert...`/`self.assert...` в
СУЩЕСТВУЮЩИХ файлах `tests/` (новые файлы, если задача их заведёт для
базовых классов, «существующими» не являются). `tests/test_invariants.py`
из сверки исключён — по AC-6 диф не должен его касаться вовсе (сравнивать
там нечего).

Остальные две части этого же AC — «сценарии не изменены» (по существу:
семантика вызовов test_-методов, требует человеческого прочтения дифа,
не формализуется без прогона по каждому изменённому тесту) и «полный
набор tests/ зелёный» (полный прогон `tests/` из чистой копии) — не
дублируются здесь: полный прогон `tests/` — обязанность CI/автогейта, не
этой планки (`skills/test-authoring.md`: «полный набор tests/ в шаге не
запускай — его гоняет CI»), а эквивалентность сценариев (не только
ассертов) вне пределов regex-сверки диффа — предмет ревью разработчика по
дифу (тот же способ, каким прецедент AC-5 ограничил себя одной
проверяемой частью критерия, не всей его формулировкой).

Красен до реализации: НЕ должен быть красным — задача ещё не тронула ни
одной строки `tests/` (ветка только что заведена от `main`), поэтому диф
пуст и тест зелёный. Зелёный с рождения: сравнивать пока нечего — тест
покраснеет РОВНО тогда, когда чей-то диф случайно тронет строку ассерта
в уже существующем файле, что и есть его единственная работа (стаб
корректной реализации: временная правка PATCHED_ATTRS одного реального
файла без единой строки assert подтвердила зелёный исход, откачена
`git checkout` без коммита).
"""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import _util  # noqa: E402

_ASSERT_LINE_RE = re.compile(
    r"^[+-](?!\+\+|--)\s*(self\.)?assert[A-Za-z_]*\s*\(|^[+-](?!\+\+|--)\s*assert\s")


class ExistingAssertionsUnchangedTest(unittest.TestCase):

    def test_ac3_no_assertion_lines_changed_in_modified_test_files(self):
        """Ни одна строка вида `assert...`/`self.assert...` не входит в
        добавленные или удалённые строки диффа `tests/` (файлы, уже
        существовавшие на `main`), исключая `tests/test_invariants.py`.

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
            "файле — AC-3 запрещает менять ассерты существующих тестов: "
            + " | ".join(offending))


if __name__ == "__main__":
    unittest.main()
