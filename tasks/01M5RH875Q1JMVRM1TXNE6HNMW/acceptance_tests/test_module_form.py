"""AC-7, AC-8, AC-9, AC-10, AC-11, AC-12, AC-13, AC-14: форма приёмников
свода — `tests/components_outcome_sandbox.py`,
`tests/test_outcome_components_module.py` и докстринга
`tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py` — против файла
волны и прежних версий в базе ветки.

Группа: разовый
Красен до реализации: на ветке нет tests/components_outcome_sandbox.py и tests/test_outcome_components_module.py, докстринг outcome_prior называет удалённые пути стенда — свод не сделан.

Приёмники читаются из HEAD рабочей копии (`git show HEAD:…`), файл волны и
прежние версии — из базы ветки (`_pult.DIFF_BASE`). Сравнение статическое
(ast): тест не исполняет ни новые, ни исходные тесты, кроме сбора
`pytest --collect-only` `outcome_prior` (AC-8).

Тест файла волны сопоставляется функции нового модуля по имени (то же имя
или имя с суффиксом `_…`) и по строкам соответствия «до → после» PLAN
(докстринг `_plan.py`). Перевод тела по требованию 17 SPEC и решению
Оператора ANSWER-1 п. 2 («`self.` → имя стенда, `self.<помощник>(…)` →
`<помощник>(<стенд>, …)`, `assertX` → `assert` с сообщением вторым
операндом») сверяется каноничным `ast.dump` с обезличенными локальными
именами (переименование локальной переменной сверку не ломает).
"""
import ast
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _ctx  # noqa: E402
import _plan  # noqa: E402
from _pult import CODE_ROOT  # noqa: E402

_STDLIB_OK = {"contextlib", "io"}
_PROJECT_ROOTS = {"tests", "orchestrator", "pytest"}
_CONSTANTS = ("PASSED_ACTION", "OUTCOME_ACTION", "BROKEN_ACTION", "PREPARE_ACTION",
              "SKIP_RECORD", "OUT_OF_BOUNDS", "NOT_RUN", "COUNTS", "FOREIGN")
_FROM_COMPONENTS = ("ComponentsOutcomeSandbox", "ForeignPlankSandbox", *_CONSTANTS)
_COMPONENTS = "tests.components_outcome_sandbox"
_ANCESTORS = ("tests.merge_outcome_sandbox", "tests.outcome_gate_sandbox")
_AC19 = "test_ac19_task_out_of_bounds_still_refused"


def _source_methods() -> list:
    return _plan.base_tests(_plan.SOURCE, _ctx.base_text(_plan.SOURCE))


def _module_tests_tree() -> ast.Module:
    return ast.Module(body=_plan.module_tests(_ctx.module_tree()), type_ignores=[])


def _source_tests_tree() -> ast.Module:
    return ast.Module(body=[t.func for t in _source_methods()], type_ignores=[])


def _shared_fixture_names() -> set:
    return {f.name for f in _plan.module_functions(
        _ctx.head_tree(_plan.FIXTURES_FILE)).values() if _plan.is_fixture(f)}


def _imports_from(tree, module: str) -> dict:
    """{имя: as-имя} инструкций верхнего уровня `from <module> import …`."""
    return {a.name: a.asname for n in tree.body
            if isinstance(n, ast.ImportFrom) and n.module == module
            for a in n.names}


def _assertion_sites(func) -> list:
    """Строки утверждений в теле: `assert`, `pytest.raises`/`fail`,
    `<что-то>.assert*`."""
    return [sub.lineno for sub in ast.walk(func)
            if isinstance(sub, ast.Assert)
            or (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                and (sub.func.attr in ("fail", "raises")
                     or sub.func.attr.startswith("assert")))]


