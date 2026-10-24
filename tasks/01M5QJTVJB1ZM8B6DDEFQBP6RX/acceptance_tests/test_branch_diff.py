"""AC-6, AC-7, AC-17: состав ветки и рабочей копии — два исходных файла
удалены, файл модуля замка добавлен, файл очереди переписан, тесты
разложены по файлам модулей, карта кода — вывод генератора, запретные
файлы и `orchestrator/` не тронуты, в файлах модулей нет `skip`/`xfail` и
пределы не выше исходных; в рабочей копии и в каталоге документов нет
временных файлов.

Группа: разовый
Красен до реализации: на ветке ещё лежат tests/test_merge_lock.py и tests/test_merge_lock_by_project.py, tests/test_merge_lock_module.py нет — свод не сделан.

Дифф — от базы ветки задачи (`_pult.DIFF_BASE`, точка расхождения с
`origin`) до HEAD рабочей копии, без поиска переименований; плюс
неотслеживаемые файлы (`_pult.changed_paths`). Карта кода сверяется как в
CI: содержимым без строки `built_at_sha`; генератор
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

import _ctx  # noqa: E402
import _plan  # noqa: E402
from _pult import CODE_ROOT, TASK_ID, changed_paths  # noqa: E402

# Файлы требования 17 SPEC.
_KEPT = (
    "tests/fixtures.py",
    "tests/sandbox.py",
    "tests/test_invariants.py",
    "tests/test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard.py",
    "tests/test_merge_gate_ci_wait.py",
    "tests/test_release.py",
    "tests/test_outcome_gate_module.py",
    "tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py",
    "tests/test_report_outcome_module.py",
    "tests/test_component_report_gates.py",
)
_ALLOWED = (_plan.LOCK_MODULE, _plan.QUEUE_FILE, *_plan.DELETED_FILES,
            _plan.MAP_FILE)
_PATCH = re.compile(r"^mutation-\d{3,}\.diff$")
_COPY = re.compile(r"^mutation-run-\d+\.tsv$")
_SKIP_NAMES = {"skip", "skipif", "xfail", "skipTest", "importorskip",
               "skipIf", "skipUnless", "expectedFailure"}
_LIMIT_KWARGS = ("timeout", "delta", "places", "rel", "abs")


def _without_built_at(text: str) -> list:
    return [line for line in text.splitlines()
            if not line.startswith("built_at_sha:")]


# ------------------------------------------------------------------ AC-6

def test_ac6_worktree_status_names_only_wave_paths():
    """`git status --porcelain` рабочей копии называет только пути волны.

    Вывод `git status --porcelain --untracked-files=all` без выкладки
    планки (`tasks/<id>/`) не содержит путей вне
    `tests/test_merge_lock_module.py`, `tests/test_merge_queue.py`,
    `tests/test_merge_lock.py`, `tests/test_merge_lock_by_project.py` и
    `docs/codebase-map.md`.

    Ловит мутацию: шаг developer оборвался и оставил в рабочей копии
    сценарий `tests/_convert_tmp.py` или выгрузку `run.log` в корне —
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


def test_ac6_docs_dir_files_not_named_test_or_mutation():
    """Каталог документов задачи: файлы не `.md`, кроме патчей и копий таблиц, не называются `test_*`/`mutation-*`.

    Первый уровень `tasks/<id>/` ссылки документов: каждый файл с
    расширением не `.md`, кроме `mutation-<nnn>.diff` и
    `mutation-run-<n>.tsv`, не начинается с `test_` и `mutation-`.

    Ловит мутацию: роль положила черновик `mutation-013.py` или
    `test_tmp.py` первым уровнем каталога документов — имя найдено, тест
    краснеет с ним.
    """
    entries = _ctx.docs_entries()
    assert entries, f"tasks/{TASK_ID}/ в ссылке документов пуст или не прочитан"
    bad = sorted(name for name, kind in entries.items()
                 if kind == "blob" and not name.endswith(".md")
                 and not _PATCH.match(name) and not _COPY.match(name)
                 and name.startswith(("test_", "mutation-")))
    assert not bad, f"посторонние файлы каталога документов: {bad}"


# ------------------------------------------------------------------ AC-7

