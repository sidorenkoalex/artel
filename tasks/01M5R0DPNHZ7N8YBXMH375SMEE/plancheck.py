"""Предпроверка планки по PLAN.md и копиям таблиц С ДИСКА каталога документов.

python3 plancheck.py [<файл планки> …]

Планка читает документы из ссылки документов (закоммиченная ревизия), а
правка PLAN.md этого шага ещё не закоммичена: здесь `_pult` подменён
модулем, у которого `artifact_text` читает каталог документов на диске;
остальное (база, HEAD рабочей копии, перечень патчей ссылки) — как у пульта."""
import subprocess
import sys
import types
from pathlib import Path

sys.dont_write_bytecode = True
DOCS = Path(__file__).resolve().parent
TASK = DOCS.name
ROOT = Path("/Users/al.sidorenko/projects/artel/.artel/projects/artel/worktrees") / TASK


def artifact_text(name: str):
    path = DOCS / name
    return path.read_text(encoding="utf-8") if path.is_file() else None


def main() -> int:
    pult = types.ModuleType("_pult")
    pult.TASK_ID = TASK
    pult.CODE_ROOT = str(ROOT)
    pult.DOCS_REPO = str(ROOT)
    pult.DOCS_REVISION = f"refs/artifacts/{TASK}"
    pult.DIFF_BASE = subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "HEAD", "main"],
        capture_output=True, text=True).stdout.strip()
    pult.DIFF_BASE_SOURCE = "merge-base"
    pult.artifact_text = artifact_text
    sys.modules["_pult"] = pult
    import os
    import pytest
    os.chdir(DOCS.parent.parent)
    files = sys.argv[1:] or ["test_mutation_tables.py", "test_module_form.py"]
    paths = [f"tasks/{TASK}/acceptance_tests/{f}" for f in files]
    # Сторож роли в conftest.py читает sys.argv: адресный прогон файлов планки.
    sys.argv = ["pytest", *paths]
    return pytest.main(paths + ["-q", "-p", "no:cacheprovider", "--assert=plain",
                          "-o", "addopts=", "--rootdir", str(DOCS)])


if __name__ == "__main__":
    sys.exit(main())