def _called(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return getattr(call.func, "id", None)


def _stand(func) -> str | None:
    """Имя стенда тестовой функции — параметр `box` или `foreign_box`."""
    params = [a.arg for a in func.args.args]
    found = [p for p in params if p in _plan.FIXTURE_CLASS]
    return found[0] if len(found) == 1 else None


def _pairs() -> list:
    """[(BaseTest, функция модуля)] перенесённых тестов."""
    funcs = _ctx.module_functions()
    transfer = _plan.transfer_map(_ctx.plan_or_empty())
    found = []
    for test in _source_methods():
        for func in _ctx.matches(funcs, test.cls, test.func.name, transfer):
            found.append((test, func))
    return found


# ------------------------------------------------------------------ AC-7

def test_ac7_sandbox_module_has_no_tests_or_claims():
    """В `tests/components_outcome_sandbox.py` нет тестовых функций и методов и нет заявок «Ловит мутацию».

    Ловит мутацию: в модуль песочницы уехал класс `Ac19ForeignPlankTest`
    вместе с `ForeignPlankSandbox` (или докстринг теста с заявкой) — имя
    `test_…` или строка «Ловит мутацию» найдены, тест краснеет.
    """
    text = _ctx.head_text(_plan.SANDBOX)
    tests = [f"{n.name} в строке {n.lineno}" for n in ast.walk(ast.parse(text))
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
             and n.name.startswith("test")]
    assert not tests, f"тесты в {_plan.SANDBOX}: {tests}"
    assert _plan.CLAIM not in text, f"заявка «{_plan.CLAIM}» в {_plan.SANDBOX}"


def test_ac7_sandbox_docstring_is_one_line():
    """Докстринг `tests/components_outcome_sandbox.py` — одна непустая строка назначения.

    Ловит мутацию: в модуль перенесён многоабзацный докстринг старого файла
    (или докстринга нет) — тест краснеет.
    """
    doc = ast.get_docstring(_ctx.head_tree(_plan.SANDBOX))
    assert doc and doc.strip(), f"у {_plan.SANDBOX} нет докстринга"
    assert "\n" not in doc.strip(), f"докстринг не одной строкой:\n{doc}"


def test_ac7_sandbox_statements_equal_old_statements_in_order():
    """Операторы верхнего уровня модуля песочницы, кроме докстринга, по `ast.dump` равны в том же порядке операторам старого файла от `import contextlib` до `COUNTS`, `ContextRunnerProc`, `ComponentsOutcomeSandbox`, `FAIL_TO_PASS_ACTION`, `FOREIGN`, `ForeignPlankSandbox`.

    Ловит мутацию: при переносе выброшен неиспользуемый песочницам
    `from orchestrator import answer` или `MATRIX_HEADERS`, `ForeignPlankSandbox`
    поставлен до `ComponentsOutcomeSandbox`, или в
    `ComponentsOutcomeSandbox.writing_task` правлено сообщение — дамп или
    порядок расходятся, тест краснеет с первым расхождением.
    """
    want = _plan.sandbox_statements(_ctx.base_tree(_plan.SOURCE))
    assert len(want) > len(_plan.SANDBOX_NAMES), (
        "в старом файле базы не найдены операторы песочницы — база прочитана не та")
    head = _ctx.head_tree(_plan.SANDBOX).body
    got = _plan.strip_docstring(head)
    assert len(got) == len(head) - 1, "у модуля песочницы нет докстринга первым оператором"
    for i, (w, g) in enumerate(zip(want, got)):
        assert ast.dump(w) == ast.dump(g), (
            f"оператор {i + 1} ({_plan.bound_names(w)}, старая строка {w.lineno}) "
            f"не равен оператору модуля в строке {g.lineno}")
    assert len(got) == len(want), (f"операторов модуля {len(got)}, а переносимых "
                                   f"операторов старого файла {len(want)}")


@pytest.mark.parametrize("path", ["tests/merge_outcome_sandbox.py",
                                  "tests/outcome_gate_sandbox.py"])
def test_ac7_ancestor_sandbox_unchanged(path):
    """Песочница-предок на HEAD побайтно равна базе.

    Ловит мутацию: `ComponentsOutcomeSandbox` дописана в
    `tests/merge_outcome_sandbox.py` (или поправлен метод `writing_task`
    предка) — текст расходится, тест краснеет.
    """
    assert _ctx.head_text(path) == _ctx.base_text(path), f"{path} изменён"


# ------------------------------------------------------------------ AC-8

def _docstring_lines(text: str) -> set:
    node = ast.parse(text).body[0]
    assert isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant), (
        "у outcome_prior базы нет докстринга модуля")
    return set(range(node.lineno, (node.end_lineno or node.lineno) + 1))


def test_ac8_prior_changes_only_two_stand_paths_in_docstring():
    """В `outcome_prior` по сравнению с базой изменены только два пути стенда в докстринге, разбивка строк та же.

    Число строк одно; каждая изменённая строка лежит в докстринге модуля
    базы и равна строке базы с заменой
    `tests.test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.MergeOutcomeSandbox`
    → `tests.merge_outcome_sandbox.MergeOutcomeSandbox` и
    `tests.test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.OutcomeGateSandbox`
    → `tests.outcome_gate_sandbox.OutcomeGateSandbox`; докстринг HEAD равен
    докстрингу базы с этими двумя заменами (обе сделаны).

    Ловит мутацию: заодно поправлен абзац «Провалидировано…» докстринга,
    путь заменён на `tests.merge_outcome_sandbox` без имени класса, или
    абзац «Стенд — …» перенесён по строкам иначе — тест краснеет со строкой.
    """
    base, head = _ctx.base_text(_plan.PRIOR), _ctx.head_text(_plan.PRIOR)
    b, h = base.split("\n"), head.split("\n")
    assert len(b) == len(h), f"{_plan.PRIOR}: строк {len(h)} вместо {len(b)}"
    allowed = _docstring_lines(base)

    def replaced(line: str) -> str:
        for old, new in _plan.PRIOR_PATHS:
            line = line.replace(old, new)
        return line

    changed = [i + 1 for i, (x, y) in enumerate(zip(b, h)) if x != y]
    wrong = [f"строка {n}: {h[n - 1]!r}" for n in changed
             if n not in allowed or h[n - 1] != replaced(b[n - 1])]
    assert not wrong, f"{_plan.PRIOR}: лишние правки:\n" + "\n".join(wrong)
    want = replaced(ast.get_docstring(ast.parse(base), clean=False) or "")
    got = ast.get_docstring(ast.parse(head), clean=False) or ""
    assert got == want, "докстринг outcome_prior не равен базе с заменой двух путей"
    for old, new in _plan.PRIOR_PATHS:
        assert old not in got and new in got, f"путь {old} не заменён на {new}"


