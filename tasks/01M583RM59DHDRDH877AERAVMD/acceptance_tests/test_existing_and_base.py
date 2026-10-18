"""Факты задачи: прежние тесты не ослаблены, база красна по нужной причине.

Группа: разовый
Красен до реализации: на базе AC-1 раннего окна красен и на HEAD (AC-9), а test_ac1–test_ac3 `CanaryLifecycleTest` ещё не проверяют живость ведения и suite до сигнала — с коротким ведением они зелёные (AC-12); AC-6, AC-7, AC-10 зелёные с рождения — они держат прежние тесты и уборку теста.

Сверка методов — разбором AST файла рабочей копии и того же файла в базе
диффа задачи (`DIFF_BASE` помощника пульта); прогон — pytest/unittest в
отдельном процессе. Дерево базы для AC-9/AC-10 — `git archive DIFF_BASE`
во временный каталог с долгоживущим файлом раннего окна из рабочей копии.
"""

import ast
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, DIFF_BASE  # noqa: E402

ROOT = Path(CODE_ROOT)
LIFECYCLE = "tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py"
LIFECYCLE_MODULE = "tests.test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle"
DRIVE_TESTS = "tests/test_canary_drive.py"
MARKER_TESTS = "tests/test_01m4beg0003ch0qa1gy0pxat03_clone_marker.py"
EARLY = "tests/test_01m583rm59dhdrdh877aeravmd_early_signal.py"
EARLY_AC1 = ("tests.test_01m583rm59dhdrdh877aeravmd_early_signal."
             "EarlySignalCanaryTest."
             "test_ac1_sigterm_sighup_in_early_window_stop_drive_and_record_signal")
UNCHANGED_AC7 = [
    (MARKER_TESTS, "CanaryCloneMarkerTest", "test_clone_launch_passes_marker_to_child"),
    (DRIVE_TESTS, "InterruptedPultTest",
     "test_interrupt_while_waiting_kills_the_clone_process_group"),
    (DRIVE_TESTS, "CloneProcessFailureTest", "test_hanging_process_is_killed_after_the_limit"),
    (DRIVE_TESTS, "CloneProcessFailureTest",
     "test_output_of_a_killed_process_is_not_lost_in_its_buffer"),
    (DRIVE_TESTS, "CloneCodeDrivesTheTaskTest",
     "test_process_is_launched_from_the_clone_with_the_result_path"),
    (DRIVE_TESTS, "CloneCodeDrivesTheTaskTest",
     "test_process_does_not_receive_a_pult_codex_home_override"),
]
WEAKENING_NAMES = {"skip", "skipIf", "skipUnless", "SkipTest", "expectedFailure",
                   "xfail", "flaky", "reruns", "retry"}
PYTEST = [sys.executable, "-m", "pytest", "-p", "no:cacheprovider",
          "-p", "timeout", "-o", "timeout=120", "-q", "-rA"]


def base_source(rel: str) -> str:
    res = subprocess.run(["git", "-C", str(ROOT), "show", f"{DIFF_BASE}:{rel}"],
                         capture_output=True, text=True)
    if res.returncode != 0:
        raise AssertionError(f"git show {DIFF_BASE}:{rel}: {res.stderr}")
    return res.stdout


