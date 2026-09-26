"""AC-2: закрытость затравочного соединения утверждается ДО снимка файлов
— через `sqlite3.ProgrammingError` либо через мёртвую слабую ссылку.

Красен до реализации: тело `CmdModelsTest::test_command_writes_nothing`
не содержит ни одного утверждения между затравкой и снимком файлов
(tests/test_models.py:688-694) — ни `assertRaises(sqlite3.
ProgrammingError)`, ни `weakref`; проверять закрытость пока нечем.
"""
import ast
import unittest

import _target

# Имя исключения, которым sqlite3 отвечает на работу с закрытым
# соединением, и модуль слабых ссылок — два приёма, названные критерием.
PROGRAMMING_ERROR = "ProgrammingError"
WEAKREF_MODULE = "weakref"


def _weakref_names(function: ast.FunctionDef) -> set[str]:
    """Локальные имена, которым присвоен результат `weakref.ref(...)`.

    Утверждение о смерти слабой ссылки говорит не о модуле `weakref`, а
    об этом имени (`self.assertIsNone(wref())`), поэтому связать
    утверждение с приёмом можно только через имя.
    """
    names: set[str] = set()
    for node in ast.walk(function):
        if not isinstance(node, ast.Assign):
            continue
        if not isinstance(node.value, ast.Call):
            continue
        func = node.value.func
        attribute = isinstance(func, ast.Attribute)
        attr = func.attr if attribute else getattr(func, "id", "")
        base = getattr(func.value, "id", "") if attribute else ""
        if attr != "ref" or base not in ("", WEAKREF_MODULE):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                names.add(target.id)
    return names


class Ac2ClosednessAssertionTest(unittest.TestCase):
    """AC-2: прямое утверждение о закрытости до снимка файлов."""

    def test_ac2_closedness_is_asserted_before_the_file_snapshot(self):
        """Между затравкой и первым `iterdir()` стоит утверждение именно о
        закрытости соединения: либо обращение к нему поднимает
        `sqlite3.ProgrammingError`, либо мёртвая слабая ссылка на него.

        Ловит мутацию: разработчик заменил `del conn` на явный `close()`,
        но прямой проверки закрытости не оставил (или сдвинул её ПОСЛЕ
        снимка файлов) — планка мутации из требования 2 исчезает, и
        возврат к `del conn` снова будет виден только как редкое падение
        на Linux, а не как красный тест.
        """
        function = _target.method_ast()
        snapshot = _target.first_snapshot_line()
        self.assertIsNotNone(
            snapshot,
            f"{_target.TARGET_NAME}: в теле нет ни одного вызова "
            f"`iterdir()` — границы «до снимка файлов» из AC-2 в теле не "
            f"стало, снимок списка файлов обязан остаться на месте")

        before = _target.nodes_before(snapshot)
        assertions = _target.assertion_calls(before)
        self.assertTrue(
            assertions,
            f"{_target.TARGET_NAME}: до первого `iterdir()` (строка "
            f"{_target.absolute(snapshot)}) нет ни одного утверждения — "
            f"AC-2 требует прямой проверки закрытости затравочного "
            f"соединения именно до снимка файлов")

        weakrefs = _weakref_names(function)
        by_exception = [call for call in assertions
                        if PROGRAMMING_ERROR in _target.names_in(call)]
        by_weakref = [call for call in assertions
                      if _target.names_in(call) & weakrefs]
        self.assertTrue(
            by_exception or by_weakref,
            f"{_target.TARGET_NAME}: утверждения до снимка файлов "
            f"({len(assertions)} шт.) не говорят о закрытости соединения — "
            f"ни одно из них не ссылается ни на `sqlite3."
            f"{PROGRAMMING_ERROR}`, ни на слабую ссылку из `{WEAKREF_MODULE}."
            f"ref(...)` (найденные слабые ссылки: {sorted(weakrefs)})")
