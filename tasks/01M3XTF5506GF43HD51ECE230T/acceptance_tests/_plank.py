"""Общий код разовых файлов планки задачи 01M3XTF5506GF43HD51ECE230T.

Не тестовый модуль: префикс `_` обязателен (skills/test-authoring.md).
Держит корень чекаута планки, базу диффа задачи и запуск pytest
отдельным процессом — всё это нужно больше чем одному `test_*.py`.
"""
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from orchestrator import gitcmd  # noqa: E402

TASK_ID = "01M3XTF5506GF43HD51ECE230T"

#: Префикс долгоживущих файлов задачи в `tests/`.
TASK_TESTS_GLOB = f"test_{TASK_ID.lower()}_*.py"

#: Таймаут одного прогона pytest отдельным процессом — ниже потолка
#: pytest-timeout пульта на один тест (120 с).
PYTEST_TIMEOUT_SEC = 110


def diff_base() -> str | None:
    """База диффа задачи — точка расхождения HEAD чекаута планки с
    `origin/<основная>` (`gitcmd.diff_base`), посчитанная в самом чекауте:
    HEAD главной копии стоит на пине, а не на ветке задачи."""
    return gitcmd.diff_base("HEAD", repo=REPO_ROOT)


def show_at(rev: str, rel: str) -> str | None:
    """Текст файла `rel` в ревизии `rev` чекаута планки; `None` — файла нет."""
    res = subprocess.run(["git", "show", f"{rev}:{rel}"], cwd=REPO_ROOT,
                         capture_output=True, text=True, timeout=60)
    return res.stdout if res.returncode == 0 else None


def run_pytest(paths, env: dict | None = None) -> subprocess.CompletedProcess:
    """pytest по относительным путям `paths` в корне чекаута планки."""
    return subprocess.run(
        [sys.executable, "-m", "pytest", *paths, "-p", "no:cacheprovider", "-q"],
        cwd=REPO_ROOT, capture_output=True, text=True,
        timeout=PYTEST_TIMEOUT_SEC, env=env if env is not None else dict(os.environ))


def tail(res: subprocess.CompletedProcess) -> str:
    return f"{res.stdout[-3000:]}\n{res.stderr[-2000:]}"
