"""Прогоны pytest пульта отводят кеш байткода в отдельный временный каталог.

Три входа прогона — `acceptance.run`, `acceptance.collect`,
`acceptance.run_full_suite` — передают в `subprocess.run` окружение с
`PYTHONPYCACHEPREFIX`: устаревший `.pyc` из `__pycache__` рабочей копии
с совпавшими временем изменения и размером исходника не исполняется.

Группа: долгоживущий
Красен до реализации: вызовы subprocess.run в acceptance.py идут без env= — переменной PYTHONPYCACHEPREFIX нет, живой прогон исполняет подложенный байткод.
"""

import os
import random
import string
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import acceptance, config, stack
from tests.sandbox import TmpDirTest

PREFIX_VAR = "PYTHONPYCACHEPREFIX"

# Настоящий `subprocess.run`: подмена общая на модуль, и вызовы, не
# относящиеся к pytest (выбор интерпретатора в `stack`), идут сквозь неё.
REAL_RUN = subprocess.run

PASSING_TEST = """import unittest


class PlankTest(unittest.TestCase):
    def test_something(self):
        self.assertTrue(True)
"""


def _inside(path: str | Path, parent: str | Path) -> bool:
    """`path` лежит в `parent` (или совпадает с ним) после разрешения ссылок."""
    child = os.path.realpath(path)
    base = os.path.realpath(parent)
    return child == base or child.startswith(base.rstrip(os.sep) + os.sep)


class FakeRun:
    """Подмена `subprocess.run`: запоминает аргументы и состояние каталога
    кеша В МОМЕНТ вызова; по желанию бросает `TimeoutExpired`."""

    def __init__(self, timeout: bool = False):
        self.timeout = timeout
        self.calls: list[dict] = []

    def __call__(self, cmd, **kwargs):
        if "pytest" not in list(cmd):
            return REAL_RUN(cmd, **kwargs)
        env = kwargs.get("env")
        prefix = env.get(PREFIX_VAR) if env is not None else None
        self.calls.append({
            "cmd": list(cmd),
            "cwd": kwargs.get("cwd"),
            "env": dict(env) if env is not None else None,
            "prefix": prefix,
            "prefix_is_dir": bool(prefix) and Path(prefix).is_dir(),
        })
        if self.timeout:
            raise subprocess.TimeoutExpired(cmd, 1, output="", stderr="")
        return subprocess.CompletedProcess(cmd, 0, "1 passed in 0.01s", "")


