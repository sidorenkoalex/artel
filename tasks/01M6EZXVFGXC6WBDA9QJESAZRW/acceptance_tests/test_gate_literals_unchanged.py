"""Признак гейта проекта — только помощниками `targets.py`: ветка не добавляет сравнений `forge`/`merge_gate` с литералом вне `targets.py` и элементов `EXEMPT` сторожа ac9 (AC-16).

Группа: разовый
Зелёный с рождения: до правок разработчика ветка не меняет ни кода `orchestrator/`/`scripts/`, ни сторожа ac9 — новых сравнений и элементов `EXEMPT` нет; метод краснеет, когда ветка их добавит.

Факт этой задачи — разница ветки с базой диффа (`_pult.DIFF_BASE`,
`_pult.changed_paths()`): после мержа сравнивать не с чем. Сравнение
«значения поля с литералом» распознаётся тем же разбором, что сторож ac9
(`field_like`/`watched_literals` файла
`tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py`), но без его
исключений: исключение, добавленное веткой, тоже новое сравнение.
"""
import ast
import subprocess
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _pult import CODE_ROOT, DIFF_BASE, changed_paths  # noqa: E402
from tests import test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project as ac9  # noqa: E402

GUARD = "tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py"
SUPPORT = "orchestrator/targets.py"
CODE_DIRS = ("orchestrator/", "scripts/")


def base_text(rel: str) -> str:
    """Текст `rel` в базе диффа; файла там нет — пусто."""
    res = subprocess.run(["git", "-C", str(CODE_ROOT), "show",
                          f"{DIFF_BASE}:{rel}"], capture_output=True, text=True)
    return res.stdout if res.returncode == 0 else ""


def head_text(rel: str) -> str:
    path = Path(CODE_ROOT) / rel
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def comparisons(source: str) -> Counter:
    """Сравнения значения `forge`/`merge_gate` с литералом: текст → число."""
    found: Counter = Counter()
    if not source:
        return found
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Compare):
            operands = [node.left, *node.comparators]
            if (any(ac9.field_like(o) for o in operands)
                    and any(ac9.watched_literals(o) for o in operands)):
                found[ast.unparse(node)] += 1
    return found


def exempt_of(source: str) -> set:
    """Значение `EXEMPT` модуля сторожа по тексту."""
    for node in ast.parse(source).body:
        if (isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "EXEMPT"
                        for t in node.targets)):
            return set(ast.literal_eval(node.value))
    return set()


def test_ac16_no_new_gate_literal_comparisons_or_exemptions():
    """Ветка не добавляет вне `orchestrator/targets.py` сравнений `forge`/`merge_gate` с литералом и элементов `EXEMPT` сторожа ac9.

    Сценарий: для каждого `.py` под `orchestrator/` и `scripts/` из путей
    задачи (`changed_paths()`), кроме `orchestrator/targets.py`, сравнения
    значения поля с литералом в рабочей копии сверяются с теми же в базе
    диффа — новых нет. `EXEMPT` сторожа ac9 в рабочей копии — подмножество
    `EXEMPT` базы.

    Ловит мутацию: отказ при непрочитанной записи сделан сравнением
    `entry.get("merge_gate") != "operator"` в `gitcmd.py` или
    `fsm_merge_gate.py` (новое сравнение в дифф-счёте); либо такое место
    внесено в `EXEMPT` сторожа (новый элемент множества).
    """
    added = {}
    for rel in changed_paths():
        if not rel.endswith(".py") or rel == SUPPORT:
            continue
        if not rel.startswith(CODE_DIRS):
            continue
        new = comparisons(head_text(rel)) - comparisons(base_text(rel))
        if new:
            added[rel] = sorted(new)
    assert added == {}, f"новые сравнения с литералом (база {DIFF_BASE}): {added}"
    base_exempt = exempt_of(base_text(GUARD))
    assert base_exempt, f"стенд: EXEMPT сторожа ac9 в базе {DIFF_BASE} не прочитан"
    extra = set(ac9.EXEMPT) - base_exempt
    assert extra == set(), f"новые элементы EXEMPT сторожа ac9: {sorted(extra)}"
