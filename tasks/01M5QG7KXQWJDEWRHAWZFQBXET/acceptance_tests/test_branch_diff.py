"""AC-5, AC-16: состав ветки задачи и рабочей копии — удалён crg, правлены
модуль и карта кода (равная выводу генератора), файлы требования 18 и
`orchestrator/` не тронуты, в модуле нет `skip`/`xfail` и пределы не выше
исходных; в рабочей копии и каталоге документов нет временных файлов.

Группа: разовый
Красен до реализации: на ветке crg ещё есть, модуль и карта не правлены — дифф ветки пуст, удаления crg в нём нет.

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

# Файлы требования 18 SPEC, которые не меняются.
_KEPT = (
    "tests/report_outcome_sandbox.py",
    "tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py",
    "tests/test_invariants.py",
    "tests/fixtures.py",
    "tests/sandbox.py",
    "tests/fd_wait.py",
    "tests/test_outcome_integrity_added_lines.py",
    "tests/test_outcome_gate_module.py",
    "tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py",
)
_ALLOWED = (_plan.SOURCE_FILE, _plan.NEW_FILE, _plan.MAP_FILE)
_SKIP_NAMES = {"skip", "skipif", "xfail", "skipTest", "importorskip",
               "skipIf", "skipUnless", "expectedFailure"}
_AMBIGUOUS_SKIP = {"skip", "skipif"}
_SKIP_OWNERS = {"pytest", "mark", "unittest"}
_LIMIT_KWARGS = ("timeout", "delta", "places", "rel", "abs")


def _without_built_at(text: str) -> list:
    return [line for line in text.splitlines()
            if not line.startswith("built_at_sha:")]


def _tree(revision: str, path: str) -> ast.Module:
    assert revision, "база диффа ветки задачи не определена при выкладке"
    text = _plan.show(CODE_ROOT, revision, path)
    assert text is not None, f"{path} нет в ревизии {revision}"
    return ast.parse(text)


def _limits(tree) -> dict:
    """{имя предела: [числа]} — именованные аргументы пределов и
    `mark.timeout(<n>)` с числовым значением."""
    found = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            if kw.arg in _LIMIT_KWARGS and isinstance(kw.value, ast.Constant) \
                    and isinstance(kw.value.value, (int, float)):
                found.setdefault(kw.arg, []).append(kw.value.value)
        if isinstance(node.func, ast.Attribute) and node.func.attr == "timeout" \
                and node.args and isinstance(node.args[0], ast.Constant):
            found.setdefault("timeout", []).append(node.args[0].value)
    return found


# ------------------------------------------------------------------ AC-5

def test_ac5_worktree_status_names_only_task_paths():
    """`git status --porcelain` рабочей копии называет только модуль, удаление crg и карту кода.

    Вывод `git status --porcelain --untracked-files=all` рабочей копии без
    выкладки планки (`tasks/<id>/`) не содержит путей вне
    `tests/test_report_outcome_module.py`,
    `tests/test_component_report_gates.py` и `docs/codebase-map.md`.

    Ловит мутацию: шаг developer оборвался и оставил в рабочей копии
    сценарий свода `convert_crg.py` или выгрузку `run.log` в корне — путь в
    выводе `git status`, тест краснеет с ним.
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


def test_ac5_docs_dir_files_not_named_test_or_mutation():
    """Файлы первого уровня каталога документов с расширением не `.md`, кроме патчей и копий таблиц, не называются `test_*`/`mutation-*`.

    Первый уровень `tasks/<id>/` ссылки документов: каждый файл, кроме
    `*.md`, патчей `mutation-<nnn>.diff` и справочных копий таблиц
    `mutation-run-<n>.tsv` (ANSWER-1 п. 1), не начинается с `test_` и
    `mutation-`.

    Ловит мутацию: роль положила черновик `mutation-014.py` или
    `test_crg_tmp.py` первым уровнем каталога документов — имя найдено,
    тест краснеет с ним.
    """
    entries = _plan.docs_entry_types(DOCS_REPO, DOCS_REVISION, TASK_ID)
    assert entries, f"tasks/{TASK_ID}/ в ссылке документов пуст или не прочитан"
    bad = sorted(name for name, kind in entries.items()
                 if kind == "blob" and not name.endswith(".md")
                 and not _plan.PATCH_NAME.match(name)
                 and not _plan.TABLE_COPY.match(name)
                 and name.startswith(("test_", "mutation-")))
    assert not bad, "файлы test_*/mutation-* в каталоге документов: " + ", ".join(bad)


# ------------------------------------------------------------------ AC-16

def test_ac16_branch_diff_only_crg_deletion_module_and_map():
    """Дифф ветки от базы — удаление crg, правка модуля и, кроме них, только карта кода.

    `git diff --name-status --no-renames <база> HEAD` содержит `D`
    `tests/test_component_report_gates.py` и `M`
    `tests/test_report_outcome_module.py`; кроме них — разве что `M`
    `docs/codebase-map.md`; неотслеживаемых путей вне них нет.

    Ловит мутацию: свод заодно поправил `tests/report_outcome_sandbox.py`
    (или вынес помощники в новый `tests/crg_helpers.py`) — лишняя строка
    диффа, тест краснеет с ней.
    """
    assert DIFF_BASE, "база диффа ветки задачи не определена при выкладке"
    out = _plan.git_out(CODE_ROOT, "diff", "--name-status", "--no-renames",
                        DIFF_BASE, "HEAD")
    entries = {tuple(line.split("\t", 1)) for line in out.splitlines() if line.strip()}
    need = {("D", _plan.SOURCE_FILE), ("M", _plan.NEW_FILE)}
    allowed = need | {("M", _plan.MAP_FILE)}
    assert need <= entries, f"в диффе ветки нет {sorted(need - entries)}: {sorted(entries)}"
    assert entries <= allowed, f"лишнее в диффе ветки: {sorted(entries - allowed)}"
    stray = sorted(p for p in changed_paths() if p not in _ALLOWED)
    assert not stray, f"посторонние пути задачи: {stray}"


