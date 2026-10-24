"""AC-5, AC-14: состав ветки задачи и каталога документов — только модуль,
удаление исходного файла и карта кода; песочница, три импортёра, общие
фикстуры, файлы волны 2б-3 и `orchestrator/` не тронуты; карта кода либо не
изменена, либо равна выводу генератора; в каталоге документов нет временных
файлов.

Группа: разовый
Красен до реализации: исходный tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py ещё лежит на ветке, а дифф ветки пуст — свод не сделан.

Дифф — от базы ветки задачи (`_pult.DIFF_BASE`, точка расхождения с
`origin`) до HEAD рабочей копии плюс неотслеживаемые файлы
(`_pult.changed_paths`); имя файла при распознанном переименовании даёт
оба пути (`git diff --no-renames`). Каталог документов — первый уровень
`tasks/<id>/` ссылки документов ревизии выкладки (`git ls-tree`). Карта
кода сверяется как в CI (`.github/workflows/ci.yml`, шаг «закоммиченная
карта не стухла»): содержимым без строки `built_at_sha`; генератор
`scripts/codebase_map.py` строит её по дереву HEAD, выгруженному во
временный каталог.
"""
import io
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _plan  # noqa: E402
from _pult import (CODE_ROOT, DIFF_BASE, DOCS_REPO, DOCS_REVISION,  # noqa: E402
                   TASK_ID, changed_paths)

_ALLOWED = {_plan.NEW_FILE, _plan.OUTCOME_FILE, _plan.MAP_FILE}


def _without_built_at(text: str) -> list:
    return [line for line in text.splitlines()
            if not line.startswith("built_at_sha:")]


def _diff_entries() -> list:
    assert DIFF_BASE, "база диффа ветки задачи не определена при выкладке"
    out = _plan.git_out(CODE_ROOT, "diff", "--name-status", "--no-renames",
                        DIFF_BASE, "HEAD")
    return [tuple(line.split("\t", 1)) for line in out.splitlines() if line.strip()]


# ------------------------------------------------------------------ AC-5

def test_ac5_branch_diff_names_only_module_source_deletion_and_map():
    """Дифф ветки против базы называет только модуль, удаление исходного файла и `docs/codebase-map.md`.

    Пути закоммиченного диффа (без поиска переименований) и
    неотслеживаемые файлы рабочей копии вне `tasks/<id>/` — подмножество
    перечня `tests/test_outcome_gate_module.py`,
    `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py`,
    `docs/codebase-map.md`; исходный файл в диффе — удалением (`D`), и
    модуль в диффе есть.

    Ловит мутацию: роль оставила в рабочей копии сценарий свода
    `tests/_convert_outcome.py` или выгрузку `mutation_before.txt` в корне,
    либо исходный файл не удалён, а опустошён — лишний путь или статус
    не `D`, тест краснеет с ним.
    """
    entries = _diff_entries()
    committed = [path for _status, path in entries]
    stray = sorted({p for p in committed + changed_paths() if p not in _ALLOWED})
    assert not stray, ("пути ветки вне модуля, удаления исходного файла и "
                       "карты кода:\n" + "\n".join(stray))
    statuses = {path: status for status, path in entries}
    assert statuses.get(_plan.OUTCOME_FILE) == "D", (
        f"{_plan.OUTCOME_FILE} в диффе ветки — {statuses.get(_plan.OUTCOME_FILE)!r}, "
        f"ожидалось удаление D")
    assert _plan.NEW_FILE in statuses, f"{_plan.NEW_FILE} в диффе ветки нет"


def test_ac5_docs_dir_has_no_temporary_files_or_subdirs():
    """В каталоге документов нет подкаталогов, кроме `acceptance_tests/`, и посторонних `test_*`/`mutation-*`.

    Первый уровень `tasks/<id>/` ссылки документов: каждый подкаталог —
    `acceptance_tests`; каждый файл с именем, начинающимся на `test_` или
    `mutation-`, — патч `mutation-<nnn>.diff` или копия таблицы
    `--copy-table` `mutation-run-<номер>.tsv`.

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
                and not _plan.PATCH_NAME.match(name) \
                and not _plan.COPY_NAME.match(name):
            problems.append(f"файл {name}")
    assert not problems, ("временные записи в каталоге документов:\n"
                          + "\n".join(problems))


# ------------------------------------------------------------------ AC-14

def test_ac14_source_file_absent_on_branch():
    """Исходного файла `tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py` в дереве HEAD ветки нет.

    Ловит мутацию: разработчик перенёс тесты в модуль, но не удалил
    исходный файл — путь найден в HEAD, тест краснеет с ним.
    """
    out = _plan.git_out(CODE_ROOT, "ls-tree", "--name-only", "HEAD", "--",
                        _plan.OUTCOME_FILE)
    assert not out.strip(), f"{_plan.OUTCOME_FILE} есть на ветке"


@pytest.mark.parametrize("path", [
    "tests/outcome_gate_sandbox.py",
    "tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py",
    "tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py",
    "tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py",
    "tests/fixtures.py",
    "tests/sandbox.py",
    "tests/report_outcome_sandbox.py",
    "tests/test_report_outcome_module.py",
    "tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py",
    "tests/test_component_report_gates.py",
])
def test_ac14_kept_file_untouched(path):
    """Песочница, три импортёра, общие фикстуры и файлы волны 2б-3 — не среди путей задачи.

    Путь `path` не входит ни в закоммиченный дифф ветки от базы, ни в
    неотслеживаемые файлы рабочей копии.

    Ловит мутацию: под функцию `refusal(box, …, case=…)` поправлен метод
    `OutcomeGateSandbox.refusal` в `tests/outcome_gate_sandbox.py` (или
    импортёр переведён на модуль) — путь найден среди путей задачи, тест
    краснеет с ним.
    """
    committed = [p for _status, p in _diff_entries()]
    assert path not in set(committed + changed_paths()), f"{path} изменён"


def test_ac14_orchestrator_untouched():
    """Ни один путь задачи не лежит под `orchestrator/`.

    Ловит мутацию: «заодно» поправлен `orchestrator/advance_gates/
    outcome_integrity.py` (или мутация патча осталась в рабочей копии и
    закоммичена) — путь найден, тест краснеет с ним.
    """
    committed = [p for _status, p in _diff_entries()]
    touched = sorted({p for p in committed + changed_paths()
                      if p.startswith("orchestrator/")})
    assert not touched, f"изменены пути orchestrator/: {touched}"


def test_ac14_codebase_map_unchanged_or_equal_to_generator_output():
    """`docs/codebase-map.md` на ветке не изменён либо равен выводу генератора по дереву HEAD.

    Если карта на HEAD отличается от базы, генератор `scripts/codebase_map.py`
    (`build_modules` + `render`) строит карту по дереву HEAD
    (`orchestrator/`, `scripts/`, `tests/`, выгруженные `git archive`), и
    её содержимое без строки `built_at_sha` совпадает с закоммиченным
    построчно.

    Ловит мутацию: роль руками вычеркнула из карты раздел исходного файла
    (или перегенерировала карту до финальной правки модуля) — строки
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
