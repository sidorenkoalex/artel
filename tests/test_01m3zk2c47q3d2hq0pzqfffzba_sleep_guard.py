"""Сторож подмены общей паузы в тестах.

Группа: долгоживущий
Красен до реализации: существующие тесты ещё патчат общий модуль time.
"""

import ast
import unittest
from pathlib import Path


class GlobalSleepPatchGuard(unittest.TestCase):
    """Паузы пульта подменяются на стороне пульта, не всего процесса."""

    def test_ac3_new_global_sleep_patch_is_rejected(self):
        """Все тестовые модули просматриваются на подмену общего sleep.

        Исключение системных инвариантов сохраняет проверку, для которой
        нужны общие поддельные часы и пауза; другие тесты изолируют паузу
        своего модуля. Новая подмена в любом из них красит сторож.

        Ловит мутацию: подмена time.sleep всего процесса в тесте
        """
        exceptions = {
            "test_invariants.py": (
                "тест системного инварианта совместно подменяет sleep и "
                "monotonic для моделирования часов процесса"
            ),
        }
        root = Path(__file__).resolve().parent
        violations = []
        for path in sorted(root.glob("test_*.py")):
            if path.name in exceptions:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            time_names = {"time"}
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    time_names.update(alias.asname or alias.name
                                      for alias in node.names if alias.name == "time")

            def is_time_module(node):
                return ((isinstance(node, ast.Name) and node.id in time_names)
                        or (isinstance(node, ast.Attribute)
                            and node.attr == "time"))

            for node in ast.walk(tree):
                if isinstance(node, (ast.Tuple, ast.List)):
                    items = node.elts
                    if (items and isinstance(items[0], ast.Constant)
                            and items[0].value == "time.sleep"):
                        violations.append(f"{path.name}:{node.lineno}")
                    if any(is_time_module(arg)
                           and isinstance(next_arg, ast.Constant)
                           and next_arg.value == "sleep"
                           for arg, next_arg in zip(items, items[1:])):
                        violations.append(f"{path.name}:{node.lineno}")
                if isinstance(node, ast.Call):
                    func = node.func
                    call_name = (func.attr if isinstance(func, ast.Attribute)
                                 else func.id if isinstance(func, ast.Name) else "")
                    is_patch = (call_name in {"patch", "patch_object", "setattr", "multiple"}
                                or (call_name == "object"
                                    and isinstance(func, ast.Attribute)
                                    and isinstance(func.value, ast.Attribute)
                                    and func.value.attr == "patch"))
                    if not is_patch:
                        continue
                    args = node.args
                    string_target = any(
                        isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                        and (arg.value == "time.sleep"
                             or arg.value.endswith(".time.sleep"))
                        for arg in args)
                    object_target = any(
                        is_time_module(arg) and next_arg.value == "sleep"
                        for arg, next_arg in zip(args, args[1:])
                        if isinstance(next_arg, ast.Constant)
                        and isinstance(next_arg.value, str))
                    keyword_target = (any(is_time_module(arg) for arg in args)
                                      and any(kw.arg == "sleep" for kw in node.keywords))
                    if string_target or object_target or keyword_target:
                        violations.append(f"{path.name}:{node.lineno}")
                elif isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    if any(isinstance(target, ast.Attribute)
                           and target.attr == "sleep" and is_time_module(target.value)
                           for target in targets):
                        violations.append(f"{path.name}:{node.lineno}")
        self.assertEqual(violations, [], "глобальная подмена time.sleep: "
                         + ", ".join(violations))


if __name__ == "__main__":
    unittest.main()
