"""AC-6, AC-7 (файлы на ветке), AC-16: состав ветки и рабочей копии — шесть
файлов волны удалены, в `tests/test_merge_after_module.py` только
добавления и прежние определения не тронуты, карта кода — вывод
генератора, файлы требования 16, `orchestrator/` и `scripts/` не тронуты,
нет новых `skip`/`xfail` и пределы не выше исходных; в рабочей копии и в
каталоге документов нет временных файлов.

Группа: разовый
Красен до реализации: на ветке ещё лежат шесть файлов волны и в модуль ничего не дописано — свод не сделан.

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

# Файлы требования 16 SPEC (кроме кода `orchestrator/` и `scripts/`).
_KEPT = (
    "tests/test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py",
    "tests/test_01m45d29bqje8fjyja4jqwsyfz_spec_gate_declared.py",
    "tests/fixtures.py",
    "tests/sandbox.py",
    "tests/test_invariants.py",
    "tests/test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard.py",
    "tests/test_fsm_map_regen.py",
)
_ALLOWED = (_plan.MODULE, *_plan.SOURCE_FILES, _plan.MAP_FILE)
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
    """`git status --porcelain` рабочей копии называет только модуль, шесть файлов волны и карту кода.

    Вывод `git status --porcelain --untracked-files=all` без выкладки
    планки (`tasks/<id>/`) не содержит путей вне
    `tests/test_merge_after_module.py`, шести файлов волны и
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

@pytest.mark.parametrize("path", list(_plan.SOURCE_FILES))
def test_ac7_wave_file_absent_on_branch(path):
    """Файла волны на HEAD ветки нет.

    Ловит мутацию: разработчик перенёс тесты, но оставил исходный файл
    (или вернул его переходным модулем) — файл есть в HEAD, тест краснеет.
    """
    assert _plan.show(CODE_ROOT, "HEAD", path) is None, f"{path} есть на ветке"


def test_ac7_module_diff_is_additions_only():
    """Дифф `tests/test_merge_after_module.py` против базы — только добавленные строки.

    `git diff -U0 --no-renames <база> HEAD -- tests/test_merge_after_module.py`
    не несёт ни одной удалённой строки (`-…`, кроме заголовка `---`), и
    хотя бы одна строка добавлена.

    Ловит мутацию: при своде дописан `github_adapter` в перечень `from
    orchestrator import (…)` (строки :46–47 переписаны), поправлена строка
    существующего теста или переписан докстринг модуля вместо дополнения
    — удалённая строка в диффе, тест краснеет с ней.
    """
    out = _plan.git_out(CODE_ROOT, "diff", "-U0", "--no-renames", _ctx.base(),
                        "HEAD", "--", _plan.MODULE)
    removed = [line for line in out.splitlines()
               if line.startswith("-") and not line.startswith("---")]
    added = [line for line in out.splitlines()
             if line.startswith("+") and not line.startswith("+++")]
    assert not removed, "удалённые строки против базы:\n" + "\n".join(removed[:20])
    assert added, "против базы ничего не добавлено"


def test_ac7_existing_definitions_of_module_unchanged():
    """Каждое определение верхнего уровня прежнего модуля (20 тестов, фикстуры, функции, константы, `DivisionSandbox`) есть в HEAD тем же.

    Для каждой функции, класса и присваивания верхнего уровня модуля в
    базе ветки в HEAD есть ровно одно определение того же имени, и его
    `ast.dump` (с декораторами, параметрами и телом) совпадает; тестов в
    базе модуля — 20.

    Ловит мутацию: свод переопределил `journal` ниже с телом из `plan`, или
    `SPEC_TEXT` — значением `guard`, или поправил фикстуру
    `merge_after_stand` — определение удвоено или иное, тест краснеет с
    именем.
    """
    base_tree = _ctx.base_module_tree()
    head_tree = _ctx.head_tree()
    total = len(_plan.module_tests(base_tree))
    assert total == _plan.MODULE_BASE_TESTS, (
        f"в базе модуля тестов {total}, SPEC называет {_plan.MODULE_BASE_TESTS}")
    problems = []
    for node in base_tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names = [node.name]
        elif isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        else:
            continue
        for name in names:
            twins = _plan.top_level_defs(head_tree, name)
            if len(twins) != 1:
                problems.append(f"{name}: в HEAD определений {len(twins)}")
            elif ast.dump(_plan.clean(twins[0])) != ast.dump(_plan.clean(node)):
                problems.append(f"{name}: изменено против базы")
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-16

def test_ac16_tests_diff_only_module_and_six_deletions():
    """Дифф `tests/` от базы — `M` модуля и `D` шести файлов волны.

    `git diff --name-status --no-renames <база> HEAD -- tests/` даёт ровно
    эти семь строк; неотслеживаемых путей под `tests/`, кроме них, нет.

    Ловит мутацию: при своде заведён общий `tests/merge_after_stands.py`
    (или поправлен `tests/sandbox.py`, или файл волны сведён, а не
    удалён) — лишняя или иная строка диффа, тест краснеет с ней.
    """
    out = _plan.git_out(CODE_ROOT, "diff", "--name-status", "--no-renames",
                        _ctx.base(), "HEAD", "--", "tests/")
    entries = sorted(tuple(line.split("\t", 1)) for line in out.splitlines()
                     if line.strip())
    expected = sorted([("M", _plan.MODULE),
                       *(("D", p) for p in _plan.SOURCE_FILES)])
    assert entries == expected, f"дифф tests/ ветки: {entries}\nожидалось: {expected}"
    stray = sorted(p for p in changed_paths() if p.startswith("tests/")
                   and p not in _ALLOWED)
    assert not stray, f"посторонние пути tests/: {stray}"


