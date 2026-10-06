"""Предел полного прогона из test_profile: разбор, раннер и диагностика."""
import contextlib
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import acceptance, config, project_profile, store, suite_run, targets
from orchestrator.doctor import cli as doctor_cli


class FullSuiteProfileTimeoutTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / "tests").mkdir()
        original = config.TARGETS.read_text(encoding="utf-8")
        self.targets_path = self.root / "targets.yaml"
        self.targets_path.write_text(original, encoding="utf-8")
        patcher = mock.patch.object(config, "TARGETS", self.targets_path)
        patcher.start()
        self.addCleanup(patcher.stop)

    def set_timeout(self, value: str) -> None:
        text = self.targets_path.read_text(encoding="utf-8")
        self.targets_path.write_text(
            text.replace("    test_profile:\n",
                         f"    test_profile:\n      full_suite_timeout_sec: {value}\n", 1),
            encoding="utf-8")

    def test_positive_integer_is_loaded_and_invalid_values_refuse(self):
        """Ловит мутацию: строка, дробь, bool или неположительное число
        проходят проверку и превращают конфигурационный предел в мусор."""
        self.set_timeout("1500")
        self.assertEqual(targets.load()["artel"]["test_profile"]
                         ["full_suite_timeout_sec"], 1500)
        for value in ("0", "-1", '"1500"', "1.5", "true"):
            with self.subTest(value=value):
                self.targets_path.write_text(
                    self.targets_path.read_text(encoding="utf-8").replace(
                        "full_suite_timeout_sec: 1500",
                        f"full_suite_timeout_sec: {value}"),
                    encoding="utf-8")
                with self.assertRaisesRegex(
                        targets.TargetsError,
                        r"test_profile\.full_suite_timeout_sec"):
                    targets.load()
                self.targets_path.write_text(
                    self.targets_path.read_text(encoding="utf-8").replace(
                        f"full_suite_timeout_sec: {value}",
                        "full_suite_timeout_sec: 1500"),
                    encoding="utf-8")

    def test_limit_and_doctor_show_profile_or_live_config(self):
        """Ловит мутацию: doctor и резолвер игнорируют подполе или
        запоминают старую константу при отсутствии подполя."""
        with mock.patch.object(config, "FULL_SUITE_TIMEOUT_SEC", 37):
            self.assertEqual(project_profile.full_suite_limit("artel"),
                             (37, "config"))
            self.assertIn("37 с", doctor_cli.full_suite_timeout_check(
                "artel").detail)
        self.set_timeout("1500")
        self.assertEqual(project_profile.full_suite_limit("artel"),
                         (1500, "профиль тестов проекта artel"))
        line = doctor_cli.full_suite_timeout_check("artel").detail
        self.assertIn("проект artel", line)
        self.assertIn("1500 с", line)
        self.assertIn("профиль тестов проекта artel", line)

    def test_gate_runner_uses_profile_limit_and_names_source(self):
        """Ловит мутацию: гейт прерывает pytest по config вместо профиля
        либо пишет в отказе предел, отличный от применённого."""
        self.set_timeout("1500")
        with mock.patch.object(store, "db", return_value=None), \
             mock.patch.object(store, "task_target", return_value="artel"), \
             mock.patch.object(acceptance, "_machine_lock",
                               return_value=contextlib.nullcontext(None)), \
             mock.patch.object(acceptance.subprocess, "run",
                               side_effect=subprocess.TimeoutExpired([], 1500)) as run, \
             mock.patch.object(acceptance, "_write_full_suite_log",
                               return_value=None):
            result = acceptance.full_suite(self.root, "T1")
        self.assertEqual(run.call_args.kwargs["timeout"], 1500)
        self.assertEqual(result.outcome, acceptance.FULL_SUITE_TIMEOUT)
        self.assertIn("превысил 1500с", result.detail)
        self.assertIn("профиль тестов проекта artel", result.detail)

    def test_direct_gate_run_without_database_does_not_create_one(self):
        """Ловит мутацию: прямой прогон открывает отсутствующий state.db,
        оставляет пустой файл и ломает последующее чтение документов задачи
        ошибкой `no such table: tasks`."""
        db_path = self.root / "absent-state.db"
        with mock.patch.object(config, "DB", db_path), \
             mock.patch.object(store, "db", side_effect=AssertionError(
                 "прямой прогон не должен открывать БД")), \
             mock.patch.object(acceptance, "_machine_lock",
                               return_value=contextlib.nullcontext(None)), \
             mock.patch.object(acceptance, "run_full_suite",
                               return_value=(True, "1 passed in 0.01s\n")), \
             mock.patch.object(acceptance, "_write_full_suite_log",
                               return_value=None):
            result = acceptance.full_suite(self.root, "T1")
        self.assertTrue(result.green)
        self.assertFalse(db_path.exists())

    def test_suite_report_uses_effective_limit(self):
        """Ловит мутацию: suite-run печатает константу вместо действующего
        предела и скрывает источник таймаута."""
        parsed = suite_run.parse(False, acceptance._full_suite_timeout_note(
            (1500, "профиль тестов проекта artel")))
        report = suite_run.render("T1", 1, suite_run.MODE_FULL, parsed,
                                  None, "", self.root / "log",
                                  (1500, "профиль тестов проекта artel"))
        self.assertIn("прогон не уложился в предел 1500 с", report)
        self.assertIn("профиль тестов проекта artel", report)
