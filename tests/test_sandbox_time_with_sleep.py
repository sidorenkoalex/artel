"""Юнит-тесты заместителя `time` песочницы — `TimeWithSleep`/`patch_sleep`/
`patch_pult_sleep` в `tests/sandbox.py` (SPEC 01M443HPZBMJGCHVGV4JQN88RS).
"""
import importlib
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import runner  # noqa: E402
from tests import sandbox  # noqa: E402
from tests.sandbox import patch_pult_sleep, patch_sleep  # noqa: E402


class PatchSleepTest(unittest.TestCase):

    def test_module_sleep_is_fake_and_stdlib_sleep_stays_real(self):
        """Под `patch_sleep(runner, f)` пауза `runner` — `f`, а `time.sleep`
        модуля `time` — настоящая функция; остальные атрибуты читаются из
        настоящего `time`, в том числе подменённые тестом поверх.

        Ловит мутацию: `patch_sleep` подменяет `time.sleep` модуля `time`
        (`mock.patch.object(time, "sleep", …)`) — `time.sleep is real`
        покраснеет; либо заместитель копирует атрибуты `time` при создании,
        а не читает их при обращении — подмена `time.monotonic` теста не
        дойдёт до `runner.time.monotonic()`.
        """
        real = time.sleep
        pauses = []
        with patch_sleep(runner, pauses.append), \
                mock.patch.object(time, "monotonic", lambda: 42.0):
            runner.time.sleep(3)
            self.assertIs(time.sleep, real)
            self.assertEqual(runner.time.monotonic(), 42.0)
        self.assertEqual(pauses, [3])
        self.assertIs(runner.time, time)


class PatchPultSleepTest(unittest.TestCase):

    def test_every_pult_module_with_a_pause_gets_the_fake_sleep(self):
        """`patch_pult_sleep(f)` подменяет паузу у каждого модуля пульта с
        `time.sleep` и снимает подмену на `close()`; `time.sleep` модуля
        `time` всё это время настоящий.

        Ловит мутацию: обход `sys.modules` пропускает вложенные пакеты
        (`orchestrator.doctor.leases`) — его `time.sleep` останется
        настоящим, и сверка списка пауз покраснеет; либо `close()` не
        снимает подмену — `module.time is time` после покраснеет.
        """
        real = time.sleep
        pauses = []
        stack = patch_pult_sleep(pauses.append)
        try:
            self.assertIs(time.sleep, real)
            for name in sandbox._PULT_SLEEP_MODULES:
                with self.subTest(module=name):
                    module = importlib.import_module(name)
                    module.time.sleep(name)
            self.assertEqual(pauses, list(sandbox._PULT_SLEEP_MODULES))
        finally:
            stack.close()
        for name in sandbox._PULT_SLEEP_MODULES:
            self.assertIs(importlib.import_module(name).time, time, name)


if __name__ == "__main__":
    unittest.main()
