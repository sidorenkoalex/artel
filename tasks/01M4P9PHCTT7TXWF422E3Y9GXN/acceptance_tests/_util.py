"""Общий код планки: текст файла в main, разбор методов, копия дерева,
прогон pytest подпроцессом и нагрузочный процесс.

База диффа (`DIFF_BASE`) и корень рабочей копии (`CODE_ROOT`) — из помощника
пульта `_pult.py`; текст main читается `git show <база>:<путь>`.
"""
import ast
import contextlib
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _pult import CODE_ROOT, DIFF_BASE  # noqa: E402

ROOT = Path(CODE_ROOT).resolve()
LIMIT_FILE = "tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py"
LIMIT_MODULE = "tests.test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs"
LIVENESS_FILE = "tests/test_liveness.py"
SANDBOX_FILE = "tests/sandbox.py"

# Методы файла full_suite_limit_runs, о которых говорят требование 2 и
# критерии: ключ — (класс, метод). ac3_cut, ac4, ac5 меняются обязательно,
# ac6_* и ac7 — если правка их коснулась.
LIMIT_METHODS = {
    "ac3_cut": ("ProfileLimitCutsGateRunTest",
                "test_ac3_gate_run_is_cut_at_profile_limit_not_config"),
    "ac4": ("ConfigLimitCutsGateRunTest",
            "test_ac4_gate_run_without_subfield_is_cut_at_patched_config"),
    "ac5": ("SuiteRunProfileLimitTest",
            "test_ac5_suite_run_cuts_at_profile_limit_and_reports_it"),
    "ac6_profile": ("TimeoutSourceTextTest",
                    "test_ac6_profile_limit_timeout_names_limit_and_profile_source"),
    "ac6_config": ("TimeoutSourceTextTest",
                   "test_ac6_config_limit_timeout_names_limit_and_config_source"),
    "ac7": ("TimeoutTextStartsTest",
            "test_ac7_timeout_texts_keep_their_starts_with_effective_limit"),
}
MANDATORY = ("ac3_cut", "ac4", "ac5")

LIVENESS_METHOD = ("GroupMemberCountPathTest",
                   "test_counts_members_exactly_when_ps_is_not_on_path")

_GIT_LOCATING_ENV = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE",
                     "GIT_OBJECT_DIRECTORY", "GIT_COMMON_DIR")


def main_text(rel: str) -> str:
    """Текст файла `rel` в базе диффа задачи (main)."""
    if not DIFF_BASE:
        raise AssertionError("база диффа задачи не определена при выкладке")
    env = {k: v for k, v in os.environ.items() if k not in _GIT_LOCATING_ENV}
    res = subprocess.run(["git", "-C", str(ROOT), "show", f"{DIFF_BASE}:{rel}"],
                         capture_output=True, text=True, env=env, timeout=60)
    if res.returncode != 0:
        raise AssertionError(f"git show {DIFF_BASE}:{rel}: {res.stderr}")
    return res.stdout


def branch_text(rel: str) -> str:
    """Текст файла `rel` в рабочей копии ветки."""
    return (ROOT / rel).read_text(encoding="utf-8")


def method_node(source: str, cls: str, name: str) -> ast.FunctionDef | None:
    for node in ast.parse(source).body:
        if isinstance(node, ast.ClassDef) and node.name == cls:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == name:
                    return item
    return None


def function_node(source: str, cls: str | None, name: str):
    """Функция модуля (`cls is None`) либо метод класса `cls` — с учётом
    наследования не ищется: берётся определение в самом классе."""
    if cls is not None:
        return method_node(source, cls, name)
    for node in ast.parse(source).body:
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    return None


def method_changed(rel: str, cls: str, name: str) -> bool:
    """Изменён ли метод: дамп его AST на ветке отличается от main."""
    before = method_node(main_text(rel), cls, name)
    after = method_node(branch_text(rel), cls, name)
    if before is None or after is None:
        return before is not after
    return ast.dump(before) != ast.dump(after)


def changed_limit_methods() -> list:
    """Ключи изменённых методов требования 2: обязательные плюс те из
    ac6_*/ac7, чей текст правка тронула."""
    keys = list(MANDATORY)
    for key, (cls, name) in LIMIT_METHODS.items():
        if key not in MANDATORY and method_changed(LIMIT_FILE, cls, name):
            keys.append(key)
    return keys


def copy_tree(dest: Path) -> Path:
    """Копия рабочей копии без `.git`, каталога задач, `.artel` и кэшей."""
    def ignore(directory, names):
        skip = {"__pycache__", ".pytest_cache"}
        if Path(directory).resolve() == ROOT:
            skip |= {".git", "tasks", ".artel"}
        return [n for n in names if n in skip]
    shutil.copytree(ROOT, dest, ignore=ignore, symlinks=True)
    return dest


def pytest_argv(nodeid: str, inner_timeout: int, prelude: str | None = None) -> list:
    """Команда прогона одного теста; `prelude` — код, исполняемый в том же
    интерпретаторе до pytest (подмена функции модуля пульта)."""
    args = [nodeid, "-p", "no:cacheprovider", "-p", "timeout", "-o",
            f"timeout={inner_timeout}", "-q", "-rf", "--tb=short"]
    if prelude is None:
        return [sys.executable, "-m", "pytest", *args]
    # `sys.argv` — как у `python -m pytest <args>`: корневой conftest читает
    # из него, какие тесты запрошены.
    code = (f"import sys\nsys.path.insert(0, '.')\n{prelude}\n"
            f"sys.argv = ['pytest', *{args!r}]\n"
            f"import pytest\nsys.exit(pytest.main({args!r}))\n")
    return [sys.executable, "-c", code]


def child_env() -> dict:
    env = {k: v for k, v in os.environ.items() if k not in _GIT_LOCATING_ENV}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def start(argv: list, cwd: Path) -> subprocess.Popen:
    return subprocess.Popen(argv, cwd=str(cwd), env=child_env(),
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, start_new_session=True)


def kill_group(proc: subprocess.Popen) -> None:
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(proc.pid, signal.SIGKILL)


def finish(proc: subprocess.Popen, deadline: float) -> tuple:
    """(код или None, если процесс не завершился к `deadline`, вывод);
    группа процессов вызова добивается в любом случае."""
    try:
        raw, _ = proc.communicate(timeout=max(0.1, deadline - time.monotonic()))
        code = proc.returncode
    except subprocess.TimeoutExpired:
        kill_group(proc)
        raw, _ = proc.communicate()
        code = None
    finally:
        kill_group(proc)
    return code, raw.decode("utf-8", errors="replace")


def run(argv: list, cwd: Path, timeout: float) -> tuple:
    """(код или None при сроке, вывод, секунды)."""
    started = time.monotonic()
    proc = start(argv, cwd)
    code, out = finish(proc, started + timeout)
    return code, out, time.monotonic() - started


@contextlib.contextmanager
def cpu_load():
    """Нагрузочный процесс критериев AC-1/AC-4: по числу ядер процессов
    `python -c 'while 1: pass'`; снимаются на любом исходе."""
    procs = [subprocess.Popen([sys.executable, "-c", "while 1: pass"],
                              stdin=subprocess.DEVNULL,
                              stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL,
                              start_new_session=True)
             for _ in range(os.cpu_count() or 1)]
    try:
        yield len(procs)
    finally:
        for proc in procs:
            kill_group(proc)
        for proc in procs:
            proc.wait()


def tail(text: str, size: int = 4000) -> str:
    return text[-size:]