def test_ac8_prior_module_without_docstring_equal_to_base():
    """`ast.dump` модуля `outcome_prior` без докстринга на HEAD равен базе.

    Ловит мутацию: заодно с докстрингом поправлен импорт
    `from tests.merge_outcome_sandbox import …` или сообщение утверждения
    теста — дамп расходится, тест краснеет.
    """
    def dump(text: str) -> str:
        tree = ast.parse(text)
        return ast.dump(ast.Module(body=_plan.strip_docstring(tree.body), type_ignores=[]))

    assert dump(_ctx.head_text(_plan.PRIOR)) == dump(_ctx.base_text(_plan.PRIOR)), (
        f"код {_plan.PRIOR} изменён")


def test_ac8_prior_collects_44_tests():
    """`pytest --collect-only` `outcome_prior` на рабочей копии собирает 44 теста.

    Ловит мутацию: правка докстринга сломала синтаксис файла (лишняя
    кавычка) или удаление файла волны сломало импорт песочниц — сбор
    падает или тестов меньше, тест краснеет с выводом сбора.
    """
    res = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q",
         "-p", "no:cacheprovider", _plan.PRIOR],
        cwd=CODE_ROOT, capture_output=True, text=True, timeout=600)
    nodes = [line for line in res.stdout.splitlines() if "::" in line]
    assert res.returncode == 0 and len(nodes) == _plan.PRIOR_COUNT, (
        f"сбор outcome_prior: код {res.returncode}, узлов {len(nodes)} вместо "
        f"{_plan.PRIOR_COUNT}:\n{res.stdout[-3000:]}\n{res.stderr[-2000:]}")


# ------------------------------------------------------------------ AC-9

def test_ac9_no_test_classes_subtest_or_unittest():
    """В `tests/test_outcome_components_module.py` нет тестовых классов, `subTest`, `unittest` и `unittest.main()`; тестовые функции есть.

    Ловит мутацию: свод оставил `class Ac19ForeignPlankTest(ForeignPlankSandbox)`
    с методами `test_…` или хвост `if __name__ == "__main__": unittest.main()`
    с `import unittest` — тест краснеет с находкой.
    """
    tree = _ctx.module_tree()
    assert _plan.module_tests(tree), f"в {_plan.MODULE} нет тестовых функций"
    problems = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            methods = [i.name for i in node.body
                       if isinstance(i, (ast.FunctionDef, ast.AsyncFunctionDef))
                       and i.name.startswith("test")]
            if methods:
                problems.append(f"класс {node.name} в строке {node.lineno}")
        if isinstance(node, ast.Attribute) and node.attr == "subTest":
            problems.append(f"subTest в строке {node.lineno}")
        if isinstance(node, (ast.Import, ast.ImportFrom)) and (
                any(a.name.split(".")[0] == "unittest" for a in node.names)
                or (getattr(node, "module", None) or "").split(".")[0] == "unittest"):
            problems.append(f"импорт unittest в строке {node.lineno}")
        if isinstance(node, ast.Name) and node.id == "unittest":
            problems.append(f"unittest в строке {node.lineno}")
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("name", list(_FROM_COMPONENTS))
def test_ac9_name_imported_from_components_sandbox_only(name):
    """Имя импортировано из `tests.components_outcome_sandbox` без переименования и ни из `tests.merge_outcome_sandbox`, ни из `tests.outcome_gate_sandbox`.

    Ловит мутацию: `PREPARE_ACTION` (или `PASSED_ACTION`) взят из
    `tests.merge_outcome_sandbox`, где есть одноимённая константа, или
    `COUNTS` переписан литералом в модуль — импорта из песочницы
    компонентов нет либо есть импорт из предка, тест краснеет с именем.
    """
    tree = _ctx.module_tree()
    names = _imports_from(tree, _COMPONENTS)
    assert name in names and names[name] in (None, name), (
        f"{name} не импортирован из {_COMPONENTS}")
    elsewhere = [m for m in _ANCESTORS if name in _imports_from(tree, m)]
    assert not elsewhere, f"{name} импортирован из {elsewhere}"


@pytest.mark.parametrize("name, module", [("MATRIX_HEADERS", "tests.outcome_gate_sandbox"),
                                          ("_sandbox", "tests.fixtures")])
def test_ac9_name_imported_from_its_module(name, module):
    """`MATRIX_HEADERS` импортирован из `tests.outcome_gate_sandbox`, `_sandbox` — из `tests.fixtures`, без переименования.

    Ловит мутацию: `MATRIX_HEADERS` взят транзитом из
    `tests.components_outcome_sandbox` (куда он переехал как ненужный
    песочницам импорт), или `_sandbox` переписан своей фикстурой —
    импорта нет, тест краснеет с именем.
    """
    names = _imports_from(_ctx.module_tree(), module)
    assert name in names and names[name] in (None, name), (
        f"{name} не импортирован из {module}")