class PycachePrefixTest(TmpDirTest):
    """Три входа прогона на подменённом `subprocess.run`."""

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 32)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)
        self.code = self.tdir / "code"
        (self.code / "tests").mkdir(parents=True)
        (self.code / "tests" / "test_marker.py").write_text(
            PASSING_TEST, encoding="utf-8")
        self.task = self.tdir / "task"
        (self.task / "acceptance_tests").mkdir(parents=True)
        (self.task / "acceptance_tests" / "test_ac.py").write_text(
            PASSING_TEST, encoding="utf-8")

    def entries(self):
        """(имя, вызов, ожидаемый cwd прогона) — все три входа; `run` и
        `collect` — и с явным `cwd`, и с `cwd=None` (тогда `config.ROOT`)."""
        return [
            ("run", lambda: acceptance.run(self.task, cwd=self.code), self.code),
            ("run(cwd=None)", lambda: acceptance.run(self.task), config.ROOT),
            ("collect", lambda: acceptance.collect(self.task, cwd=self.code),
             self.code),
            ("collect(cwd=None)", lambda: acceptance.collect(self.task),
             config.ROOT),
            ("run_full_suite", lambda: acceptance.run_full_suite(self.code),
             self.code),
        ]

    def call(self, invoke, timeout: bool = False) -> dict:
        fake = FakeRun(timeout=timeout)
        with mock.patch.object(acceptance.subprocess, "run", side_effect=fake):
            invoke()
        # Подмена общая на модуль subprocess: выбор интерпретатора в
        # `stack` тоже может звать его — берём только вызов pytest.
        pytest_calls = [c for c in fake.calls if "pytest" in c["cmd"]]
        self.assertEqual(len(pytest_calls), 1,
                         f"ожидался один вызов pytest, зерно {self.seed}: "
                         f"{[c['cmd'] for c in fake.calls]}")
        return pytest_calls[0]

    def test_ac1_every_entry_passes_env_with_pycache_prefix(self):
        """Каждый вход прогона отдаёт `subprocess.run` окружение с переменной кеша.

        `run`, `collect` (с явным `cwd` и без него) и `run_full_suite`
        зовутся на подменённом `subprocess.run`; у каждого вызова аргумент
        `env` есть и в нём непустой `PYTHONPYCACHEPREFIX`.

        Ловит мутацию: `env=` передан в `run`, но забыт в `collect` или
        `run_full_suite` — у того вызова `env` равен `None`, тест краснеет
        с именем входа.
        """
        for name, invoke, _cwd in self.entries():
            with self.subTest(entry=name):
                call = self.call(invoke)
                self.assertIsNotNone(call["env"], f"{name}: env не передан")
                self.assertTrue(call["prefix"],
                                f"{name}: в env нет {PREFIX_VAR}")

    def test_ac2_other_variables_match_process_environment(self):
        """Окружение прогона — то же окружение пульта плюс одна переменная кеша.

        В окружение процесса на время вызова добавляются случайные
        переменные (зерно печатается); в `env` каждого из трёх вызовов все
        ключи, кроме `PYTHONPYCACHEPREFIX`, совпадают с `os.environ` по
        составу и значениям.

        Ловит мутацию: окружение собрано с нуля (`env={PYTHONPYCACHEPREFIX:
        …}`) или к нему заодно добавлен `PYTHONDONTWRITEBYTECODE` — ключи
        пропали или появился лишний, сравнение с `os.environ` краснеет.
        """
        for name, invoke, _cwd in self.entries():
            extra = {
                "ARTEL_PROBE_" + "".join(self.rng.choices(
                    string.ascii_uppercase, k=8)): "".join(self.rng.choices(
                        string.ascii_letters + string.digits, k=12))
                for _ in range(self.rng.randint(1, 4))}
            with self.subTest(entry=name), mock.patch.dict(os.environ, extra):
                expected = {k: v for k, v in os.environ.items()
                            if k != PREFIX_VAR}
                call = self.call(invoke)
                self.assertIsNotNone(call["env"], f"{name}: env не передан")
                got = {k: v for k, v in call["env"].items() if k != PREFIX_VAR}
                self.assertEqual(
                    got, expected,
                    f"{name}: env расходится с os.environ, зерно {self.seed}")

    def test_ac3_cache_dir_exists_outside_cwd_and_root_during_call(self):
        """Каталог кеша существует в момент вызова и лежит вне `cwd` и `config.ROOT`.

        Подмена `subprocess.run` смотрит на каталог из `PYTHONPYCACHEPREFIX`
        в момент вызова: он есть на диске, не вложен в `cwd` прогона и не
        вложен в корень пульта — для всех трёх входов, включая `cwd=None`.

        Ловит мутацию: каталог кеша заведён внутри рабочей копии
        (`cwd / ".pycache"`) или только назван, но не создан — проверка
        вложенности или существования в момент вызова краснеет.
        """
        for name, invoke, cwd in self.entries():
            with self.subTest(entry=name):
                call = self.call(invoke)
                prefix = call["prefix"]
                self.assertTrue(prefix, f"{name}: в env нет {PREFIX_VAR}")
                self.assertTrue(call["prefix_is_dir"],
                                f"{name}: каталога {prefix} нет во время вызова")
                self.assertTrue(os.path.realpath(call["cwd"])
                                == os.path.realpath(cwd),
                                f"{name}: cwd прогона {call['cwd']}, ждали {cwd}")
                self.assertFalse(_inside(prefix, cwd),
                                 f"{name}: {prefix} внутри cwd {cwd}")
                self.assertFalse(_inside(prefix, config.ROOT),
                                 f"{name}: {prefix} внутри {config.ROOT}")

    def test_ac4_cache_dir_removed_after_return_and_after_timeout(self):
        """После возврата каждого входа каталога кеша нет — и после таймаута тоже.

        Каждый из трёх входов зовётся дважды: подмена возвращает обычный
        результат и подмена бросает `subprocess.TimeoutExpired`. Каталог,
        существовавший в момент вызова, после возврата функции удалён;
        разным прогонам достаются разные каталоги.

        Ловит мутацию: каталог создаётся `tempfile.mkdtemp()` без удаления
        либо удаляется только на успешной ветке, а ветка `except
        TimeoutExpired` возвращает раньше уборки — каталог остаётся на
        диске.
        """
        seen: list[str] = []
        for name, invoke, _cwd in self.entries():
            for timeout in (False, True):
                with self.subTest(entry=name, timeout=timeout):
                    call = self.call(invoke, timeout=timeout)
                    prefix = call["prefix"]
                    self.assertTrue(prefix, f"{name}: в env нет {PREFIX_VAR}")
                    self.assertTrue(call["prefix_is_dir"],
                                    f"{name}: каталога {prefix} нет во время вызова")
                    self.assertFalse(Path(prefix).exists(),
                                     f"{name} (таймаут={timeout}): каталог "
                                     f"{prefix} не удалён после возврата")
                    self.assertNotIn(prefix, seen,
                                     f"{name}: каталог кеша переиспользован")
                    seen.append(prefix)

    def test_ac5_full_suite_xdist_call_carries_pycache_prefix(self):
        """Вызов полного набора с xdist несёт переменную кеша в `env`.

        `run_full_suite` зовётся на подменённом `subprocess.run`; в команде
        есть `-n` и `-p xdist`, и тот же вызов получает `env` с
        `PYTHONPYCACHEPREFIX` — рабочие процессы xdist наследуют его от
        главного процесса pytest.

        Ловит мутацию: `env=` передан в `run`/`collect`, а ветка полного
        набора с `-n … -p xdist` оставлена без него — `env` вызова равен
        `None`.
        """
        workers = self.rng.randint(1, 8)
        with mock.patch.object(config, "FULL_SUITE_WORKERS", workers):
            call = self.call(lambda: acceptance.run_full_suite(self.code))
        cmd = call["cmd"]
        self.assertIn("-n", cmd, cmd)
        p_values = [cmd[i + 1] for i, tok in enumerate(cmd)
                    if tok == "-p" and i + 1 < len(cmd)]
        self.assertIn("xdist", p_values, cmd)
        self.assertIsNotNone(call["env"], "env не передан вызову с xdist")
        self.assertTrue(call["prefix"], f"в env вызова с xdist нет {PREFIX_VAR}")