def head_source(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def find_class(tree: ast.Module, name: str) -> ast.ClassDef:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == name:
            return node
    raise AssertionError(f"класса {name} нет")


def find_method(cls: ast.ClassDef, name: str):
    for node in cls.body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def body_without_docstring(fn: ast.FunctionDef) -> str:
    body = fn.body
    if (body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        body = body[1:]
    return "\n".join(ast.dump(stmt) for stmt in body)


def assert_calls(fn: ast.FunctionDef) -> list[str]:
    return [ast.dump(node) for node in ast.walk(fn)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr.startswith("assert")]


def summary_line(output: str) -> str:
    lines = [line for line in output.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def living_groups(pgids) -> list[int]:
    search = os.pathsep.join([os.environ.get("PATH", ""), "/bin", "/usr/bin"])
    res = subprocess.run([shutil.which("ps", path=search) or "ps",
                          "-A", "-o", "pgid=,stat="],
                         capture_output=True, text=True, timeout=30, check=True)
    alive = set()
    for line in res.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and not parts[1].startswith("Z"):
            alive.add(int(parts[0]))
    return [g for g in pgids if g in alive]


class ExistingLifecycleTestsKeptTest(unittest.TestCase):
    def test_ac6_lifecycle_tests_same_methods_limit_and_signal_point(self):
        """`CanaryLifecycleTest` после задачи: те же методы, утверждения, предел 20 с и точка сигнала; прогон зелёный без пропусков.

        Тела методов `test_*` класса (без докстрингов) совпадают с базой;
        утверждения базового `assert_signal_cleanup` все на месте;
        `launch_signalled` по-прежнему ждёт файл наблюдения не дольше 20 с и
        только после этого ожидания шлёт `os.kill(child.pid, signum)`; в файле
        нет пропусков, `xfail`, повторов; pytest класса — код 0 без skipped/xfailed.

        Ловит мутацию: разработчик подгоняет общий помощник — поднимает предел ожидания до 60 с, переносит `os.kill` в подменённый `Popen` или помечает метод `expectedFailure` — сверка AST или итог pytest это показывают.
        """
        self.assertTrue(DIFF_BASE, "база диффа задачи не вычислена")
        base = find_class(ast.parse(base_source(LIFECYCLE)), "CanaryLifecycleTest")
        head_tree = ast.parse(head_source(LIFECYCLE))
        head = find_class(head_tree, "CanaryLifecycleTest")
        base_tests = [n for n in base.body
                      if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]
        self.assertTrue(base_tests)
        for fn in base_tests:
            with self.subTest(method=fn.name):
                now = find_method(head, fn.name)
                self.assertIsNotNone(now, f"метод {fn.name} пропал")
                self.assertEqual(body_without_docstring(now), body_without_docstring(fn),
                                 f"тело {fn.name} изменено")
        cleanup_now = find_method(head, "assert_signal_cleanup")
        self.assertIsNotNone(cleanup_now)
        kept = assert_calls(cleanup_now)
        for call in assert_calls(find_method(base, "assert_signal_cleanup")):
            self.assertIn(call, kept, "утверждение assert_signal_cleanup снято")
        launch = find_method(head, "launch_signalled")
        self.assertIsNotNone(launch)
        numbers = [n.value for n in ast.walk(launch)
                   if isinstance(n, ast.Constant) and isinstance(n.value, (int, float))
                   and not isinstance(n.value, bool)]
        self.assertIn(20, numbers, "предел 20 с пропал")
        self.assertFalse([v for v in numbers if v > 20], f"предел вырос: {numbers}")
        waits = [n for n in ast.walk(launch) if isinstance(n, ast.While)
                 and "observation" in ast.dump(n.test) and "exists" in ast.dump(n.test)]
        self.assertTrue(waits, "ожидания файла наблюдения нет")
        kills = [n for n in ast.walk(launch) if isinstance(n, ast.Call)
                 and ast.unparse(n.func) == "os.kill" and n.args
                 and ast.unparse(n.args[0]) == "child.pid"]
        self.assertTrue(kills, "сигнал процессу теста команде не посылается")
        self.assertTrue(all(k.lineno > waits[0].lineno for k in kills),
                        "сигнал посылается до появления файла наблюдения")
        used = {n.id for n in ast.walk(head_tree) if isinstance(n, ast.Name)} | \
               {n.attr for n in ast.walk(head_tree) if isinstance(n, ast.Attribute)}
        self.assertFalse(used & WEAKENING_NAMES, f"ослабление: {used & WEAKENING_NAMES}")
        res = subprocess.run(PYTEST + [f"{LIFECYCLE}::CanaryLifecycleTest"], cwd=ROOT,
                             capture_output=True, text=True, timeout=600)
        tail = summary_line(res.stdout)
        self.assertEqual(res.returncode, 0, res.stdout[-4000:] + res.stderr[-2000:])
        for word in ("skipped", "xfailed", "xpassed", "rerun", "failed", "error"):
            self.assertNotIn(word, tail, tail)

    def test_ac7_other_canary_drive_methods_unchanged_and_green(self):
        """Шесть названных методов не правлены и проходят.

        Каждый метод (целиком, с докстрингом) совпадает с базой по AST, а
        pytest по их адресам проходит с кодом 0 без пропусков.

        Ловит мутацию: правка `_drive_in_clone` ломает `CanaryCloneMarkerTest` (объект `Popen` без `pid` либо вызов вне `_interrupt_on_signal` даёт `AttributeError`/ошибку `signal`), а разработчик «чинит» метод теста — AST расходится с базой, либо без правки метода pytest красный.
        """
        self.assertTrue(DIFF_BASE, "база диффа задачи не вычислена")
        nodes = []
        for rel, cls, method in UNCHANGED_AC7:
            with self.subTest(method=f"{cls}::{method}"):
                was = find_method(find_class(ast.parse(base_source(rel)), cls), method)
                now = find_method(find_class(ast.parse(head_source(rel)), cls), method)
                self.assertIsNotNone(was, f"{cls}::{method} нет в базе")
                self.assertIsNotNone(now, f"{cls}::{method} пропал")
                self.assertEqual(ast.dump(now), ast.dump(was), f"{cls}::{method} правлен")
            nodes.append(f"{rel}::{cls}::{method}")
        res = subprocess.run(PYTEST + nodes, cwd=ROOT, capture_output=True, text=True,
                             timeout=600)
        tail = summary_line(res.stdout)
        self.assertEqual(res.returncode, 0, res.stdout[-4000:] + res.stderr[-2000:])
        self.assertIn(f"{len(nodes)} passed", tail, tail)
        for word in ("skipped", "xfailed", "rerun", "failed", "error"):
            self.assertNotIn(word, tail, tail)


_SHORT_PREFIX = '''
import subprocess as _ac12_subprocess
_ac12_real_popen = _ac12_subprocess.Popen
def _ac12_popen(argv, *args, **kwargs):
    proc = _ac12_real_popen(argv, *args, **kwargs)
    if isinstance(argv, (list, tuple)) and any("ac12-short" in str(a) for a in argv):
        proc.wait()
    return proc
_ac12_subprocess.Popen = _ac12_popen
'''

_MUTANT_RUNNER = r'''
import json, re, sys, unittest
import importlib
module = importlib.import_module(sys.argv[1])
prefix = sys.argv[2]
names = sys.argv[3:]
source, count = re.subn(r"time\.sleep\(\s*\d+(?:\.\d+)?\s*\)",
                        "time.sleep(0)  # ac12-short", module._CHILD)
print("AC12-REPLACED " + str(count), flush=True)
if count < 2:
    sys.exit(3)
module._CHILD = prefix + source
suite = unittest.TestSuite(module.CanaryLifecycleTest(name) for name in names)
result = unittest.TextTestRunner(verbosity=2, stream=sys.stdout).run(suite)
bad = [str(test) for test, _ in result.failures + result.errors]
print("AC12-RESULT " + json.dumps({"bad": bad, "run": result.testsRun}), flush=True)
'''


class ShortLivedFixtureTurnsLifecycleRedTest(unittest.TestCase):
    def test_ac12_short_lived_drive_and_suite_make_ac1_to_ac3_red(self):
        """С коротким самозавершающимся ведением и suite test_ac1–test_ac3 краснеют.

        В отдельном процессе у модуля `CanaryLifecycleTest` подменяется общий
        `_CHILD`: каждое `time.sleep(N)` подменённых suite и ведения → `sleep(0)`,
        а созданный такой процесс дожидается своего конца до возврата. Тогда
        до сигнала ни ведение, ни suite не живы — каждый из test_ac1, test_ac2,
        test_ac3 обязан упасть; а без подмены (AC-6) они зелёные.

        Ловит мутацию: живость до сигнала не проверяется в общем пути `launch_signalled`/`assert_signal_cleanup` — test_ac1 и test_ac2 с мгновенно завершившимися процессами проходят: «не живы после сигнала» верно и без сигнала.
        """
        names = ["test_ac1_sigterm_cleans_clone_origin_and_both_process_groups",
                 "test_ac2_sighup_cleans_clone_origin_and_both_process_groups",
                 "test_ac3_signal_records_non_green_existing_verdict"]
        res = subprocess.run([sys.executable, "-c", _MUTANT_RUNNER, LIFECYCLE_MODULE,
                              _SHORT_PREFIX] + names, cwd=ROOT, capture_output=True,
                             text=True, timeout=600)
        out = res.stdout + res.stderr
        self.assertIn("AC12-REPLACED", out, out[-3000:])
        replaced = int(re.search(r"AC12-REPLACED (\d+)", out).group(1))
        self.assertGreaterEqual(replaced, 2, "подменённые suite и ведение не на time.sleep")
        found = re.search(r"AC12-RESULT (\{.*\})", out)
        self.assertIsNotNone(found, out[-3000:])
        verdict = json.loads(found.group(1))
        self.assertEqual(verdict["run"], len(names), verdict)
        for name in names:
            with self.subTest(method=name):
                self.assertTrue(any(name in bad for bad in verdict["bad"]),
                                f"{name} зелёный с коротким ведением; {out[-3000:]}")


class BaseTreeEarlySignalTest(unittest.TestCase):
    """Тест AC-1 раннего окна на дереве базы диффа задачи."""

    @classmethod
    def setUpClass(cls):
        cls.base_dir = Path(tempfile.mkdtemp(prefix="early-signal-base-"))
        archive = subprocess.run(["git", "-C", str(ROOT), "archive", "--format=tar",
                                  str(DIFF_BASE), "orchestrator", "tests", "scripts"],
                                 capture_output=True)
        if archive.returncode != 0:
            raise AssertionError(archive.stderr.decode(errors="replace"))
        with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
            tar.extractall(cls.base_dir, filter="data")
        shutil.copy2(ROOT / EARLY, cls.base_dir / EARLY)
        env = {**os.environ, "PYTHONPATH": str(cls.base_dir)}
        cls.base_run = subprocess.run([sys.executable, "-m", "unittest", "-v", EARLY_AC1],
                                      cwd=cls.base_dir, env=env, capture_output=True,
                                      text=True, timeout=300)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.base_dir, ignore_errors=True)

    def test_ac9_early_sigterm_red_on_base_for_live_drive_green_at_head(self):
        """AC-1 раннего окна на базе красен именно из-за живого ведения, на HEAD — зелёный.

        На дереве `DIFF_BASE` с долгоживущим файлом из рабочей копии тест
        падает с текстом «SIGTERM: процесс ведения жив»; тот же тест на
        рабочей копии проходит.

        Ловит мутацию: правка не закрывает окно для SIGTERM (откладывание только SIGHUP) — прогон на HEAD красный; либо тест раннего окна шлёт сигнал не в окне — на базе он зелёный или падает по другой причине.
        """
        self.assertTrue(DIFF_BASE, "база диффа задачи не вычислена")
        base_out = self.base_run.stdout + self.base_run.stderr
        self.assertNotEqual(self.base_run.returncode, 0, base_out[-4000:])
        self.assertIn("SIGTERM: процесс ведения жив", base_out, base_out[-4000:])
        head = subprocess.run([sys.executable, "-m", "unittest", "-v", EARLY_AC1],
                              cwd=ROOT, capture_output=True, text=True, timeout=300)
        self.assertEqual(head.returncode, 0, (head.stdout + head.stderr)[-4000:])

    def test_ac10_base_red_run_leaves_no_living_recorded_groups(self):
        """После красного прогона AC-1 на базе живых процессов записанных групп нет.

        Из вывода прогона базы берутся файлы наблюдения («наблюдение: {...}»)
        с pgid ведения и suite; после выхода процесса unittest ни в одной из
        этих групп нет живых процессов — уборка теста их сняла и дождалась.

        Ловит мутацию: уборка теста раннего окна не зарегистрирована или шлёт SIGKILL без ожидания — выжившее на базе ведение `sleep 90` остаётся в своей группе после выхода прогона.
        """
        out = self.base_run.stdout + self.base_run.stderr
        groups = set()
        for found in re.finditer(r"наблюдение: (\{.*\})", out):
            state = json.loads(found.group(1))
            groups.update(state[k] for k in ("drive_pgid", "suite_pgid") if state.get(k))
        self.assertTrue(groups, out[-4000:])
        self.assertEqual(living_groups(sorted(groups)), [], out[-4000:])


if __name__ == "__main__":
    unittest.main()
