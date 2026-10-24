"""AC-6, AC-17, AC-18: состав ветки задачи — три исходных файла удалены, в
трёх импортёрах сменён только источник импорта, в `tests/` больше ничего,
`orchestrator/`, общие фикстуры и файлы волны 1б не тронуты, карта кода либо
не изменена, либо равна выводу генератора.

Группа: разовый
Красен до реализации: на ветке ещё лежат три исходных файла волны, импортёры берут песочницу из tests.test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate, новых файлов нет — свод не сделан.

Дифф — от базы ветки задачи (`_pult.DIFF_BASE`, точка расхождения с
`origin`) до HEAD рабочей копии, без поиска переименований; плюс
неотслеживаемые файлы (`_pult.changed_paths`). Карта кода сверяется как в
CI (`.github/workflows/ci.yml`, шаг «закоммиченная карта не стухла»):
содержимым без строки `built_at_sha`; генератор
`scripts/codebase_map.py` строит её по дереву HEAD, выгруженному во
временный каталог.
"""
import ast
import io
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _plan  # noqa: E402
from _pult import CODE_ROOT, DIFF_BASE, changed_paths  # noqa: E402

_KEPT = (
    "tests/fixtures.py",
    "tests/sandbox.py",
    "tests/test_doc_commit_module.py",
    "tests/test_doc_commit.py",
    "tests/test_doc_commit_suite_gate.py",
    "tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py",
    "tests/test_doc_commit_held_base.py",
    "tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py",
    "tests/test_notes_batch_flush_edges.py",
)
_MAP = "docs/codebase-map.md"


def _import_from(tree, module: str) -> list:
    return [n for n in tree.body
            if isinstance(n, ast.ImportFrom) and n.module == module]


def _without_built_at(text: str) -> list:
    return [line for line in text.splitlines()
            if not line.startswith("built_at_sha:")]


# ------------------------------------------------------------------ AC-6

@pytest.mark.parametrize("path", list(_plan.IMPORTERS))
def test_ac6_importer_changes_only_import_source(path):
    """В импортёре сменён только источник импорта песочницы, с тем же списком имён.

    В базе у импортёра ровно один `from tests.test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate
    import (…)`; на HEAD такого импорта нет, есть ровно один
    `from tests.outcome_gate_sandbox import (…)` с тем же списком имён в
    том же порядке; строки файла до и после этого оператора совпадают с
    базой построчно (докстринг с устаревшей ссылкой не правится).

    Ловит мутацию: разработчик заодно поправил в докстринге импортёра
    ссылку на `tests.test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate` или
    добавил в импорт имя `GATE_ACTIONS` — строка вне оператора или список
    имён расходится, тест краснеет.
    """
    assert DIFF_BASE, "база диффа ветки задачи не определена при выкладке"
    base = _plan.show(CODE_ROOT, DIFF_BASE, path)
    head = _plan.show(CODE_ROOT, "HEAD", path)
    assert base is not None, f"{path} нет в базе ветки {DIFF_BASE}"
    assert head is not None, f"{path} нет в HEAD ветки"
    old = _import_from(ast.parse(base), _plan.OLD_MODULE)
    assert len(old) == 1, f"в базе {path} импортов из {_plan.OLD_MODULE}: {len(old)}"
    head_tree = ast.parse(head)
    assert not _import_from(head_tree, _plan.OLD_MODULE), (
        f"{path} на HEAD ещё импортирует {_plan.OLD_MODULE}")
    new = _import_from(head_tree, _plan.NEW_MODULE)
    assert len(new) == 1, f"в {path} импортов из {_plan.NEW_MODULE}: {len(new)}"
    names = lambda node: [(a.name, a.asname) for a in node.names]
    assert names(new[0]) == names(old[0]), (
        f"{path}: список имён импорта {names(new[0])} ≠ исходному {names(old[0])}")
    base_lines, head_lines = base.splitlines(), head.splitlines()
    o, n = old[0], new[0]
    assert head_lines[:n.lineno - 1] == base_lines[:o.lineno - 1], (
        f"{path}: строки до импорта изменены")
    assert head_lines[n.end_lineno:] == base_lines[o.end_lineno:], (
        f"{path}: строки после импорта изменены")


# ------------------------------------------------------------------ AC-17

def test_ac17_three_source_files_absent_on_branch():
    """Трёх исходных файлов волны в дереве HEAD ветки нет.

    Ловит мутацию: разработчик перенёс тесты, но не удалил
    `tests/test_outcome_integrity.py` (или другой исходный файл) — путь
    найден в HEAD, тест краснеет с ним.
    """
    out = _plan.git_out(CODE_ROOT, "ls-tree", "--name-only", "HEAD", "--",
                        *_plan.SOURCE_FILES)
    present = sorted(p for p in out.splitlines() if p)
    assert not present, f"исходные файлы волны есть на ветке: {present}"


# ------------------------------------------------------------------ AC-18

