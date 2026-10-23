"""`GroupSignalTest` без внука (AC-6): вместо зависания — явный провал
`AssertionError` «внук не появился».

Группа: разовый
Красен до реализации: `run_cli` держит дескриптор канала внука на запись до `thread.join()`, а `read_grandchild_pid` ждёт конца данных — сценарий без внука висит до таймаута pytest (120 с).

Разовый: проверяется поведение помощников тестового файла
`tests/test_canary_parallel_protection.py` (`run_cli`,
`read_grandchild_pid`), а не код пульта; помощники долгоживущего файла —
только `tests/sandbox.py`.

Срока по часам тест не задаёт: от зависания — `timeout = 120` pytest.
"""
import unittest
from unittest import mock

from tests import test_canary_parallel_protection as protection

NO_GRANDCHILD = "import sys\nsys.exit(0)\n"


class GroupSignalWithoutGrandchildTest(unittest.TestCase):
    def test_ac6_missing_grandchild_fails_with_reason_instead_of_hanging(self):
        """Сценарий `GroupSignalTest`, внук которого сразу выходит, не пишет pid.

        Сценарий: `_GRANDCHILD` файла защиты подменён программой, которая
        сразу выходит; запускается настоящий метод
        `GroupSignalTest.test_parent_sigterm_reaches_grandchild_in_child_group`
        отдельным прогоном `unittest`. Дочерний дожидается внука и выходит,
        родитель завершает прогон, согласующий поток не получает pid. Исход
        вложенного прогона — провал, текст которого несёт `AssertionError` с
        «внук не появился»; ошибок (не провалов) нет.

        Ловит мутацию: `run_cli` закрывает дескриптор канала внука на запись
        только после `thread.join()` — прогон висит до таймаута pytest; либо
        `read_grandchild_pid` при пустых данных зовёт `int(b"")` —
        `ValueError` без «внук не появился».
        """
        case = protection.GroupSignalTest(
            "test_parent_sigterm_reaches_grandchild_in_child_group")
        result = unittest.TestResult()
        with mock.patch.object(protection, "_GRANDCHILD", NO_GRANDCHILD):
            case.run(result)
        report = "\n".join(text for _case, text in
                           result.failures + result.errors)
        self.assertEqual(result.testsRun, 1, report)
        self.assertEqual(result.errors, [], report)
        self.assertEqual(len(result.failures), 1, report)
        self.assertIn("AssertionError", report)
        self.assertIn("внук не появился", report)
