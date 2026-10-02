"""Граница переданного и текущего окружения признака шага роли."""

import os
import unittest
from unittest import mock

from orchestrator import config, runner


class RoleEnvironmentSourceTest(unittest.TestCase):
    def test_explicit_empty_environment_does_not_read_process_marker(self):
        """Ловит мутацию: явный пустой env заменяется на os.environ через `or`.

        Тогда операторский словарь ложно распознаётся как шаг роли, если
        вызывающий pytest сам запущен с ARTEL_ROLE.
        """
        with mock.patch.dict(os.environ, {config.ARTEL_ROLE_ENV: "developer"}):
            self.assertTrue(runner.in_role_environment())
            self.assertFalse(runner.in_role_environment({}))