def test_ac9_stdlib_only_contextlib_io_and_no_unused_imports():
    """Из стандартной библиотеки импортированы только `contextlib` и `io` (плюс `pytest`), каждое импортированное имя используется.

    Корень каждого импорта верхнего уровня — `tests`, `orchestrator`,
    `pytest`, `contextlib` или `io`; имя, связанное импортом (`as`-имя или
    первый сегмент), встречается в модуле именем (`Name`) вне самих
    импортов.

    Ловит мутацию: свод перенёс импорты старого файла целиком —
    `json`, `Path`, `SimpleNamespace`, `checkpoint`, `js_source` не
    используются тестами — тест краснеет с именами.
    """
    tree = _ctx.module_tree()
    imported, foreign = {}, []
    for node in tree.body:
        if isinstance(node, ast.Import):
            roots = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            roots = [(node.module or "").split(".")[0]]
        else:
            continue
        foreign += [r for r in roots if r not in _STDLIB_OK | _PROJECT_ROOTS]
        for a in node.names:
            imported[(a.asname or a.name).split(".")[0]] = node.lineno
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert not foreign, f"импорты вне contextlib/io/pytest/tests/orchestrator: {foreign}"
    unused = sorted(name for name in imported if name not in used)
    assert not unused, f"неиспользуемые импорты: {unused}"


# ------------------------------------------------------------------ AC-10

def test_ac10_module_docstring_purpose_source_tables_and_stand():
    """Докстринг модуля называет свод из прежнего файла (ADR-0020 п. 8, таблицы PLAN) и стенд по новым путям, без строк группы и красноты.

    Докстринг непуст и содержит: имя прежнего файла
    `test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components`, `ADR-0020`,
    `PLAN`, пути стенда
    `tests.components_outcome_sandbox.ComponentsOutcomeSandbox` и
    `tests.merge_outcome_sandbox.MergeOutcomeSandbox`; строк
    «Группа: долгоживущий» и «Красен до реализации» в нём нет.

    Ловит мутацию: свод перенёс прежний докстринг дословно — со строками
    «Группа: долгоживущий»/«Красен до реализации» и старым путём стенда, —
    или написал одну строку назначения без свода и стенда — тест краснеет
    с недостающим.
    """
    raw = ast.get_docstring(_ctx.module_tree()) or ""
    doc = " ".join(raw.split())
    assert doc, f"у {_plan.MODULE} нет докстринга"
    missing = [w for w in ("test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components",
                           "ADR-0020", "PLAN",
                           "tests.components_outcome_sandbox.ComponentsOutcomeSandbox",
                           "tests.merge_outcome_sandbox.MergeOutcomeSandbox")
               if w not in doc]
    assert not missing, f"докстринг модуля не называет: {missing}"
    present = [w for w in ("Группа: долгоживущий", "Красен до реализации") if w in raw]
    assert not present, f"докстринг модуля несёт строки: {present}"


# ------------------------------------------------------------------ AC-11

@pytest.mark.parametrize("name, cls", [("box", "ComponentsOutcomeSandbox"),
                                       ("foreign_box", "ForeignPlankSandbox")])
def test_ac11_fixture_is_yield_from_sandbox_of_its_class(name, cls):
    """Фикстура — `yield from _sandbox(<класс>)` и ничего больше: ни утверждений, ни иных вызовов.

    Тело фикстуры без докстринга — единственный оператор
    `yield from _sandbox(<класс>)`.

    Ловит мутацию: фикстура `box` сразу зовёт `box.component_task(...)`
    (утверждение подготовки) или `foreign_box` построена на
    `ComponentsOutcomeSandbox` — лишний вызов или не тот класс, тест
    краснеет.
    """
    funcs = _ctx.module_functions()
    assert name in funcs, f"фикстуры {name} в {_plan.MODULE} нет"
    func = funcs[name]
    assert _plan.is_fixture(func), f"{name} не помечена pytest.fixture"
    body = _plan.strip_docstring(func.body)
    want = ast.dump(ast.parse(f"yield from _sandbox({cls})").body[0])
    assert len(body) == 1 and ast.dump(body[0]) == want, (
        f"тело {name}: {[ast.unparse(s) for s in body]}, ожидалось "
        f"«yield from _sandbox({cls})»")


def test_ac11_fixtures_call_no_asserting_methods():
    """Ни одна фикстура модуля не содержит утверждений и не зовёт непосредственно методов и помощников с утверждениями.

    Ловит мутацию: свод завёл фикстуру `frontend_task`, которая зовёт
    `box.component_task(project, "frontend")` или `mandate_answer(...)` —
    вызов найден, тест краснеет с именем.
    """
    asserting = set(_plan.ASSERTING) | set(_plan.OUTCOME_HELPERS)
    problems = []
    for func in _ctx.module_tree().body:
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                or not _plan.is_fixture(func):
            continue
        problems += [f"фикстура {func.name}: утверждение в строке {line}"
                     for line in _assertion_sites(func)]
        problems += [f"фикстура {func.name}: вызов {_called(sub)} в строке {sub.lineno}"
                     for sub in ast.walk(func)
                     if isinstance(sub, ast.Call) and _called(sub) in asserting]
    assert not problems, "\n".join(problems)


