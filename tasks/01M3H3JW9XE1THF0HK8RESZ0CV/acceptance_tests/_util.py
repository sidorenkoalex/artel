"""Общие помощники планки 01M3H3JW9XE1THF0HK8RESZ0CV: корень рабочей
копии и дифф ветки задачи от общего предка с `main`.

Помощники нужны двум файлам планки (AC-3 — «catalog.py не изменён»,
AC-4 — «существующие наборы не ослаблены»), поэтому живут отдельным
модулем `_*.py` рядом с тестами, а не копией в каждом из них.

Дифф считается от `git merge-base main HEAD` до РАБОЧЕГО ДЕРЕВА (без
второго коммита в `git diff`): правка, ещё не закоммиченная
разработчиком, — такая же правка защищённого файла, как и коммит.
"""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import config  # noqa: E402


def git(*args: str) -> str:
    """`git <args>` в корне рабочей копии — stdout без хвостовых пробелов."""
    res = subprocess.run(["git", *args], cwd=REPO_ROOT,
                         capture_output=True, text=True, check=True)
    return res.stdout.strip()


def current_branch() -> str:
    return git("rev-parse", "--abbrev-ref", "HEAD")


def merge_base() -> str:
    """Общий предок текущей ветки и `config.MAIN_BRANCH`."""
    return git("merge-base", config.MAIN_BRANCH, "HEAD")


def changed_paths() -> list[str]:
    """Пути, изменённые веткой задачи относительно общего предка с main,
    включая незакоммиченные правки рабочего дерева и новые файлы, ещё не
    добавленные в индекс (новый файл тестов разработчик может держать
    неотслеженным до коммита шага)."""
    changed = git("diff", "--name-only", merge_base()).splitlines()
    new = git("ls-files", "--others", "--exclude-standard").splitlines()
    return [p for p in changed + new if p]


def text_at_merge_base(path: str) -> str:
    """Содержимое `path` на общем предке с main (`git show`), пустая
    строка — файла там не было."""
    base = merge_base()
    res = subprocess.run(["git", "show", f"{base}:{path}"], cwd=REPO_ROOT,
                         capture_output=True, text=True)
    return res.stdout if res.returncode == 0 else ""
