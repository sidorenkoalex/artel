"""Юнит-тесты отведения кеша байткода прогонов pytest пульта
(`orchestrator/acceptance.py::_pytest_env`, SPEC 01M3Y7G6T3MK7A899521VF9N7B).

Сценарии AC-1…AC-6 (переменная `PYTHONPYCACHEPREFIX` в `env` у
`acceptance.run`, `acceptance.collect`, `acceptance.run_full_suite`,
каталог вне `cwd`/`config.ROOT`, уборка после `subprocess.TimeoutExpired`,
xdist, живой прогон с подложенным `.pyc`) держит долгоживущий файл
`tests/test_01m3y7g6t3mk7a899521vf9n7b_pycache.py`. Здесь — свойства,
которые он не покрывает: уборка каталога после исключения, отличного от
таймаута, перекрытие уже заданной в окружении пульта переменной и
неизменность `os.environ` самого пульта.
"""
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import acceptance  # noqa: E402
from tests.sandbox import TmpDirTest  # noqa: E402

PREFIX_VAR = "PYTHONPYCACHEPREFIX"

PASSING_TEST = """import unittest


class MarkerTest(unittest.TestCase):
    def test_always_passes(self):
        self.assertTrue(True)
"""

REAL_RUN = subprocess.run


class _RecordingRun:
    """Подмена `subprocess.run`: вызов pytest записывает `env` и
    существование каталога кеша в момент вызова, затем отдаёт `outcome`
    (исключение бросает); прочие вызовы идут в настоящий `subprocess.run`."""

    def __init__(self, outcome):
        self.outcome = outcome
        self.envs: list[dict] = []
        self.dir_existed: list[bool] = []

    def __call__(self, cmd, **kwargs):
        if "pytest" not in list(cmd):
            return REAL_RUN(cmd, **kwargs)
        env = kwargs.get("env") or {}
        self.envs.append(dict(env))
        prefix = env.get(PREFIX_VAR)
        self.dir_existed.append(bool(prefix) and Path(prefix).is_dir())
        if isinstance(self.outcome, BaseException):
            raise self.outcome
        return subprocess.CompletedProcess(cmd, 0, "1 passed in 0.01s", "")


class PytestEnvTest(TmpDirTest):

    def setUp(self):
        super().setUp()
        self.code = self.tdir / "code"
        (self.code / "tests").mkdir(parents=True)
        (self.code / "tests" / "test_marker.py").write_text(
            PASSING_TEST, encoding="utf-8")
        self.task = self.tdir / "task"
        (self.task / "acceptance_tests").mkdir(parents=True)
        (self.task / "acceptance_tests" / "test_ac.py").write_text(
            PASSING_TEST, encoding="utf-8")

    def entries(self):
        return [
            ("acceptance.run",
             lambda: acceptance.run(self.task, cwd=self.code)),
            ("acceptance.collect",
             lambda: acceptance.collect(self.task, cwd=self.code)),
            ("acceptance.run_full_suite",
             lambda: acceptance.run_full_suite(self.code)),
        ]

    def test_cache_dir_removed_after_non_timeout_exception(self):
        """Каталог кеша убран и тогда, когда `subprocess.run` бросил не
        `TimeoutExpired`, а иное исключение (интерпретатора нет —
        `FileNotFoundError`); само исключение доходит до вызывающего.

        Ловит мутацию: уборка каталога вписана только в ветку `except
        subprocess.TimeoutExpired` и в успешный путь, а не в `finally`/
        контекстный менеджер — на `FileNotFoundError` каталог остаётся на
        диске."""
        for name, invoke in self.entries():
            with self.subTest(entry=name):
                fake = _RecordingRun(FileNotFoundError("python нет"))
                with mock.patch.object(acceptance.subprocess, "run",
                                       side_effect=fake):
                    with self.assertRaises(FileNotFoundError):
                        invoke()
                self.assertEqual(len(fake.envs), 1, name)
                prefix = fake.envs[0].get(PREFIX_VAR)
                self.assertTrue(prefix, f"{name}: в env нет {PREFIX_VAR}")
                self.assertTrue(fake.dir_existed[0],
                                f"{name}: каталога не было во время вызова")
                self.assertFalse(Path(prefix).exists(),
                                 f"{name}: каталог {prefix} не удалён")

    def test_existing_prefix_in_pult_environment_is_overridden(self):
        """Переменная, уже заданная в окружении пульта (например, на
        `__pycache__` внутри worktree), заменяется свежим каталогом прогона;
        `os.environ` пульта после прогона прежний — и на успешном пути, и
        после `subprocess.TimeoutExpired`.

        Ловит мутацию: окружение собрано `env.setdefault(PYTHONPYCACHEPREFIX,
        …)` (унаследованное значение побеждает) либо переменная пишется прямо
        в `os.environ` вместо копии — в `env` вызова старое значение или
        `os.environ` после возврата изменён."""
        inherited = str(self.code / "__pycache_shared__")
        for name, invoke in self.entries():
            for outcome in (None, subprocess.TimeoutExpired(["pytest"], 1)):
                with self.subTest(entry=name, timeout=outcome is not None), \
                     mock.patch.dict(os.environ, {PREFIX_VAR: inherited}):
                    before = dict(os.environ)
                    fake = _RecordingRun(outcome)
                    with mock.patch.object(acceptance.subprocess, "run",
                                           side_effect=fake):
                        invoke()
                    prefix = fake.envs[0].get(PREFIX_VAR)
                    self.assertTrue(prefix)
                    self.assertNotEqual(prefix, inherited,
                                        f"{name}: унаследован {inherited}")
                    self.assertTrue(fake.dir_existed[0], name)
                    self.assertEqual(dict(os.environ), before,
                                     f"{name}: os.environ пульта изменён")

    def test_cleanup_retries_when_late_writer_blocks_rmtree(self):
        """Первая попытка удалить каталог кеша падает `OSError` («Directory
        not empty» — рабочий процесс xdist дописал `.pyc` после таймаута);
        уборка повторяет попытку, каталог удалён, а `acceptance.run_full_suite`
        отдаёт свой исход таймаута, а не исключение уборки.

        Ловит мутацию: один `shutil.rmtree` без повтора (или без перехвата
        `OSError`) — исключение уборки подменяет исход прогона либо каталог
        остаётся на диске."""
        real_rmtree = acceptance.shutil.rmtree
        failures = {"left": 1}

        def flaky_rmtree(path, *args, **kwargs):
            if failures["left"] and not kwargs.get("ignore_errors"):
                failures["left"] -= 1
                raise OSError(66, "Directory not empty", path)
            return real_rmtree(path, *args, **kwargs)

        fake = _RecordingRun(subprocess.TimeoutExpired(["pytest"], 1))
        with mock.patch.object(acceptance.subprocess, "run", side_effect=fake), \
             mock.patch.object(acceptance.shutil, "rmtree",
                               side_effect=flaky_rmtree), \
             mock.patch.object(acceptance, "_CACHE_RMTREE_PAUSE_SEC", 0):
            green, output = acceptance.run_full_suite(self.code)
        self.assertFalse(green)
        self.assertIn("превысил", output)
        self.assertEqual(failures["left"], 0, "уборка не дошла до rmtree")
        prefix = fake.envs[0][PREFIX_VAR]
        self.assertFalse(Path(prefix).exists(), f"каталог {prefix} не удалён")


if __name__ == "__main__":
    unittest.main()