def test_ac11_stand_by_former_class():
    """`foreign_box` берут ровно функции бывших `Ac19`, `Ac25`, `Ac27`, прочие тесты — `box`.

    Для каждого перенесённого теста файла волны: функции бывших
    `Ac19ForeignPlankTest`, `Ac25TrainingProjectTest`,
    `Ac27OutOfBoundsForeignTest` берут параметр `foreign_box` и не берут
    `box`; функции бывших `Ac16`, `Ac17`, `Ac18`, `Ac22`, `Ac13Ac14` берут
    `box` и не берут `foreign_box`.

    Ловит мутацию: свод отдал всем тестам `foreign_box` (или бывшему
    `Ac27` — `box`, у которого нет `exit_with_foreign`) — тест краснеет с
    именем.
    """
    problems, seen = [], 0
    for test, func in _pairs():
        seen += 1
        params = {a.arg for a in func.args.args}
        want, other = ((_plan.FOREIGN_BOX, _plan.BOX) if test.cls in _plan.FOREIGN_CLASSES
                       else (_plan.BOX, _plan.FOREIGN_BOX))
        if want not in params or other in params:
            problems.append(f"{test.key} → {func.name}: параметры {sorted(params)}, "
                            f"ожидался {want} без {other}")
    assert seen, "ни один тест файла волны не найден в модуле"
    assert not problems, "\n".join(problems)


def test_ac11_fixture_names_differ_from_shared_fixtures():
    """Имена фикстур модуля не совпадают с фикстурами `tests/fixtures.py`.

    Ловит мутацию: стенд назван `real_git` или `tmp_root` — он затеняет
    общую фикстуру корневого `conftest.py`, тест краснеет с именем.
    """
    own = {f.name for f in _ctx.module_functions().values() if _plan.is_fixture(f)}
    shared = _shared_fixture_names()
    assert shared, f"в {_plan.FIXTURES_FILE} не найдено фикстур"
    assert own, f"в {_plan.MODULE} нет фикстур"
    assert not own & shared, f"имена общих фикстур: {sorted(own & shared)}"


# ------------------------------------------------------------------ AC-12

@pytest.mark.parametrize("name", list(_plan.HELPERS))
def test_ac12_helper_signature_and_body_verbatim(name):
    """Помощник — функция модуля с сигнатурой критерия, тело по AST равно телу метода с `self` → `box`.

    Сигнатура (параметры, аннотации, возвращаемый тип) равна дословной из
    критерия; каноничный дамп тела равен дампу тела метода бывшего
    тестового класса базы, где `self` заменён на `box`.

    Ловит мутацию: в `mandate_answer` утверждение исхода переписано на
    `assert exc.code in (None, 0), …`, введён параметр `case`, у
    `review_section` снята аннотация `-> str`, или `broken_consumer`
    фиксирует выбор `broken` — тест краснеет с именем помощника.
    """
    func = _ctx.module_functions().get(name)
    assert func is not None, f"функции {name} в {_plan.MODULE} нет"
    assert _plan.signature_dump(func) == _plan.reference_signature(name), (
        f"сигнатура {name} не равна «{_plan.HELPER_SIGNATURES[name].splitlines()[0]}»")
    method = _plan.class_method(_ctx.base_tree(_plan.SOURCE), _plan.HELPER_CLASS[name], name)
    assert method is not None, f"{_plan.HELPER_CLASS[name]}.{name} нет в базе"
    assert _plan.actual_helper_body(func) == _plan.expected_helper_body(method, "box"), (
        f"тело {name} не равно телу метода с self → box")


def test_ac12_mandate_answer_keeps_box_assert_in_and_review_import_inside():
    """Утверждение `mandate_answer` — вызов `box.assertIn(...)`; локальный импорт `review` — внутри тела `review_section`.

    Ловит мутацию: свод переписал утверждение исхода в `assert …` (guard
    увидел бы его иначе, чем требует критерий) или вынес
    `from orchestrator import review` на уровень модуля — тест краснеет.
    """
    funcs = _ctx.module_functions()
    mandate = funcs.get("mandate_answer")
    review = funcs.get("review_section")
    assert mandate is not None and review is not None, "помощников в модуле нет"
    calls = [n for n in ast.walk(mandate) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute) and n.func.attr == "assertIn"
             and isinstance(n.func.value, ast.Name) and n.func.value.id == "box"]
    assert calls, "в mandate_answer нет box.assertIn(...)"
    inner = [n for n in ast.walk(review) if isinstance(n, ast.ImportFrom)
             and n.module == "orchestrator" and any(a.name == "review" for a in n.names)]
    assert inner, "локального импорта review в review_section нет"
    top = [n for n in _ctx.module_tree().body if isinstance(n, (ast.Import, ast.ImportFrom))
           and any((a.asname or a.name) == "review" for a in n.names)]
    assert not top, "review импортирован на уровне модуля"


