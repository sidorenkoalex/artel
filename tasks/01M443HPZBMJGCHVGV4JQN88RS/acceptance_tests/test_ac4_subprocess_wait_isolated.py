"""Пауза `subprocess` не попадает в счётчик пауз исправленного теста `tests/test_main_ci_line.py` (AC-4).

Группа: разовый

Красен до реализации: `AwaitMainCiUnknownTest` подменяет `time.sleep` на весь процесс (`mock.patch("time.sleep") as sleep`) — проба видит подменённый `time.sleep`, а ожидание дочернего процесса попадает в `sleep` и роняет `sleep.assert_not_called()`.

Группа «разовый»: предмет — одно исправленное место этой задачи
(`tests/test_main_ci_line.py::AwaitMainCiUnknownTest`, строка ~360 по
пину 16f663b4); общее свойство дерева держит долгоживущий сторож
`tests/test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard.py`.

Приём: тест `AwaitMainCiUnknownTest` прогоняется как есть, а проверяемый
им `fsm_merge_gate._await_main_ci` обёрнут пробой. В момент вызова — то
есть внутри теста, под всеми его подменами — проба сверяет, что
`time.sleep` модуля `time` — та самая функция, что была до теста, и
запускает настоящий дочерний процесс, живущий 0.3 с, ожидая его
`Popen.wait(timeout=…)`: в Python 3.13 это цикл `Popen._wait` с паузами
`time.sleep`. Затем зовётся настоящий `_await_main_ci`.
"""
import subprocess
import sys
import time
import unittest
from unittest import mock

from _plank import CODE_ROOT  # noqa: F401  (кладёт корень кода в sys.path)

from orchestrator import fsm_merge_gate  # noqa: E402
from tests import test_main_ci_line  # noqa: E402

REAL_SLEEP = time.sleep
CHILD = [sys.executable, "-c", "import time; time.sleep(0.3)"]


class SubprocessWaitIsolatedTest(unittest.TestCase):

    def test_ac4_child_wait_inside_fixed_test_does_not_touch_its_sleep(self):
        """Внутри `AwaitMainCiUnknownTest` `time.sleep` модуля `time` настоящий, и ожидание живого дочернего процесса не ломает `sleep.assert_not_called()`.

        Сценарий: `fsm_merge_gate._await_main_ci` обёрнут пробой (см.
        докстринг модуля); все методы `AwaitMainCiUnknownTest`
        прогоняются своим `unittest.TestResult`. Проба вызвана хотя бы раз;
        при каждом вызове `sys.modules["time"].sleep is REAL_SLEEP`;
        дочерний процесс дождан; все методы теста зелёные — пауза
        `subprocess` не попала в его счётчик пауз.

        Ловит мутацию: в `AwaitMainCiUnknownTest` остаётся (или
        возвращена) `mock.patch("time.sleep") as sleep` либо
        `mock.patch.object(fsm_merge_gate.time, "sleep")` — проба увидит
        мок вместо настоящей функции, `Popen._wait` наполнит `sleep`
        вызовами, и `sleep.assert_not_called()` теста покраснеет.
        """
        original = fsm_merge_gate._await_main_ci
        probes = []

        def probe(*args, **kwargs):
            seen = sys.modules["time"].sleep
            child = subprocess.Popen(CHILD)
            code = child.wait(timeout=30)
            probes.append((seen is REAL_SLEEP, repr(seen), code))
            return original(*args, **kwargs)

        suite = unittest.defaultTestLoader.loadTestsFromTestCase(
            test_main_ci_line.AwaitMainCiUnknownTest)
        self.assertGreater(suite.countTestCases(), 0)
        result = unittest.TestResult()
        with mock.patch.object(fsm_merge_gate, "_await_main_ci", probe):
            suite.run(result)

        self.assertTrue(probes, "проба не вызвана: тест не дошёл до "
                                "fsm_merge_gate._await_main_ci")
        for real, seen, code in probes:
            self.assertEqual(code, 0)
            self.assertTrue(real, f"во время теста time.sleep модуля time "
                                  f"подменён: {seen}")
        failures = [f"{t.id()}:\n{tb}" for t, tb in
                    result.failures + result.errors]
        self.assertTrue(result.wasSuccessful(), "\n".join(failures))


if __name__ == "__main__":
    unittest.main()
