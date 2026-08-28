"""Приёмочные тесты T061 — AC-2 (SPEC.md, «Критерии приёмки»):
claude-only side_effect существует единственной парой хелперов в
`tests/sandbox.py` (для `subprocess.run` и для `subprocess.Popen`);
локальные копии в `tests/*.py` удалены.

Имена хелперов — `claude_only_run`/`claude_only_popen` — не выдумка
этого файла: это уже существующие имена в `tests/test_doctor.py`
(SPEC.md, «Контекст», требование 2 прямо называет их как то, что
«заменяется на импорт» из `tests/sandbox.py`), тот же контракт
переносится без изменений (SPEC требование 5 — поведение не меняется).
"""
import ast
import importlib
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

TESTS_DIR = REPO_ROOT / "tests"
SANDBOX_PATH = TESTS_DIR / "sandbox.py"

HELPER_NAMES = ("claude_only_run", "claude_only_popen")


def _own_function_definitions(py_file: Path, names) -> set:
    """Имена из `names`, определённые НЕПОСРЕДСТВЕННО в файле как
    def верхнего уровня/вложенная — не импортированные."""
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in names:
                found.add(node.name)
    return found


def _inline_claude_only_side_effect_closures(py_file: Path) -> int:
    """Число вложенных `def side_effect(...)`, которые внутри себя
    проверяют строку "claude" — сигнатура двух инлайн-closure
    `tests/test_git_fixation.py`, которые SPEC (требование 2) просит
    заменить на импорт `sandbox.claude_only_popen`."""
    tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "side_effect":
            for sub in ast.walk(node):
                if isinstance(sub, ast.Constant) and sub.value == "claude":
                    count += 1
                    break
    return count


class SandboxDefinesClaudeOnlyHelperPairTest(unittest.TestCase):
    """AC-2: единственная пара хелперов в `tests/sandbox.py`."""

    def test_ac2_sandbox_exports_both_helpers(self):
        sandbox = importlib.import_module("tests.sandbox")
        for name in HELPER_NAMES:
            self.assertTrue(hasattr(sandbox, name),
                            f"tests/sandbox.py не определяет {name}")
            self.assertTrue(callable(getattr(sandbox, name)),
                            f"tests.sandbox.{name} не является вызываемым")

    def test_ac2_claude_only_run_intercepts_only_claude(self):
        sandbox = importlib.import_module("tests.sandbox")

        side_effect = sandbox.claude_only_run("готово\n", 0)

        claude_result = side_effect(["claude", "-p", "x"])
        self.assertEqual(claude_result.returncode, 0)
        self.assertEqual(claude_result.stdout, "готово\n")

        # Не-claude вызов того же общего subprocess.run уходит в
        # настоящий вызов, не в заглушку.
        real_result = side_effect([sys.executable, "-c", "print('настоящий')"],
                                  capture_output=True, text=True)
        self.assertEqual(real_result.returncode, 0)
        self.assertIn("настоящий", real_result.stdout)

    def test_ac2_claude_only_popen_intercepts_only_claude(self):
        sandbox = importlib.import_module("tests.sandbox")
        fake_proc = object()

        side_effect = sandbox.claude_only_popen(fake_proc)

        self.assertIs(side_effect(["claude", "-p", "x"]), fake_proc)

        real_proc = side_effect([sys.executable, "-c", "print('настоящий')"],
                                stdout=subprocess.PIPE, text=True)
        try:
            out, _ = real_proc.communicate()
            self.assertIn("настоящий", out)
        finally:
            real_proc.wait()


class NoLocalClaudeOnlyHelperCopiesTest(unittest.TestCase):
    """AC-2: локальные копии хелперов в `tests/*.py` удалены."""

    def test_ac2_no_test_file_still_defines_the_helpers_locally(self):
        offenders = {}
        for py_file in sorted(TESTS_DIR.glob("*.py")):
            if py_file.name in ("sandbox.py", "__init__.py"):
                continue
            found = _own_function_definitions(py_file, HELPER_NAMES)
            if found:
                offenders[py_file.name] = sorted(found)

        self.assertEqual(
            offenders, {},
            f"локальные определения {HELPER_NAMES} остались вместо "
            f"импорта из tests.sandbox: {offenders}")

    def test_ac2_git_fixation_no_longer_has_inline_claude_side_effect(self):
        target = TESTS_DIR / "test_git_fixation.py"
        self.assertTrue(target.is_file(), "tests/test_git_fixation.py не найден")

        count = _inline_claude_only_side_effect_closures(target)

        self.assertEqual(
            count, 0,
            "tests/test_git_fixation.py всё ещё содержит собственный "
            "инлайн side_effect с проверкой claude вместо импорта "
            "sandbox.claude_only_popen")


if __name__ == "__main__":
    unittest.main()