def test_ac12_tests_call_helpers_by_bare_name_and_sandbox_methods_via_stand():
    """Тесты зовут помощников голым именем, методы песочниц — через стенд.

    Вызовов `<что-то>.mandate_answer/review_section/broken_consumer(…)` в
    модуле нет, а голый вызов каждого помощника есть; в модуле нет функций
    верхнего уровня и голых вызовов с именами методов
    `ComponentsOutcomeSandbox`/`ForeignPlankSandbox` базы.

    Ловит мутацию: бывший `Ac13Ac14` оставил `box.mandate_answer(...)` (у
    песочницы такого метода нет), или метод `exit_with_foreign` вынесен в
    функцию модуля `exit_with_foreign(foreign_box, …)` — тест краснеет.
    """
    tree = _ctx.module_tree()
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
    problems = []
    for helper in _plan.HELPERS:
        if any(isinstance(c.func, ast.Attribute) and c.func.attr == helper for c in calls):
            problems.append(f"{helper} вызван методом стенда")
        if not any(isinstance(c.func, ast.Name) and c.func.id == helper for c in calls):
            problems.append(f"{helper} ни разу не вызван голым именем")
    base = _ctx.base_tree(_plan.SOURCE)
    methods = set()
    for cls in ("ComponentsOutcomeSandbox", "ForeignPlankSandbox"):
        methods |= _plan.class_method_names(base, cls)
    assert methods, "методов песочниц в базе не найдено"
    problems += [f"функция модуля {n}" for n in sorted(set(_ctx.module_functions()) & methods)]
    problems += [f"голый вызов {c.func.id} в строке {c.lineno}" for c in calls
                 if isinstance(c.func, ast.Name) and c.func.id in methods]
    assert not problems, "\n".join(problems)


def test_ac12_stand_attribute_assignments_same_order():
    """Присваивания атрибутам стенда (`no_marker`, `git_fail`, `cases[…]`) идут через имя фикстуры дословно и тем же порядком.

    Для каждого перенесённого теста: последовательность целей присваиваний
    атрибутам стенда в функции равна последовательности целей `self.…` в
    методе, где `self` заменён именем стенда функции.

    Ловит мутацию: в бывшем `test_ac16_component_change_runs_only_its_component`
    сброс `box.no_marker = False` поставлен до вызова `developer_advance`
    или выброшен, `git_fail` присвоен через локальную переменную — тест
    краснеет с именем теста.
    """
    problems, seen = [], 0
    for test, func in _pairs():
        stand = _stand(func)
        if stand is None:
            problems.append(f"{func.name}: стенд не определён")
            continue
        want = [t.replace("self", stand, 1)
                for t in _plan.attribute_assignments(test.func, "self")]
        if want:
            seen += 1
        got = _plan.attribute_assignments(func, stand)
        if got != want:
            problems.append(f"{test.key} → {func.name}: присваивания {got}, ожидались {want}")
    assert seen, "в перенесённых тестах не найдено присваиваний атрибутам стенда"
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("cls", list(_plan.SANDBOX_CLASSES))
def test_ac12_sandbox_class_unchanged(cls):
    """Класс песочницы в `tests/components_outcome_sandbox.py` по `ast.dump` равен своему классу в файле волны базы.

    Ловит мутацию: под функцию модуля из `ComponentsOutcomeSandbox.component_task`
    убрано утверждение подготовки или в `ForeignPlankSandbox` добавлен
    метод `mandate_answer` — дамп расходится, тест краснеет.
    """
    want = _plan.class_node(_ctx.base_tree(_plan.SOURCE), cls)
    got = _plan.class_node(_ctx.head_tree(_plan.SANDBOX), cls)
    assert want is not None, f"{cls} нет в {_plan.SOURCE} базы"
    assert got is not None, f"{cls} нет в {_plan.SANDBOX} на HEAD"
    assert ast.dump(got) == ast.dump(want), f"{cls} изменён"


# ------------------------------------------------------------------ AC-13

def test_ac13_test_bodies_equal_source_after_replacements():
    """Тело каждой перенесённой тестовой функции по AST равно телу исходного метода после замен требования 17 (решение Оператора ANSWER-1 п. 2).

    Ожидаемое тело — тело метода базы без докстринга, где
    `self.<помощник>(…)` → `<помощник>(<стенд>, …)`, `self` → стенд
    функции, оператор `self.assertEqual(a, b[, m])` → `assert a == b[, m]`,
    `assertTrue(x[, m])` → `assert x[, m]`, `assertIn` → `in`,
    `assertNotIn` → `not in`; локальные имена обезличены по порядку
    появления. Каноничные дампы совпадают.

    Ловит мутацию: в бывшем `test_ac14_id_mandate_on_consumer_lifts_finding`
    выбор `other` зафиксирован литералом, в бывшем
    `test_ac17_first_refusal_names_component` выпало
    `assert broken in refused[-1], …`, или `assertEqual(len(passed), 2, …)`
    перенесён как `assert len(passed) >= 2, …` — тест краснеет с именем.
    """
    problems, seen = [], 0
    for test, func in _pairs():
        seen += 1
        stand = _stand(func)
        if stand is None:
            problems.append(f"{func.name}: стенд не определён")
            continue
        if _plan.actual_test_body(func) != _plan.expected_test_body(test.func, stand):
            problems.append(f"{test.key} → {func.name}: тело не равно исходному после замен")
    assert seen, "ни один тест файла волны не найден в модуле"
    assert not problems, "\n".join(problems)