def test_ac16_branch_diff_outside_tests_only_codebase_map():
    """Вне `tests/` дифф ветки от базы — не больше `docs/codebase-map.md`.

    Ловит мутацию: разработчик поправил `orchestrator/merge_after.py`,
    `scripts/guard.py` или `docs/backlog.md` «заодно» — путь в диффе, тест
    краснеет с ним.
    """
    out = _plan.git_out(CODE_ROOT, "diff", "--name-only", "--no-renames",
                        _ctx.base(), "HEAD")
    stray = sorted(p for p in out.splitlines() if p.strip()
                   and not p.startswith("tests/") and p != _plan.MAP_FILE
                   and not p.startswith(f"tasks/{TASK_ID}/"))
    assert not stray, f"посторонние пути диффа ветки: {stray}"


def test_ac16_code_and_requirement_16_files_untouched():
    """`orchestrator/`, `scripts/` и файлы требования 16 в пути задачи не входят.

    Ни один путь задачи (закоммиченный дифф от базы и неотслеживаемые
    файлы) не лежит под `orchestrator/` или `scripts/` и не совпадает с
    `…merge_gate_merge_after.py`, `…spec_gate_declared.py`,
    `tests/fixtures.py`, `tests/sandbox.py`, `tests/test_invariants.py`,
    долгоживущим файлом sleep-guard, `tests/test_fsm_map_regen.py`.

    Ловит мутацию: под фикстуру поправлен `tests/fixtures.py` (или
    перенесён заодно `…merge_gate_merge_after.py` волны 3м-2в) — путь
    найден, тест краснеет с ним.
    """
    touched = sorted(p for p in changed_paths()
                     if p.startswith(("orchestrator/", "scripts/")) or p in _KEPT)
    assert not touched, f"изменены запретные пути: {touched}"


def test_ac16_codebase_map_equals_generator_output_on_branch_tree():
    """`docs/codebase-map.md` на ветке равна выводу генератора по дереву HEAD.

    Генератор `scripts/codebase_map.py` (`build_modules` + `render`) строит
    карту по дереву HEAD (`orchestrator/`, `scripts/`, `tests/`, выгруженные
    `git archive`); её содержимое без строки `built_at_sha` совпадает с
    закоммиченным построчно.

    Ловит мутацию: роль не регенерировала карту после удаления шести файлов
    волны (или вписала раздел модуля руками) — строки расходятся, тест
    краснеет с первым расхождением.
    """
    head_map = _ctx.head_text(_plan.MAP_FILE)
    archive = subprocess.run(
        ["git", "-C", str(CODE_ROOT), "archive", "--format=tar", "HEAD",
         "orchestrator", "scripts", "tests"], capture_output=True, timeout=60)
    assert archive.returncode == 0, f"git archive HEAD: {archive.stderr!r}"
    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(fileobj=io.BytesIO(archive.stdout)) as tar:
            tar.extractall(tmp, filter="data")
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


def _skip_uses(tree) -> list:
    found = [ast.unparse(n) for n in ast.walk(tree)
             if isinstance(n, ast.Attribute) and n.attr in _SKIP_NAMES]
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            found += [f"импорт {a.name}" for a in node.names if a.name in _SKIP_NAMES]
    return found


def test_ac16_no_new_skip_or_xfail_in_module():
    """В модуле нет новых `skip`/`xfail` против базы.

    Каждое обращение `pytest.mark.skip`/`skipif`/`xfail`, `pytest.skip`,
    `unittest.skip*`, `skipTest`, `importorskip` (и импорт этих имён) в
    модуле HEAD встречается не чаще, чем в базе — в шести файлах волны и
    прежнем модуле вместе.

    Ловит мутацию: тест `answer`, падающий без origin, помечен
    `@pytest.mark.skip(reason="…")` — обращение новое, тест краснеет с ним.
    """
    base = [u for t in (*_ctx.base_trees().values(), _ctx.base_module_tree())
            for u in _skip_uses(t)]
    new = _skip_uses(_ctx.head_tree())
    extra = list(new)
    for use in base:
        if use in extra:
            extra.remove(use)
    assert not extra, "новые skip/xfail в модуле:\n" + "\n".join(extra)


@pytest.mark.parametrize("name", list(_LIMIT_KWARGS))
def test_ac16_limits_not_raised_against_source_files(name):
    """Пределы (`timeout`, допуски `delta`/`places`/`rel`/`abs`) модуля не выше исходных.

    Каждое числовое значение предела `name` в модуле HEAD не больше
    наибольшего значения того же предела в шести файлах волны и прежнем
    модуле базы; предела, которого в базе не было, в модуле нет.

    Ловит мутацию: свод добавил `@pytest.mark.timeout(600)` перенесённому
    тесту `answer` с настоящим git — значение выше исходного (или новое),
    тест краснеет с ним.
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

    base = [v for tree in (*_ctx.base_trees().values(), _ctx.base_module_tree())
            for v in limits(tree)]
    new = limits(_ctx.head_tree())
    ceiling = max(base, default=None)
    raised = [v for v in new if ceiling is None or v > ceiling]
    assert not raised, f"предел {name}: значения {raised} при исходном наибольшем {ceiling}"
