"""AC-9, AC-11: состав ветки задачи — исходные файлы волны удалены, в `tests/`
только удаления и новый сводный файл, `orchestrator/` не тронут.

Группа: разовый
Красен до реализации: на ветке ещё лежат четыре исходных файла волны и нет tests/test_notes_module.py — свод не сделан.

Дифф — от базы ветки задачи (`_pult.DIFF_BASE`, точка расхождения с
`origin`) до HEAD рабочей копии, без поиска переименований; плюс
неотслеживаемые файлы (`_pult.changed_paths`).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _plan  # noqa: E402
from _pult import CODE_ROOT, DIFF_BASE, changed_paths  # noqa: E402


def test_ac9_source_files_absent_on_branch():
    """Четырёх исходных файлов волны в дереве HEAD ветки нет.

    Ловит мутацию: разработчик перенёс тесты в новый файл, но не удалил
    `tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py` (или
    другой исходный файл) — путь найден в HEAD, тест краснеет с ним.
    """
    out = _plan.git_out(CODE_ROOT, "ls-tree", "--name-only", "HEAD", "--",
                        *_plan.SOURCE_FILES)
    present = sorted(p for p in out.splitlines() if p)
    assert not present, f"исходные файлы волны есть на ветке: {present}"


def test_ac11_tests_diff_only_deletions_and_new_module_orchestrator_untouched():
    """В `tests/` — только удаление четырёх файлов и новый файл; `orchestrator/` цел.

    `git diff --name-status --no-renames <база> HEAD -- tests/` даёт ровно
    четыре строки `D` исходных файлов и одну `A` нового файла;
    неотслеживаемых файлов под `tests/`, кроме нового, нет; ни один путь
    задачи не лежит под `orchestrator/`, `tests/fixtures.py` и
    `tests/sandbox.py` не изменены.

    Ловит мутацию: при своде поправлен `tests/sandbox.py` (или
    `tests/fixtures.py`) под фикстуру нового файла, либо исходный файл
    правлен, а не удалён — лишняя строка диффа, тест краснеет с ней.
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
    paths = changed_paths()
    stray_tests = sorted(p for p in paths if p.startswith("tests/")
                         and p not in _plan.SOURCE_FILES and p != _plan.NEW_FILE)
    orchestrator = sorted(p for p in paths if p.startswith("orchestrator/"))
    assert not stray_tests, f"посторонние пути tests/: {stray_tests}"
    assert not orchestrator, f"изменены пути orchestrator/: {orchestrator}"
