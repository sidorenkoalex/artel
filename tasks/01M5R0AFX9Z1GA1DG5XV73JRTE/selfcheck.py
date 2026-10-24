"""Самопроверка шага developer: функции планки задачи против PLAN.md и
патчей с ДИСКА каталога документов (ссылка документов до автокоммита шага
их ещё не несёт), HEAD рабочей копии и базы ветки. Не замена `plank-run`.

python3 selfcheck.py [подстрока имени теста]
"""
import pathlib
import sys
import traceback
import types

DOCS = pathlib.Path(__file__).resolve().parent
TASK = DOCS.name
WT = DOCS.parent.parent / "worktrees" / TASK
BASE = "72d52fd367828949767e234ecbe9b0cc79851084"

pult = types.ModuleType("_pult")
pult.CODE_ROOT = str(WT)
pult.DIFF_BASE = BASE
pult.DOCS_REPO = str(WT)
pult.DOCS_REVISION = "HEAD"
pult.TASK_ID = TASK


def artifact_text(name):
    path = DOCS / name
    return path.read_text(encoding="utf-8") if path.exists() else None


pult.artifact_text = artifact_text
sys.modules["_pult"] = pult
sys.path.insert(0, str(DOCS / "acceptance_tests"))

import _plan  # noqa: E402

_plan.docs_entry_types = lambda repo, rev, task: {
    p.name: ("tree" if p.is_dir() else "blob") for p in DOCS.iterdir()}

import importlib  # noqa: E402

import pytest  # noqa: E402

want = sys.argv[1] if len(sys.argv) > 1 else ""
bad = 0
for mod_name in ("test_mutation_patches", "test_module_form",
                 "test_mutation_tables"):
    mod = importlib.import_module(mod_name)
    for name in sorted(dir(mod)):
        if not name.startswith("test_") or want not in name:
            continue
        func = getattr(mod, name)
        marks = getattr(func, "pytestmark", [])
        cases = [()]
        for mark in marks:
            if mark.name == "parametrize":
                cases = [c if isinstance(c, tuple) else (c,) for c in mark.args[1]]
        for case in cases:
            try:
                func(*case)
                print(f"ok   {mod_name}::{name}{list(case) if case else ''}")
            except BaseException as exc:  # noqa: BLE001
                bad += 1
                text = str(exc).strip().splitlines()
                print(f"FAIL {mod_name}::{name}{list(case) if case else ''}: "
                      + "\n     ".join(text[:12]))
                if not text:
                    traceback.print_exc()
print("красных:", bad)
