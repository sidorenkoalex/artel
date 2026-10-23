"""Планка AC-7, AC-8: границы правки ветки задачи.

Группа: разовый
Зелёный с рождения: до реализации ветка не отличается от базы — прочие методы tests/test_suite_run.py и файлы вне зоны не тронуты; тест держит эту границу на диффе разработчика.

База сравнения — `DIFF_BASE` помощника пульта (точка расхождения ветки
задачи с `origin`), дифф путей — `changed_paths()` того же помощника.
"""
import ast
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, DIFF_BASE, changed_paths  # noqa: E402

ROOT = Path(CODE_ROOT or ".").resolve()
SUITE_REL = "tests/test_suite_run.py"
CHANGED_METHOD = ("GateArgvTest", "test_gate_call_argv_unchanged")
ALLOWED = {SUITE_REL, "docs/codebase-map.md"}


def _methods(source):
    """{(класс, метод): дамп AST без позиций} всех методов классов."""
    found = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    found[(node.name, item.name)] = ast.dump(item)
    return found


class DiffScopePlankTest(unittest.TestCase):

    def test_ac7_other_existing_methods_unchanged(self):
        """Прочие существующие методы `tests/test_suite_run.py` не тронуты.

        Файл на базе `DIFF_BASE` и в рабочей копии разбираются `ast`;
        каждый метод класса базы, кроме
        `GateArgvTest.test_gate_call_argv_unchanged`, обязан остаться под
        тем же классом с тем же деревом (форматирование и номера строк не
        в счёт). Новые методы и классы допустимы.

        Ловит мутацию: разработчик попутно правит соседний метод
        (`PytestCommandTest.test_pytest_executable_and_module_forms` или
        иной) либо переименовывает его — дамп расходится или метод
        пропадает.
        """
        self.assertTrue(DIFF_BASE, "пульт не назвал базу диффа")
        res = subprocess.run(
            ["git", "-C", str(ROOT), "show", f"{DIFF_BASE}:{SUITE_REL}"],
            capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stderr)
        before = _methods(res.stdout)
        after = _methods((ROOT / SUITE_REL).read_text(encoding="utf-8"))
        for key, dump in before.items():
            if key == CHANGED_METHOD:
                continue
            with self.subTest(method=".".join(key)):
                self.assertIn(key, after, "метод исчез")
                self.assertEqual(after[key], dump, "метод изменён")

    def test_ac8_diff_outside_zone_is_empty(self):
        """Дифф ветки вне `tests/test_suite_run.py` и карты кода пуст.

        `changed_paths()` помощника пульта (закоммиченный дифф от базы
        плюс неотслеживаемые файлы вне документов задачи) не содержит путей
        кроме двух разрешённых; в частности `orchestrator/acceptance.py`,
        `orchestrator/stack.py`, `orchestrator/config.py`,
        `tests/sandbox.py`.

        Ловит мутацию: разработчик чинит выбор интерпретатора в
        `orchestrator/stack.py` или подменяет помощник в
        `tests/sandbox.py` — путь появляется в диффе.
        """
        extra = sorted(set(changed_paths()) - ALLOWED)
        self.assertEqual(extra, [], f"правка вне зоны: {extra}")


if __name__ == "__main__":
    unittest.main()
