"""`orchestrator/store.py`: описание `_AutoClosingConnection` о цикле ссылок, механизм закрытия без `gc`/`weakref` с эталоном-замером; `tests/test_store_db_connection_close.py` не тронут и зелёный (AC-5, AC-6).

Группа: разовый

Красен до реализации: описание `_AutoClosingConnection` утверждает закрытие «при потере последней ссылки» счётчиком ссылок и не называет цикл ссылок, `sys.getrefcount` в `orchestrator/store.py` не зовётся (AC-6); AC-5 зелёный с рождения — файл не тронут и зелёный, тест держит это на всём пути задачи.
"""
import ast
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _util import (CONN_CLOSE_TEST, DIFF_BASE, ROOT, STORE, changed_paths,  # noqa: E402
                   find_class, head_source, parse, run_pytest)

FORBIDDEN = ("при потере последней ссылки", "уничтожает нециклические",
             "по счётчику ссылок немедленно")


def _is_getrefcount(node) -> bool:
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "getrefcount")


class StoreMechanismTest(unittest.TestCase):

    def test_ac5_connection_close_test_untouched_and_green(self):
        """`tests/test_store_db_connection_close.py` не изменён относительно базы диффа и проходит.

        Сценарий: путь не входит в `changed_paths()`, `git diff` от базы
        диффа по нему (включая незакоммиченное) пуст; прогон файла pytest —
        код 0, провалов нет.

        Ловит мутацию: разработчик ослабил ожидание `ResourceWarning` или
        `__del__` в этом файле под новый учёт — путь есть в диффе; либо
        учёт ломает `__del__`/WAL — прогон красный.
        """
        self.assertNotIn(CONN_CLOSE_TEST, changed_paths())
        diff = subprocess.run(["git", "-C", str(ROOT), "diff", DIFF_BASE, "--",
                               CONN_CLOSE_TEST], capture_output=True, text=True)
        self.assertEqual(diff.returncode, 0, diff.stderr)
        self.assertEqual(diff.stdout, "", "файл изменён")
        run = run_pytest([CONN_CLOSE_TEST])
        self.assertEqual(run.code, 0, run.tail())
        self.assertEqual(run.failed(), {}, run.tail())
        self.assertTrue(run.passed(), run.tail())

    def test_ac6_docstring_names_cycle_and_mechanism_measures_baseline(self):
        """Описание `_AutoClosingConnection` называет цикл ссылок; в `store.py` нет `gc`/`weakref`; эталон `sys.getrefcount` — замер, не числовая константа.

        Сценарий: разбор `orchestrator/store.py` головы. Описание класса не
        несёт прежних утверждений о закрытии счётчиком ссылок («при потере
        последней ссылки», «уничтожает нециклические», «по счётчику ссылок
        немедленно») и несёт слово «цикл». Модуль не импортирует и не
        называет `gc` и `weakref`. `getrefcount` зовётся, хотя бы один вызов
        стоит вне сравнения (замер эталона), и ни одно сравнение с
        `getrefcount` не сравнивает с числовым литералом либо с именем
        модуля, присвоенным числу.

        Ловит мутацию: эталон зашит `sys.getrefcount(conn) == 3` (или
        `<= _BASELINE` с `_BASELINE = 3`) — на другой версии CPython число
        внутренних ссылок цикла иное; либо брошенные соединения ищутся
        `gc.get_referrers`/`weakref.finalize`; либо описание оставлено
        прежним.
        """
        source = head_source(STORE)
        tree = parse(source)
        cls = find_class(tree, "_AutoClosingConnection")
        self.assertIsNotNone(cls, "класса _AutoClosingConnection нет")
        doc = ast.get_docstring(cls) or ""
        flat = " ".join(doc.split())
        for phrase in FORBIDDEN:
            self.assertNotIn(phrase, flat, f"описание: «{phrase}»")
        self.assertIn("цикл", flat.lower(), "описание не называет цикл ссылок")

        used = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                used |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                used.add(node.module.split(".")[0])
            elif isinstance(node, ast.Name):
                used.add(node.id)
        self.assertFalse(used & {"gc", "weakref"}, "механизм использует gc/weakref")

        numeric = {}
        for node in tree.body:
            if isinstance(node, (ast.Assign, ast.AnnAssign)) and isinstance(
                    node.value, ast.Constant) and isinstance(node.value.value, (int, float)) \
                    and not isinstance(node.value.value, bool):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                numeric.update({t.id: node.value.value for t in targets
                                if isinstance(t, ast.Name)})

        def is_number(expr) -> bool:
            if isinstance(expr, ast.Constant):
                return isinstance(expr.value, (int, float)) and not isinstance(expr.value, bool)
            if isinstance(expr, ast.Name):
                return expr.id in numeric
            if isinstance(expr, ast.BinOp):
                return is_number(expr.left) and is_number(expr.right)
            if isinstance(expr, ast.UnaryOp):
                return is_number(expr.operand)
            return False

        calls = [n for n in ast.walk(tree) if _is_getrefcount(n)]
        self.assertTrue(calls, "sys.getrefcount в store.py не зовётся")
        in_compare = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                sides = [node.left, *node.comparators]
                for i, side in enumerate(sides):
                    if any(_is_getrefcount(x) for x in ast.walk(side)):
                        in_compare |= {id(x) for x in ast.walk(side)}
                        others = sides[:i] + sides[i + 1:]
                        self.assertFalse(any(is_number(o) for o in others),
                                         f"эталон — числовая константа: "
                                         f"{ast.unparse(node)}")
        self.assertTrue([c for c in calls if id(c) not in in_compare],
                        "нет замера эталона вне сравнения")


if __name__ == "__main__":
    unittest.main()
