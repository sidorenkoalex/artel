"""Проверки миграции пауз в названных модулях и их тестах.

Группа: разовый
Красен до реализации: в названных модулях нет локальных _pause, а тесты
ещё подменяют общий time.sleep.
"""

import ast
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from orchestrator import config, gitcmd  # noqa: E402


MODULES = (
    "orchestrator/runner.py", "orchestrator/auto.py",
    "orchestrator/acceptance.py", "orchestrator/fsm_merge_gate.py",
    "orchestrator/merge_queue.py", "orchestrator/liveness.py",
    "orchestrator/pause.py", "orchestrator/watch.py",
    "orchestrator/doctor/leases.py",
)


def base_source(base, path):
    source, error = gitcmd.show(base, path)
    if source is None:
        raise AssertionError(f"нет базового {path}: {error}")
    return source


def is_sleep_call(node):
    return (isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "sleep"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "time")


def global_patch_scopes(source):
    """Методы с прежней подменой общей паузы."""
    tree = ast.parse(source)
    found = set()
    for name, parent in named_functions(tree).items():
        for node in ast.walk(parent):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                    and (node.value == "time.sleep"
                         or node.value.endswith(".time.sleep")):
                found.add(name)
            if isinstance(node, (ast.Call, ast.Tuple, ast.List)):
                args = node.args if isinstance(node, ast.Call) else node.elts
                if any(isinstance(a, (ast.Attribute, ast.Name))
                       and ((isinstance(a, ast.Attribute) and a.attr == "time")
                            or (isinstance(a, ast.Name) and a.id == "time"))
                       and isinstance(b, ast.Constant) and b.value == "sleep"
                       for a, b in zip(args, args[1:])):
                    found.add(name)
            if not isinstance(node, ast.Call):
                continue
            args = node.args
            string_patch = any(
                isinstance(a, ast.Constant) and isinstance(a.value, str)
                and (a.value == "time.sleep" or a.value.endswith(".time.sleep"))
                for a in args)
            object_patch = any(
                isinstance(a, ast.Attribute) and a.attr == "time"
                and isinstance(b, ast.Constant) and b.value == "sleep"
                for a, b in zip(args, args[1:]))
            direct_patch = any(
                isinstance(a, ast.Name) and a.id == "time"
                and isinstance(b, ast.Constant) and b.value == "sleep"
                for a, b in zip(args, args[1:]))
            if string_patch or object_patch or direct_patch:
                found.add(name)
    return found


def named_functions(tree):
    """Методы с именем класса, чтобы одинаковые setUp не затирали друг друга."""
    result = {}
    for top in tree.body:
        if isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef)):
            result[top.name] = top
        elif isinstance(top, ast.ClassDef):
            for node in top.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    result[f"{top.name}.{node.name}"] = node
    return result


