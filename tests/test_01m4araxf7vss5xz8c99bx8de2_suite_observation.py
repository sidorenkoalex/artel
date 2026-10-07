"""Наблюдаемые записи и сообщения полного прогона.

Группа: долгоживущий
Красен до реализации: действия журнала «прогон: время» и строки нагрузки ещё нет.
"""

import contextlib
import json
import re
import subprocess
from pathlib import Path
from unittest import mock

from orchestrator import (acceptance, appendix_tree, config, project_profile,
                          store, suite_lock, suite_run)
from tests.sandbox import TmpRootTest


class SuiteObservationTest(TmpRootTest):
    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        self.task = "T001"
        store.insert_task(self.conn, self.task, "Прогон", "in_dev",
                          "task/t001-progon", config.DEFAULT_TARGET, 25.0)
        (self.root / "tests").mkdir(exist_ok=True)

    def records(self):
        return [row for row in store.task_steps(self.conn, self.task)
                if row["action"] == "прогон: время"]

    def write_scenario(self, outcome):
        body = {
            "green": "import pytest\ndef test_a(): assert True\n"
                     "def test_b(): assert True\n"
                     "def test_c(): pytest.skip('fixture')\n",
            "red": "import pytest\ndef test_a(): assert True\n"
                   "def test_b(): assert False\n"
                   "def test_c(): pytest.skip('fixture')\n",
            "timeout": "import time\ndef test_busy(): time.sleep(20)\n",
        }[outcome]
        (self.root / "tests" / "test_case.py").write_text(body, encoding="utf-8")

    def run_gate(self, outcome):
        self.write_scenario(outcome)
        with mock.patch.object(config, "FULL_SUITE_WORKERS", 1), \
                mock.patch.object(config, "FULL_SUITE_TIMEOUT_SEC", 4), \
                mock.patch.object(project_profile, "full_suite_limit",
                                  return_value=(4, "config")):
            return acceptance.full_suite(self.root, self.task, fresh=True)

    def run_suite_command(self, outcome):
        """Фоновое тело команды на временном дереве с настоящим pytest."""
        self.write_scenario(outcome)
        suite_tree = appendix_tree.SuiteTree(self.root, "", "", "")
        with mock.patch.object(suite_run.workspace, "path", return_value=self.root), \
                mock.patch.object(suite_run.workspace, "repo", return_value=self.root), \
                mock.patch.object(suite_run.appendix_tree, "suite_tree",
                                  return_value=contextlib.nullcontext(suite_tree)), \
                mock.patch.object(project_profile, "full_suite_limit",
                                  return_value=(4, "config")), \
                mock.patch.object(config, "FULL_SUITE_TIMEOUT_SEC", 4), \
                mock.patch.object(config, "FULL_SUITE_WORKERS", 1):
            self.assertIsNone(suite_lock.acquire(self.task, 1))
            suite_run.background(self.task, "1", suite_run.MODE_FULL)
        result = config.LOGS / "suite-run" / self.task / "result.json"
        self.assertTrue(result.exists())
        return json.loads(result.read_text(encoding="utf-8"))["report"]

    def assert_record_fields(self, row, count, timeout=False):
        detail = row["detail"]
        payload = json.loads(detail)
        fields = {}

        def visit(value, path=""):
            if isinstance(value, dict):
                for key, child in value.items():
                    visit(child, f"{path}.{key}")
            elif isinstance(value, list):
                for child in value:
                    visit(child, path)
            else:
                fields[path.lower()] = value

        visit(payload)

        def field(pattern, exclude=r"(?!)"):
            found = [value for key, value in fields.items()
                     if re.search(pattern, key) and not re.search(exclude, key)]
            self.assertTrue(found, f"нет поля {pattern}: {detail}")
            return found[0]

        self.assertGreater(float(field(r"duration|elapsed|длительн")), 0)
        self.assertEqual(int(field(r"xdist|worker|процессов_pytest")), 1)
        self.assertGreater(int(field(r"cores|cpu_count|числ.*ядер")), 0)
        for boundary in ("start", "end"):
            for minutes in ("1", "5"):
                self.assertIsNotNone(field(
                    rf"(?=.*(?:load|нагруз))(?=.*{boundary})(?=.*{minutes})"))
        tests = field(r"(?:test(?:s)?(?:_count|_total)?|тестов|числ.*тест)$",
                      r"per.?test|на.?тест")
        per_test = field(r"per.?test|на.?тест|test.?seconds")
        if timeout:
            self.assertIsNone(tests)
            self.assertIsNone(per_test)
        else:
            self.assertEqual(int(tests), count)
            self.assertGreater(float(per_test), 0)
        self.top_processes(row)

    def assert_load_line(self, message, record):
        candidates = [line for line in message.splitlines()
                      if re.search(r"(?i)(load average|нагрузк)", line)]
        self.assertEqual(len(candidates), 1, message)
        line = candidates[0]
        self.assertRegex(line, r"\d+[.,]\d+")
        self.assertRegex(line, r"(?i)(pid|процесс)")
        recorded = record["detail"]
        for value in re.findall(r"(?<!\d)\d+(?:[.,]\d+)?(?!\d)", line):
            self.assertIn(value, recorded, f"значение {value} не записано")

    def top_processes(self, row):
        payload = json.loads(row["detail"])
        pending = [payload]
        while pending:
            item = pending.pop()
            if isinstance(item, dict):
                pending.extend(item.values())
            elif isinstance(item, list):
                if (len(item) == 3 and all(isinstance(p, dict)
                                           and any("pid" in str(k).lower()
                                                   for k in p)
                                           for p in item)):
                    return item
                pending.extend(item)
        self.fail("в записи нет списка трёх процессов с pid")

    def test_ac1_gate_writes_each_outcome_with_metrics(self):
        """Три исхода полного гейта дают ровно одну запись измерения каждый.

        Ловит мутацию: красный прогон или таймаут проходит мимо записи,
        поэтому в журнале отсутствует измерение с пустым числом тестов.
        """
        for outcome, count, timeout in (
                ("green", 3, False), ("red", 3, False),
                ("timeout", None, True)):
            before = len(self.records())
            result = self.run_gate(outcome)
            self.assertEqual(result.outcome,
                             {"green": acceptance.FULL_SUITE_GREEN,
                              "red": acceptance.FULL_SUITE_RED,
                              "timeout": acceptance.FULL_SUITE_TIMEOUT}[outcome])
            after = self.records()
            self.assertEqual(len(after), before + 1, outcome)
            self.assert_record_fields(after[-1], count, timeout)

    # AC-2: skip — решение Оператора 07.10 (вариант В): suite-run не пишет
    # запись в журнал задачи — это запрещает долгоживущий тест
    # tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py::FootprintTest::
    # test_ac23_task_state_untouched_and_no_files_outside_state; строку
    # нагрузки в отчёте о таймауте suite-run держит AC-5.

    def test_ac3_pytest_tree_is_excluded_from_top_processes(self):
        """Нагрузка работающего pytest не вытесняет внешние процессы.

        Ловит мутацию: снимок сортирует все процессы без исключения дерева
        прогона и включает известный pid рабочего процесса pytest в запись.
        """
        pid_file = self.root / "pytest.pid"
        parent_file = self.root / "pytest_parent.pid"
        (self.root / "tests" / "test_busy.py").write_text(
            "import os, time\n"
            f"def test_busy():\n    open({str(pid_file)!r}, 'w').write(str(os.getpid()))\n"
            f"    open({str(parent_file)!r}, 'w').write(str(os.getppid()))\n"
            "    end = time.monotonic() + 20\n"
            "    while time.monotonic() < end: pass\n",
            encoding="utf-8")
        original_run = subprocess.run
        ps_calls = []

        def fake_run(argv, *args, **kwargs):
            if Path(str(argv[0])).name != "ps":
                return original_run(argv, *args, **kwargs)
            ps_calls.append(argv)
            child = pid_file.read_text().strip() if pid_file.exists() else "44444"
            parent = (parent_file.read_text().strip()
                      if parent_file.exists() else "44445")
            processes = [
                ("90002", "1", "400.0", "outsideB"),
                (child, parent, "950.0", "pytest-worker"),
                ("90003", "1", "300.0", "outsideC"),
                (parent, "1", "850.0", "pytest-main"),
                ("90001", "1", "500.0", "outsideA"),
            ]
            selectors = []
            for index, item in enumerate(argv[:-1]):
                if item == "-o" or (str(item).startswith("-")
                                    and str(item).endswith("o")):
                    selectors.extend(str(argv[index + 1]).split(","))
            def cell(selector, row):
                pid, ppid, cpu, name = row
                return {"pid": pid, "ppid": ppid, "%cpu": cpu,
                        "pcpu": cpu, "cpu": cpu, "comm": name,
                        "command": name, "etime": "00:30"}.get(
                            selector.strip(" ="), "0")
            output = "\n".join(" ".join(cell(selector, row)
                                             for selector in selectors)
                                for row in processes) + "\n"
            return subprocess.CompletedProcess(argv, 0, output, "")

        with mock.patch.object(config, "FULL_SUITE_WORKERS", 1), \
                mock.patch.object(config, "FULL_SUITE_TIMEOUT_SEC", 5), \
                mock.patch.object(acceptance.subprocess, "run",
                                  side_effect=fake_run):
            result = acceptance.full_suite(self.root, self.task, fresh=True)
        self.assertEqual(result.outcome, acceptance.FULL_SUITE_TIMEOUT)
        self.assertTrue(pid_file.exists(), "pytest не достиг теста до таймаута")
        row = self.records()[-1]
        child_pid = pid_file.read_text().strip()
        self.assertNotRegex(row["detail"], rf"(?<!\d){re.escape(child_pid)}(?!\d)")
        processes = self.top_processes(row)
        if ps_calls:
            self.assertEqual([str(item.get("pid")) for item in processes],
                             ["90001", "90002", "90003"])
        cpu = []
        for process in processes:
            self.assertTrue(any("name" in str(key).lower() or
                                "имя" in str(key).lower() for key in process))
            cpu_keys = [key for key in process if "cpu" in str(key).lower()
                        or "percent" in str(key).lower()
                        or "%" in str(key)]
            self.assertTrue(cpu_keys)
            cpu.append(float(process[cpu_keys[0]]))
        self.assertEqual(cpu, sorted(cpu, reverse=True))

    def test_ac4_gate_timeout_repeats_recorded_load_on_one_line(self):
        """Отказ гейта по таймауту показывает записанный снимок нагрузки.

        Ловит мутацию: отказ называет только предел времени, и Оператор
        не видит нагрузку, которая уже сохранилась в журнале.
        """
        result = self.run_gate("timeout")
        self.assertEqual(result.outcome, acceptance.FULL_SUITE_TIMEOUT)
        self.assert_load_line(result.detail, self.records()[-1])

    def test_ac5_suite_timeout_repeats_recorded_load_on_one_line(self):
        """Отчёт suite-run по таймауту показывает тот же снимок нагрузки.

        Ловит мутацию: фоновой прогон снимает нагрузку, но короткий
        отчёт команды по таймауту не переносит её в строку для роли.

        Правка Оператора 07.10 (вариант В): suite-run не пишет журнал
        задачи, поэтому эталон строки — подставленный снимок load average,
        а не запись журнала.
        """
        with mock.patch.object(acceptance.os, "getloadavg",
                               return_value=(7.25, 6.5, 5.75)):
            report = self.run_suite_command("timeout")
        candidates = [line for line in report.splitlines()
                      if re.search(r"(?i)(load average|нагрузк)", line)]
        self.assertEqual(len(candidates), 1, report)
        line = candidates[0]
        self.assertIn("7.25", line)
        self.assertIn("6.5", line)
        self.assertRegex(line, r"(?i)(pid|процесс)")
