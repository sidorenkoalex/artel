"""Раздельные исходы полного прогона и уборка его дочерней группы.

Группа: долгоживущий
Зелёный с рождения: продуктовый full_suite уже различает исходы; задача меняет тесты.
"""

import contextlib
import json
import os
import select
import signal
import subprocess
import sys
from pathlib import Path
from unittest import mock

from orchestrator import acceptance, config, project_profile, store, suite_lock
from tests.sandbox import TmpRootTest


class SeparateSuiteScenarios(TmpRootTest):
    def setUp(self):
        super().setUp()
        store.create_schema(store.db())
        self.conn = store.db()
        self.task = "T001"
        store.insert_task(self.conn, self.task, "Измерения", "in_dev",
                          "task/t001-measurements", config.DEFAULT_TARGET, 25.0)
        (self.root / "tests").mkdir(exist_ok=True)

    def records(self):
        return [r for r in store.task_steps(self.conn, self.task)
                if r["action"] == "прогон: время"]

    @contextlib.contextmanager
    def settings(self, workers):
        with mock.patch.object(config, "FULL_SUITE_WORKERS", workers), \
                mock.patch.object(config, "FULL_SUITE_TIMEOUT_SEC", 4), \
                mock.patch.object(project_profile, "full_suite_limit",
                                  return_value=(4, "config")), \
                mock.patch.dict(os.environ, {
                    "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTEST_ADDOPTS": ""}):
            yield

    def scenario(self, red=False, reverse=False):
        bodies = ["def test_pass(): assert True\n",
                  f"def test_result(): assert {not red!r}\n",
                  "def test_skip(): pytest.skip('fixture')\n"]
        if reverse:
            bodies.reverse()
        (self.root / "tests" / "test_case.py").write_text(
            "import pytest\n" + "".join(bodies), encoding="utf-8")

    def run_real(self, workers, red, reverse=False):
        self.scenario(red, reverse=reverse)
        original = subprocess.Popen
        processes = []
        caches = []

        def launch(argv, *args, **kwargs):
            if "pytest" in argv:
                self.assertTrue(suite_lock.held_by_me())
                cache = Path(kwargs["env"]["PYTHONPYCACHEPREFIX"])
                self.assertEqual(list(cache.iterdir()), [])
                caches.append(cache)
            proc = original(argv, *args, **kwargs)
            if "pytest" in argv:
                processes.append(proc)
            return proc

        before = len(self.records())
        with self.settings(workers), mock.patch.object(subprocess, "Popen", launch):
            result = acceptance.full_suite(
                self.root, self.task, fresh=True,
                command=[sys.executable, "-m", "pytest", "-p", "xdist",
                         "-p", "timeout"])
        self.assertEqual(len(processes), 1)
        self.assertEqual(processes[0].returncode, 1 if red else 0,
                         result.log_path.read_text() if result.log_path else result.detail)
        self.assertEqual(result.outcome, acceptance.FULL_SUITE_RED if red
                         else acceptance.FULL_SUITE_GREEN)
        self.assertEqual(len(self.records()), before + 1)
        for cache in caches:
            self.assertFalse(cache.exists())
        return json.loads(self.records()[-1]["detail"])

    def assert_metrics(self, metrics, workers, timeout=False):
        self.assertGreater(metrics["duration_seconds"], 0)
        self.assertEqual(metrics["xdist_workers"], workers)
        self.assertGreater(metrics["cpu_cores"], 0)
        for boundary in ("start", "end"):
            for minutes in (1, 5):
                self.assertIsNotNone(metrics[f"load_{boundary}_{minutes}"])
        self.assertEqual(len(metrics["top_processes"]), 3)
        for process in metrics["top_processes"]:
            self.assertIn("pid", process)
        if timeout:
            self.assertIsNone(metrics["tests"])
            self.assertIsNone(metrics["seconds_per_test"])
        else:
            self.assertEqual(metrics["tests"], 3)
            self.assertGreater(metrics["seconds_per_test"], 0)
            if workers == 2:
                self.assertEqual(metrics["seconds_per_test"],
                                 metrics["duration_seconds"] / metrics["tests"])

    def test_ac1_missing_real_red_workers_two(self):
        """Недостающее red workers=2 проверяется на двух порядках тестов.

        Связка: публичный гейт — штатный замок — процесс pytest — журнал БД.
        Остальные три green/red-сочетания уже есть в исходном классе;
        разовая планка наблюдает их совместно с этим дополнением.
        Ловит мутацию: таймаут засчитывается за RED, skipped теряется из
        счётчика или нормализация workers=2 перестаёт равняться duration/3.
        """
        for reverse in (False, True):
            with self.subTest(reverse=reverse):
                self.assert_metrics(self.run_real(2, True, reverse=reverse), 2)

    def test_ac3_timeout_kills_group_and_failure_cleanup_is_bounded(self):
        """Сигнал готовности ребёнка предшествует управляемому TimeoutExpired.

        Связка: full_suite — штатная ветка таймаута — настоящая группа
        процессов — журнал БД. Ребёнок держит stdout открытым до смерти;
        EOF после communicate доказывает прекращение всей группы.
        Отдельный RuntimeError после готовности проверяет аварийную уборку.
        Пределы select/communicate — страховка, наступление таймаута задаётся
        исключением, а не истечением реальных четырёх секунд.
        Ловит мутацию: убивается только родитель, ребёнок удерживает stdout;
        или аварийная ветка оставляет группу жить после исключения.
        """
        original = subprocess.Popen
        child_code = ("import os,signal; signal.alarm(30); "
                      "print(os.getpid(), flush=True); signal.pause()")
        parent_code = ("import subprocess,sys; "
                       f"p=subprocess.Popen([sys.executable,'-c',{child_code!r}]); "
                       "p.wait(timeout=30)")
        for exceptional in (False, True):
            with self.subTest(exceptional=exceptional):
                launched = []
                cleanup_calls = []
                timeouts = []
                before = len(self.records())

                def launch(argv, *args, **kwargs):
                    if "pytest" not in argv:
                        return original(argv, *args, **kwargs)
                    proc = original([sys.executable, "-c", parent_code],
                                    *args, **kwargs)
                    launched.append(proc)
                    real_communicate = proc.communicate
                    cleanup_calls.append(real_communicate)
                    first = True

                    def communicate(*comm_args, **comm_kwargs):
                        nonlocal first
                        if not first:
                            return real_communicate(timeout=10)
                        first = False
                        timeouts.append(comm_kwargs.get("timeout"))
                        ready, _, _ = select.select([proc.stdout], [], [], 10)
                        self.assertTrue(ready, "ребёнок не подал сигнал готовности")
                        self.assertTrue(proc.stdout.readline().strip().isdigit())
                        if exceptional:
                            raise RuntimeError("fixture after child ready")
                        raise subprocess.TimeoutExpired(argv, 4)

                    proc.communicate = communicate
                    return proc

                self.scenario()
                try:
                    with self.settings(1), mock.patch.object(subprocess, "Popen", launch):
                        if exceptional:
                            with self.assertRaisesRegex(RuntimeError, "fixture after child ready"):
                                acceptance.full_suite(self.root, self.task, fresh=True)
                        else:
                            result = acceptance.full_suite(self.root, self.task, fresh=True)
                            self.assertEqual(result.outcome, acceptance.FULL_SUITE_TIMEOUT)
                    self.assertEqual(timeouts, [4])
                    self.assertEqual(len(launched), 1)
                    self.assertEqual(launched[0].returncode, -signal.SIGKILL)
                    self.assertTrue(launched[0].stdout.closed)
                    if not exceptional:
                        self.assertEqual(len(self.records()), before + 1)
                        self.assert_metrics(json.loads(self.records()[-1]["detail"]),
                                            1, timeout=True)
                finally:
                    for proc, communicate in zip(launched, cleanup_calls):
                        try:
                            os.killpg(proc.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        # Оригинальный метод обходит инъекцию исключения и
                        # гарантированно закрывает каналы даже при assertFailure.
                        communicate(timeout=10)

    def test_ac4_real_start_delay_is_timeout_with_unknown_count(self):
        """Задержка перед импортом pytest остаётся внутри штатных четырёх секунд.

        Связка: полный гейт — холодный timed subprocess — запись БД.
        Задержка 4,2 с — вход сценария из AC, не опрос наступления события.
        Ловит мутацию: отсчёт переносится за импорт pytest, либо задержка
        объявляется успешным green/red и появляется известный счётчик тестов.
        """
        for workers in (1, 2):
            with self.subTest(workers=workers):
                self.scenario()
                before = len(self.records())
                with self.settings(workers):
                    result = acceptance.full_suite(
                        self.root, self.task, fresh=True,
                        command=[sys.executable, "-c",
                                 "import runpy,sys,time; time.sleep(4.2); "
                                 "sys.argv[0]='pytest'; "
                                 "runpy.run_module('pytest',run_name='__main__')",
                                 "-p", "xdist", "-p", "timeout"])
                self.assertEqual(result.outcome, acceptance.FULL_SUITE_TIMEOUT)
                self.assertEqual(len(self.records()), before + 1)
                self.assert_metrics(json.loads(self.records()[-1]["detail"]),
                                    workers, timeout=True)