@pytest.mark.parametrize("path", ["tests/test_merge_lock.py",
                                  "tests/test_merge_lock_by_project.py"])
def test_ac7_source_file_absent_on_branch(path):
    """Исходного файла волны на HEAD ветки нет.

    Ловит мутацию: разработчик перенёс тесты, но оставил исходный файл
    (или вернул его переходным модулем) — файл есть в HEAD, тест краснеет.
    """
    assert _plan.show(CODE_ROOT, "HEAD", path) is None, f"{path} есть на ветке"


def test_ac7_each_source_test_lives_in_its_module_file_only():
    """Тесты замка и `LegacyTouchHeartbeatTest` — в файле модуля замка, тесты очереди и двух классов by_project — в файле очереди.

    Для каждого исходного теста, не названного в PLAN удалённым дублем,
    функция с его именем есть в его файле модуля и нет в другом.

    Ловит мутацию: `WaitTextsAnyOrderTest::test_texts_name_own_project_
    holder_in_every_insertion_order` положен в `tests/test_merge_lock_module.py`
    (или `LegacyTouchHeartbeatTest` — в файл очереди) — функция не в своём
    файле, тест краснеет с ней.
    """
    removed = set(_plan.removed_duplicates(_ctx.plan_text()))
    trees = _ctx.head_trees()
    problems = []
    for test in _ctx.base_tests().values():
        if test.key in removed:
            continue
        other = next(p for p in _plan.MODULE_FILES if p != test.target)
        if not _plan.moved_to(test.name, _plan.module_tests(trees[test.target])):
            problems.append(f"{test.key}: нет в {test.target}")
        if _plan.moved_to(test.name, _plan.module_tests(trees[other])):
            problems.append(f"{test.key}: лежит в {other}")
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-17

def test_ac17_tests_diff_only_new_lock_module_rewritten_queue_and_two_deletions():
    """Дифф `tests/` от базы — `A` файла модуля замка, `M` файла очереди, `D` двух исходных файлов.

    `git diff --name-status --no-renames <база> HEAD -- tests/` даёт ровно
    эти четыре строки; неотслеживаемых путей под `tests/`, кроме них, нет.

    Ловит мутацию: при своде заведён общий `tests/merge_stand.py` для двух
    файлов модулей (или исходный файл сведён, а не удалён) — лишняя или
    иная строка диффа, тест краснеет с ней.
    """
    out = _plan.git_out(CODE_ROOT, "diff", "--name-status", "--no-renames",
                        _ctx.base(), "HEAD", "--", "tests/")
    entries = sorted(tuple(line.split("\t", 1)) for line in out.splitlines()
                     if line.strip())
    expected = sorted([("A", _plan.LOCK_MODULE), ("M", _plan.QUEUE_FILE),
                       ("D", _plan.LOCK_SOURCE), ("D", _plan.BY_PROJECT_SOURCE)])
    assert entries == expected, f"дифф tests/ ветки: {entries}\nожидалось: {expected}"
    stray = sorted(p for p in changed_paths() if p.startswith("tests/")
                   and p not in _ALLOWED)
    assert not stray, f"посторонние пути tests/: {stray}"


def test_ac17_branch_diff_outside_tests_only_codebase_map():
    """Вне `tests/` дифф ветки от базы — не больше `docs/codebase-map.md`.

    Ловит мутацию: разработчик поправил `orchestrator/merge_queue.py` или
    `docs/backlog.md` «заодно» — путь в диффе, тест краснеет с ним.
    """
    out = _plan.git_out(CODE_ROOT, "diff", "--name-only", "--no-renames",
                        _ctx.base(), "HEAD")
    stray = sorted(p for p in out.splitlines() if p.strip()
                   and not p.startswith("tests/") and p != _plan.MAP_FILE
                   and not p.startswith(f"tasks/{TASK_ID}/"))
    assert not stray, f"посторонние пути диффа ветки: {stray}"


