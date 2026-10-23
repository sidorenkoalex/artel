"""Факты этой задачи: формулировка докстринга `scripts/guard.py` (AC-8) и
неизменность модулей гейта неослабления в диффе ветки (AC-9, первая
часть; вторая часть AC-9 — счёт тестов — в долгоживущем файле
`test_01m5n9wk9sgb7kdyjp736dp6cv_plank_forms.py`).

Группа: разовый

Красен до реализации: докстринг `scan_acceptance_tests` в `scripts/guard.py` ещё говорит «unittest на гейте»; проверка диффа (AC-9) зелёна с рождения — ветка пока ничего не меняет.

Текст guard читается из рабочей копии задачи (`CODE_ROOT` помощника
пульта), пути диффа — `changed_paths()` помощника пульта.
"""
import ast
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, changed_paths  # noqa: E402

GUARD = "scripts/guard.py"
READ_ONLY = ("orchestrator/advance_gates/test_integrity.py",
             "orchestrator/advance_gates/two_sided.py")


def guard_text() -> str:
    return (Path(CODE_ROOT) / GUARD).read_text(encoding="utf-8")


class TaskFactsTest(unittest.TestCase):

    def test_ac8_docstring_says_pytest_on_gate(self):
        """Докстринг `scan_acceptance_tests` говорит «pytest на гейте», фразы «unittest на гейте» в guard нет.

        Сценарий: разбор `scripts/guard.py` рабочей копии; докстринг
        `scan_acceptance_tests` (место прежней строки 865) с
        нормализованными пробелами содержит «pytest на гейте»; во всём
        тексте файла (пробелы и переносы нормализованы) нет «unittest на
        гейте».

        Ловит мутацию: фраза не исправлена или исправлена в другом месте —
        докстринг функции без «pytest на гейте» либо «unittest на гейте»
        осталась в файле.
        """
        text = guard_text()
        tree = ast.parse(text)
        func = next(node for node in tree.body
                    if isinstance(node, ast.FunctionDef)
                    and node.name == "scan_acceptance_tests")
        doc = " ".join((ast.get_docstring(func) or "").split())
        self.assertIn("pytest на гейте", doc)
        self.assertNotIn("unittest на гейте", " ".join(text.split()))

    def test_ac9_branch_keeps_gate_modules_unchanged(self):
        """Дифф ветки задачи не содержит `test_integrity.py` и `two_sided.py`.

        Ловит мутацию: разработчик правит модуль гейта неослабления или
        двустороннего прогона вместо `scripts/guard.py` — путь появляется
        в `changed_paths()`.
        """
        paths = set(changed_paths())
        for path in READ_ONLY:
            self.assertNotIn(path, paths)


if __name__ == "__main__":
    unittest.main()
