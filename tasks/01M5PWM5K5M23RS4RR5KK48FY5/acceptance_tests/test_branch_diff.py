"""AC-4, AC-7, AC-15: состав ветки задачи и каталога документов — только пути
требования 14 и карта кода, два исходных файла удалены, в трёх импортёрах
сменён только источник импорта, `orchestrator/`, общие фикстуры и файлы
волны 2б-3 не тронуты, карта кода либо не изменена, либо равна выводу
генератора; в каталоге документов нет временных файлов.

Группа: разовый
Красен до реализации: на ветке ещё лежат два исходных файла свода, импортёры берут песочницу из tests.test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate, новых файлов и PLAN.md нет — свод не сделан.

Дифф — от базы ветки задачи (`_pult.DIFF_BASE`, точка расхождения с
`origin`) до HEAD рабочей копии плюс неотслеживаемые файлы
(`_pult.changed_paths`); имя файла при распознанном переименовании даёт
оба пути (`git diff --no-renames`). Каталог документов — первый уровень
`tasks/<id>/` ссылки документов ревизии выкладки (`git ls-tree`). Карта
кода сверяется как в CI (`.github/workflows/ci.yml`, шаг «закоммиченная
карта не стухла»): содержимым без строки `built_at_sha`; генератор
`scripts/codebase_map.py` строит её по дереву HEAD, выгруженному во
временный каталог.

Итог зелени `outcome_gate` и трёх импортёров по CI кодовой ветки (AC-7)
планка не проверяет: планка гоняется на переходе `in_dev → verifying`
до пуша ветки и до ревью, а итог CI по решению Оператора (ANSWER-1, п. 1)
записывает ревьювер в REVIEW — его сверяет ревью и приёмка.
"""
import ast
import io
import re
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _plan  # noqa: E402
from _pult import (CODE_ROOT, DIFF_BASE, DOCS_REPO, DOCS_REVISION,  # noqa: E402
                   TASK_ID, artifact_text, changed_paths)

_ALLOWED = {
    *_plan.AFTER_FILES, *_plan.SOURCE_FILES, _plan.OUTCOME_FILE,
    *_plan.IMPORTERS, _plan.MAP_FILE,
}
_COLLECT_TOTAL = 122


def _import_from(tree, module: str) -> list:
    return [n for n in tree.body
            if isinstance(n, ast.ImportFrom) and n.module == module]


def _without_built_at(text: str) -> list:
    return [line for line in text.splitlines()
            if not line.startswith("built_at_sha:")]


def _diff_entries() -> list:
    assert DIFF_BASE, "база диффа ветки задачи не определена при выкладке"
    out = _plan.git_out(CODE_ROOT, "diff", "--name-status", "--no-renames",
                        DIFF_BASE, "HEAD")
    return [tuple(line.split("\t", 1)) for line in out.splitlines() if line.strip()]


# ------------------------------------------------------------------ AC-4

def test_ac4_branch_diff_names_only_requirement_14_paths_and_map():
    """Дифф ветки против базы называет только пути требования 14 и `docs/codebase-map.md`.

    Пути закоммиченного диффа (без поиска переименований) и
    неотслеживаемые файлы рабочей копии вне `tasks/<id>/` — подмножество
    перечня: `tests/outcome_gate_sandbox.py`,
    `tests/test_outcome_gate_module.py`, два удаляемых исходных файла,
    `outcome_gate`, три импортёра, `docs/codebase-map.md`.

    Ловит мутацию: роль оставила в рабочей копии сценарий переноса
    `tests/_move_sandbox.py` или выгрузку `mutation_before.txt` в корне,
    либо закоммитила черновик `tasks/<id>/PLAN.md` в кодовую ветку —
    лишний путь найден, тест краснеет с ним.
    """
    committed = [path for _status, path in _diff_entries()]
    stray = sorted({p for p in committed + changed_paths() if p not in _ALLOWED})
    assert not stray, "пути ветки вне требования 14 и карты кода:\n" + "\n".join(stray)


def test_ac4_docs_dir_has_no_temporary_files_or_subdirs():
    """В каталоге документов нет подкаталогов, кроме `acceptance_tests/`, и посторонних `test_*`/`mutation-*`.

    Первый уровень `tasks/<id>/` ссылки документов: каждый подкаталог —
    `acceptance_tests`; каждый файл с именем, начинающимся на `test_` или
    `mutation-`, — патч вида `mutation-<nnn>.diff`.

    Ловит мутацию: роль положила в каталог документов выгрузку
    `mutation-before.txt`, сценарий `test_tmp.py` или каталог `scratch/` —
    запись найдена, тест краснеет с её именем.
    """
    entries = _plan.docs_typed_entries(DOCS_REPO, DOCS_REVISION, TASK_ID)
    assert entries, "каталог документов задачи в ссылке документов пуст"
    problems = []
    for kind, name in entries:
        if kind == "tree":
            if name != "acceptance_tests":
                problems.append(f"подкаталог {name}/")
        elif name.startswith(("test_", "mutation-")) \
                and not _plan.PATCH_NAME.match(name):
            problems.append(f"файл {name}")
    assert not problems, ("временные записи в каталоге документов:\n"
                          + "\n".join(problems))


# ------------------------------------------------------------------ AC-7

