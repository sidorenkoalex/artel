"""Общий код разовых файлов планки задачи 01M446WV7S94FTZGJCGMPJ667F.

Не тестовый модуль: префикс `_` обязателен (skills/test-authoring.md).
Держит корень рабочей копии кода, в которую выложена планка, и git-вызов
в этой копии.
"""
import subprocess
import sys
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parents[3]
if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))

TASK_ID = "01M446WV7S94FTZGJCGMPJ667F"


def git(*args: str, cwd: Path = CODE_ROOT, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                          text=True, timeout=120, **kw)