def test_ac17_orchestrator_and_requirement_17_files_untouched():
    """`orchestrator/` и файлы требования 17 в пути задачи не входят.

    Ни один путь задачи (закоммиченный дифф от базы и неотслеживаемые
    файлы) не лежит под `orchestrator/` и не совпадает с `tests/fixtures.py`,
    `tests/sandbox.py`, `tests/test_invariants.py`, долгоживущим файлом
    sleep-guard, `tests/test_merge_gate_ci_wait.py`, `tests/test_release.py`
    или файлом волн 2а-1б/2б-4.

    Ловит мутацию: под фикстуру поправлен `tests/fixtures.py` (или правка
    описания `tests/test_release.py:8`) — путь найден, тест краснеет с ним.
    """
    touched = sorted(p for p in changed_paths()
                     if p.startswith("orchestrator/") or p in _KEPT)
    assert not touched, f"изменены запретные пути: {touched}"


def test_ac17_codebase_map_equals_generator_output_on_branch_tree():
    """`docs/codebase-map.md` на ветке равна выводу генератора по дереву HEAD.

    Генератор `scripts/codebase_map.py` (`build_modules` + `render`) строит
    карту по дереву HEAD (`orchestrator/`, `scripts/`, `tests/`, выгруженные
    `git archive`); её содержимое без строки `built_at_sha` совпадает с
    закоммиченным построчно.

    Ловит мутацию: роль не регенерировала карту после удаления
    `tests/test_merge_lock.py` (или вписала раздел руками) — строки
    расходятся, тест краснеет с первым расхождением.
    """
    head_map = _ctx.head_text(_plan.MAP_FILE)
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
        pytest.fail(f"{_plan.MAP_FILE} на HEAD не равна выводу генератора: строка "
                    f"{diff + 1}: генератор {want[diff:diff + 1]!r}, на ветке "
                    f"{got[diff:diff + 1]!r}")


@pytest.mark.parametrize("path", ["tests/test_merge_lock_module.py",
                                  "tests/test_merge_queue.py"])
def test_ac17_no_skip_or_xfail_in_module_file(path):
    """В файле модуля нет `skip`/`xfail` ни в каком виде.

    Ни обращений `pytest.mark.skip`/`skipif`/`xfail`, `pytest.skip`,
    `unittest.skip*`, `skipTest`, `importorskip`, ни импорта этих имён.

    Ловит мутацию: тест, зависающий без подмены паузы, помечен
    `@pytest.mark.skip(reason="…")` — имя найдено, тест краснеет со строкой.
    """
    tree = ast.parse(_ctx.head_text(path))
    found = [f"{ast.unparse(n)} в строке {n.lineno}" for n in ast.walk(tree)
             if isinstance(n, ast.Attribute) and n.attr in _SKIP_NAMES]
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            found += [f"импорт {a.name}" for a in node.names if a.name in _SKIP_NAMES]
    assert not found, f"skip/xfail в {path}:\n" + "\n".join(found)


@pytest.mark.parametrize("name", list(_LIMIT_KWARGS))
def test_ac17_limits_not_raised_against_source_files(name):
    """Пределы (`timeout`, допуски `delta`/`places`/`rel`/`abs`) файлов модулей не выше исходных.

    Каждое числовое значение предела `name` в двух файлах модулей не больше
    наибольшего значения того же предела в трёх исходных файлах; предела,
    которого в исходных не было, в файлах модулей нет.

    Ловит мутацию: свод поднял `join(timeout=10)` до `join(timeout=30)` или
    добавил `@pytest.mark.timeout(600)` — значение выше исходного (или
    новое), тест краснеет с ним.
    """
    def limits(tree) -> list:
        found = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for kw in node.keywords:
                if kw.arg == name and isinstance(kw.value, ast.Constant) \
                        and isinstance(kw.value.value, (int, float)):
                    found.append(kw.value.value)
            if name == "timeout" and isinstance(node.func, ast.Attribute) \
                    and node.func.attr == "timeout" and node.args \
                    and isinstance(node.args[0], ast.Constant):
                found.append(node.args[0].value)
        return found

    base = [v for tree in _ctx.base_trees().values() for v in limits(tree)]
    new = [v for tree in _ctx.head_trees().values() for v in limits(tree)]
    ceiling = max(base, default=None)
    raised = [v for v in new if ceiling is None or v > ceiling]
    assert not raised, f"предел {name}: значения {raised} при исходном наибольшем {ceiling}"