class StaleBytecodeLiveTest(TmpDirTest):
    """Живой прогон `acceptance.run` без подмены `subprocess.run`."""

    def cache_tag(self) -> str:
        res = subprocess.run(
            [stack.pytest_python_executable(), "-c",
             "import sys; print(sys.implementation.cache_tag)"],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(res.returncode, 0, res.stderr)
        return res.stdout.strip()

    def compile_stale(self, source: Path, cfile: Path) -> None:
        """`.pyc` от текущего содержимого `source` — тем же интерпретатором,
        которым пульт гоняет pytest, с проверкой по времени и размеру."""
        script = ("import py_compile, sys\n"
                  "py_compile.compile(sys.argv[1], cfile=sys.argv[2], "
                  "doraise=True, invalidation_mode="
                  "py_compile.PycInvalidationMode.TIMESTAMP)\n")
        res = subprocess.run(
            [stack.pytest_python_executable(), "-c", script,
             str(source), str(cfile)],
            capture_output=True, text=True, timeout=60)
        self.assertEqual(res.returncode, 0, res.stderr)

    def test_ac6_stale_pyc_with_same_mtime_and_size_is_not_executed(self):
        """Подложенный `.pyc` другой версии модуля не исполняется прогоном пульта.

        Во временном каталоге модуль и тест к нему; в `__pycache__` лежит
        `.pyc` от другой версии модуля с тем же временем изменения и тем же
        размером исходника (случай 02.10). Значения версий случайны (зерно
        печатается). `acceptance.run` по этому каталогу зелёный: тест видит
        актуальный исходник.

        Ловит мутацию: `PYTHONPYCACHEPREFIX` убран из окружения прогона —
        интерпретатор берёт подложенный байткод, тест модуля видит старое
        значение и `acceptance.run` отдаёт красный результат.
        """
        seed = random.randrange(1 << 32)
        print(f"зерно: {seed}")
        rng = random.Random(seed)
        alphabet = string.ascii_lowercase
        old = "".join(rng.choices(alphabet, k=16))
        new = old
        while new == old:
            new = "".join(rng.choices(alphabet, k=16))
        module = f"stale_probe_{''.join(rng.choices(alphabet, k=8))}"

        task = self.tdir / "task"
        tests_dir = task / "acceptance_tests"
        tests_dir.mkdir(parents=True)
        source = tests_dir / f"{module}.py"
        source.write_text(f'VALUE = "{old}"\n', encoding="utf-8")
        pycache = tests_dir / "__pycache__"
        pycache.mkdir()
        self.compile_stale(source, pycache / f"{module}.{self.cache_tag()}.pyc")
        stat = source.stat()
        source.write_text(f'VALUE = "{new}"\n', encoding="utf-8")
        os.utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns))
        self.assertEqual(source.stat().st_size, stat.st_size)
        self.assertEqual(int(source.stat().st_mtime), int(stat.st_mtime))
        (tests_dir / "test_stale_probe.py").write_text(
            f"import unittest\n\nimport {module}\n\n\n"
            "class StaleProbeTest(unittest.TestCase):\n"
            "    def test_reads_current_source(self):\n"
            f'        self.assertEqual({module}.VALUE, "{new}")\n',
            encoding="utf-8")
        cwd = self.tdir / "cwd"
        cwd.mkdir()

        green, tail = acceptance.run(task, cwd=cwd)

        self.assertTrue(green, f"зерно {seed}: прогон исполнил подложенный "
                               f"байткод\n{tail}")


if __name__ == "__main__":
    unittest.main()
