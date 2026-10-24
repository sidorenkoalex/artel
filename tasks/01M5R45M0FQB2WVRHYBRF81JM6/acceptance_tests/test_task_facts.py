"""Факты задачи: границы диффа ветки, неизменность `read_tree` снаружи, свежесть карты и счёт вызовов git в PLAN.md.

Группа: разовый
Красен до реализации: PLAN.md задачи ещё нет — счёт вызовов git до и после (AC-9) не прочитать; карта `docs/codebase-map.md` коммита ветки не несёт новый долгоживущий файл `tests/`, пока разработчик её не перегенерирует (AC-8); проверки сигнатуры, `subprocess` и границ диффа зелёные с рождения — до реализации дифф кода пуст.

Свойства AC-1…AC-7 держит долгоживущий файл задачи в `tests/`
(`test_<id>_batched_reads.py`); здесь — то, что после мержа проверять не
на чем: дифф ветки от её базы и документ PLAN.md ссылки документов.
"""
import inspect
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import (CODE_ROOT, DIFF_BASE, artifact_text, branch_diff,  # noqa: E402
                   changed_paths)

sys.path.insert(0, CODE_ROOT)
from orchestrator import artifact_branch  # noqa: E402
from scripts import codebase_map  # noqa: E402

READ_TREE_DOC = ("{путь: текст} всех файлов `tasks/<id>/` артефактной ветки "
                 "задачи;\nпустой словарь — ветки нет или каталог в ней пуст.")
UNTOUCHED = ("orchestrator/amend.py", "orchestrator/retro.py",
             "orchestrator/gitcmd.py")
SUBCOMMANDS = ("show", "ls-tree", "cat-file", "rev-parse")


def file_diff(diff: str, path: str) -> str:
    """Часть unified-диффа `diff`, относящаяся к файлу `path`."""
    parts = re.split(r"(?m)^diff --git ", diff)
    return "".join(p for p in parts if p.startswith(f"a/{path} b/{path}"))


def exists_at_base(path: str) -> bool:
    res = subprocess.run(["git", "-C", CODE_ROOT, "cat-file", "-e",
                          f"{DIFF_BASE}:{path}"], capture_output=True, text=True)
    return res.returncode == 0


def committed_map() -> str:
    res = subprocess.run(["git", "-C", CODE_ROOT, "show",
                          "HEAD:docs/codebase-map.md"],
                         capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    return res.stdout


def without_sha(text: str) -> list[str]:
    return [line for line in text.splitlines()
            if not line.startswith("built_at_sha:")]


def test_ac8_read_tree_name_signature_and_doc_unchanged():
    """`artifact_branch.read_tree` есть под прежним именем, с прежней сигнатурой и строкой документации.

    Зелёный с рождения: держит внешний вид `read_tree` для `amend.py` и
    `retro.py` — сигнатура `(task_id: str) -> dict` и докстринг о
    возвращаемом значении слово в слово.
    """
    assert str(inspect.signature(artifact_branch.read_tree)) == "(task_id: str) -> dict"
    assert inspect.getdoc(artifact_branch.read_tree) == READ_TREE_DOC


def test_ac8_no_new_direct_subprocess_in_artifact_branch():
    """В добавленных строках `orchestrator/artifact_branch.py` нет `subprocess`.

    Ловит мутацию: `cat-file --batch` запущен своим `subprocess.run`/
    `subprocess.Popen` прямо в `artifact_branch.py` — строка с
    `subprocess` среди добавленных строк диффа файла, тест краснеет.
    """
    part = file_diff(branch_diff(), "orchestrator/artifact_branch.py")
    added = [line for line in part.splitlines()
             if line.startswith("+") and not line.startswith("+++")]
    assert not [line for line in added if "subprocess" in line], added


def test_ac8_diff_leaves_callers_gitcmd_and_existing_tests_alone():
    """Дифф ветки не трогает `amend.py`, `retro.py`, `gitcmd.py`; в `tests/` только новые файлы.

    Ловит мутацию: разработчик правит вызывающего (`amend.py`/`retro.py`),
    примитив `gitcmd.py` или существующий файл `tests/` — путь среди
    `changed_paths()`, тест краснеет с его именем.
    """
    paths = changed_paths()
    assert not [p for p in paths if p in UNTOUCHED], paths
    existing = [p for p in paths if p.startswith("tests/") and exists_at_base(p)]
    assert not existing, f"существующие файлы tests/ в диффе: {existing}"


def test_ac8_codebase_map_matches_the_generator():
    """`docs/codebase-map.md` коммита ветки совпадает с выводом генератора (кроме строки `built_at_sha`).

    Ловит мутацию: `read_tree` получил новые помощники или в `tests/`
    добавлен файл, а карта не перегенерирована (или поправлена руками) —
    строки карты коммита расходятся с выводом `scripts/codebase_map.py`.
    """
    root = Path(CODE_ROOT)
    modules, resolved, imported_by = codebase_map.build_modules(root)
    generated = codebase_map.render(modules, resolved, imported_by, "x")
    assert without_sha(committed_map()) == without_sha(generated)


def test_ac9_plan_counts_git_calls_before_and_after():
    """PLAN.md несёт счёт вызовов git на `Ac5ProofMismatchTest` до и после — всего и по `show`, `ls-tree`, `cat-file`, `rev-parse`.

    Строка каждого показателя (`всего` и четыре подкоманды) несёт не
    меньше двух чисел — значение «до» и «после».

    Ловит мутацию: PLAN.md без счёта, без названия теста или без одной из
    подкоманд (скажем, `cat-file` пропущен) — строки показателя с двумя
    числами нет, тест краснеет с его именем.
    """
    text = artifact_text("PLAN.md")
    assert text is not None, "PLAN.md нет в ссылке документов задачи"
    assert "Ac5ProofMismatchTest" in text
    for token in ("всего",) + SUBCOMMANDS:
        lines = [line for line in text.splitlines()
                 if token in line.lower() and len(re.findall(r"\d+", line)) >= 2]
        assert lines, f"в PLAN.md нет строки «{token}» со счётом до и после"
