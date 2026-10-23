"""Границы правки двух тестовых файлов гонки (AC-7): изменены только
сообщения утверждений двух тестов гонки и помощники `run_cli` /
`read_grandchild_pid`; ни одно утверждение не удалено, не заменено, не
ослаблено.

Группа: разовый
Зелёный с рождения: до правок рабочая копия обоих файлов равна базе диффа — нарушений границы нет; тест краснеет только от правки вне разрешённого.

Разовый: сверка исходника тестовых файлов рабочей копии с базой диффа
задачи (`DIFF_BASE` помощника пульта) — после мержа сверять не с чем.
Сравнение — по AST (`ast.dump` без позиций): комментарии и переносы строк
не в счёт, докстринги и код — в счёт.
"""
import ast
import sys
import unittest
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _race_tests import (HELPERS, PARALLEL, PROTECTION,  # noqa: E402
                         RACE_TESTS, base_source, head_source, is_assertion,
                         method, row_assertions)


def _normalized(tree: ast.Module, path: str) -> ast.Module:
    """Дерево без разрешённых правок: сообщение утверждения о строках
    прогона снято, тела помощников заменены на `pass`."""
    for race_path, cls, name, _output in RACE_TESTS:
        if race_path != path:
            continue
        for call in row_assertions(method(tree, cls, name)):
            call.args = call.args[:2]
            call.keywords = [k for k in call.keywords if k.arg != "msg"]
    if path in HELPERS:
        cls, names = HELPERS[path]
        for name in names:
            method(tree, cls, name).body = [ast.Pass()]
    return tree


def _parts(tree: ast.Module) -> dict:
    """Имя верхнего узла (класса — с методами) → дамп, для текста провала."""
    parts = {}
    for index, node in enumerate(tree.body):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                key = (f"{node.name}.{item.name}" if hasattr(item, "name")
                       else f"{node.name}[{ast.dump(item)[:40]}]")
                parts[key] = ast.dump(item)
            parts[node.name] = ast.dump(ast.ClassDef(
                name=node.name, bases=node.bases, keywords=node.keywords,
                body=[], decorator_list=node.decorator_list))
        else:
            parts[getattr(node, "name", f"#{index}:{type(node).__name__}")] = \
                ast.dump(node)
    return parts


class RaceFilesScopeTest(unittest.TestCase):
    def test_ac7_only_messages_and_two_helpers_changed(self):
        """Вне двух сообщений и двух помощников файлы равны базе; утверждения целы.

        Сценарий: для `tests/test_canary_parallel_protection.py` и
        `tests/test_canary_parallel.py` деревья базы диффа и рабочей копии
        нормализуются одинаково — у утверждения о строках прогона двух
        тестов гонки снято сообщение, тела `_ProtectionSandbox.run_cli` и
        `_ProtectionSandbox.read_grandchild_pid` заменены на `pass` — и
        обязаны совпасть целиком. Каждое утверждение (`self.assert*`,
        `assert`) базы в этих помощниках есть и в рабочей копии того же
        помощника.

        Ловит мутацию: заодно поправлен прочий тестовый метод (например,
        `SigintTest.test_parent_sigint_stops_children_with_exit_130`, вне
        мандата) или утверждение теста гонки (`assertEqual` → `assertIn`,
        снятое `assertNotIn(… завершён …)`); либо в `run_cli` удалено
        `self.assertEqual(errors, [], run.out)`.
        """
        for path in (PROTECTION, PARALLEL):
            with self.subTest(path=path):
                base = _normalized(ast.parse(base_source(path)), path)
                head = _normalized(ast.parse(head_source(path)), path)
                base_parts, head_parts = _parts(base), _parts(head)
                changed = sorted(key for key in base_parts.keys() | head_parts.keys()
                                 if base_parts.get(key) != head_parts.get(key))
                self.assertEqual(changed, [],
                                 f"{path}: изменено вне разрешённого")
                self.assertEqual(ast.dump(head), ast.dump(base),
                                 f"{path}: порядок или состав узлов изменён")

        cls, names = HELPERS[PROTECTION]
        base_tree = ast.parse(base_source(PROTECTION))
        head_tree = ast.parse(head_source(PROTECTION))
        for name in names:
            with self.subTest(helper=name):
                kept = Counter(ast.dump(n) for n in ast.walk(
                    method(head_tree, cls, name)) if is_assertion(n))
                lost = Counter(ast.dump(n) for n in ast.walk(
                    method(base_tree, cls, name)) if is_assertion(n)) - kept
                self.assertEqual(list(lost), [],
                                 f"{cls}.{name}: утверждения базы пропали")
