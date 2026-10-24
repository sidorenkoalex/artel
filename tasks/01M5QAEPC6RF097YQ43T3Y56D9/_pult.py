"""Временная подмена `_pult` для сверки планки по диску (удаляется к концу шага)."""
import os
import subprocess
from pathlib import Path

import _plan

DOCS = Path(__file__).resolve().parent
TASK_ID = "01M5QAEPC6RF097YQ43T3Y56D9"
CODE_ROOT = Path("/Users/al.sidorenko/projects/artel/.artel/projects/artel/worktrees") / TASK_ID
DIFF_BASE = "579a38199ce682917b9d5e40f15ac95cde4aaddc"
DOCS_REPO = CODE_ROOT
DOCS_REVISION = "HEAD"


def artifact_text(name: str):
    path = DOCS / name
    return path.read_text(encoding="utf-8") if path.is_file() else None


def changed_paths():
    out = subprocess.run(["git", "-C", str(CODE_ROOT), "status", "--porcelain",
                          "--untracked-files=all"], capture_output=True,
                         text=True).stdout
    return [line[3:] for line in out.splitlines() if line.startswith("??")]


def _entries(_repo, _revision, _task_id):
    return sorted(p for p in os.listdir(DOCS))


def _typed(_repo, _revision, _task_id):
    return [("tree" if (DOCS / p).is_dir() else "blob", p)
            for p in sorted(os.listdir(DOCS))]


_plan.docs_entries = _entries
_plan.docs_typed_entries = _typed
