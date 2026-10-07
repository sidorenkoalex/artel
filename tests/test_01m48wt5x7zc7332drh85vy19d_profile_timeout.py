"""Тесты предела полного прогона устойчивы к наличию подполя профиля.

Группа: долгоживущий
Красен до реализации: зависимый тестовый модуль ещё не в этой ветке; его setUp пока дублирует подполе профиля.
"""

import importlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import config


class ProfileTimeoutAcceptanceTest(unittest.TestCase):
    def test_ac18_profile_timeout_tests_pass_with_and_without_field(self):
        """Тестовый модуль выполняется с профилем артели, содержащим предел, и без него.

        Ловит мутацию: set_timeout вставляет второе одноимённое поле — вариант с исходным пределом краснеет при загрузке YAML.
        """
        module = importlib.import_module("tests.test_full_suite_profile_timeout")
        source = (Path(__file__).resolve().parent.parent / "targets.yaml").read_text(
            encoding="utf-8")
        source = "\n".join(line for line in source.splitlines()
                           if "full_suite_timeout_sec:" not in line) + "\n"
        self.assertIn("    test_profile:\n", source)
        with tempfile.TemporaryDirectory() as temp_dir:
            for initial in (source,
                            source.replace("    test_profile:\n",
                                           "    test_profile:\n      full_suite_timeout_sec: 1500\n", 1)):
                path = Path(temp_dir) / "targets.yaml"
                path.write_text(initial, encoding="utf-8")
                with mock.patch.object(config, "TARGETS", path):
                    suite = unittest.defaultTestLoader.loadTestsFromModule(module)
                    stream = io.StringIO()
                    result = unittest.TextTestRunner(stream=stream).run(suite)
                self.assertTrue(result.wasSuccessful(), stream.getvalue())