def test_ac13_assertion_literals_carried_verbatim():
    """Литералы утверждений исходных тестов есть в тестовых функциях модуля дословно.

    Каждый строковый и числовой литерал смысловых аргументов `self.assert*`
    тестовых методов файла волны (без аргумента сообщения) встречается
    литералом вне докстрингов в тестовых функциях модуля.

    Ловит мутацию: при переносе ожидание `"tests_writing"` переписано как
    `"tests-writing"`, или `assertEqual(len(skips), 1, …)` — как
    `assert len(skips) == 2, …` — исходного литерала нет, тест краснеет с
    ним.
    """
    new_lits = _plan.non_docstring_constants(_module_tests_tree())
    missing = {lit for lit in _plan.assertion_literals(_source_tests_tree())
               if lit not in new_lits}
    assert not missing, ("литералы утверждений исходных тестов не найдены в "
                         "модуле:\n" + "\n".join(sorted(map(repr, missing))))


def test_ac13_assertion_constants_stay_constants():
    """Константы, с которыми сравнивали исходные утверждения, остались теми же константами.

    Каждое имя константы (`ВЕРХНИЙ_РЕГИСТР`) в смысловых аргументах
    `self.assert*` исходных тестов встречается именем (`Name`) в тестовых
    функциях модуля.

    Ловит мутацию: `assertEqual(self.records(rows, BROKEN_ACTION), [], …)`
    перенесён как `assert box.records(rows, "переход отклонён: … — сломан
    правкой") == []` — имени `BROKEN_ACTION` нет, тест краснеет с ним.
    """
    names = {n.id for n in ast.walk(_module_tests_tree()) if isinstance(n, ast.Name)}
    missing = sorted(c for c in _plan.assertion_constant_names(_source_tests_tree())
                     if c not in names)
    assert not missing, ("константы утверждений исходных тестов не найдены "
                         "именем в модуле: " + ", ".join(missing))


def test_ac13_equality_not_weakened_and_message_is_second_operand():
    """Перенесённый тест: литералы равенств — в `==`, вхождений — в `in`; число `assert` с сообщением и без равно числу `self.assert*` с сообщением и без; `<что-то>.assert*` в тестовых функциях нет.

    Для каждого перенесённого теста: литералы его `assertEqual` стоят в
    функции в сравнении `==`/`!=`/`is`; литералы `assertIn`/`assertNotIn` —
    в сравнении `in`/`not in` или на равенство; операторов `assert` с
    сообщением столько же, сколько `self.assert*` с сообщением, без
    сообщения — столько же, сколько без; вызовов метода `assert*` в
    функции нет.

    Ловит мутацию: `assertEqual(self.state(t), "in_dev", …)` перенесён как
    `assert "in_dev" in box.state(t), …`, бывший
    `assertTrue(passed[0].startswith(…))` без сообщения получил
    `box.note(…)`, или сообщение `box.explain(rows, output)` потеряно —
    тест краснеет с именем.
    """
    problems, seen = [], 0
    for test, func in _pairs():
        seen += 1
        equal, member = _plan.equality_literals(test.func)
        compared = _plan.compare_operands(func)
        eq_lits = set().union(*[l for k, l in compared if k == "eq"] or [set()])
        in_lits = set().union(*[l for k, l in compared if k == "in"] or [set()])
        lost_eq = sorted(map(repr, equal - eq_lits))
        lost_in = sorted(map(repr, member - eq_lits - in_lits))
        if lost_eq or lost_in:
            problems.append(f"{test.key}: равенства без {lost_eq}, вхождения без {lost_in}")
        calls = _plan.assert_calls(test.func)
        want = (sum(1 for c in calls if _plan.message_arg(c) is not None),
                sum(1 for c in calls if _plan.message_arg(c) is None))
        asserts = [n for n in ast.walk(func) if isinstance(n, ast.Assert)]
        got = (sum(1 for a in asserts if a.msg is not None),
               sum(1 for a in asserts if a.msg is None))
        if got != want:
            problems.append(f"{test.key} → {func.name}: assert с сообщением/без {got}, "
                            f"в исходном {want}")
        problems += [f"{func.name}: {ast.unparse(sub.func)}(…) в строке {sub.lineno}"
                     for sub in ast.walk(func) if _plan.is_method_assert(sub)]
    assert seen, "ни один тест файла волны не найден в модуле"
    assert not problems, "\n".join(problems)