def test_ac16_requirement_18_files_and_orchestrator_untouched():
    """Файлы требования 18 и всё под `orchestrator/` в пути задачи не входят и на HEAD равны базе.

    Ловит мутацию: под свод поправлен `tests/report_outcome_sandbox.py`
    (или `orchestrator/acceptance.py` «заодно», или переходной модуль
    задачи 01M590GJAF0EDV4NBC4C99MFVH) — путь среди путей задачи либо
    текст HEAD отличается от базы, тест краснеет с ним.
    """
    assert DIFF_BASE, "база диффа ветки задачи не определена при выкладке"
    touched = sorted(p for p in changed_paths()
                     if p.startswith("orchestrator/") or p in _KEPT)
    differ = sorted(p for p in _KEPT if _plan.show(CODE_ROOT, "HEAD", p)
                    != _plan.show(CODE_ROOT, DIFF_BASE, p))
    res = _plan.git(CODE_ROOT, "diff", "--quiet", DIFF_BASE, "HEAD", "--",
                    "orchestrator/")
    assert not touched, f"изменены запретные пути: {touched}"
    assert not differ, f"на HEAD отличаются от базы: {differ}"
    assert res.returncode == 0, "orchestrator/ на HEAD отличается от базы"


def test_ac16_codebase_map_equals_generator_output():
    """`docs/codebase-map.md` на HEAD равен выводу генератора по дереву HEAD.

    Генератор `scripts/codebase_map.py` (`build_modules` + `render`) строит
    карту по дереву HEAD (`orchestrator/`, `scripts/`, `tests/`,
    выгруженные `git archive`), и её содержимое без строки `built_at_sha`
    совпадает с закоммиченным построчно.

    Ловит мутацию: роль удалила crg, но карту не регенерировала (раздел
    `tests/test_component_report_gates.py` в ней остался) или правила её
    руками — строки расходятся, тест краснеет с первым расхождением.
    """
    head_map = _plan.show(CODE_ROOT, "HEAD", _plan.MAP_FILE)
    assert head_map is not None, f"{_plan.MAP_FILE} нет в HEAD ветки"
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


def test_ac16_no_skip_or_xfail_in_module():
    """В модуле нет `skip`/`xfail` ни в каком виде.

    Ни обращений `pytest.mark.skip`/`skipif`/`xfail`, `pytest.skip`,
    `unittest.skip*`, `skipTest`, `importorskip`, ни импорта этих имён.

    Ловит мутацию: долгий перенесённый тест помечен
    `@pytest.mark.skip(reason="…")` или `pytest.xfail(...)` — имя найдено,
    тест краснеет со строкой.
    """
    tree = _tree("HEAD", _plan.NEW_FILE)
    found = [f"{ast.unparse(n)} в строке {n.lineno}" for n in ast.walk(tree)
             if isinstance(n, ast.Attribute) and n.attr in _SKIP_NAMES
             and (n.attr not in _AMBIGUOUS_SKIP
                  or ast.unparse(n.value).rsplit(".", 1)[-1] in _SKIP_OWNERS)]
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            found += [f"импорт {a.name}" for a in node.names if a.name in _SKIP_NAMES]
    assert not found, f"skip/xfail в {_plan.NEW_FILE}:\n" + "\n".join(found)


@pytest.mark.parametrize("name", list(_LIMIT_KWARGS))
def test_ac16_limits_not_raised_against_source(name):
    """Пределы (`timeout`, допуски `delta`/`places`/`rel`/`abs`) модуля не выше исходных.

    Каждое числовое значение предела `name` в модуле HEAD не больше
    наибольшего значения того же предела в crg и модуле базы; предела,
    которого там не было, в модуле нет; `pytest.approx` есть, только если
    он был в исходных файлах.

    Ловит мутацию: свод добавил `@pytest.mark.timeout(600)` перенесённому
    `test_parallel_first_installs_run_once_without_refusal` или поднял
    `timeout=` вызова — значение выше исходного (или новое), тест краснеет
    с ним.
    """
    base, base_approx = {}, False
    for tree in (_tree(DIFF_BASE, _plan.SOURCE_FILE), _tree(DIFF_BASE, _plan.NEW_FILE)):
        for key, values in _limits(tree).items():
            base.setdefault(key, []).extend(values)
        base_approx |= any(isinstance(n, ast.Attribute) and n.attr == "approx"
                           for n in ast.walk(tree))
    head = _tree("HEAD", _plan.NEW_FILE)
    new = _limits(head).get(name, [])
    approx = [n.lineno for n in ast.walk(head)
              if isinstance(n, ast.Attribute) and n.attr == "approx"]
    ceiling = max(base.get(name, []), default=None)
    raised = [v for v in new if ceiling is None or v > ceiling]
    assert not raised, (f"предел {name}: значения {raised} при исходном "
                        f"наибольшем {ceiling}")
    if not base_approx:
        assert not approx, f"pytest.approx в строках {approx}, в исходных его не было"
