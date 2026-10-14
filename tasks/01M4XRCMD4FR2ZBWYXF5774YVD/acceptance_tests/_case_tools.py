"""Исполнение исходных и изменённых тестов как предмета разовой приёмки."""

import ast
import collections
import functools
import importlib
import json
import os
import subprocess
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import acceptance, config, store, suite_lock
from tests.sandbox import TmpRootTest
from _baseline import SOURCE
from _pult import CODE_ROOT, TASK_ID


TARGET = "tests/test_01m4araxf7vss5xz8c99bx8de2_suite_observation.py"


def current_paths():
    root = Path(CODE_ROOT)
    return [root / TARGET, *sorted((root / "tests").glob(
        f"test_{TASK_ID.lower()}_*.py"))]


def cases(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from cases(item)
        else:
            yield item


@functools.lru_cache(maxsize=1)
def observe_current():
    """Один запуск текущих сценариев для AC-5–7, без подмены их исходов."""
    suite = unittest.TestSuite()
    for path in current_paths():
        module = importlib.import_module(f"tests.{path.stem}")
        suite.addTests(unittest.defaultTestLoader.loadTestsFromModule(module))
    identities = [case.id() for case in cases(suite)]
    roots, databases, caches, processes, launches, runs = [], [], [], [], [], []
    original_setup = TmpRootTest.setUp
    original_popen = subprocess.Popen
    original_full_suite = acceptance.full_suite
    outer_cache = os.environ.get("PYTHONPYCACHEPREFIX")
    real_root, real_db = config.ROOT, config.DB
    before_names = {p.name for p in Path(real_root).iterdir()}
    active = [""]

    class ObservedResult(unittest.TestResult):
        def startTest(self, test):
            active[0] = test.id()
            super().startTest(test)

    def setup(case):
        original_setup(case)
        roots.append(case.root)
        databases.append(Path(config.DB))

    def launch(argv, *args, **kwargs):
        env = kwargs.get("env", {})
        owns_cache = ("PYTHONPYCACHEPREFIX" in env
                      and env["PYTHONPYCACHEPREFIX"] != outer_cache)
        if owns_cache:
            caches.append(Path(env["PYTHONPYCACHEPREFIX"]))
        proc = original_popen(argv, *args, **kwargs)
        if owns_cache:
            processes.append(proc)
            entry = {"proc": proc, "argv": list(argv), "test": active[0],
                     "env": dict(env), "root": kwargs.get("cwd"),
                     "lock": suite_lock.held_by_me(), "communicate": [], "wait": []}
            launches.append(entry)
            if any("pytest" in str(arg) for arg in argv):
                original_communicate = proc.communicate
                original_wait = proc.wait

                def communicate(*args, **kwargs):
                    entry["communicate"].append(kwargs.get("timeout"))
                    return original_communicate(*args, **kwargs)

                def wait(*args, **kwargs):
                    entry["wait"].append(kwargs.get("timeout"))
                    return original_wait(*args, **kwargs)

                proc.communicate = communicate
                proc.wait = wait
        return proc

    def full_suite(root, task_id, *args, **kwargs):
        before = [r for r in store.task_steps(store.db(), task_id)
                  if r["action"] == "прогон: время"]
        offset = len(launches)
        result = original_full_suite(root, task_id, *args, **kwargs)
        after = [r for r in store.task_steps(store.db(), task_id)
                 if r["action"] == "прогон: время"]
        runs.append({"outcome": result.outcome, "added": len(after) - len(before),
                     "metrics": json.loads(after[-1]["detail"]) if after else {},
                     "launches": launches[offset:]})
        return result

    result = ObservedResult()
    with mock.patch.object(TmpRootTest, "setUp", setup), \
            mock.patch.object(subprocess, "Popen", launch), \
            mock.patch.object(acceptance, "full_suite", full_suite):
        suite.run(result)
    return {
        "result": result, "identities": identities,
        "runs": runs,
        "launches": launches,
        "roots": roots, "databases": databases, "caches": caches,
        "processes": processes, "real_root": real_root, "real_db": real_db,
        "restored_root": config.ROOT, "restored_db": config.DB,
        "new_root_entries": {p.name for p in Path(real_root).iterdir()} - before_names,
    }


def baseline_failures():
    """Задержка находится в настоящем timed child, после Popen."""
    module = types.ModuleType("baseline_suite_observation")
    exec(compile(SOURCE, "baseline_suite_observation.py", "exec"), module.__dict__)
    original = subprocess.Popen
    observations = []

    def launch(argv, *args, **kwargs):
        if "pytest" in argv:
            root = Path(kwargs["cwd"])
            red = "assert False" in (root / "tests" / "test_case.py").read_text()
            workers = int(argv[argv.index("-n") + 1]) if "-n" in argv else 1
            if red or workers == 2:
                command = [argv[0], "-c",
                           "import runpy,sys,time; time.sleep(4.2); "
                           "sys.argv[0]='pytest'; "
                           "runpy.run_module('pytest',run_name='__main__')",
                           *argv[argv.index("pytest") + 1:]]
                observations.append((red, workers))
                return original(command, *args, **kwargs)
        return original(argv, *args, **kwargs)

    results = []
    names = ("test_ac1_gate_writes_each_outcome_with_metrics",
             "test_gate_writes_workers_2_metrics")
    with mock.patch.object(subprocess, "Popen", launch):
        for name in names:
            result = unittest.TestResult()
            module.SuiteObservationTest(name).run(result)
            results.append(result)
    return results, observations


def assertion_inventory(source):
    """Нижняя граница количества утверждений каждого вида.

    Перенос в помощники, локальные имена и вынесение ожидаемых значений в
    переменные не меняют инвентаризацию. Значения и исходы проверяются
    исполнением сценариев; счётчик не объявляется доказательством полной
    семантической эквивалентности произвольных программ.
    """
    return collections.Counter(
        node.func.attr for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr.startswith("assert"))
