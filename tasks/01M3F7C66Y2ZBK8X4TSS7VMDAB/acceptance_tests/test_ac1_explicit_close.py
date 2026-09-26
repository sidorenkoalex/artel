"""AC-1: затравочное соединение теста закрывается явным приёмом до
первого `iterdir()`, а `del` не стоит вместо закрытия.

Красен до реализации: в теле `CmdModelsTest::test_command_writes_nothing`
закрытия нет вовсе — соединение отпускается строкой `del conn`
(tests/test_models.py:692), ни `close()`, ни `contextlib.closing` в теле
не вызываются.
"""
import ast
import unittest

import _target


def _close_moments(function: ast.FunctionDef) -> dict[str, int]:
    """Относительные строки, на которых соединение ЗАКРЫТО явным приёмом.

    Ключ — приём, значение — строка, к которой закрытие уже случилось:
    для прямого вызова `conn.close()` это строка самого вызова (годится и
    для `try/finally`, и для `with conn:` рядом с `close()`), для
    `with contextlib.closing(...)` — строка КОНЦА блока, потому что
    именно на выходе из него `closing` зовёт `close()`.
    """
    moments: dict[str, int] = {}
    for node in ast.walk(function):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "close"):
            moments[f"вызов close() на строке {node.lineno}"] = node.lineno
        if isinstance(node, ast.With):
            for item in node.items:
                expr = item.context_expr
                if not isinstance(expr, ast.Call):
                    continue
                func = expr.func
                name = (func.attr if isinstance(func, ast.Attribute)
                        else getattr(func, "id", ""))
                if name == "closing":
                    moments[f"выход из closing() на строке "
                            f"{node.end_lineno}"] = node.end_lineno
    return moments


class Ac1ExplicitCloseTest(unittest.TestCase):
    """AC-1: явное закрытие затравки вместо `del conn`."""

    def test_ac1_seed_connection_is_closed_explicitly_before_snapshot(self):
        """Тело теста закрывает затравочное соединение явным приёмом
        (`close()` или `contextlib.closing`) раньше первого `iterdir()`, и
        ни один `del` не стоит раньше этого закрытия.

        Ловит мутацию: разработчик оставил закрытие на `del conn` и
        `__del__` (или перенёс его в `addCleanup`, то есть на teardown) —
        момент закрытия снова зависит от циклической сборки мусора, и
        снимок «до» опять делается при живом соединении, ради чего задача
        и заведена.
        """
        function = _target.method_ast()
        snapshot = _target.first_snapshot_line()
        self.assertIsNotNone(
            snapshot,
            f"{_target.TARGET_NAME}: в теле нет ни одного вызова "
            f"`iterdir()` — критерий AC-1 говорит «до первого `iterdir()` "
            f"снимка», значит снимок списка файлов обязан остаться на месте")

        moments = _close_moments(function)
        self.assertTrue(
            moments,
            f"{_target.TARGET_NAME}: в теле метода нет явного закрытия "
            f"затравочного соединения — AC-1 требует `contextlib.closing` / "
            f"`try-finally` / `with` (видимых в теле самого теста), а не "
            f"`del conn` и не `self.addCleanup(conn.close)`")

        earliest = min(moments.values())
        self.assertLess(
            earliest, snapshot,
            f"{_target.TARGET_NAME}: явное закрытие ({sorted(moments)}) "
            f"стоит не раньше первого `iterdir()` (строка "
            f"{_target.absolute(snapshot)}) — снимок списка файлов снова "
            f"делается при живом соединении")

        deletes = [node.lineno for node in ast.walk(function)
                   if isinstance(node, ast.Delete)]
        for line in deletes:
            self.assertGreater(
                line, earliest,
                f"{_target.TARGET_NAME}: `del` на строке "
                f"{_target.absolute(line)} стоит раньше явного закрытия "
                f"(строка {_target.absolute(earliest)}) — значит соединение "
                f"по-прежнему отпускается удалением ссылки, а не закрывается")
