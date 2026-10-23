"""Тесты гонки SIGTERM несут вывод сообщением утверждения о строках прогона
(AC-1).

Группа: разовый
Красен до реализации: на базе утверждение `assertEqual(sorted((r["title"], r["outcome"]) …), [...])` в обоих тестах гонки идёт без сообщения — вывода родителя и дочерних в провале нет.

Разовый: сверка исходника тестовых файлов рабочей копии с базой диффа
задачи (`DIFF_BASE` помощника пульта) — после мержа сверять не с чем.
"""
import ast
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _race_tests import (RACE_TESTS, base_source, head_source,  # noqa: E402
                         message_of, method, row_assertions)


def _mentions(node: ast.AST, expression: str) -> bool:
    target = ast.dump(ast.parse(expression, mode="eval").body)
    return any(ast.dump(sub) == target for sub in ast.walk(node))


class RaceAssertionMessageTest(unittest.TestCase):
    def test_ac1_row_assertion_carries_output_and_keeps_literals(self):
        """Утверждение о строках прогона: сообщение — вывод, само утверждение — с базы.

        Сценарий: для `BaselineTest.test_parent_sigterm_leaves_canary_baseline_unchanged`
        (`tests/test_canary_parallel_protection.py`) и
        `StopTest.test_parent_sigterm_stops_children_and_skips_queue`
        (`tests/test_canary_parallel.py`) в рабочей копии и на базе диффа
        ищется `self.assertEqual(sorted(...), [("alfa", "оборвана сигналом
        SIGTERM"), ("beta", "оборвана сигналом SIGTERM")])` — ровно одно в
        каждом методе. Первые два аргумента совпадают с базой дословно (по
        AST), у вызова рабочей копии есть сообщение (третий аргумент или
        `msg=`), и в нём встречается `run.out` (BaselineTest) / `out`
        (StopTest).

        Ловит мутацию: сообщение не добавлено (утверждение как на базе);
        либо сообщением идёт не вывод (например, `self.rows()`); либо
        литерал ожидания изменён/ослаблен (`assertIn` вместо
        `assertEqual`, другой текст строки) — вызов не найден или его
        аргументы расходятся с базой.
        """
        for path, cls, name, output in RACE_TESTS:
            with self.subTest(test=f"{cls}.{name}"):
                base = row_assertions(method(ast.parse(base_source(path)),
                                             cls, name))
                head = row_assertions(method(ast.parse(head_source(path)),
                                             cls, name))
                self.assertEqual(len(base), 1, f"база: {path}")
                self.assertEqual(len(head), 1,
                                 f"{path}: утверждение о строках прогона с "
                                 f"литералами базы не найдено или не одно")
                self.assertEqual([ast.dump(a) for a in head[0].args[:2]],
                                 [ast.dump(a) for a in base[0].args[:2]])
                message = message_of(head[0])
                self.assertIsNotNone(message, f"{path}: сообщения нет")
                self.assertTrue(_mentions(message, output),
                                f"{path}: сообщение {ast.unparse(message)} "
                                f"не несёт {output}")
