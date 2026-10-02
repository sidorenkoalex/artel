"""AC-5: исправление только в `tests/`, conftest и test_invariants не тронуты.

Группа: разовый
Зелёный с рождения: до реализации ветка задачи не меняет кодовых файлов — дифф от базы пуст, ограничения выполняются тривиально; тест сторожит, что исправление их не нарушит.

Дифф — от точки расхождения ветки с `origin/<основная>`
(`gitcmd.diff_base`): коммиты, рабочее дерево и неотслеживаемые новые
файлы вне `tasks/`. Автогенерируемая карта `docs/codebase-map.md`
допускается: её регенерация обязательна при правке `tests/*.py`
(skills/conventions-core.md), это не исправление.
"""
import unittest

from _plank import changed_paths, diff_base

#: Генерируемая карта кода: обязана обновляться вместе с `tests/*.py`.
GENERATED = {"docs/codebase-map.md"}


class FixScopeTest(unittest.TestCase):
    """Правки ветки задачи лежат только в `tests/`."""

    def setUp(self):
        base = diff_base()
        self.assertTrue(base, "база ветки задачи не вычислена")
        self.changed = changed_paths(base)

    def test_ac5_changes_only_under_tests(self):
        """Все изменённые веткой пути — под `tests/` (кроме карты кода).

        Ловит мутацию: причину закрыли правкой пульта —
        `orchestrator/runner.py` или `orchestrator/stack.py` в диффе
        ветки, тест красный с этим путём.
        """
        outside = [p for p in self.changed
                   if not p.startswith("tests/") and p not in GENERATED]
        self.assertEqual(outside, [], "правки вне tests/")

    def test_ac5_conftest_and_invariants_untouched(self):
        """Ни один `conftest.py` и `tests/test_invariants.py` не изменены.

        Ловит мутацию: изоляцию CLI положили в `conftest.py` (корневой
        или `tests/conftest.py`) или поправили `tests/test_invariants.py`
        — путь появляется в диффе, тест красный.
        """
        touched = [p for p in self.changed
                   if p == "conftest.py" or p.endswith("/conftest.py")
                   or p == "tests/test_invariants.py"]
        self.assertEqual(touched, [], "тронуты файлы «только чтение»")


if __name__ == "__main__":
    unittest.main()
