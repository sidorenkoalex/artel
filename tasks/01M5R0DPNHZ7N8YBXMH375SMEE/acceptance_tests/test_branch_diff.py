"""AC-6, AC-19: состав ветки задачи и каталога документов — только два
новых модуля, дописка модуля гейта исходов, строка импорта двух импортёров,
удаление двух файлов волны и карта кода; общие фикстуры, песочница гейта
исходов, инварианты, файл двусторонних вариантов и `orchestrator/` не
тронуты; карта кода либо не изменена, либо равна выводу генератора; в
каталоге документов нет временных файлов; в новых и изменённых файлах
`tests/` нет `skip`/`xfail`, пределы не подняты.

Группа: разовый
Красен до реализации: оба файла волны ещё лежат на ветке, а дифф ветки пуст — свод не сделан.

Дифф — от базы ветки задачи (`_pult.DIFF_BASE`, точка расхождения с
`origin`) до HEAD рабочей копии плюс неотслеживаемые файлы
(`_pult.changed_paths`); при распознанном переименовании берутся оба пути
(`git diff --no-renames`). Каталог документов — первый уровень
`tasks/<id>/` ссылки документов ревизии выкладки (`git ls-tree`). Карта
кода сверяется как в CI: содержимым без строки `built_at_sha`; генератор
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

import _ctx  # noqa: E402
import _plan  # noqa: E402
from _pult import CODE_ROOT, changed_paths  # noqa: E402

_ADDED = {_plan.MERGE_SANDBOX: "A", _plan.MERGE_MODULE: "A"}
_MODIFIED = {_plan.GATE_MODULE: "M", **{p: "M" for p in _plan.IMPORTERS}}
_DELETED = {p: "D" for p in _plan.SOURCE_FILES}
_ALLOWED = {**_ADDED, **_MODIFIED, **_DELETED}
# Новые и изменённые файлы `tests/` задачи (AC-19: skip/xfail, пределы).
_CHANGED_TESTS = (_plan.MERGE_SANDBOX, _plan.MERGE_MODULE, _plan.GATE_MODULE,
                  *_plan.IMPORTERS)
_SKIP_NAMES = {"skip", "skipif", "xfail", "skipTest", "importorskip",
               "skipIf", "skipUnless", "expectedFailure"}
_AMBIGUOUS_SKIP = {"skip", "skipif"}
_SKIP_OWNERS = {"pytest", "mark", "unittest"}
_LIMITS = ("timeout", "delta", "places", "rel", "abs", "full_suite_timeout_sec")


def _without_built_at(text: str) -> list:
    return [line for line in text.splitlines()
            if not line.startswith("built_at_sha:")]


def _diff_entries() -> list:
    out = _plan.git_out(CODE_ROOT, "diff", "--name-status", "--no-renames",
                        _ctx.base(), "HEAD")
    return [tuple(line.split("\t", 1)) for line in out.splitlines() if line.strip()]


def _task_paths() -> set:
    return {p for _status, p in _diff_entries()} | set(changed_paths())


# ------------------------------------------------------------------ AC-6

def test_ac6_branch_diff_names_only_allowed_paths_with_their_statuses():
    """Дифф ветки против базы называет только два новых модуля, модуль гейта исходов, два импортёра, удаление двух файлов волны и карту кода.

    Пути закоммиченного диффа (без поиска переименований) и неотслеживаемые
    файлы рабочей копии вне `tasks/<id>/` — подмножество перечня критерия
    плюс `docs/codebase-map.md`; у каждого пути перечня в диффе свой статус:
    новые модули — `A`, модуль гейта исходов и импортёры — `M`, файлы
    волны — `D`.

    Ловит мутацию: роль оставила в рабочей копии сценарий свода
    `tests/_convert_merge.py` или выгрузку `mutation_before.txt`, либо
    файл волны не удалён, а опустошён, либо импортёр не переведён на новый
    модуль — лишний путь или статус не тот, тест краснеет с ним.
    """
    entries = _diff_entries()
    paths = [p for _status, p in entries] + changed_paths()
    stray = sorted({p for p in paths if p not in _ALLOWED and p != _plan.MAP_FILE})
    assert not stray, ("пути ветки вне перечня критерия и карты кода:\n"
                       + "\n".join(stray))
    statuses = {path: status for status, path in entries}
    wrong = [f"{path}: {statuses.get(path)!r}, ожидалось {want}"
             for path, want in sorted(_ALLOWED.items())
             if statuses.get(path) != want]
    assert not wrong, "статусы путей диффа:\n" + "\n".join(wrong)


def test_ac6_docs_dir_has_no_temporary_files_or_subdirs():
    """В каталоге документов нет подкаталогов, кроме `acceptance_tests/`, и посторонних `test_*`/`mutation-*`.

    Первый уровень `tasks/<id>/` ссылки документов: каждый подкаталог —
    `acceptance_tests`; каждый файл с именем, начинающимся на `test_` или
    `mutation-`, — патч `mutation-<nnn>.diff` или копия таблицы
    `mutation-run-<номер>.tsv`.

    Ловит мутацию: роль положила в каталог документов выгрузку
    `mutation-before.txt`, сценарий `test_convert.py` или каталог
    `scratch/` — запись найдена, тест краснеет с её именем.
    """
    entries = _ctx.docs_typed_entries()
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


# ------------------------------------------------------------------ AC-19

@pytest.mark.parametrize("path", list(_plan.SOURCE_FILES))
def test_ac19_wave_file_absent_on_branch(path):
    """Файла волны (`merge_outcome_gate`, `added_lines`) в дереве HEAD ветки нет.

    Ловит мутацию: разработчик перенёс тесты, но не удалил исходный файл —
    путь найден в HEAD, тест краснеет с ним.
    """
    out = _plan.git_out(CODE_ROOT, "ls-tree", "--name-only", "HEAD", "--", path)
    assert not out.strip(), f"{path} есть на ветке"


@pytest.mark.parametrize("path", [
    "tests/outcome_gate_sandbox.py",
    "tests/fixtures.py",
    "tests/sandbox.py",
    "tests/test_invariants.py",
    "tests/test_01m56tnz3e72xy9xstavs99cn2_two_sided_variants.py",
])
def test_ac19_kept_file_untouched(path):
    """Песочница гейта исходов, общие фикстуры, инварианты и файл двусторонних вариантов — не среди путей задачи.

    Путь `path` не входит ни в закоммиченный дифф ветки от базы, ни в
    неотслеживаемые файлы рабочей копии.

    Ловит мутацию: под функцию модуля `no_gate_refusal(box, …, case=…)`
    поправлен метод `OutcomeGateSandbox.no_gate_refusal` в
    `tests/outcome_gate_sandbox.py`, или фикстура `box` дописана в
    `tests/fixtures.py` — путь найден среди путей задачи, тест краснеет.
    """
    assert path not in _task_paths(), f"{path} изменён"


def test_ac19_orchestrator_untouched():
    """Ни один путь задачи не лежит под `orchestrator/`.

    Ловит мутацию: мутация патча осталась в рабочей копии и закоммичена
    (или «заодно» поправлен `orchestrator/advance_gates/outcome_integrity.py`)
    — путь найден, тест краснеет с ним.
    """
    touched = sorted(p for p in _task_paths() if p.startswith("orchestrator/"))
    assert not touched, f"изменены пути orchestrator/: {touched}"


def test_ac19_codebase_map_unchanged_or_equal_to_generator_output():
    """`docs/codebase-map.md` на ветке не изменён либо равен выводу генератора по дереву HEAD.

    Если карта на HEAD отличается от базы, генератор `scripts/codebase_map.py`
    (`build_modules` + `render`) строит карту по дереву HEAD
    (`orchestrator/`, `scripts/`, `tests/`, выгруженные `git archive`), и
    её содержимое без строки `built_at_sha` совпадает с закоммиченным
    построчно.

    Ловит мутацию: роль руками вычеркнула из карты раздел удалённого файла
    (или перегенерировала карту до финальной правки модуля) — строки
    расходятся, тест краснеет с первым расхождением.
    """
    base_map = _plan.show(CODE_ROOT, _ctx.base(), _plan.MAP_FILE)
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


@pytest.mark.parametrize("path", list(_CHANGED_TESTS))
def test_ac19_no_skip_or_xfail_in_new_and_changed_test_files(path):
    """В новых и изменённых файлах `tests/` задачи нет `skip`/`xfail` ни в каком виде, которого не было на базе.

    Число обращений `pytest.mark.skip`/`skipif`/`xfail`, `pytest.skip`,
    `unittest.skip*`, `skipTest`, `importorskip` и импортов этих имён в
    файле на HEAD не больше, чем в его версии на базе (у нового файла — 0).

    Ловит мутацию: тест, упавший после свода, помечен
    `@pytest.mark.skip(reason="…")` или `pytest.xfail(...)` — обращение
    найдено, тест краснеет со строкой.
    """
    def skips(tree) -> list:
        found = [f"{ast.unparse(n)} в строке {n.lineno}" for n in ast.walk(tree)
                 if isinstance(n, ast.Attribute) and n.attr in _SKIP_NAMES
                 and (n.attr not in _AMBIGUOUS_SKIP
                      or ast.unparse(n.value).rsplit(".", 1)[-1] in _SKIP_OWNERS)]
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                found += [f"импорт {a.name}" for a in node.names
                          if a.name in _SKIP_NAMES]
        return found

    head = skips(_ctx.head_tree(path))
    old = _plan.show(CODE_ROOT, _ctx.base(), path)
    base = skips(ast.parse(old)) if old is not None else []
    assert len(head) <= len(base), (f"skip/xfail в {path} (на базе {len(base)}):\n"
                                    + "\n".join(head))


def _limits(tree) -> dict:
    """{имя предела: [числа]} — именованные аргументы пределов,
    `mark.timeout(<n>)` и ключи словарей-литералов с числовым значением."""
    found = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and key.value in _LIMITS \
                        and isinstance(value, ast.Constant) \
                        and isinstance(value.value, (int, float)) \
                        and not isinstance(value.value, bool):
                    found.setdefault(key.value, []).append(value.value)
        if not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            if kw.arg in _LIMITS and isinstance(kw.value, ast.Constant) \
                    and isinstance(kw.value.value, (int, float)) \
                    and not isinstance(kw.value.value, bool):
                found.setdefault(kw.arg, []).append(kw.value.value)
        if isinstance(node.func, ast.Attribute) and node.func.attr == "timeout" \
                and node.args and isinstance(node.args[0], ast.Constant):
            found.setdefault("timeout", []).append(node.args[0].value)
    return found


@pytest.mark.parametrize("name", list(_LIMITS))
def test_ac19_limits_not_raised_against_sources(name):
    """Пределы (`timeout`, допуски, `full_suite_timeout_sec`) в новых и изменённых файлах `tests/` не выше исходных.

    Каждое числовое значение предела `name` в этих файлах на HEAD
    (именованный аргумент, `mark.timeout(<n>)`, ключ словаря-литерала) не
    больше наибольшего значения того же предела в файлах волны, модуле
    гейта исходов и импортёрах на базе; предела, которого там не было, на
    HEAD нет.

    Ловит мутацию: свод добавил `@pytest.mark.timeout(600)` долгому тесту
    бывшего `Ac3MergePrepareTest` или поднял `timeout=` вызова — значение
    выше исходного (или новое), тест краснеет с ним.
    """
    base = []
    for path in (*_plan.SOURCE_FILES, _plan.GATE_MODULE, *_plan.IMPORTERS):
        base += _limits(_ctx.base_tree(path)).get(name, [])
    ceiling = max(base, default=None)
    raised = []
    for path in _CHANGED_TESTS:
        raised += [f"{path}: {v}" for v in _limits(_ctx.head_tree(path)).get(name, [])
                   if ceiling is None or v > ceiling]
    assert not raised, (f"предел {name}: значения {raised} при исходном "
                        f"наибольшем {ceiling}")
