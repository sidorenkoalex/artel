"""Юнит-тесты самовыбора интерпретатора `orchestrator/artel.py` (SPEC
01M1SHK3MD4ZF9NYXSCT67J8AP, требования 1-6, 8-9).

Регрессия постоянная — переживает закрытие
tasks/01M1SHK3MD4ZF9NYXSCT67J8AP/acceptance_tests/, которые проверяют то
же самое подробнее (AC-1..AC-9), но живут только пока задача открыта.
Реальный интерпретатор ниже REQUIRED_PYTHON в этой песочнице недоступен —
`sys.version_info`/`os.execv` подменяются тем же приёмом, что и
`tests/test_stack.py::CheckStackTest`, а `orchestrator.artel` перегружается
`importlib.reload` (её top-level код исполняет проверку версии безусловно,
одинаково для `python3 orchestrator/artel.py`, `python3 -m
orchestrator.artel` и простого импорта).
"""
import importlib
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import artel, config, stack  # noqa: E402

OLD_VERSION_INFO = (3, 9, 0, "final", 0)


class _FakeExecvInvoked(Exception):
    """`os.execv` заменил бы образ процесса — тест обязан остановиться
    здесь же, а не продолжать module-level код перезагрузки."""


def _make_fake_venv(tmp_path: Path) -> Path:
    venv_dir = tmp_path / "venv"
    bin_dir = venv_dir / "bin"
    bin_dir.mkdir(parents=True)
    os.symlink(sys.executable, bin_dir / "python")
    return venv_dir


class _ArtelReloadTestCase(unittest.TestCase):

    def tearDown(self):
        importlib.reload(artel)
        super().tearDown()


class RequiredPythonReadFromStackTest(_ArtelReloadTestCase):

    def test_threshold_tracks_stack_required_python(self):
        """AC-2: точка входа читает порог прямым импортом `stack.py`, не
        собственную зашитую копию — подмена `stack.REQUIRED_PYTHON`
        обязана изменить решение точки входа."""
        with mock.patch.object(stack, "REQUIRED_PYTHON", (999, 0)), \
             mock.patch.object(config, "VENV_DIR",
                               Path(tempfile.mkdtemp()) / "no-venv-here",
                               create=True):
            buf = io.StringIO()
            with redirect_stderr(buf):
                with self.assertRaises(SystemExit) as ctx:
                    importlib.reload(artel)
        self.assertEqual(2, ctx.exception.code)
        self.assertIn("999", buf.getvalue())


class OldInterpreterWithUsableVenvTest(_ArtelReloadTestCase):

    def test_reexecs_via_os_execv_with_marker(self):
        """AC-3/AC-8: venv пригоден, маркера ещё нет — `os.execv` тем же
        путём, хвост исходных аргументов сохранён, окружение дополнено
        (не построено заново) маркером против рекурсии."""
        with tempfile.TemporaryDirectory() as tmp:
            venv_dir = _make_fake_venv(Path(tmp))
            execv_calls = []

            def fake_execv(path, args):
                execv_calls.append((path, list(args)))
                raise _FakeExecvInvoked()

            sentinel = ("ARTEL_TEST_SENTINEL_BOOTSTRAP", "held")
            os.environ[sentinel[0]] = sentinel[1]
            try:
                with mock.patch.object(sys, "version_info", OLD_VERSION_INFO), \
                     mock.patch.object(config, "VENV_DIR", venv_dir, create=True), \
                     mock.patch.object(sys, "argv",
                                       ["orchestrator/artel.py", "status"]), \
                     mock.patch.object(os, "execv", side_effect=fake_execv):
                    with self.assertRaises(_FakeExecvInvoked):
                        importlib.reload(artel)
            finally:
                os.environ.pop(sentinel[0], None)
                os.environ.pop(artel._REEXEC_MARKER_ENV, None)

        self.assertEqual(1, len(execv_calls))
        path, args = execv_calls[0]
        self.assertEqual(str(venv_dir / "bin" / "python"), path)
        self.assertIn("status", args)


class OldInterpreterWithoutUsableVenvTest(_ArtelReloadTestCase):

    def test_refuses_named_with_exit_code_2(self):
        """AC-4/AC-9: venv нет — именованный отказ (версия, путь
        интерпретатора, подсказка venv-sync), код выхода 2."""
        buf = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "no-such-venv"
            with mock.patch.object(sys, "version_info", OLD_VERSION_INFO), \
                 mock.patch.object(config, "VENV_DIR", missing, create=True), \
                 redirect_stderr(buf):
                with self.assertRaises(SystemExit) as ctx:
                    importlib.reload(artel)
        self.assertEqual(2, ctx.exception.code)
        printed = buf.getvalue()
        self.assertIn("3.9", printed)
        self.assertIn(sys.executable, printed)
        self.assertIn("venv-sync", printed)


class ReexecMarkerAlreadySetTest(_ArtelReloadTestCase):

    def test_refuses_without_second_execv(self):
        """AC-5/AC-9: маркер уже стоит — отказ без повторного `os.execv`,
        даже если venv формально пригоден."""
        with tempfile.TemporaryDirectory() as tmp:
            venv_dir = _make_fake_venv(Path(tmp))
            os.environ[artel._REEXEC_MARKER_ENV] = "1"
            try:
                with mock.patch.object(sys, "version_info", OLD_VERSION_INFO), \
                     mock.patch.object(config, "VENV_DIR", venv_dir, create=True), \
                     mock.patch.object(os, "execv") as execv:
                    with self.assertRaises(SystemExit) as ctx:
                        importlib.reload(artel)
            finally:
                os.environ.pop(artel._REEXEC_MARKER_ENV, None)
        execv.assert_not_called()
        self.assertEqual(2, ctx.exception.code)


class ModernInterpreterPassthroughTest(_ArtelReloadTestCase):

    def test_no_reexec_for_modern_interpreter(self):
        """AC-6/AC-9: интерпретатор ≥ минимума — без `os.execv`."""
        with mock.patch.object(os, "execv", side_effect=AssertionError(
                "os.execv не должен вызываться для современного интерпретатора")):
            importlib.reload(artel)
        self.assertTrue(hasattr(artel, "main"))


if __name__ == "__main__":
    unittest.main()
