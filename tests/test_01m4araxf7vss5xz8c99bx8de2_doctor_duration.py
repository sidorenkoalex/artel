"""Проверки нагрузки машины и роста времени на тест через doctor.

Группа: долгоживущий
Красен до реализации: doctor ещё не показывает нагрузку и не открывает suite.duration.
"""

import contextlib
import os
import shutil
import subprocess
from pathlib import Path
from unittest import mock

from orchestrator import acceptance, alerts, config, doctor, store
from tests.sandbox import TmpRootTest


class DoctorDurationTest(TmpRootTest):
    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        self.task = "T001"
        store.insert_task(self.conn, self.task, "Нагрузка", "in_dev",
                          "task/t001-load", config.DEFAULT_TARGET, 25.0)
        (self.root / "tests").mkdir(exist_ok=True)

    def triggers(self):
        return [row for row in alerts.open_alerts(self.conn, "trigger")
                if row["source"] == "suite.duration"]

    def doctor_checks(self):
        """Для сигнала времени процессная проверка видит спокойный снимок."""
        original_run = subprocess.run

        def fake_run(argv, *args, **kwargs):
            if Path(str(argv[0])).name != "ps":
                return original_run(argv, *args, **kwargs)
            selectors = []
            for index, item in enumerate(argv[:-1]):
                if item == "-o" or (str(item).startswith("-")
                                    and str(item).endswith("o")):
                    selectors.extend(str(argv[index + 1]).split(","))
            values = {"pid": "98765", "ppid": "1", "pcpu": "1.0",
                      "%cpu": "1.0", "cpu": "1.0", "comm": "idle",
                      "command": "idle", "etime": "01:23", "time": "01:23"}
            line = " ".join(values.get(item.strip(" ="), "0")
                            for item in selectors)
            return subprocess.CompletedProcess(argv, 0, line + "\n", "")

        # Живой смок — настоящий вызов CLI роли, по секунде-пять на каждый
        # прогон doctor: к сигналу времени он не относится, а пять таких
        # вызовов были больше трети лимита pytest-timeout у test_ac7 (SPEC
        # 01M4G8MNEPECNX1TCEDW4T4RPX, требование 8).
        smoke = doctor.Check("live-smoke", "ok", "живой смок заменён тестом")
        with mock.patch.object(doctor.subprocess, "run", side_effect=fake_run), \
                mock.patch.object(doctor, "_live_smoke_run",
                                  lambda role: smoke):
            return doctor.all_checks(self.conn)

    @contextlib.contextmanager
    def warm_pytest_env(self):
        """Окружение прогона с кешем байткода, общим для прогонов теста.

        Пульт даёт каждому прогону свежий `PYTHONPYCACHEPREFIX`, и pytest
        с xdist компилируется заново — около секунды на каждый из
        девятнадцати прогонов test_ac7 (SPEC 01M4G8MNEPECNX1TCEDW4T4RPX,
        требование 8). К сигналу времени это не относится. Байткод
        каталога теста — переписываемого `test_case.py` — перед каждым
        прогоном убирается: иначе файл того же размера в ту же секунду
        исполнился бы старым байткодом с прежней паузой."""
        cache = self.root / ".pycache-warm"
        for own in {self.root, self.root.resolve()}:
            shutil.rmtree(cache / str(own).lstrip(os.sep), ignore_errors=True)
        yield dict(os.environ, PYTHONPYCACHEPREFIX=str(cache))

    def measured_run(self, delay, count=4, workers=1):
        body = "import time\n"
        body += f"def test_case_0(): time.sleep({delay!r})\n"
        body += "".join(f"def test_case_{number}(): assert True\n"
                        for number in range(1, count))
        (self.root / "tests" / "test_case.py").write_text(body, encoding="utf-8")
        with mock.patch.object(config, "FULL_SUITE_WORKERS", workers), \
                mock.patch.object(acceptance, "_pytest_env",
                                  self.warm_pytest_env):
            acceptance.full_suite(self.root, self.task, fresh=True)
        rows = [row for row in store.task_steps(self.conn, self.task)
                if row["action"] == "прогон: время"]
        self.assertTrue(rows, "полный прогон не записал измерение")

    def journal_measurement(self, duration, tests=4, workers=1):
        acceptance.journal_suite_metrics(self.task, {
            "duration_seconds": duration,
            "tests": tests,
            "seconds_per_test": duration / tests,
            "xdist_workers": workers,
            "load_start_1": 0.4,
            "load_start_5": 0.5,
            "load_end_1": 0.6,
            "load_end_5": 0.7,
            "cpu_cores": 8,
            "top_processes": [{"pid": 98765, "cpu_percent": 12.5,
                               "name": "loadhog", "age": "01:23"}],
        })

    def test_ac6_machine_load_is_ok_or_warn_never_fail(self):
        """Свободная машина даёт ok, высокий load и процесс дают warn.

        Ловит мутацию: doctor игнорирует одно из двух условий перегрузки
        либо повышает предупреждение до блокирующего исхода fail.
        """
        self.assertEqual(config.MACHINE_LOAD_PROCESS_CORES, 4)
        original_run = subprocess.run

        def check(load5, process_cpu):
            def fake_run(argv, *args, **kwargs):
                if Path(str(argv[0])).name != "ps":
                    return original_run(argv, *args, **kwargs)
                selectors = []
                for index, item in enumerate(argv[:-1]):
                    if item == "-o" or (str(item).startswith("-")
                                        and str(item).endswith("o")):
                        selectors.extend(str(argv[index + 1]).split(","))
                values = {"pid": "98765", "ppid": "1", "pcpu": str(process_cpu),
                          "%cpu": str(process_cpu), "cpu": str(process_cpu),
                          "comm": "loadhog", "command": "loadhog",
                          "etime": "01:23", "time": "01:23"}
                line = " ".join(values.get(item.strip(" ="), "0")
                                for item in selectors)
                return subprocess.CompletedProcess(argv, 0, line + "\n", "")

            with mock.patch.object(doctor.os, "getloadavg",
                                   return_value=(0.2, load5, load5)), \
                    mock.patch.object(doctor.os, "cpu_count", return_value=8), \
                    mock.patch.object(doctor.subprocess, "run", side_effect=fake_run):
                return doctor.all_checks(self.conn)

        idle = check(0.3, 25.0)
        idle_load = [item for item in idle if "0.3" in item.detail]
        self.assertTrue(idle_load, "doctor не показал проверку нагрузки")
        self.assertTrue(all(item.status == "ok" for item in idle_load))

        busy_load = check(20.5, 25.0)
        load_rows = [item for item in busy_load if "20.5" in item.detail]
        self.assertTrue(load_rows)
        self.assertTrue(any(item.status == "warn" and "8" in item.detail
                            for item in load_rows))
        self.assertTrue(all(item.status != "fail" for item in load_rows))

        busy_process = check(0.3, 550.0)
        process_rows = [item for item in busy_process if "loadhog" in item.detail]
        self.assertTrue(process_rows)
        self.assertTrue(any(item.status == "warn" and "98765" in item.detail
                            and "550" in item.detail and "01:23" in item.detail
                            for item in process_rows))
        self.assertTrue(all(item.status != "fail" for item in process_rows))

    def test_ac7_duration_calibrates_and_ignores_worker_changes(self):
        """После окна рост времени на тест открывает сигнал с нагрузкой.

        Ловит мутацию: doctor считает длительность вместо времени на тест
        или продолжает прежнее окно после смены числа процессов xdist.
        """
        k = config.SUITE_DURATION_CALIBRATION_RUNS
        ratio = config.SUITE_DURATION_RATIO
        self.assertEqual((k, ratio), (8, 0.6))
        for _ in range(k):
            self.journal_measurement(1.12)
        target = config.DEFAULT_TARGET
        checks = [check for check in self.doctor_checks()
                  if check.name == f"suite-duration:{target}"]
        self.assertTrue(checks)
        self.assertFalse(self.triggers(), "окно ещё не закрыто")

        self.journal_measurement(28, tests=100)
        target = config.DEFAULT_TARGET
        checks = [check for check in self.doctor_checks()
                  if check.name == f"suite-duration:{target}"]
        self.assertTrue(checks)
        self.assertFalse(self.triggers(), "рост числа тестов сам не сигнал")

        self.journal_measurement(4, workers=2)
        target = config.DEFAULT_TARGET
        checks = [check for check in self.doctor_checks()
                  if check.name == f"suite-duration:{target}"]
        self.assertTrue(checks)
        self.assertFalse(self.triggers(), "новое число xdist открывает окно")

        for _ in range(k - 1):
            self.journal_measurement(1.12, workers=2)
        target = config.DEFAULT_TARGET
        checks = [check for check in self.doctor_checks()
                  if check.name == f"suite-duration:{target}"]
        self.assertTrue(checks)
        self.assertFalse(self.triggers(), "ровно k записей")

        # Диагностические 0.8 с за четыре теста добавляют 0.2 с на тест.
        self.journal_measurement(1.92, workers=2)
        target = config.DEFAULT_TARGET
        checks = [check for check in self.doctor_checks()
                  if check.name == f"suite-duration:{target}"]
        self.assertTrue(checks)
        found = self.triggers()
        self.assertEqual(len(found), 1)
        message = found[0]["message"]
        self.assertRegex(message, r"(?i)(на тест|per.test)")
        self.assertRegex(message, r"(?i)(медиан|median)")
        self.assertRegex(message, r"(?i)(load|нагрузк)")
        self.assertRegex(message, r"(?i)(pid|процесс)")

    def test_duration_high_eighth_has_no_signal(self):
        """Ловит мутацию: doctor открывает сигнал на высокой восьмой записи
        до завершения калибровочного окна."""
        for _ in range(7):
            self.journal_measurement(1.12)  # 0.28 с на тест
        self.journal_measurement(1.92)  # 0.48 с на тест
        checks = [check for check in self.doctor_checks()
                  if check.name == f"suite-duration:{config.DEFAULT_TARGET}"]
        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0].status, "ok")
        self.assertFalse(self.triggers())

    def test_duration_delayed_ninth_triggers(self):
        """Ловит мутацию: doctor теряет превышение 0.48 с на девятой
        записи после восьми нормальных 0.28 с на тест."""
        for _ in range(8):
            self.journal_measurement(1.12)  # 0.28 с на тест
        self.journal_measurement(1.92)  # 0.48 с на тест
        checks = [check for check in self.doctor_checks()
                  if check.name == f"suite-duration:{config.DEFAULT_TARGET}"]
        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0].status, "warn")
        self.assertEqual(len(self.triggers()), 1)

    def test_duration_normal_ninth_then_delayed_tenth_triggers(self):
        """Ловит мутацию: doctor теряет сигнал на десятой записи после
        нормальной девятой 0.28 с и задержанной десятой 0.48 с на тест."""
        for _ in range(8):
            self.journal_measurement(1.12)
        self.journal_measurement(1.12)  # девятая, 0.28 с на тест
        checks = [check for check in self.doctor_checks()
                  if check.name == f"suite-duration:{config.DEFAULT_TARGET}"]
        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0].status, "ok")
        self.assertFalse(self.triggers())
        self.journal_measurement(1.92)  # десятая, 0.48 с на тест
        checks = [check for check in self.doctor_checks()
                  if check.name == f"suite-duration:{config.DEFAULT_TARGET}"]
        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0].status, "warn")
        self.assertEqual(len(self.triggers()), 1)

    def test_ac8_ack_restarts_calibration_after_signal(self):
        """Подтверждение сигнала переносит точку отсчёта на новые записи.

        Ловит мутацию: doctor перечитывает старую калибровку после ack
        и сразу повторно открывает тот же suite.duration без нового окна.
        """
        k = config.SUITE_DURATION_CALIBRATION_RUNS
        # Один настоящий прогон держит запись замера полным прогоном; его
        # время на тест одно из восьми и медиану окна 0.28 с не сдвигает.
        self.measured_run(0.01)
        for _ in range(k - 1):
            self.journal_measurement(1.12)  # 0.28 с на тест
        self.journal_measurement(1.92)  # 0.48 с на тест
        self.doctor_checks()
        found = self.triggers()
        self.assertEqual(len(found), 1)
        store.ack_alert(self.conn, found[0]["id"], "operator", "отложено")
        self.doctor_checks()
        self.assertFalse(self.triggers())
        for _ in range(k):
            self.journal_measurement(1.12)
        self.doctor_checks()
        self.assertFalse(self.triggers())