class PauseMigrationTest(unittest.TestCase):
    """Факты миграции сверяются с точкой расхождения ветки."""

    @classmethod
    def setUpClass(cls):
        branch = gitcmd.current_branch()
        cls.base = gitcmd.diff_base(branch)
        if cls.base is None:
            raise AssertionError(f"не удалось определить базу {branch}")

    def test_ac1_all_pause_sites_keep_arguments_and_control_flow(self):
        """Каждая исходная пауза идёт через локальную обёртку.

        Для девяти модулей список пауз каждой прежней функции
        сравнивается с её новыми вызовами _pause: аргументы и порядок
        вызовов остаются теми же. Сама
        обёртка ровно передаёт полученный аргумент time.sleep.

        Ловит мутацию: в runner оставлен прямой time.sleep либо у _pause
        изменён аргумент — сравнение AST показывает лишний прямой вызов
        или отличающееся тело обёртки.
        """
        for path in MODULES:
            with self.subTest(path=path):
                before = ast.parse(base_source(self.base, path))
                after = ast.parse((config.ROOT / path).read_text(encoding="utf-8"))
                old_pauses = [n for n in ast.walk(before) if is_sleep_call(n)]
                self.assertTrue(old_pauses, f"в базе {path} нет пауз")
                wrappers = [n for n in after.body
                            if isinstance(n, ast.FunctionDef) and n.name == "_pause"]
                self.assertEqual(len(wrappers), 1, path)
                wrapper = wrappers[0]
                self.assertEqual([a.arg for a in wrapper.args.args], ["seconds"], path)
                self.assertEqual(wrapper.args.posonlyargs + wrapper.args.kwonlyargs,
                                 [], path)
                self.assertIsNone(wrapper.args.vararg, path)
                self.assertIsNone(wrapper.args.kwarg, path)
                body = wrapper.body[1:] if (wrapper.body
                    and isinstance(wrapper.body[0], ast.Expr)
                    and isinstance(wrapper.body[0].value, ast.Constant)
                    and isinstance(wrapper.body[0].value.value, str)) else wrapper.body
                self.assertEqual(len(body), 1, path)
                call = body[0].value if isinstance(body[0], (ast.Expr, ast.Return)) else None
                self.assertTrue(is_sleep_call(call), path)
                self.assertEqual(len(call.args), 1, path)
                self.assertEqual(ast.dump(call.args[0]),
                                 ast.dump(ast.Name(id="seconds", ctx=ast.Load())), path)
                self.assertEqual(call.keywords, [], path)
                direct = [n for n in ast.walk(after) if is_sleep_call(n)]
                self.assertEqual(len(direct), 1, path)
                self.assertIs(direct[0], call)

                old_functions = {n.name: n for n in before.body
                                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                                 and any(is_sleep_call(c) for c in ast.walk(n))}
                new_functions = {n.name: n for n in after.body
                                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
                expected_total = 0
                for name, old in old_functions.items():
                    self.assertIn(name, new_functions, path)
                    old_calls = sorted((c for c in ast.walk(old) if is_sleep_call(c)),
                                       key=lambda c: (c.lineno, c.col_offset))
                    new_calls = sorted((c for c in ast.walk(new_functions[name])
                                        if isinstance(c, ast.Call)
                                        and isinstance(c.func, ast.Name)
                                        and c.func.id == "_pause"),
                                       key=lambda c: (c.lineno, c.col_offset))
                    expected_total += len(old_calls)
                    self.assertEqual([[ast.dump(arg) for arg in c.args] for c in new_calls],
                                     [[ast.dump(arg) for arg in c.args] for c in old_calls],
                                     f"{path}:{name}: длительности или порядок пауз изменены")
                    self.assertTrue(all(not c.keywords for c in new_calls), path)
                actual_total = sum(isinstance(c, ast.Call)
                                   and isinstance(c.func, ast.Name)
                                   and c.func.id == "_pause"
                                   for c in ast.walk(after))
                self.assertEqual(actual_total, expected_total, path)

    def test_ac2_migrated_tests_patch_local_pause_and_keep_assertions(self):
        """Прежние подмены заменены в тех же тестовых сценариях.

        У каждого метода, подменявшего общий sleep на базе ветки,
        теперь есть подмена _pause; исходные утверждения в затронутых
        файлах остаются на месте, а общей подмены больше нет.

        Ловит мутацию: перенос патча runner.time.sleep на runner._pause
        пропущен в одном setUp — имя _pause отсутствует в его AST.
        """
        test_root = config.ROOT / "tests"
        migrated = 0
        for path in sorted(test_root.glob("test_*.py")):
            rel = path.relative_to(config.ROOT).as_posix()
            old_source, _ = gitcmd.show(self.base, rel)
            if old_source is None:
                continue
            old_scopes = global_patch_scopes(old_source)
            if not old_scopes or path.name == "test_invariants.py":
                continue
            migrated += len(old_scopes)
            new_source = path.read_text(encoding="utf-8")
            self.assertEqual(global_patch_scopes(new_source), set(), rel)
            old_tree, new_tree = ast.parse(old_source), ast.parse(new_source)
            new_scopes = named_functions(new_tree)
            for name in old_scopes:
                self.assertIn(name, new_scopes, rel)
                pause_targets = [n for n in ast.walk(new_scopes[name])
                                 if (isinstance(n, ast.Constant)
                                     and isinstance(n.value, str)
                                     and (n.value == "_pause"
                                          or n.value.endswith("._pause")))
                                 or (isinstance(n, ast.Attribute) and n.attr == "_pause")]
                self.assertTrue(pause_targets, f"{rel}:{name}: нет локальной подмены")
            def assertions(tree):
                return [ast.dump(n, include_attributes=False) for n in ast.walk(tree)
                        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                        and n.func.attr.startswith("assert")]
            self.assertEqual(assertions(new_tree), assertions(old_tree),
                             f"{rel}: существующие утверждения изменены")
        self.assertGreater(migrated, 0, "в базе не обнаружены подмены для миграции")


if __name__ == "__main__":
    unittest.main()