def test_ac18_tests_diff_only_deletions_new_files_and_importers():
    """Дифф `tests/` от базы — три удаления, два новых файла и три правленых импортёра.

    `git diff --name-status --no-renames <база> HEAD -- tests/` даёт ровно
    три строки `D` исходных файлов, две `A` (`tests/outcome_gate_sandbox.py`,
    `tests/test_outcome_gate_module.py`) и три `M` импортёров (их
    содержимое — AC-6); неотслеживаемых файлов под `tests/`, кроме этих,
    нет.

    Ловит мутацию: при своде заведён вспомогательный
    `tests/outcome_gate_helpers.py` или исходный файл правлен, а не удалён
    — лишняя строка диффа, тест краснеет с ней.
    """
    assert DIFF_BASE, "база диффа ветки задачи не определена при выкладке"
    out = _plan.git_out(CODE_ROOT, "diff", "--name-status", "--no-renames",
                        DIFF_BASE, "HEAD", "--", "tests/")
    entries = sorted(tuple(line.split("\t", 1)) for line in out.splitlines()
                     if line.strip())
    expected = sorted([("D", p) for p in _plan.SOURCE_FILES]
                      + [("A", p) for p in _plan.AFTER_FILES]
                      + [("M", p) for p in _plan.IMPORTERS])
    assert entries == expected, (f"дифф tests/ ветки: {entries}\nожидалось: "
                                 f"{expected}")
    allowed = set(_plan.SOURCE_FILES) | set(_plan.AFTER_FILES) | set(_plan.IMPORTERS)
    stray = sorted(p for p in changed_paths() if p.startswith("tests/")
                   and p not in allowed)
    assert not stray, f"посторонние пути tests/: {stray}"


def test_ac18_orchestrator_fixtures_sandbox_and_wave_1b_untouched():
    """`orchestrator/`, общие фикстуры и файлы волны 1б в пути задачи не входят.

    Ни один путь задачи (закоммиченный дифф от базы и неотслеживаемые
    файлы) не лежит под `orchestrator/` и не совпадает с
    `tests/fixtures.py`, `tests/sandbox.py` или файлом волны 1б.

    Ловит мутацию: под фикстуру нового файла поправлен `tests/sandbox.py`
    (или `orchestrator/advance_gates/outcome_integrity.py` «заодно») —
    путь найден среди путей задачи, тест краснеет с ним.
    """
    touched = sorted(p for p in changed_paths()
                     if p.startswith("orchestrator/") or p in _KEPT)
    assert not touched, f"изменены запретные пути: {touched}"


def test_ac18_codebase_map_unchanged_or_equal_to_generator_output():
    """`docs/codebase-map.md` на ветке не изменён либо равен выводу генератора по дереву HEAD.

    Если карта на HEAD отличается от базы, генератор `scripts/codebase_map.py`
    (`build_modules` + `render`) строит карту по дереву HEAD
    (`orchestrator/`, `scripts/`, `tests/`, выгруженные `git archive`), и
    её содержимое без строки `built_at_sha` совпадает с закоммиченным
    построчно.

    Ловит мутацию: роль руками вписала в карту раздел
    `tests/outcome_gate_sandbox.py` с другим назначением (или правила карту
    до финальной правки модуля) — строки расходятся, тест краснеет с
    первым расхождением.
    """
    assert DIFF_BASE, "база диффа ветки задачи не определена при выкладке"
    base_map = _plan.show(CODE_ROOT, DIFF_BASE, _MAP)
    head_map = _plan.show(CODE_ROOT, "HEAD", _MAP)
    assert head_map is not None, f"{_MAP} нет в HEAD ветки"
    if head_map == base_map:
        return
    archive = subprocess.run(
        ["git", "-C", str(CODE_ROOT), "archive", "--format=tar", "HEAD",
         "orchestrator", "scripts", "tests"], capture_output=True, timeout=120)
    assert archive.returncode == 0, f"git archive HEAD: {archive.stderr!r}"
    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
            tar.extractall(tmp)
        code = ("import sys; from pathlib import Path; "
                f"sys.path.insert(0, {str(Path(CODE_ROOT) / 'scripts')!r}); "
                "import codebase_map as m; "
                f"mods, res, imp = m.build_modules(Path({tmp!r})); "
                "sys.stdout.write(m.render(mods, res, imp, 'x'))")
        res = subprocess.run([sys.executable, "-c", code], cwd=tmp,
                             capture_output=True, text=True, timeout=300)
    assert res.returncode == 0, f"генератор карты не отработал: {res.stderr}"
    want, got = _without_built_at(res.stdout), _without_built_at(head_map)
    if want != got:
        diff = next((i for i, (a, b) in enumerate(zip(want, got)) if a != b),
                    min(len(want), len(got)))
        pytest.fail(f"{_MAP} на HEAD не равна выводу генератора: строка "
                    f"{diff + 1}: генератор {want[diff:diff + 1]!r}, на ветке "
                    f"{got[diff:diff + 1]!r}")
