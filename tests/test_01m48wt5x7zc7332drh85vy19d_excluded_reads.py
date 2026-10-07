"""Сторож чтения путей, исключённых из ключа базы.

Группа: долгоживущий
Зелёный с рождения: существующие тесты не читают содержимое исключённых путей настоящего репозитория.
"""

import ast
import random
import unittest
from pathlib import Path


class ExcludedReadsTest(unittest.TestCase):
    def test_ac17_real_repo_exclusions_are_unread_and_guard_detects_new_reader(self):
        """Сторож принимает нынешний набор и находит чтение каждого исключённого пути в новом файле.

        Ловит мутацию: сканирование пропускает новый вызов read_text от корня настоящего репозитория — опасный тест остаётся зелёным.
        """
        seed = random.randrange(2**32)
        print(f"зерно: {seed}")
        excluded = (("tasks", "example", "SPEC.md"),
                    ("docs", "retro", "example.md"),
                    ("docs", "backlog.md"))
        rng = random.Random(seed)
        order = list(excluded)
        rng.shuffle(order)
        sources = [(str(path), path.read_text(encoding="utf-8"))
                   for path in Path(__file__).parent.rglob("*.py")]
        synthetic = []
        for parts in order:
            expr = "REPO_ROOT" + "".join(f" / {part!r}" for part in parts)
            synthetic.append(("synthetic", f"({expr}).read_text()"))
            synthetic.append(("synthetic_alias", f"candidate = {expr}\ncandidate.read_text()"))
            config_expr = "config.ROOT" + "".join(f" / {part!r}" for part in parts)
            synthetic.append(("synthetic_config", f"({config_expr}).read_text()"))
            file_expr = "Path(__file__).resolve().parents[1]" + "".join(
                f" / {part!r}" for part in parts)
            synthetic.append(("synthetic_file", f"({file_expr}).read_text()"))

        for label, cases, expected in (("suite", sources, 0),
                                       ("synthetic", synthetic, 4 * len(excluded))):
            found = []
            for name, source in cases:
                tree = ast.parse(source, filename=name)
                bindings = {}
                for node in ast.walk(tree):
                    if isinstance(node, ast.Assign):
                        for target in node.targets:
                            if isinstance(target, ast.Name):
                                bindings[target.id] = node.value

                def components(expr, seen=frozenset()):
                    if (isinstance(expr, ast.Attribute) and expr.attr == "ROOT" and
                            isinstance(expr.value, ast.Name) and expr.value.id == "config"):
                        return ()
                    if isinstance(expr, ast.Name):
                        if expr.id in {"REPO_ROOT", "_REPO_ROOT"}:
                            return ()
                        if expr.id in bindings and expr.id not in seen:
                            return components(bindings[expr.id], seen | {expr.id})
                    if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Div):
                        head = components(expr.left, seen)
                        if head is not None and isinstance(expr.right, ast.Constant) and isinstance(expr.right.value, str):
                            return (*head, expr.right.value)
                    if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute) and expr.func.attr in {"resolve", "absolute"}:
                        return components(expr.func.value, seen)
                    rendered = ast.unparse(expr)
                    if rendered.startswith("Path(__file__).resolve().parent.parent") or rendered.startswith("Path(__file__).resolve().parents[1]"):
                        return ()
                    return None

                for node in ast.walk(tree):
                    if not isinstance(node, ast.Call):
                        continue
                    if isinstance(node.func, ast.Attribute):
                        if node.func.attr not in {"read_text", "read_bytes", "open",
                                                  "iterdir", "glob", "rglob",
                                                  "copy", "copy2", "copyfile", "copytree"}:
                            continue
                        target = (node.args[0] if node.func.attr.startswith("copy") and node.args
                                  else node.func.value)
                    elif isinstance(node.func, ast.Name) and node.func.id == "open" and node.args:
                        target = node.args[0]
                    else:
                        continue
                    parts = components(target)
                    forbidden = parts is not None and (
                        parts[:1] == ("tasks",) or
                        parts[:2] == ("docs", "retro") or
                        parts[:2] == ("docs", "backlog.md"))
                    if forbidden:
                        found.append(f"{name}:{node.lineno}: {ast.unparse(target)}")
            self.assertEqual(len(found), expected,
                             f"зерно {seed}, {label}: {found}")
