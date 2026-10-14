"""Приёмка переноса проверок длительности в долгоживущие тесты.

Группа: разовый
Красен до реализации: в DoctorDurationTest нет трёх отдельных граничных методов и контролируемого журнала, а в SuiteObservationTest нет нового сценария workers=2.
"""

import ast
import hashlib
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, artifact_text, changed_paths

from orchestrator import config

DOCTOR = "tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py"
OBSERVATION = "tests/test_01m4araxf7vss5xz8c99bx8de2_suite_observation.py"
HISTORICAL = "tasks/01M4ARAXF7VSS5XZ8C99BX8DE2/acceptance_tests/long_lived.sha256.txt"


def source_and_methods(path):
    source = (Path(CODE_ROOT) / path).read_text(encoding="utf-8")
    tree = ast.parse(source)
    methods = {node.name: node for node in ast.walk(tree)
               if isinstance(node, ast.FunctionDef)}
    return source, methods


def segment(source, node):
    return ast.get_source_segment(source, node)


def calls(node, name):
    return [item for item in ast.walk(node)
            if isinstance(item, ast.Call) and isinstance(item.func, ast.Attribute)
            and item.func.attr == name]


class DoctorDurationRepairAcceptance(unittest.TestCase):
    def assert_case_green(self, module_name, class_name, name):
        import importlib
        case_class = getattr(importlib.import_module(module_name), class_name)
        self.assertTrue(hasattr(case_class, name), f"нет метода {name}")
        case = case_class(name)
        result = unittest.TestResult()
        case.run(result)
        failures = [trace for _, trace in result.failures + result.errors]
        self.assertFalse(failures, f"{name}: {failures}")
        self.assertEqual(result.testsRun, 1)
        self.assertFalse(result.skipped, f"{name}: тест пропущен")

    def test_ac1_exact_eight_and_later_boundaries(self):
        """Отдельные журналы проверяют высокую восьмую, задержанную девятую и десятую.

        Ловит мутацию: восьмая запись ошибочно открывает сигнал либо
        задержанная девятая после восьми нормальных его не открывает.
        """
        source, methods = source_and_methods(DOCTOR)
        names = (
            "test_duration_high_eighth_has_no_signal",
            "test_duration_delayed_ninth_triggers",
            "test_duration_normal_ninth_then_delayed_tenth_triggers",
        )
        for name in names:
            with self.subTest(name=name):
                self.assertIn(name, methods)
                body = segment(source, methods[name])
                self.assertIn("0.28", body)
                self.assertIn("0.48", body)
                self.assertIn("self.doctor_checks()", body)
                self.assert_case_green("tests.test_01m4araxf7vss5xz8c99bx8de2_doctor_duration", "DoctorDurationTest", name)
        main = segment(source, methods["test_ac7_duration_calibrates_and_ignores_worker_changes"])
        self.assertRegex(main, r"range\(k\s*-\s*1\)|range\(7\)")

    def test_ac2_controlled_journal_and_real_doctor(self):
        """Алгоритмическая серия идёт через публичный журнал и настоящий doctor.

        Ловит мутацию: дорогое измерение pytest остаётся источником
        калибровки или подменяется проверка порога внутри doctor.
        """
        source, methods = source_and_methods(DOCTOR)
        main = methods["test_ac7_duration_calibrates_and_ignores_worker_changes"]
        main_body = segment(source, main)
        self.assertFalse(calls(main, "measured_run"))
        self.assertFalse(calls(main, "full_suite"))
        self.assertFalse(calls(main, "check_suite_duration"))
        self.assertFalse(calls(main, "sleep"))
        self.assertFalse(calls(main, "randrange"))
        self.assertIn("journal_suite_metrics", source)
        self.assertIn("doctor.all_checks(self.conn)", segment(source, methods["doctor_checks"]))
        self.assertGreaterEqual(main_body.count("self.doctor_checks()"), 5)
        for key in ("duration_seconds", "tests", "seconds_per_test",
                    "xdist_workers", "load_start_1", "load_start_5",
                    "load_end_1", "load_end_5", "cpu_cores",
                    "top_processes", "pid", "cpu_percent", "name", "age"):
            self.assertIn(key, source)
        for value in ("1.12", "0.28", "28", "100", "4", "1.0", "1.92", "0.48"):
            self.assertIn(value, source)
        self.assert_case_green("tests.test_01m4araxf7vss5xz8c99bx8de2_doctor_duration",
                               "DoctorDurationTest", "test_ac7_duration_calibrates_and_ignores_worker_changes")

    def test_ac3_separate_real_workers_two_integration(self):
        """Старый workers=1 сохранён, новый workers=2 измеряется настоящим full_suite.

        Ловит мутацию: worker count не попадает в запись или время на
        тест не равно длительности, делённой на три результата.
        """
        source, methods = source_and_methods(OBSERVATION)
        old = segment(source, methods["test_ac1_gate_writes_each_outcome_with_metrics"])
        self.assertEqual(hashlib.sha256(old.encode()).hexdigest(),
                         "55019d598b7415511f8e31db5f628e2d1b42c384d3ae4b75d0fb02f976804b04")
        name = "test_gate_writes_workers_2_metrics"
        self.assertIn(name, methods)
        body = segment(source, methods[name])
        for token in ("full_suite", "FULL_SUITE_WORKERS", "FULL_SUITE_TIMEOUT_SEC",
                      "full_suite_limit", "duration_seconds", "seconds_per_test",
                      "xdist_workers"):
            self.assertIn(token, body)
        self.assert_case_green("tests.test_01m4araxf7vss5xz8c99bx8de2_suite_observation", "SuiteObservationTest", name)

    def test_ac4_fifteen_assertions_keep_doctor_target_checks(self):
        """Пять точных suite-duration checks заменяют пять проверок журнала.

        Ловит мутацию: непустой общий all_checks засчитывается вместо
        результата suite-duration нужной цели или один этап пропущен.
        """
        source, methods = source_and_methods(DOCTOR)
        node = methods["test_ac7_duration_calibrates_and_ignores_worker_changes"]
        body = segment(source, node)
        assertions = [item for item in ast.walk(node)
                      if isinstance(item, ast.Call)
                      and isinstance(item.func, ast.Attribute)
                      and item.func.attr.startswith("assert")]
        self.assertGreaterEqual(len(assertions), 15)
        self.assertEqual(body.count("self.assertTrue(checks)"), 5)
        self.assertEqual(body.count("target = config.DEFAULT_TARGET"), 5)
        self.assertGreaterEqual(body.count("suite-duration:{target}"), 5)
        self.assertGreaterEqual(body.count("self.doctor_checks()"), 5)
        self.assertIn("doctor.all_checks(self.conn)", segment(source, methods["doctor_checks"]))
        self.assertFalse(calls(node, "check_suite_duration"))

    def test_ac5_constants_and_preserved_regressions(self):
        """Константы, старые проверки и четыре регрессии сохраняют силу.

        Ловит мутацию: пропадает проверка ack, уменьшается число методов
        или в алгоритм снова попадает случайная задержка.
        """
        source, methods = source_and_methods(DOCTOR)
        self.assertEqual((config.SUITE_DURATION_CALIBRATION_RUNS,
                          config.SUITE_DURATION_RATIO), (8, 0.6))
        for name, digest in (
            ("test_ac6_machine_load_is_ok_or_warn_never_fail",
             "9f85182a122e4a89a65a1e65035515af51c36c496b6fae7204b6331b0cb1eb7e"),
            ("test_ac8_ack_restarts_calibration_after_signal",
             "330f977261eccd65cab36ac2f3fd5b708e956e87648194e2b3683c0988f348a6"),
        ):
            self.assertEqual(hashlib.sha256(segment(source, methods[name]).encode()).hexdigest(), digest)
        self.assertGreaterEqual(len([name for name in methods if name.startswith("test_")]), 6)
        main = segment(source, methods["test_ac7_duration_calibrates_and_ignores_worker_changes"])
        self.assertIn("0.2", source)
        self.assertNotIn("time.sleep", main)
        self.assertNotIn("random.", main)
        self.assertNotIn("2188121822", main)
        for name in ("test_duration_high_eighth_has_no_signal",
                     "test_duration_delayed_ninth_triggers",
                     "test_duration_normal_ninth_then_delayed_tenth_triggers"):
            self.assertIn(name, methods)

    def test_ac6_matrix_and_historical_lock(self):
        """Инвентаризация имеет 15 строк, старый перечень задачи не меняется.

        Ловит мутацию: из матрицы выпадает утверждение или обновляется
        исторический перечень вместо обычной правки смерженного теста.
        """
        spec = artifact_text("SPEC.md")
        self.assertIsNotNone(spec)
        inventory = spec.split("## Инвентаризация 15 учитываемых утверждений", 1)[1]
        inventory = inventory.split("## ", 1)[0]
        numbered = re.findall(r"^\|\s*(\d+)\s*\|", inventory, re.MULTILINE)
        self.assertEqual(numbered, [str(n) for n in range(1, 16)])
        self.assertNotIn(HISTORICAL, changed_paths())
        self.assertIn(DOCTOR, spec)