@pytest.mark.parametrize("path", [
    "tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py",
    "tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py",
    "tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py",
])
def test_ac7_importer_changes_only_import_source(path):
    """В импортёре сменён только источник импорта песочницы, с тем же списком имён.

    В базе у импортёра ровно один `from tests.test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate
    import (…)`; на HEAD такого импорта нет, есть ровно один
    `from tests.outcome_gate_sandbox import (…)` с тем же списком имён в
    том же порядке; строки файла до и после этого оператора совпадают с
    базой построчно (устаревшие ссылки докстринга не правятся, ANSWER-1,
    п. 7).

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

    def names(node):
        return [(a.name, a.asname) for a in node.names]

    assert names(new[0]) == names(old[0]), (
        f"{path}: список имён импорта {names(new[0])} ≠ исходному {names(old[0])}")
    base_lines, head_lines = base.splitlines(), head.splitlines()
    o, n = old[0], new[0]
    assert head_lines[:n.lineno - 1] == base_lines[:o.lineno - 1], (
        f"{path}: строки до импорта изменены")
    assert head_lines[n.end_lineno:] == base_lines[o.end_lineno:], (
        f"{path}: строки после импорта изменены")


def test_ac7_plan_names_collect_only_result_122():
    """В PLAN есть итог `pytest --collect-only` по `outcome_gate` и трём импортёрам — 122 теста.

    В PLAN есть строка, где стоят `collect-only` и число 122.

    Ловит мутацию: роль привела итог сбора только по `outcome_gate` (42) или
    не привела его вовсе — строки с `collect-only` и 122 нет, тест
    краснеет.
    """
    plan = artifact_text("PLAN.md")
    assert plan is not None, "PLAN.md в ссылке документов задачи нет"
    total = re.compile(rf"(?<![\d.,]){_COLLECT_TOTAL}(?!\d)")
    assert any("collect-only" in line and total.search(line)
               for line in plan.splitlines()), (
        f"в PLAN нет строки с итогом pytest --collect-only ({_COLLECT_TOTAL} "
        f"тестов) по outcome_gate и трём импортёрам")


# ------------------------------------------------------------------ AC-15

@pytest.mark.parametrize("path", [
    "tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py",
    "tests/test_outcome_integrity.py",
])
def test_ac15_source_file_absent_on_branch(path):
    """Исходного файла свода в дереве HEAD ветки нет.

    Ловит мутацию: разработчик перенёс тесты, но не удалил
    `tests/test_outcome_integrity.py` (или id-файл) — путь найден в HEAD,
    тест краснеет с ним.
    """
    out = _plan.git_out(CODE_ROOT, "ls-tree", "--name-only", "HEAD", "--", path)
    assert not out.strip(), f"{path} есть на ветке"


def test_ac15_orchestrator_fixtures_sandbox_and_wave_2b3_untouched():
    """`orchestrator/`, общие фикстуры и файлы волны 2б-3 в пути задачи не входят.

    Ни один путь задачи (закоммиченный дифф от базы и неотслеживаемые
    файлы) не лежит под `orchestrator/` и не совпадает с
    `tests/fixtures.py`, `tests/sandbox.py` или файлом волны 2б-3
    (`tests/report_outcome_sandbox.py`, `tests/test_report_outcome_module.py`,
    `tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py`,
    `tests/test_component_report_gates.py` — ANSWER-1, п. 8).

    Ловит мутацию: под фикстуру `id_box` поправлен `tests/fixtures.py`
    (или `orchestrator/advance_gates/outcome_integrity.py` «заодно») —
    путь найден среди путей задачи, тест краснеет с ним.
    """
    kept = {"tests/fixtures.py", "tests/sandbox.py", *_plan.WAVE_2B3_FILES}
    committed = [path for _status, path in _diff_entries()]
    touched = sorted({p for p in committed + changed_paths()
                      if p.startswith("orchestrator/") or p in kept})
    assert not touched, f"изменены запретные пути: {touched}"


def test_ac15_codebase_map_unchanged_or_equal_to_generator_output():
    """`docs/codebase-map.md` на ветке не изменён либо равен выводу генератора по дереву HEAD.

    Если карта на HEAD отличается от базы, генератор `scripts/codebase_map.py`
    (`build_modules` + `render`) строит карту по дереву HEAD
    (`orchestrator/`, `scripts/`, `tests/`, выгруженные `git archive`), и
    её содержимое без строки `built_at_sha` совпадает с закоммиченным
    построчно.

    Ловит мутацию: роль руками вписала в карту раздел
    `tests/outcome_gate_sandbox.py` с другим назначением (или
    перегенерировала карту до финальной правки модуля) — строки
    расходятся, тест краснеет с первым расхождением.
    """
    assert DIFF_BASE, "база диффа ветки задачи не определена при выкладке"
    base_map = _plan.show(CODE_ROOT, DIFF_BASE, _plan.MAP_FILE)
    head_map = _plan.show(CODE_ROOT, "HEAD", _plan.MAP_FILE)
    assert head_map is not None, f"{_plan.MAP_FILE} нет в HEAD ветки"
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
        pytest.fail(f"{_plan.MAP_FILE} на HEAD не равна выводу генератора: строка "
                    f"{diff + 1}: генератор {want[diff:diff + 1]!r}, на ветке "
                    f"{got[diff:diff + 1]!r}")
