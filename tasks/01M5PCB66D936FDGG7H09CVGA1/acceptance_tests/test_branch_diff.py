"""AC-13, AC-15: состав ветки задачи — шесть исходных файлов волны удалены, в
`tests/` только удаления и новый сводный файл, `orchestrator/`,
`tests/fixtures.py`, `tests/sandbox.py` и файлы волны 1а не тронуты.

Группа: разовый
Красен до реализации: на ветке ещё лежат шесть исходных файлов волны и нет tests/test_doc_commit_module.py — свод не сделан.

Дифф — от базы ветки задачи (`_pult.DIFF_BASE`, точка расхождения с
`origin`) до HEAD рабочей копии, без поиска переименований; плюс
неотслеживаемые файлы (`_pult.changed_paths`).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _plan  # noqa: E402
from _pult import CODE_ROOT, DIFF_BASE, changed_paths  # noqa: E402

_KEPT = (
    "tests/fixtures.py",
    "tests/sandbox.py",
    "tests/test_notes.py",
    "tests/test_notes_apply.py",
    "tests/test_notes_row_format.py",
    "tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py",
    "tests/test_notes_module.py",
)


def test_ac13_six_source_files_absent_on_branch():
    """Шести исходных файлов волны в дереве HEAD ветки нет.

    Ловит мутацию: разработчик перенёс тесты в новый файл, но не удалил
    `tests/test_notes_batch_flush_edges.py` (или другой исходный файл) —
    путь найден в HEAD, тест краснеет с ним.
    """
    out = _plan.git_out(CODE_ROOT, "ls-tree", "--name-only", "HEAD", "--",
                        *_plan.SOURCE_FILES)
    present = sorted(p for p in out.splitlines() if p)
    assert not present, f"исходные файлы волны есть на ветке: {present}"


def test_ac15_tests_diff_only_six_deletions_and_new_module():
    """Дифф `tests/` от базы — ровно шесть удалений и добавление нового файла.

    `git diff --name-status --no-renames <база> HEAD -- tests/` даёт ровно
    шесть строк `D` исходных файлов и одну `A` нового файла;
    неотслеживаемых файлов под `tests/`, кроме нового, нет.

    Ловит мутацию: при своде заведён вспомогательный
    `tests/doc_commit_helpers.py` или исходный файл правлен, а не удалён —
    лишняя строка диффа, тест краснеет с ней.
    """
    assert DIFF_BASE, "база диффа ветки задачи не определена при выкладке"
    out = _plan.git_out(CODE_ROOT, "diff", "--name-status", "--no-renames",
                        DIFF_BASE, "HEAD", "--", "tests/")
    entries = sorted(tuple(line.split("\t", 1)) for line in out.splitlines()
                     if line.strip())
    expected = sorted([("D", p) for p in _plan.SOURCE_FILES]
                      + [("A", _plan.NEW_FILE)])
    assert entries == expected, (f"дифф tests/ ветки: {entries}\nожидалось: "
                                 f"{expected}")
    stray = sorted(p for p in changed_paths() if p.startswith("tests/")
                   and p not in _plan.SOURCE_FILES and p != _plan.NEW_FILE)
    assert not stray, f"посторонние пути tests/: {stray}"


def test_ac15_orchestrator_fixtures_sandbox_and_wave_1a_untouched():
    """`orchestrator/`, общие фикстуры и файлы волны 1а в пути задачи не входят.

    Ни один путь задачи (закоммиченный дифф от базы и неотслеживаемые
    файлы) не лежит под `orchestrator/` и не совпадает с
    `tests/fixtures.py`, `tests/sandbox.py` или файлом волны 1а.

    Ловит мутацию: под фикстуру нового файла поправлен `tests/sandbox.py`
    (или `orchestrator/notes.py` «заодно») — путь найден среди путей
    задачи, тест краснеет с ним.
    """
    paths = changed_paths()
    touched = sorted(p for p in paths
                     if p.startswith("orchestrator/") or p in _KEPT)
    assert not touched, f"изменены запретные пути: {touched}"
