"""AC-11 (tasks/01M1RDCAFENSW2VVAPECHCVGMM/SPEC.md, требование 5):
`orchestrator/doctor.py::all_checks` подключает `check_stack()` одной
строкой; логика сравнения версий не дублируется в `doctor.py`.

Красен до реализации: сегодняшний `all_checks` (orchestrator/doctor.py)
не зовёт `check_stack` — статический разбор `ast` не найдёт такого вызова
в теле функции.

Разбор — `ast`, без импорта `orchestrator.doctor`: тест не должен зависеть
от того, существует ли уже `orchestrator/stack.py` (импорт `doctor.py`
упал бы, если разработчик добавил `from . import stack`, а `stack.py`
ещё не готов на промежуточном шаге) — тем же приёмом, что
`scripts/guard.py::module_docstring`/`scripts/codebase_map.py`.
"""
import ast
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DOCTOR_PY = REPO_ROOT / "orchestrator" / "doctor.py"


def _find_function(tree: ast.Module, name: str):
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def _calls_check_stack(func: ast.FunctionDef) -> bool:
    for node in ast.walk(func):
        if not isinstance(node, ast.Call):
            continue
        target = node.func
        if isinstance(target, ast.Attribute) and target.attr == "check_stack":
            return True
        if isinstance(target, ast.Name) and target.id == "check_stack":
            return True
    return False


class DoctorHookupTest(unittest.TestCase):

    def test_ac11_all_checks_calls_check_stack_once_without_local_version_logic(self):
        """`all_checks` зовёт `check_stack()` (одна точка подключения,
        требование 5) и сам `doctor.py` не заводит свою копию манифеста
        (`REQUIRED_PYTHON` как отдельная константа `doctor.py` — признак
        того, что сравнение версий продублировано вместо переноса в
        `stack.py`, требование 5/«Не входит»).

        Ловит мутацию: `all_checks` не подключает `check_stack()` вовсе
        (первый `assertTrue` откажет), либо разработчик скопировал
        сравнение версий целиком в `doctor.py`, заведя там свою
        `REQUIRED_PYTHON` вместо импорта из `stack.py` (второй
        `assertNotIn` откажет).
        """
        source = DOCTOR_PY.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(DOCTOR_PY))
        func = _find_function(tree, "all_checks")
        self.assertIsNotNone(func, "orchestrator/doctor.py не содержит "
                                   "функцию all_checks")

        self.assertTrue(
            _calls_check_stack(func),
            "all_checks() не вызывает check_stack() (требование 5)")
        self.assertNotIn(
            "REQUIRED_PYTHON", source,
            "orchestrator/doctor.py заводит свою копию REQUIRED_PYTHON "
            "— манифест обязан жить единственным источником в "
            "orchestrator/stack.py (требование 5)")


if __name__ == "__main__":
    unittest.main()
