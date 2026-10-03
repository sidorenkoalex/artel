"""Общий код разовых файлов планки задачи 01M409YNSWACNFKNJE2X263ZSD.

Не тестовый модуль: префикс `_` обязателен (skills/test-authoring.md).
Держит корень рабочей копии кода, в которую выложена планка, чтение
PLAN.md из ссылки документов задачи и git-вызов в этой копии.
"""
import subprocess
import sys
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parents[3]
if str(CODE_ROOT) not in sys.path:
    sys.path.insert(0, str(CODE_ROOT))

from orchestrator import artifact_branch, gitcmd  # noqa: E402

TASK_ID = "01M409YNSWACNFKNJE2X263ZSD"


def read_plan() -> tuple[str | None, str]:
    """(текст PLAN.md, причина) из ссылки документов задачи — не с диска."""
    return gitcmd.show(artifact_branch.branch_name(TASK_ID),
                       f"tasks/{TASK_ID}/PLAN.md")


def git(*args: str, cwd: Path = CODE_ROOT, **kw) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                          text=True, timeout=120, **kw)
