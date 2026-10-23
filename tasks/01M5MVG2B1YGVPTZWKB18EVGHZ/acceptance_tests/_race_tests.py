"""Общий код AC-1 и AC-7: исходники двух тестовых файлов на базе диффа
задачи и в рабочей копии, поиск утверждения о строках прогона в тестах
гонки SIGTERM."""
import ast
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, DIFF_BASE  # noqa: E402

PROTECTION = "tests/test_canary_parallel_protection.py"
PARALLEL = "tests/test_canary_parallel.py"
# (файл, класс, метод, выражение вывода в сообщении)
RACE_TESTS = (
    (PROTECTION, "BaselineTest",
     "test_parent_sigterm_leaves_canary_baseline_unchanged", "run.out"),
    (PARALLEL, "StopTest",
     "test_parent_sigterm_stops_children_and_skips_queue", "out"),
)
HELPERS = {PROTECTION: ("_ProtectionSandbox", ("run_cli", "read_grandchild_pid"))}
ROW_LITERALS = [("alfa", "оборвана сигналом SIGTERM"),
                ("beta", "оборвана сигналом SIGTERM")]


def base_source(path: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(CODE_ROOT), "show", f"{DIFF_BASE}:{path}"],
        capture_output=True, text=True, check=False)
    if done.returncode != 0:
        raise AssertionError(f"git show {DIFF_BASE}:{path}: {done.stderr}")
    return done.stdout


def head_source(path: str) -> str:
    return (Path(CODE_ROOT) / path).read_text(encoding="utf-8")


def method(tree: ast.Module, cls: str, name: str) -> ast.FunctionDef:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == cls:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == name:
                    return item
    raise AssertionError(f"нет метода {cls}.{name}")


def _literal(node):
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError, TypeError):
        return None


def row_assertions(func: ast.FunctionDef) -> list:
    """Вызовы `self.assertEqual(sorted(...), [("alfa", …), ("beta", …)])`."""
    found = []
    for node in ast.walk(func):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "assertEqual" and len(node.args) >= 2
                and isinstance(node.args[0], ast.Call)
                and isinstance(node.args[0].func, ast.Name)
                and node.args[0].func.id == "sorted"
                and _literal(node.args[1]) == ROW_LITERALS):
            found.append(node)
    return found


def message_of(call: ast.Call):
    if len(call.args) >= 3:
        return call.args[2]
    for keyword in call.keywords:
        if keyword.arg == "msg":
            return keyword.value
    return None


def is_assertion(node) -> bool:
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr.startswith("assert")) or isinstance(node, ast.Assert)