def test_ac13_locals_do_not_shadow_module_functions_or_fixtures():
    """Локальные имена функций модуля не совпадают с функциями и фикстурами модуля и с фикстурами `tests/fixtures.py`.

    Ловит мутацию: бывший тест оставил локальное `box = …` или
    `review_section = …`, затеняющее фикстуру или помощника модуля — тест
    краснеет с именем.
    """
    funcs = _ctx.module_functions()
    taken = set(funcs) | _shared_fixture_names()
    problems = []
    for func in funcs.values():
        stored = {n.id for n in ast.walk(func)
                  if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
        problems += [f"{func.name}: локальное {name}" for name in sorted(stored & taken)]
    assert not problems, "\n".join(problems)


def test_ac13_renamed_locals_listed_in_plan():
    """PLAN перечисляет переименованные локальные имена: каждое имя исходных тестов, совпавшее с функцией или фикстурой модуля.

    Локальные имена тестовых методов файла волны, совпадающие с функцией
    верхнего уровня модуля на HEAD или фикстурой `tests/fixtures.py`: каждое
    стоит в PLAN в обратных кавычках. Совпадений нет — перечень пуст.

    Ловит мутацию: разработчик переименовал локальное имя, совпавшее с
    фикстурой, но не записал перечень в PLAN — имени нет, тест краснеет с
    ним.
    """
    taken = set(_ctx.module_functions()) | _shared_fixture_names()
    wanted = set()
    for test in _source_methods():
        wanted |= {n.id for n in ast.walk(test.func)
                   if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)
                   and n.id in taken}
    if not wanted:
        return
    plan = _ctx.plan_text()
    missing = sorted(name for name in wanted if f"`{name}`" not in plan)
    assert not missing, f"в PLAN нет перечня переименованных локальных: {missing}"


# ------------------------------------------------------------------ AC-14

def test_ac14_every_test_function_declares_mutation():
    """У каждой тестовой функции модуля есть строка «Ловит мутацию:».

    Ловит мутацию: свод перенёс тест с докстрингом, укороченным до первой
    фразы, без заявки — функция перечислена, тест краснеет.
    """
    tests = _plan.module_tests(_ctx.module_tree())
    assert tests, f"тестовых функций в {_plan.MODULE} нет"
    without = [f.name for f in tests if "Ловит мутацию:" not in (ast.get_docstring(f) or "")]
    assert not without, "функции без «Ловит мутацию:»:\n" + "\n".join(without)


def test_ac14_ac19_claim_without_fsm_advance_lines():
    """Заявка `test_ac19_task_out_of_bounds_still_refused` не ссылается на строки `fsm_advance.py`, а называет гейт словами.

    В докстринге функции нет `fsm_advance.py:<цифры>`; есть
    `fsm_advance.tests_writing` и либо формулировка критерия «гейт
    FAIL_TO_PASS добавляется только по профилю задачи в границе …
    условие `in_outcome_bounds(profile)`», либо формулировка решения
    Оператора ANSWER-1 п. 3 «добавление `_tests_writing_foreign_plank_gate`
    без условия».

    Ловит мутацию: свод перенёс заявку дословно — с
    «`fsm_advance.py:609–613`» — или заменил номера строк на свежие
    «`fsm_advance.py:617`» — тест краснеет.
    """
    func = _ctx.module_functions().get(_AC19)
    assert func is not None, f"функции {_AC19} в модуле нет"
    doc = " ".join((ast.get_docstring(func) or "").split())
    assert "Ловит мутацию:" in doc, f"у {_AC19} нет заявки"
    assert not re.search(r"fsm_advance\.py:\d", doc), (
        f"заявка {_AC19} ссылается на строки fsm_advance.py:\n{doc}")
    assert "fsm_advance.tests_writing" in doc, (
        f"заявка {_AC19} не называет fsm_advance.tests_writing:\n{doc}")
    spec = ("гейт FAIL_TO_PASS добавляется только по профилю задачи в границе" in doc
            and "in_outcome_bounds(profile)" in doc)
    answer = "_tests_writing_foreign_plank_gate" in doc and "без условия" in doc
    assert spec or answer, (f"заявка {_AC19} не несёт формулировки критерия или "
                            f"решения ANSWER-1 п. 3:\n{doc}")


def test_ac14_every_source_test_transferred_or_listed_as_removed_duplicate():
    """Каждый из 17 тестов файла волны перенесён в модуль либо перечислен в PLAN удалённым дублем.

    Тест файла волны базы, не перечисленный в разделе «…дубл…» PLAN,
    сопоставлен функции модуля (по имени или соответствию PLAN).

    Ловит мутацию: при своде пропал бывший `test_ac27_foreign_out_of_bounds_not_checked`
    (не перенесён и не записан дублем) — тест краснеет с его именем.
    """
    funcs = _ctx.module_functions()
    plan = _ctx.plan_or_empty()
    transfer, removed = _plan.transfer_map(plan), _ctx.removed_keys(plan)
    tests = _source_methods()
    assert len(tests) == _plan.CLAIMS, f"тестов в файле волны базы {len(tests)}"
    lost = [t.key for t in tests if t.key not in removed
            and not _ctx.matches(funcs, t.cls, t.func.name, transfer)]
    assert not lost, ("тесты не перенесены и не перечислены удалёнными дублями:\n"
                      + "\n".join(lost))
