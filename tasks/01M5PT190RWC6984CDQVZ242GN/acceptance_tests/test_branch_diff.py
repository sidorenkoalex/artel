"""AC-5, AC-8, AC-9, AC-20: состав ветки задачи — исходный файл сведён к
переходному модулю, в импортёре сменён только источник импорта, в `tests/`
больше ничего, защищённые и общие файлы и `orchestrator/` не тронуты, карта
кода либо не изменена, либо равна выводу генератора; в рабочей копии и в
каталоге документов задачи нет временных файлов.

Группа: разовый
Красен до реализации: на ветке исходный файл волны ещё целиком, импортёр берёт песочницу из tests.test_01m590gjaf0edv4nbc4c99mfvh_report_outcome, новых файлов нет — свод не сделан.

Дифф — от базы ветки задачи (`_pult.DIFF_BASE`, точка расхождения с
`origin`) до HEAD рабочей копии, без поиска переименований; плюс
неотслеживаемые файлы (`_pult.changed_paths`). Карта кода сверяется как в
CI (`.github/workflows/ci.yml`, шаг «закоммиченная карта не стухла»):
содержимым без строки `built_at_sha`; генератор
`scripts/codebase_map.py` строит её по дереву HEAD, выгруженному во
временный каталог. Каталог документов задачи — первый уровень
`tasks/<id>/` ссылки документов ревизии выкладки (`_pult.DOCS_REVISION`).
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
                   TASK_ID, changed_paths)

_KEPT = (
    "tests/fixtures.py",
    "tests/sandbox.py",
    "tests/fd_wait.py",
    "tests/test_invariants.py",
    "tests/test_outcome_integrity_added_lines.py",
    "docs/invariants.md",
    # файлы волны 2а-1 (01M5PHK9K0YQCTPA6CK94BBZ33)
    "tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py",
    "tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_outcome_gate.py",
    "tests/test_outcome_integrity.py",
    "tests/outcome_gate_sandbox.py",
    "tests/test_outcome_gate_module.py",
    "tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py",
    "tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py",
    "tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py",
)
_MAP = "docs/codebase-map.md"
# Пути требований 6–8 SPEC.
_ALLOWED = (_plan.SOURCE_FILE, _plan.SANDBOX_FILE, _plan.NEW_FILE, _plan.IMPORTER)
_PATCH = re.compile(r"^mutation-\d{3,}\.diff$")


def _import_from(tree, module: str) -> list:
    return [n for n in tree.body
            if isinstance(n, ast.ImportFrom) and n.module == module]


def _without_built_at(text: str) -> list:
    return [line for line in text.splitlines()
            if not line.startswith("built_at_sha:")]


def _head(path: str) -> str:
    text = _plan.show(CODE_ROOT, "HEAD", path)
    assert text is not None, f"{path} нет в HEAD ветки"
    return text


# ------------------------------------------------------------------ AC-5

def test_ac5_worktree_status_names_only_requirement_6_8_paths():
    """`git status --porcelain` рабочей копии называет только пути требований 6–8.

    Вывод `git status --porcelain --untracked-files=all` рабочей копии без
    выкладки планки (`tasks/<id>/`) не содержит путей вне
    `tests/report_outcome_sandbox.py`, `tests/test_report_outcome_module.py`,
    исходного файла волны и `tests/test_component_report_gates.py`.

    Ловит мутацию: шаг developer оборвался и оставил в рабочей копии
    сценарий `tests/_mutate_tmp.py` (или выгрузку `run.log` в корне) —
    путь в выводе `git status`, тест краснеет с ним.
    """
    out = _plan.git_out(CODE_ROOT, "status", "--porcelain", "--untracked-files=all")
    stray = []
    for line in out.splitlines():
        if not line.strip():
            continue
        path = line[3:].split(" -> ")[-1].strip('"')
        if path.startswith(f"tasks/{TASK_ID}/") or path in _ALLOWED:
            continue
        stray.append(line)
    assert not stray, "посторонние пути в git status рабочей копии:\n" + "\n".join(stray)


def test_ac5_docs_dir_has_no_subdirs_and_no_test_or_mutation_named_files():
    """Каталог документов задачи: подкаталог только `acceptance_tests/`, файлы не `test_*`/`mutation-*`.

    Первый уровень `tasks/<id>/` ссылки документов: из каталогов есть
    только `acceptance_tests`; каждый файл с расширением не `.md`, кроме
    патчей `mutation-<nnn>.diff`, не начинается с `test_` и `mutation-`.

    Ловит мутацию: роль сложила выгрузки прогонов в подкаталог `runs/` или
    положила черновик `mutation-013.py` / `test_tmp.py` первым уровнем —
    имя найдено, тест краснеет с ним.
    """
    entries = _plan.docs_entry_types(DOCS_REPO, DOCS_REVISION, TASK_ID)
    assert entries, f"tasks/{TASK_ID}/ в ссылке документов пуст или не прочитан"
    problems = [f"подкаталог {name}/" for name, kind in sorted(entries.items())
                if kind == "tree" and name != "acceptance_tests"]
    for name, kind in sorted(entries.items()):
        if kind != "blob" or name.endswith(".md") or _PATCH.match(name):
            continue
        if name.startswith(("test_", "mutation-")):
            problems.append(f"файл {name}")
    assert not problems, "посторонние записи каталога документов:\n" + "\n".join(problems)


# ------------------------------------------------------------------ AC-8

def test_ac8_transition_module_is_docstring_and_one_import():
    """Исходный файл волны на ветке — ровно докстринг и строка импорта из `tests.report_outcome_sandbox`.

    Файл есть в HEAD; верхний уровень — два оператора: однострочный
    докстринг, где названы `tests/test_invariants.py` и
    `tests/report_outcome_sandbox.py`, и `from tests.report_outcome_sandbox
    import ReportSandbox, junit, vitest_report, vitest_test` (имена — по
    порядку, без переименований).

    Ловит мутацию: разработчик удалил исходный файл вместо сведения (или
    оставил в нём `PytestSpy`, или добавил в импорт `Fake`) — файла нет,
    операторов больше двух или список имён другой, тест краснеет.
    """
    tree = ast.parse(_head(_plan.SOURCE_FILE))
    assert len(tree.body) == 2, (
        f"операторов верхнего уровня {len(tree.body)}: "
        f"{[type(n).__name__ for n in tree.body]}")
    doc = ast.get_docstring(tree)
    assert doc and "\n" not in doc.strip(), f"докстринг не в одну строку: {doc!r}"
    for name in (_plan.INVARIANTS_TEST, _plan.SANDBOX_FILE):
        assert name in doc, f"в докстринге нет ссылки на {name}: {doc!r}"
    node = tree.body[1]
    assert isinstance(node, ast.ImportFrom) and node.module == _plan.NEW_MODULE \
        and node.level == 0, f"второй оператор — не импорт из {_plan.NEW_MODULE}"
    assert [(a.name, a.asname) for a in node.names] == \
        [(n, None) for n in _plan.TRANSITION_NAMES], (
        f"имена импорта: {[(a.name, a.asname) for a in node.names]}")


def test_ac8_transition_module_exports_names_from_sandbox_module():
    """Имена переходного модуля — те же объекты, что в `tests.report_outcome_sandbox`.

    В отдельном интерпретаторе рабочей копии импорт старого пути модуля
    даёт `ReportSandbox`, `junit`, `vitest_report`, `vitest_test`, и
    каждый из них — тот же объект, что в модуле песочницы.

    Ловит мутацию: в переходном модуле импорт заменён копией
    `def junit(...)` (или опечатка в имени модуля) — объекты не тождественны
    либо импорт падает, тест краснеет.
    """
    code = ("import tests.report_outcome_sandbox as new, importlib; "
            f"old = importlib.import_module({_plan.OLD_MODULE!r}); "
            f"print(all(getattr(old, n) is getattr(new, n) for n in "
            f"{list(_plan.TRANSITION_NAMES)!r}))")
    res = subprocess.run([sys.executable, "-c", code], cwd=CODE_ROOT,
                         capture_output=True, text=True, timeout=110)
    assert res.returncode == 0, f"импорт переходного модуля упал:\n{res.stderr[-3000:]}"
    assert res.stdout.strip() == "True", f"имена не тождественны: {res.stdout!r}"


# ------------------------------------------------------------------ AC-9

def test_ac9_importer_changes_only_import_source():
    """В `tests/test_component_report_gates.py` сменён только источник импорта песочницы, с тем же списком имён.

    В базе у импортёра ровно один `from
    tests.test_01m590gjaf0edv4nbc4c99mfvh_report_outcome import (…)`; на HEAD
    такого импорта нет, есть ровно один `from tests.report_outcome_sandbox
    import (…)` с тем же списком имён в том же порядке; строки файла до и
    после этого оператора совпадают с базой построчно.

    Ловит мутацию: разработчик добавил в импорт имя `entry` или заодно
    поправил соседнюю строку импортёра — список имён или строки вне
    оператора расходятся, тест краснеет.
    """
    assert DIFF_BASE, "база диффа ветки задачи не определена при выкладке"
    base = _plan.show(CODE_ROOT, DIFF_BASE, _plan.IMPORTER)
    assert base is not None, f"{_plan.IMPORTER} нет в базе ветки {DIFF_BASE}"
    head = _head(_plan.IMPORTER)
    old = _import_from(ast.parse(base), _plan.OLD_MODULE)
    assert len(old) == 1, f"в базе импортов из {_plan.OLD_MODULE}: {len(old)}"
    head_tree = ast.parse(head)
    assert not _import_from(head_tree, _plan.OLD_MODULE), (
        f"{_plan.IMPORTER} на HEAD ещё импортирует {_plan.OLD_MODULE}")
    new = _import_from(head_tree, _plan.NEW_MODULE)
    assert len(new) == 1, f"импортов из {_plan.NEW_MODULE}: {len(new)}"
    names = lambda node: [(a.name, a.asname) for a in node.names]
    assert names(new[0]) == names(old[0]), (
        f"список имён импорта {names(new[0])} ≠ исходному {names(old[0])}")
    base_lines, head_lines = base.splitlines(), head.splitlines()
    o, n = old[0], new[0]
    assert head_lines[:n.lineno - 1] == base_lines[:o.lineno - 1], (
        "строки до импорта изменены")
    assert head_lines[n.end_lineno:] == base_lines[o.end_lineno:], (
        "строки после импорта изменены")


@pytest.mark.parametrize("path", ["tests/test_invariants.py", "docs/invariants.md"])
def test_ac9_invariants_test_and_doc_unchanged(path):
    """`tests/test_invariants.py` и `docs/invariants.md` на HEAD равны базе и не в путях задачи.

    Ловит мутацию: разработчик поправил импорт в `tests/test_invariants.py:3131`
    на `tests.report_outcome_sandbox` (или путь в `docs/invariants.md:71`) —
    текст HEAD отличается от базы, тест краснеет.
    """
    assert DIFF_BASE, "база диффа ветки задачи не определена при выкладке"
    assert _plan.show(CODE_ROOT, "HEAD", path) == \
        _plan.show(CODE_ROOT, DIFF_BASE, path), f"{path} изменён на ветке"
    assert path not in changed_paths(), f"{path} среди путей задачи"


# ------------------------------------------------------------------ AC-20

def test_ac20_tests_diff_only_transition_new_files_and_importer():
    """Дифф `tests/` от базы — правленый исходный файл, два новых файла и правленый импортёр.

    `git diff --name-status --no-renames <база> HEAD -- tests/` даёт ровно
    `M` исходного файла (содержимое — AC-8), `A`
    `tests/report_outcome_sandbox.py` и `tests/test_report_outcome_module.py`
    и `M` `tests/test_component_report_gates.py` (содержимое — AC-9);
    неотслеживаемых путей под `tests/`, кроме этих, нет.

    Ловит мутацию: при своде заведён вспомогательный
    `tests/report_outcome_helpers.py` или исходный файл удалён, а не сведён
    — лишняя/иная строка диффа, тест краснеет с ней.
    """
    assert DIFF_BASE, "база диффа ветки задачи не определена при выкладке"
    out = _plan.git_out(CODE_ROOT, "diff", "--name-status", "--no-renames",
                        DIFF_BASE, "HEAD", "--", "tests/")
    entries = sorted(tuple(line.split("\t", 1)) for line in out.splitlines()
                     if line.strip())
    expected = sorted([("M", _plan.SOURCE_FILE), ("A", _plan.SANDBOX_FILE),
                       ("A", _plan.NEW_FILE), ("M", _plan.IMPORTER)])
    assert entries == expected, f"дифф tests/ ветки: {entries}\nожидалось: {expected}"
    stray = sorted(p for p in changed_paths() if p.startswith("tests/")
                   and p not in _ALLOWED)
    assert not stray, f"посторонние пути tests/: {stray}"


def test_ac20_orchestrator_fixtures_and_neighbours_untouched():
    """`orchestrator/`, общие фикстуры, соседние тесты и файлы волны 2а-1 в пути задачи не входят.

    Ни один путь задачи (закоммиченный дифф от базы и неотслеживаемые
    файлы) не лежит под `orchestrator/` и не совпадает с
    `tests/fixtures.py`, `tests/sandbox.py`, `tests/fd_wait.py`,
    `tests/test_invariants.py`, `tests/test_outcome_integrity_added_lines.py`
    или файлом волны 2а-1.

    Ловит мутацию: под фикстуру нового файла поправлен `tests/fixtures.py`
    (или `orchestrator/reporters/outcome.py` «заодно») — путь найден среди
    путей задачи, тест краснеет с ним.
    """
    touched = sorted(p for p in changed_paths()
                     if p.startswith("orchestrator/") or p in _KEPT)
    assert not touched, f"изменены запретные пути: {touched}"


def test_ac20_codebase_map_unchanged_or_equal_to_generator_output():
    """`docs/codebase-map.md` на ветке не изменён либо равен выводу генератора по дереву HEAD.

    Если карта на HEAD отличается от базы, генератор `scripts/codebase_map.py`
    (`build_modules` + `render`) строит карту по дереву HEAD
    (`orchestrator/`, `scripts/`, `tests/`, выгруженные `git archive`), и
    её содержимое без строки `built_at_sha` совпадает с закоммиченным
    построчно.

    Ловит мутацию: роль руками вписала в карту раздел
    `tests/report_outcome_sandbox.py` с другим назначением (или правила карту
    до финальной правки модуля) — строки расходятся, тест краснеет с
    первым расхождением.
    """
    assert DIFF_BASE, "база диффа ветки задачи не определена при выкладке"
    base_map = _plan.show(CODE_ROOT, DIFF_BASE, _MAP)
    head_map = _head(_MAP)
    if head_map == base_map:
        return
    archive = subprocess.run(
        ["git", "-C", str(CODE_ROOT), "archive", "--format=tar", "HEAD",
         "orchestrator", "scripts", "tests"], capture_output=True, timeout=60)
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
                             capture_output=True, text=True, timeout=110)
    assert res.returncode == 0, f"генератор карты не отработал: {res.stderr}"
    want, got = _without_built_at(res.stdout), _without_built_at(head_map)
    if want != got:
        diff = next((i for i, (a, b) in enumerate(zip(want, got)) if a != b),
                    min(len(want), len(got)))
        pytest.fail(f"{_MAP} на HEAD не равна выводу генератора: строка "
                    f"{diff + 1}: генератор {want[diff:diff + 1]!r}, на ветке "
                    f"{got[diff:diff + 1]!r}")
