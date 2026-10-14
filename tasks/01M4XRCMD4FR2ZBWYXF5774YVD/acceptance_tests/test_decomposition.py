"""Разовые свидетельства изменения SuiteObservationTest.

Группа: разовый
Красен до реализации: исходные green/red не отключают автозагрузку плагинов; отчёта сравнения ещё нет.

Снимок исходного класса нужен только для воспроизведения старых точных
ожиданий на базе; изменённые тесты исполняются из кодовой ветки.
"""

import ast
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _baseline import SOURCE
from _case_tools import (TARGET, assertion_inventory, baseline_failures,
                         current_paths, observe_current)
from _pult import artifact_text, changed_paths
from orchestrator import acceptance


class DecompositionEvidence(unittest.TestCase):
    def assert_success(self, observation):
        result = observation["result"]
        self.assertEqual(result.errors, [], str(result.errors))
        self.assertEqual(result.failures, [], str(result.failures))
        self.assertEqual(result.skipped, [])
        self.assertEqual(result.expectedFailures, [])
        self.assertEqual(result.unexpectedSuccesses, [])

    def test_ac1_four_real_cases_have_exit_codes_and_isolated_plugins(self):
        """Старые и новые тесты вместе дают четыре реальные интеграции.

        Наблюдение за Popen не заменяет процесс и его вывод. Проверяются
        реальные exit-коды, замок и окружение каждого green/red-вызова.
        Ловит мутацию: workers=2 red исчезает, TIMEOUT допускается вместо
        завершения либо локальное отключение автозагрузки забыто.
        """
        observation = observe_current()
        self.assert_success(observation)
        seen = set()
        codes = {acceptance.FULL_SUITE_GREEN: 0, acceptance.FULL_SUITE_RED: 1}
        for run in observation["runs"]:
            if run["outcome"] not in codes:
                continue
            workers = run["metrics"]["xdist_workers"]
            seen.add((workers, run["outcome"]))
            with self.subTest(workers=workers, outcome=run["outcome"]):
                self.assertEqual(len(run["launches"]), 1)
                launch = run["launches"][0]
                self.assertEqual(launch["proc"].returncode, codes[run["outcome"]])
                self.assertTrue(launch["lock"])
                argv = launch["argv"]
                self.assertTrue(launch["env"].get("PYTEST_DISABLE_PLUGIN_AUTOLOAD")
                                or "--disable-plugin-autoload" in argv,
                                "автозагрузка посторонних плагинов не отключена")
                self.assertTrue(any("pytest" in str(arg) for arg in argv))
                if "-n" in argv:
                    self.assertEqual(workers, int(argv[argv.index("-n") + 1]))
                plugins = [argv[i + 1] for i, arg in enumerate(argv[:-1]) if arg == "-p"]
                self.assertTrue({"xdist", "xdist.plugin"}.intersection(plugins))
                self.assertTrue({"timeout", "pytest_timeout"}.intersection(plugins))
        self.assertTrue({(workers, outcome) for workers in (1, 2)
                         for outcome in codes} <= seen, str(seen))

    def test_ac2_each_gate_result_has_one_complete_measurement(self):
        """Измерения читаются из БД после настоящих сценариев самого класса.

        Каждый законченный green/red учитывает skipped в числе трёх;
        таймауты оставляют неизвестные счётчики, сохраняя нагрузку и CPU.
        Ловит мутацию: запись дублируется, skipped теряется, или время
        workers=2 делится на число процессов вместо числа тестов.
        """
        observation = observe_current()
        self.assert_success(observation)
        self.assertTrue(observation["runs"])
        for run in observation["runs"]:
            with self.subTest(outcome=run["outcome"], metrics=run["metrics"]):
                self.assertEqual(run["added"], 1)
                metrics = run["metrics"]
                self.assertGreater(metrics["duration_seconds"], 0)
                self.assertGreater(metrics["cpu_cores"], 0)
                for boundary in ("start", "end"):
                    for minutes in (1, 5):
                        self.assertIsNotNone(metrics[f"load_{boundary}_{minutes}"])
                self.assertEqual(len(metrics["top_processes"]), 3)
                for process in metrics["top_processes"]:
                    self.assertIn("pid", process)
                if run["outcome"] == acceptance.FULL_SUITE_TIMEOUT:
                    self.assertIsNone(metrics["tests"])
                    self.assertIsNone(metrics["seconds_per_test"])
                else:
                    self.assertEqual(metrics["tests"], 3)
                    self.assertGreater(metrics["seconds_per_test"], 0)
                    if metrics["xdist_workers"] == 2:
                        self.assertEqual(metrics["seconds_per_test"],
                                         metrics["duration_seconds"] / metrics["tests"])

    def test_ac5_reproduced_old_failure_and_reported_residual_risk(self):
        """На неизменном продукте старые ожидания расходятся с TIMEOUT.

        Новые реальные сценарии и отдельные таймауты исполняются в том же
        прогоне проверки. Отчёт разработчика читается из ссылки документов;
        допускаются текстовые приложения, на которые ссылается PLAN.
        Ловит мутацию: задержка вынесена до timed subprocess, старый тест
        больше не падает; либо отчёт скрывает принятый остаточный риск.
        """
        results, observations = baseline_failures()
        self.assertEqual(observations, [(True, 1), (False, 2)])
        for result, expected in zip(results, (
                acceptance.FULL_SUITE_RED, acceptance.FULL_SUITE_GREEN)):
            self.assertEqual(result.errors, [], str(result.errors))
            self.assertEqual(len(result.failures), 1, str(result.failures))
            failure = result.failures[0][1]
            self.assertIn(acceptance.FULL_SUITE_TIMEOUT, failure)
            self.assertIn(expected, failure)
        self.assert_success(observe_current())
        plan = artifact_text("PLAN.md")
        self.assertIsNotNone(plan, "нет отчёта разработчика PLAN.md")
        report = plan
        for name in re.findall(r"\]\(([^)]+\.(?:md|txt|log))\)", plan):
            # Только относительное приложение этой задачи, без внешних URL.
            if ":" in name or name.startswith("/") or ".." in Path(name).parts:
                continue
            report += "\n" + (artifact_text(name) or "")
        self.assertRegex(report.lower(), r"остаточн\w*\s+риск")
        self.assertRegex(report.lower(), r"холодн|планировщик|временн\w*\s+отказ")
        self.assertRegex(report, r"4[.,]2")
        self.assertIn("TIMEOUT", report)

    def test_ac6_original_neighbouring_scenarios_still_execute(self):
        """Исходные AC3–5 действительно исполняются и не пропускаются.

        Наблюдение включает настоящий фоновый suite-run, pytest PID,
        порядок внешних процессов и строки нагрузки с исходными значениями.
        Ловит мутацию: соседний метод удалён, пропущен или теперь падает
        из-за утраты снимка процессов/строки нагрузки.
        """
        observation = observe_current()
        self.assert_success(observation)
        for method in (
                "test_ac3_pytest_tree_is_excluded_from_top_processes",
                "test_ac4_gate_timeout_repeats_recorded_load_on_one_line",
                "test_ac5_suite_timeout_repeats_recorded_load_on_one_line"):
            self.assertTrue(any(identity.endswith("." + method)
                                for identity in observation["identities"]), method)

    def test_ac7_temporary_roots_databases_and_caches_are_removed(self):
        """После исполнения сценариев временные ресурсы исчезают.

        Фиксируются реальные пути общей песочницы и кеша дочерних запусков;
        конфигурация родительского процесса возвращается к прежним путям.
        Ловит мутацию: тест начинает использовать настоящий root/БД,
        забывает уборку кеша/процесса или меняет общую песочницу.
        """
        observation = observe_current()
        self.assert_success(observation)
        self.assertTrue(observation["roots"])
        for root, database in zip(observation["roots"], observation["databases"]):
            self.assertNotEqual(root, observation["real_root"])
            self.assertNotEqual(database, observation["real_db"])
            self.assertTrue(database.is_relative_to(root), str(database))
            self.assertFalse(root.exists(), str(root))
            self.assertFalse(database.exists(), str(database))
        for cache in observation["caches"]:
            self.assertFalse(cache.exists(), str(cache))
        for proc in observation["processes"]:
            self.assertIsNotNone(proc.poll(), str(proc.pid))
        self.assertEqual(observation["restored_root"], observation["real_root"])
        self.assertEqual(observation["restored_db"], observation["real_db"])
        self.assertEqual(observation["new_root_entries"], set())
        self.assertNotIn("tests/sandbox.py", changed_paths())

    def test_ac8_assertions_and_product_implementation_are_preserved(self):
        """Декомпозиция сохраняет исходные методы и виды утверждений.

        Сверка учитывает перенос утверждений между файлами, не номера строк
        и не локальные имена. Неизменность продукта берётся из диффа задачи.
        Ловит мутацию: исключение PID через assertNotRegex заменено assertNotIn,
        переименован исходный метод, увеличен лимит или изменён acceptance.py.
        """
        before = assertion_inventory(SOURCE)
        after = before.__class__()
        method_names = set()
        for path in current_paths():
            source = path.read_text(encoding="utf-8")
            after.update(assertion_inventory(source))
            method_names.update(node.name for node in ast.walk(ast.parse(source))
                                if isinstance(node, ast.FunctionDef))
        self.assertFalse(before - after,
                         f"утрачены виды утверждений: {before - after}")
        original_methods = {node.name for node in ast.parse(SOURCE).body
                            if isinstance(node, ast.ClassDef)
                            for node in node.body if isinstance(node, ast.FunctionDef)}
        self.assertTrue(original_methods <= method_names,
                        f"утрачены методы: {original_methods - method_names}")
        product_changes = [name for name in changed_paths()
                           if name.startswith(("orchestrator/", "scripts/"))]
        self.assertEqual(product_changes, [], product_changes)
        observation = observe_current()
        self.assert_success(observation)
        for launch in observation["launches"]:
            calls = launch["communicate"] or launch["wait"]
            if not calls:
                # Управляемая группа из AC-3 не загружает pytest; её
                # штатный timeout=4 проверяется самим долгоживущим тестом.
                continue
            expected = (5 if launch["test"].endswith(
                ".test_ac3_pytest_tree_is_excluded_from_top_processes") else 4)
            self.assertEqual(calls[0], expected, launch["test"])
