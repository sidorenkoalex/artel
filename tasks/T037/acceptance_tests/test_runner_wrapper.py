"""Приёмочные тесты T037 — обёртка cli-вызова агента вместо прямого
мокинга `runner.subprocess.Popen` в тестах (SPEC.md, критерий AC-3).

Статическая AST-проверка исходников `tests/*.py`, а не поведения:
критерий формулируется как отсутствие определённого паттерна мокинга
(«прямого мокинга `runner.subprocess.Popen` в тестах не остаётся»,
требование 2), а не как новое поведение самого раннера — тем же
подходом, что AC-1 tasks/T036 (AST по `fsm.py` вместо grep по тексту,
чтобы не путаться с упоминаниями `subprocess`/`Popen` в докстроках и
комментариях).
"""
import ast
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

TESTS_DIR = REPO_ROOT / "tests"


def _dotted_name(node) -> str | None:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return None


def _runner_popen_mock_lines(source: str, filename: str) -> list:
    """Строки, где тест мокает `runner.subprocess.Popen` напрямую:
    `mock.patch("runner.subprocess.Popen", ...)` (строковая цель) или
    `mock.patch.object(runner.subprocess, "Popen", ...)` (объектная
    цель) — единственные два паттерна мокинга `mock.patch*`, найденные
    в текущем наборе тестов (см. SPEC.md «Контекст»)."""
    tree = ast.parse(source, filename=filename)
    hits = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func_name = _dotted_name(node.func) or ""
        if func_name.endswith("patch") and node.args:
            target = node.args[0]
            if (isinstance(target, ast.Constant)
                    and target.value == "runner.subprocess.Popen"):
                hits.append(node.lineno)
        elif func_name.endswith("patch.object") and len(node.args) >= 2:
            obj_name = _dotted_name(node.args[0])
            attr_arg = node.args[1]
            if (obj_name == "runner.subprocess"
                    and isinstance(attr_arg, ast.Constant)
                    and attr_arg.value == "Popen"):
                hits.append(node.lineno)
    return hits


class NoDirectRunnerPopenMockingRemainsTest(unittest.TestCase):
    """AC-3: тесты, ранее мокавшие `runner.subprocess.Popen` на пути
    вызова агента, мокают заведённую обёртку cli-вызова."""

    def test_ac3_no_test_file_mocks_runner_subprocess_popen_directly(self):
        offenders = {}
        for py_file in sorted(TESTS_DIR.glob("*.py")):
            source = py_file.read_text(encoding="utf-8")
            hits = _runner_popen_mock_lines(source, py_file.name)
            if hits:
                offenders[py_file.name] = hits
        self.assertEqual(
            offenders, {},
            f"остался прямой мокинг runner.subprocess.Popen в тестах "
            f"(файл: строки) — должен быть переведён на мокинг обёртки "
            f"cli-вызова агента (требование 2 SPEC): {offenders}")


if __name__ == "__main__":
    unittest.main()
