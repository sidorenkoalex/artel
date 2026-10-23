"""Условное подключение `tests.fixtures` корневым `conftest.py` (ADR-0027,
часть А1; решение Оператора 24.10.2026 по красному CI 40028534489).

Зеркала репозитория в тестах (`tests/test_fsm_advance_tests_writing_test_
groups.py::CollectFromTestsDirTest`) берут корневой `conftest.py` без
`tests/fixtures.py`: подключение плагина обязано пропускать отсутствующий
модуль, а при модуле в дереве — давать фикстуры. Зеркало строится из
настоящего корневого `conftest.py`; пока Приложение 1 PLAN на него не
наложено (ветка задачи вне CI), строки приложения дописываются к нему
тестом — тем же текстом.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

CODE_ROOT = Path(__file__).resolve().parents[1]

# Строки Приложения 1 PLAN задачи 01M5N9V4S984GRRXSMBK5JX7V1.
APPENDIX_LINES = (
    "import importlib.util\n"
    'pytest_plugins = (["tests.fixtures"]\n'
    '                  if importlib.util.find_spec("tests.fixtures") else [])\n')

PROBE = (
    "def test_plain():\n"
    "    pass\n"
    "\n"
    "def test_uses_fixture(tmp_dir):\n"
    "    assert type(tmp_dir).__name__ == 'TmpDirTest'\n")


def mirror_conftest() -> str:
    text = (CODE_ROOT / "conftest.py").read_text(encoding="utf-8")
    if "pytest_plugins" not in text:
        text += "\n" + APPENDIX_LINES
    return text


@pytest.mark.parametrize("with_module", [False, True])
def test_mirror_collects_with_and_without_fixtures_module(tmp_path, with_module):
    """Зеркало без `tests/fixtures.py` собирается, тест на фикстуру падает «fixture not found»; с модулем — фикстура видна.

    Зеркало: симлинки `orchestrator`, `scripts`, `pyproject.toml`,
    `tests/__init__.py`, `tests/sandbox.py` (и `tests/fixtures.py` во
    втором варианте), `conftest.py` — корневой с подключением; pytest —
    подпроцессом из корня зеркала.

    Ловит мутацию: подключение в корневом `conftest.py` безусловное
    (`pytest_plugins = ["tests.fixtures"]`) — зеркало без модуля падает
    ImportError на загрузке `conftest.py`, вариант `False` краснеет; условие
    перевёрнуто или список всегда пуст — вариант `True` краснеет на
    «fixture 'tmp_dir' not found».
    """
    for name in ("orchestrator", "scripts", "pyproject.toml"):
        os.symlink(CODE_ROOT / name, tmp_path / name)
    (tmp_path / "conftest.py").write_text(mirror_conftest(), encoding="utf-8")
    (tmp_path / "tests").mkdir()
    entries = ["__init__.py", "sandbox.py"] + (["fixtures.py"] if with_module else [])
    for entry in entries:
        os.symlink(CODE_ROOT / "tests" / entry, tmp_path / "tests" / entry)
    (tmp_path / "tests" / "test_probe.py").write_text(PROBE, encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_probe.py",
         "-p", "no:cacheprovider", "-p", "timeout", "-o", "timeout=120"],
        cwd=tmp_path, capture_output=True, text=True, timeout=300)
    output = proc.stdout + proc.stderr
    assert "ImportError" not in output, output
    if with_module:
        assert proc.returncode == 0, output
        assert "2 passed" in output, output
    else:
        assert "1 passed" in output, output
        assert "fixture 'tmp_dir' not found" in output, output
