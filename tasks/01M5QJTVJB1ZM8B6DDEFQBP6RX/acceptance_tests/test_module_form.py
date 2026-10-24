"""AC-8 … AC-14 (форма): файлы модулей `tests/test_merge_lock_module.py` и
`tests/test_merge_queue.py` против трёх исходных файлов базы ветки —
стиль pytest без классов и `subTest`, фикстуры из тел `setUp`, константы,
помощники-функции, дословные ожидания, циклы, паузы и потоки, заявки.

Группа: разовый
Красен до реализации: tests/test_merge_lock_module.py на ветке ещё нет, tests/test_merge_queue.py — прежний unittest-файл с классами — свод не сделан.

Файлы модулей читаются из HEAD рабочей копии, исходные — из базы ветки
(`_pult.DIFF_BASE`). Сравнение статическое (ast): тест не исполняет ни
новые, ни исходные тесты. «Тело дословно» сверяется `ast.dump` тела
источника, переведённого правилами SPEC и решения 6 ANSWER-1: `self.` →
параметр стенда, `self.<КОНСТАНТА>` → константа модуля, `self.<помощник>(…)`
→ `<функция>(<стенд>, …)`, `super().setUp()` отброшен, у фикстуры —
допустимый хвост `return`/`yield` стенда. «Функция, в которую перенесён
тест» — функция-тест его файла модуля с его именем (`_plan.moved_to`).
"""
import ast
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _ctx  # noqa: E402
import _plan  # noqa: E402

_FILES = list(_plan.MODULE_FILES)


def _calls_named(tree, name: str) -> list:
    return [n for n in ast.walk(tree) if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name) and n.func.id == name]


def _base_methods(trees: dict, path: str, cls: str, method: str):
    node = _plan.class_method(trees[path], cls, method)
    assert node is not None, f"{path}::{cls}.{method} нет в базе"
    return node


def _moved_tests(base_tests: dict, head_trees: dict, removed: set):
    """[(BaseTest, функция модуля)] перенесённых тестов."""
    pairs = []
    for test in base_tests.values():
        if test.key in removed:
            continue
        for func in _plan.moved_to(test.name, _plan.module_tests(head_trees[test.target])):
            pairs.append((test, func))
    return pairs


def _assertions(func) -> list:
    return [n for n in ast.walk(func) if _plan.is_assertion_node(n)
            and not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                     and n.func.attr == "fail")]


def _base_assertions(func) -> list:
    """Утверждения исходного теста: `self.assert*`, `self.assertRaises`,
    `raise AssertionError`."""
    found = []
    for n in ast.walk(func):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                and isinstance(n.func.value, ast.Name) and n.func.value.id == "self" \
                and n.func.attr.startswith("assert"):
            found.append(n)
        elif _plan.is_assertion_error_raise(n):
            found.append(n)
    return found


def _context():
    plan = _ctx.plan_text()
    return (_ctx.base_trees(), _ctx.base_tests(), _ctx.head_trees(),
            set(_plan.removed_duplicates(plan)))


# ------------------------------------------------------------------ AC-8

@pytest.mark.parametrize("path", _FILES)
def test_ac8_no_classes_subtest_unittest_syspath_main_or_unused_imports(path):
    """В файле модуля нет тестовых классов, `subTest`, импорта `unittest`, `sys.path.insert`, `__main__` и неиспользуемых импортов.

    Файл есть в HEAD и несёт тестовые функции; ни один класс не несёт
    методов `test_*` и не наследует `TmpRootTest`/`TestCase`; обращений
    `subTest` нет; нет `import unittest` и `from unittest import …` кроме
    `mock`; нет вызова `sys.path.insert`; на верхнем уровне нет `if __name__
    == "__main__"`; каждое имя, связанное импортом, используется в файле.

    Ловит мутацию: свод оставил `class RunWindowTest(TmpRootTest)`, строку
    `sys.path.insert(0, …)` (замок :17), импорт `threading` в файле очереди
    или хвост `unittest.main()` — находка перечислена, тест краснеет.
    """
    tree = _ctx.head_trees()[path]
    assert _plan.module_tests(tree), f"в {path} нет тестовых функций"
    problems = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            bases = {ast.unparse(b).rsplit(".", 1)[-1] for b in node.bases}
            methods = [i.name for i in node.body if isinstance(i, ast.FunctionDef)
                       and i.name.startswith("test")]
            if methods or bases & {"TmpRootTest", "TestCase"}:
                problems.append(f"тестовый класс {node.name} в строке {node.lineno}")
        if isinstance(node, ast.Attribute) and node.attr == "subTest":
            problems.append(f"subTest в строке {node.lineno}")
        if isinstance(node, ast.Import) and any(
                a.name == "unittest" or a.name.startswith("unittest.")
                and a.name != "unittest.mock" for a in node.names):
            problems.append(f"import unittest в строке {node.lineno}")
        if isinstance(node, ast.ImportFrom) and node.module == "unittest" and any(
                a.name != "mock" for a in node.names):
            problems.append(f"from unittest import … в строке {node.lineno}")
        if isinstance(node, ast.Call) and ast.unparse(node.func) == "sys.path.insert":
            problems.append(f"sys.path.insert в строке {node.lineno}")
    problems += [f"блок __main__ в строке {n.lineno}" for n in tree.body
                 if isinstance(n, ast.If) and "__main__" in ast.unparse(n.test)]
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                bound = (alias.asname or alias.name).split(".")[0]
                if bound not in used:
                    problems.append(f"неиспользуемый импорт {bound} в строке "
                                    f"{node.lineno}")
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-9

def _fixture_roots(tree) -> dict:
    """{фикстура: опирается ли (через фикстуры файла) на `tmp_root`}."""
    fixtures = {f.name: f for f in _plan.fixtures(tree)}

    def rooted(name, seen=()):
        params = [a.arg for a in fixtures[name].args.args]
        if "tmp_root" in params:
            return True
        return any(p in fixtures and p not in seen and rooted(p, (*seen, name))
                   for p in params)

    return {name: rooted(name) for name in fixtures}


def _setup_dumps(base_trees, path: str, param: str) -> dict:
    """{(файл, класс): тело setUp, переведённое со стендом `param`}."""
    dumps = {}
    for src, cls in _plan.SETUPS[path]:
        tree = base_trees[src]
        method = _base_methods(base_trees, src, cls, "setUp")
        dumps[(src, cls)] = _plan.translated_body(
            method, cls, param, _plan.class_constants(tree), drop_super=True)
    return dumps


def _fixture_match(base_trees, path: str, fixture) -> set:
    """Источники `setUp`, телу которого равно тело фикстуры."""
    body = _plan.body_dump(fixture, drop_trailing_return=True)
    matched = set()
    for arg in fixture.args.args:
        for source, dump in _setup_dumps(base_trees, path, arg.arg).items():
            if dump == body:
                matched.add(source)
    return matched


@pytest.mark.parametrize("path", _FILES)
def test_ac9_fixtures_over_tmp_root_bodies_equal_setups_without_assertions(path):
    """Фикстуры файла — поверх `tmp_root`, без утверждений, тело каждой — тело исходного `setUp`.

    Каждая фикстура файла опирается на `tmp_root` (параметром или через
    другую фикстуру файла), не содержит утверждений, и её тело (без хвоста
    `return`/`yield` стенда) равно телу одного из `setUp` источников файла
    без `super().setUp()` с заменой `self.` её параметром: для замка —
    `AcquireReleaseTest`, `ProcessOwnershipTest`, `RunWindowTest`,
    `ConcurrentAcquireTest`, `_Base`; для очереди — `_QueueTestBase`, `_Base`.
    Каждый `setUp` источников покрыт фикстурой.

    Ловит мутацию: фикстура замка вставляет одну задачу вместо двух, держит
    `assert store.db()`, зовёт `super().setUp()` или для `_Base` фикстуры
    нет (подготовка `cmd_init` перенесена в каждый тест) — фикстура или
    `setUp` без пары, тест краснеет с ним.
    """
    base_trees = _ctx.base_trees()
    tree = _ctx.head_trees()[path]
    fixtures = _plan.fixtures(tree)
    assert fixtures, f"в {path} нет фикстур"
    roots = _fixture_roots(tree)
    problems, covered = [], set()
    for fixture in fixtures:
        if not roots[fixture.name]:
            problems.append(f"фикстура {fixture.name} не опирается на tmp_root")
        problems += [f"фикстура {fixture.name}: утверждение в строке {n.lineno}"
                     for n in ast.walk(fixture) if _plan.is_assertion_node(n)]
        matched = _fixture_match(base_trees, path, fixture)
        if not matched:
            problems.append(f"фикстура {fixture.name}: тело не равно ни одному "
                            f"setUp {[c for _s, c in _plan.SETUPS[path]]}")
        covered |= matched
    missing = [cls for src, cls in _plan.SETUPS[path] if (src, cls) not in covered]
    if missing:
        problems.append(f"setUp без фикстуры: {missing}")
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("path", _FILES)
def test_ac9_equal_setup_bodies_share_one_fixture(path):
    """Одинаковые тела `setUp` сведены в одну фикстуру в пределах файла.

    Никакие две фикстуры файла не равны телу одного и того же `setUp`
    (у замка `AcquireReleaseTest.setUp` и `RunWindowTest.setUp` равны по
    AST — одна фикстура на обоих).

    Ловит мутацию: свод завёл `acquire_release_stand` и `run_window_stand`
    с одним телом — две фикстуры с одним источником, тест краснеет с ними.
    """
    base_trees = _ctx.base_trees()
    fixtures = _plan.fixtures(_ctx.head_trees()[path])
    bodies = {}
    for fixture in fixtures:
        for arg in fixture.args.args:
            for source, dump in _setup_dumps(base_trees, path, arg.arg).items():
                if dump == _plan.body_dump(fixture, drop_trailing_return=True):
                    bodies.setdefault(dump, set()).add(fixture.name)
    twins = sorted(sorted(names) for names in bodies.values() if len(names) > 1)
    assert not twins, f"фикстуры с одинаковым телом: {twins}"


def test_ac9_base_fixture_in_each_module_file_with_same_body():
    """Фикстура общей части `_Base` есть в каждом из двух файлов, тела одинаковые.

    В каждом файле модуля есть фикстура, равная телу `_Base.setUp`
    by_project; тела этих двух фикстур равны (`ast.dump`, без докстринга).

    Ловит мутацию: файл очереди импортирует фикстуру `_Base` из файла замка
    (или её тело во втором файле упрощено без `declare_target`) — фикстуры
    нет или тела расходятся, тест краснеет.
    """
    base_trees = _ctx.base_trees()
    head = _ctx.head_trees()
    source = (_plan.BY_PROJECT_SOURCE, "_Base")
    found = {}
    for path in _FILES:
        for fixture in _plan.fixtures(head[path]):
            if source in _fixture_match(base_trees, path, fixture):
                found[path] = fixture
    missing = [p for p in _FILES if p not in found]
    assert not missing, f"нет фикстуры _Base в {missing}"
    dumps = {_plan.body_dump(f) for f in found.values()}
    assert len(dumps) == 1, "тела фикстур _Base двух файлов расходятся"


def test_ac9_fixture_names_differ_from_shared_fixtures():
    """Имена фикстур файлов модулей не совпадают с фикстурами `tests/fixtures.py`.

    Ловит мутацию: фикстура стенда названа `tmp_root` (затеняет общую) —
    имя совпало, тест краснеет с ним.
    """
    shared = {f.name for f in _plan.fixtures(ast.parse(_ctx.head_text(_plan.FIXTURES_FILE)))}
    assert shared, f"в {_plan.FIXTURES_FILE} не найдено фикстур"
    clash = sorted(f"{p}::{f.name}" for p, t in _ctx.head_trees().items()
                   for f in _plan.fixtures(t) if f.name in shared)
    assert not clash, f"имена совпадают с tests/fixtures.py: {clash}"


# ------------------------------------------------------------------ AC-10

def test_ac10_class_attributes_and_other_host_are_module_constants():
    """`TASK`, `HOLDER_TASK`, `THREADS`, `TASK_A`/`B`/`C`, `OTHER_HOST` — константы модуля с прежними литералами.

    В файле модуля замка — `TASK`, `HOLDER_TASK`, `THREADS`, `OTHER_HOST`,
    в файле очереди — `TASK_A`, `TASK_B`, `TASK_C`, `OTHER_HOST`: присваивание
    верхнего уровня имени литералу, равному литералу атрибута класса (или
    константы модуля by_project) в базе.

    Ловит мутацию: `THREADS = 4` (или `OTHER_HOST` не перенесён во второй
    файл, а взят импортом) — значение другое или присваивания нет, тест
    краснеет с именем.
    """
    base_trees = _ctx.base_trees()
    head = _ctx.head_trees()
    problems = []
    for path, names in _plan.CONSTANTS.items():
        for name, (src, cls) in names.items():
            want = _plan.class_constant(base_trees[src], cls, name)
            try:
                got = _plan.class_constant(head[path], None, name)
            except LookupError:
                problems.append(f"{path}: нет константы {name} = {want!r}")
                continue
            if got != want or type(got) is not type(want):
                problems.append(f"{path}: {name} = {got!r}, ожидалось {want!r}")
    assert not problems, "\n".join(problems)


def test_ac10_alive_foreign_pid_called_with_the_stand():
    """`_alive_foreign_pid` вызывается со стендом — параметром функции-теста.

    В каждой функции, в которую перенесён исходный тест, звавший
    `_alive_foreign_pid(self)`, есть вызов `_alive_foreign_pid(<x>)` с одним
    аргументом — именем параметра этой функции; других вызовов в файлах
    модулей нет.

    Ловит мутацию: свод зовёт `_alive_foreign_pid(None)` или без аргумента
    (уборка процесса не регистрируется) — вызов не со стендом, тест
    краснеет с функцией.
    """
    base_trees, tests, head, removed = _context()
    problems = []
    for test, func in _moved_tests(tests, head, removed):
        if not _calls_named(test.func, "_alive_foreign_pid"):
            continue
        params = {a.arg for a in func.args.args}
        calls = _calls_named(func, "_alive_foreign_pid")
        if not calls:
            problems.append(f"{func.name}: нет вызова _alive_foreign_pid")
    for path, tree in head.items():
        for func in _plan.module_functions(tree).values():
            params = {a.arg for a in func.args.args}
            for call in _calls_named(func, "_alive_foreign_pid"):
                if len(call.args) != 1 or call.keywords or not (
                        isinstance(call.args[0], ast.Name)
                        and call.args[0].id in params):
                    problems.append(f"{path}:{call.lineno}: {ast.unparse(call)} — "
                                    f"не со стендом")
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-11

def test_ac11_helpers_are_module_functions_with_verbatim_bodies():
    """Помощники `row`, `seed`, `enqueue`, `rows_by_pid`, `new_task`, `seed_lock`, `locks`, `clear` — функции модуля с телом источника.

    В каждом файле модуля есть функции своего перечня (замок — `row`,
    `acquire_release_seed`, `process_ownership_seed`, `new_task`,
    `seed_lock`, `locks`, `clear`; очередь — `enqueue`, `rows_by_pid`,
    `new_task`, `seed_lock`, `locks`, `clear`; имя — имя перечня либо, кроме
    двух `seed`, оно же с префиксом `<префикс>_`: функция `row` затенила бы
    локальную `row = self.row()` исходных тестов, `_plan.helper_names`);
    первый параметр — стенд,
    остальные параметры — как у метода без `self`, тело — тело метода с
    заменой `self.` первым параметром и `self.<помощник>(…)` вызовом
    функции; для `row` — каждого из трёх одинаковых методов.

    Ловит мутацию: `seed_lock` вызывает `stand.locks()` вместо `locks(stand)`,
    `process_ownership_seed` потерял значение по умолчанию `hostname=None`
    или `new_task` не наращивает `counter` — тело или параметры другие,
    тест краснеет с именем.
    """
    base_trees = _ctx.base_trees()
    head = _ctx.head_trees()
    problems = []
    for path, helpers in _plan.HELPERS.items():
        funcs = _plan.module_functions(head[path])
        actual = _plan.helper_names(head[path], path)
        renames = _plan.helper_renames(head[path], path)
        for name, sources in helpers.items():
            func = funcs.get(actual.get(name, ""))
            if func is None or not func.args.args:
                problems.append(f"{path}: нет функции {name}(<стенд>, …)")
                continue
            param = func.args.args[0].arg
            for src, cls, method in sources:
                node = _base_methods(base_trees, src, cls, method)
                want = _plan.translated_body(node, cls, param,
                                             _plan.class_constants(base_trees[src]))
                if _plan.body_dump(_plan.renamed_calls(func, renames)) != want:
                    problems.append(f"{path}::{name}: тело ≠ {cls}.{method}")
                if _plan.rest_args_dump(func.args, True) != \
                        _plan.rest_args_dump(node.args, True):
                    problems.append(f"{path}::{name}: параметры ≠ {cls}.{method}")
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("path", _FILES)
def test_ac11_helper_calls_are_function_calls_and_no_body_twins(path):
    """Вызовы перенесённых помощников — вызовы функций; одинаковых по телу функций нет.

    В файле нет вызова `<стенд>.<помощник>(…)` (`row`, `seed`, `enqueue`,
    `rows_by_pid`, `new_task`, `seed_lock`, `locks`, `clear`) через параметр
    функции; никакие две функции верхнего уровня, не тесты и не фикстуры, не
    совпадают параметрами и телом.

    Ловит мутацию: стенд получил методы-обёртки и тесты зовут
    `stand.row()`, или три `row` перенесены тремя функциями
    `acquire_release_row`/`process_ownership_row`/`run_window_row` — вызов
    или двойник найден, тест краснеет.
    """
    tree = _ctx.head_trees()[path]
    problems = []
    for func in _plan.module_functions(tree).values():
        params = {a.arg for a in func.args.args}
        for node in ast.walk(func):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr in _plan.HELPER_METHODS \
                    and isinstance(node.func.value, ast.Name) \
                    and node.func.value.id in params | {"self"}:
                problems.append(f"{func.name}: {ast.unparse(node.func)}(…) в "
                                f"строке {node.lineno}")
    seen = {}
    for func in _plan.module_functions(tree).values():
        if func.name.startswith("test") or _plan.is_fixture(func):
            continue
        key = (_plan.rest_args_dump(func.args, True), _plan.body_dump(func))
        seen.setdefault(key, []).append(func.name)
    problems += [f"функции с одним телом: {names}" for names in seen.values()
                 if len(names) > 1]
    assert not problems, "\n".join(problems)


def test_ac11_helper_list_in_plan_and_nested_functions_stay_nested():
    """Перечень помощников — в PLAN; `fake_sleep`, `fake_monotonic`, `worker` остались вложенными.

    Каждое имя функции-помощника обоих файлов (`row`,
    `acquire_release_seed`, `process_ownership_seed`, `enqueue`,
    `rows_by_pid`, `new_task`, `seed_lock`, `locks`, `clear`) есть в
    PLAN словом; в файлах модулей нет функций верхнего уровня `fake_sleep`,
    `fake_monotonic`, `worker`, а функция, в которую перенесён исходный тест
    с вложенной функцией этого имени, держит её вложенной.

    Ловит мутацию: свод вынес `worker` потоков `ConcurrentAcquireTest` на
    верхний уровень модуля (или PLAN не перечислил `rows_by_pid`) — имя
    найдено на верхнем уровне или не найдено в PLAN, тест краснеет.
    """
    plan = _ctx.plan_text()
    base_trees, tests, head, removed = _context()
    problems = []
    names = sorted({_plan.helper_names(head[path], path).get(n, n)
                    for path, helpers in _plan.HELPERS.items() for n in helpers})
    problems += [f"помощник {n} не назван в PLAN" for n in names
                 if not re.search(rf"(?<![\w]){re.escape(n)}(?![\w])", plan)]
    for path, tree in head.items():
        problems += [f"{path}: {n} на верхнем уровне"
                     for n in _plan.module_functions(tree) if n in _plan.NESTED]
    for test, func in _moved_tests(tests, head, removed):
        nested = {n.name for n in ast.walk(test.func)
                  if isinstance(n, ast.FunctionDef) and n.name in _plan.NESTED}
        have = {n.name for n in ast.walk(func) if isinstance(n, ast.FunctionDef)
                and n is not func}
        missing = sorted(nested - have)
        if missing:
            problems.append(f"{func.name}: нет вложенных {missing}")
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-12

def test_ac12_every_source_assertion_carried_in_same_normal_form():
    """Каждое утверждение исходного теста есть в функции, в которую он перенесён, в той же нормальной форме.

    Для каждого `self.assert*`, `self.assertRaises` и `raise AssertionError`
    исходного теста функция модуля несёт утверждение той же нормальной формы
    (`assertEqual(a, b)` ↔ `assert a == b`, `assertIsNone(x)` ↔ `assert x is
    None`, `assertTrue(x)` ↔ `assert x`, `assertRaises(E)` ↔
    `pytest.raises(E)`, `self.<КОНСТАНТА>` ↔ константа, `self.<помощник>()`
    ↔ функция, `ctx.exception` ↔ `excinfo.value`): литерал остаётся
    литералом, константа — константой, сравнение — тем же оператором.

    Ловит мутацию: `assertEqual(row["pid"], os.getpid())` перенесён как
    `assert row["pid"]`, `assertIn(self.HOLDER_TASK, refusal)` — как
    `assert "T999" in refusal`, `assertEqual(minutes, 3)` — как `assert
    minutes >= 3` — формы нет в функции, тест краснеет с ней.
    """
    base_trees, tests, head, removed = _context()
    problems = []
    for test, func in _moved_tests(tests, head, removed):
        tree = head[test.target]
        canon_new = _plan.canon_for(tree, func, None,
                                    _plan.helper_renames(tree, test.target))
        have = [_plan.normal_form(n, canon_new) for n in _assertions(func)]
        canon_old = _plan.canon_for(base_trees[test.path], test.func, test.cls)
        for node in _base_assertions(test.func):
            form = _plan.normal_form(node, canon_old)
            if form not in have:
                problems.append(f"{test.key} → {func.name}: нет "
                                f"{ast.unparse(node)[:100]}")
    assert not problems, "\n".join(problems)


def test_ac12_raises_bare_no_match_and_exception_text_checked_after_block():
    """`pytest.raises(E)` без `match`; текст исключения — `assert <текст> in str(excinfo.value)` после блока.

    В файлах модулей ни один вызов не передаёт `match=`; каждый
    `pytest.raises` — один позиционный аргумент без именованных. Для
    каждого исходного `assertIn(<текст>, str(ctx.exception))` в функции
    модуля есть `assert <текст> in str(<x>.value)`, где `<x>` — имя `as`
    блока `with pytest.raises(…)`, и строка утверждения — после конца
    блока.

    Ловит мутацию: свод перенёс проверку текста в `pytest.raises(SystemExit,
    match="sess-holder")` или оставил `assert` внутри блока `with` (он не
    исполнится после исключения) — тест краснеет с функцией.
    """
    base_trees, tests, head, removed = _context()
    problems = []
    for path, tree in head.items():
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and any(k.arg == "match" for k in node.keywords):
                problems.append(f"{path}:{node.lineno}: match=")
            if _plan.is_pytest_raises(node) and (len(node.args) != 1 or node.keywords):
                problems.append(f"{path}:{node.lineno}: {ast.unparse(node)}")
    for test, func in _moved_tests(tests, head, removed):
        texts = [n for n in _base_assertions(test.func)
                 if isinstance(n, ast.Call) and n.func.attr == "assertIn"
                 and len(n.args) >= 2 and "exception" in ast.unparse(n.args[1])]
        if not texts:
            continue
        blocks = {}
        for node in ast.walk(func):
            if isinstance(node, ast.With):
                for item in node.items:
                    if _plan.is_pytest_raises(item.context_expr) and \
                            isinstance(item.optional_vars, ast.Name):
                        blocks[item.optional_vars.id] = node.end_lineno
        canon_old = _plan.canon_for(base_trees[test.path], test.func, test.cls)
        canon_new = _plan.canon_for(head[test.target], func, None,
                                    _plan.helper_renames(head[test.target], test.target))
        for text in texts:
            want = _plan.normal_form(text, canon_old)
            ok = False
            for node in ast.walk(func):
                if not (isinstance(node, ast.Assert) and isinstance(node.test, ast.Compare)):
                    continue
                right = node.test.comparators[0]
                owner = [n.value.id for n in ast.walk(right)
                         if isinstance(n, ast.Attribute) and n.attr == "value"
                         and isinstance(n.value, ast.Name)]
                if owner and owner[0] in blocks and node.lineno > blocks[owner[0]] \
                        and _plan.normal_form(node, canon_new) == want:
                    ok = True
            if not ok:
                problems.append(f"{test.key} → {func.name}: нет assert … in "
                                f"str(excinfo.value) после блока для "
                                f"{ast.unparse(text)}")
    assert not problems, "\n".join(problems)


def test_ac12_msg_text_is_assert_second_operand_or_pytest_fail():
    """Текст `msg` исходного утверждения — второй операнд `assert` той же формы или аргумент `pytest.fail`.

    Для каждого исходного `self.assert*` с сообщением функция модуля несёт
    `assert` той же нормальной формы с тем же сообщением (`ast.dump`), либо
    `pytest.fail(<то же сообщение>)`.

    Ловит мутацию: `self.assertIsNone(refusal, "мёртвый pid держателя …")`
    перенесён как `assert refusal is None` без пояснения (или с другим
    текстом) — пары нет, тест краснеет с функцией.
    """
    base_trees, tests, head, removed = _context()
    problems = []
    for test, func in _moved_tests(tests, head, removed):
        canon_old = _plan.canon_for(base_trees[test.path], test.func, test.cls)
        canon_new = _plan.canon_for(head[test.target], func, None,
                                    _plan.helper_renames(head[test.target], test.target))
        pairs, fails = set(), set()
        for node in ast.walk(func):
            if isinstance(node, ast.Assert) and node.msg is not None:
                pairs.add((_plan.normal_form(node, canon_new),
                           _plan.dump_canon(node.msg, canon_new)))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr == "fail" and node.args:
                fails.add(_plan.dump_canon(node.args[0], canon_new))
        for node in _base_assertions(test.func):
            if not isinstance(node, ast.Call):
                continue
            msg = _plan.msg_arg(node)
            if msg is None:
                continue
            pair = (_plan.normal_form(node, canon_old), _plan.dump_canon(msg, canon_old))
            if pair not in pairs and pair[1] not in fails:
                problems.append(f"{test.key} → {func.name}: сообщение "
                                f"{ast.unparse(msg)[:80]} потеряно")
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-13

def _subtest_loops(func):
    """(внешний цикл `for`, имена ярлыка `subTest`) исходного теста; нет — None."""
    for node in ast.walk(func):
        if not isinstance(node, ast.For):
            continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.With):
                for item in sub.items:
                    call = item.context_expr
                    if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) \
                            and call.func.attr == "subTest":
                        labels = {n.id for k in call.keywords for n in ast.walk(k.value)
                                  if isinstance(n, ast.Name)}
                        return node, labels
    return None


def _loops(node) -> list:
    return [n for n in ast.walk(node) if isinstance(n, ast.For)]


def _loop_key(loop) -> tuple:
    return (ast.dump(loop.target), ast.unparse(loop.iter).replace("self.", ""))


def test_ac13_subtest_sets_kept_as_loops_with_label_in_every_message():
    """Наборы `subTest` (by_project :67, :95, :130) — прежним циклом в одной функции, ярлык — в сообщении каждого утверждения подслучая.

    Для каждого исходного теста с `subTest` есть ровно одна функция модуля,
    без `parametrize`; её циклы `for` повторяют исходные (цель и
    перебираемое выражение); у каждого `assert` внутри внешнего цикла есть
    сообщение, в котором (прямо или через имя, присвоенное в функции)
    стоят все имена ярлыка `subTest` (`own_first`; `p_target`, `q_target`;
    `order`, `p_target`).

    Ловит мутацию: набор `WaitTextsAnyOrderTest` разложен в
    `@pytest.mark.parametrize("order", …)` (общее состояние счётчика
    задач потеряно), или ярлык `order` пропал из сообщения `assert entered
    == …` — тест краснеет с функцией.
    """
    base_trees, tests, head, removed = _context()
    problems = []
    seen = 0
    for test in tests.values():
        found = _subtest_loops(test.func)
        if found is None or test.key in removed:
            continue
        seen += 1
        outer, labels = found
        funcs = _plan.moved_to(test.name, _plan.module_tests(head[test.target]))
        if len(funcs) != 1:
            problems.append(f"{test.key}: функций модуля {len(funcs)}, нужна одна")
            continue
        func = funcs[0]
        if any(isinstance(d, ast.Call) and ast.unparse(d.func).endswith("parametrize")
               for d in func.decorator_list):
            problems.append(f"{func.name}: parametrize вместо цикла")
        want = [_loop_key(loop) for loop in _loops(outer)]
        have = [_loop_key(loop) for loop in _loops(func)]
        if not all(key in have for key in want):
            problems.append(f"{func.name}: циклы {want} не перенесены")
            continue
        new_outer = next(loop for loop in _loops(func) if _loop_key(loop) == want[0])
        assigned = {}
        for node in ast.walk(func):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        assigned.setdefault(target.id, set()).update(
                            n.id for n in ast.walk(node.value) if isinstance(n, ast.Name))
        for node in ast.walk(new_outer):
            if not isinstance(node, ast.Assert):
                continue
            if node.msg is None:
                problems.append(f"{func.name}:{node.lineno}: assert без сообщения")
                continue
            names = {n.id for n in ast.walk(node.msg) if isinstance(n, ast.Name)}
            for name in list(names):
                names |= assigned.get(name, set())
            if not labels <= names:
                problems.append(f"{func.name}:{node.lineno}: в сообщении нет "
                                f"ярлыка {sorted(labels - names)}")
    assert seen == 3, f"исходных тестов с subTest {seen}, критерий называет три"
    assert not problems, "\n".join(problems)


def test_ac13_pause_raise_threads_barrier_and_wait_limits_carried_verbatim():
    """`raise AssertionError(...)` подмены паузы, потоки, `Barrier`, `wait(timeout=5)`, `join(timeout=10)` перенесены дословно.

    Функция, в которую перенесён `WaitForWindowOtherProjectQueueTest::
    test_earlier_entry_of_other_project_does_not_delay_entry`, держит
    вложенную `fake_sleep` с `raise AssertionError("задача P ушла в паузу
    очереди")`; функция `ConcurrentAcquireTest::test_concurrent_acquire_on_
    free_lock_exactly_one_wins` — каждый вызов `threading.Barrier(…)`,
    `threading.Thread(…)`, `.wait(…)`, `.join(…)`, `.start()` источника
    (`self.THREADS` → `THREADS`) и вложенную `worker` с телом источника.

    Ловит мутацию: `raise AssertionError` заменён на `pytest.fail("…")`,
    `barrier.wait(timeout=5)` — на `barrier.wait()`, или `worker` потерял
    `except Exception` — вызова или тела нет, тест краснеет с ним.
    """
    base_trees, tests, head, removed = _context()
    problems = []
    pause_key = ("WaitForWindowOtherProjectQueueTest::"
                 "test_earlier_entry_of_other_project_does_not_delay_entry")
    race_key = ("ConcurrentAcquireTest::"
                "test_concurrent_acquire_on_free_lock_exactly_one_wins")
    for key in (pause_key, race_key):
        test = tests[key]
        funcs = _plan.moved_to(test.name, _plan.module_tests(head[test.target]))
        if not funcs:
            problems.append(f"{key}: функции в {test.target} нет")
            continue
        func = funcs[0]
        canon = _plan.Canon(set(), {}, _plan.class_constants(base_trees[test.path]),
                             set())
        canon_new = _plan.Canon(set(), {}, set(), set())
        have_calls = {_plan.dump_canon(n, canon_new) for n in ast.walk(func)
                      if isinstance(n, ast.Call)}
        have_raises = {_plan.dump_canon(n, canon_new) for n in ast.walk(func)
                       if _plan.is_assertion_error_raise(n)}
        for node in ast.walk(test.func):
            if _plan.is_assertion_error_raise(node) and \
                    _plan.dump_canon(node, canon) not in have_raises:
                problems.append(f"{func.name}: нет {ast.unparse(node)}")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr in ("Barrier", "Thread", "wait", "join", "start") \
                    and _plan.dump_canon(node, canon) not in have_calls:
                problems.append(f"{func.name}: нет {ast.unparse(node)}")
        old_nested = {n.name: _plan.dump_canon(n, canon) for n in ast.walk(test.func)
                      if isinstance(n, ast.FunctionDef) and n is not test.func
                      and n.name == "worker"}
        new_nested = {n.name: _plan.dump_canon(n, canon_new) for n in ast.walk(func)
                      if isinstance(n, ast.FunctionDef) and n is not func}
        for name, dump in old_nested.items():
            if new_nested.get(name) != dump:
                problems.append(f"{func.name}: вложенная {name} не дословна")
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-14

@pytest.mark.parametrize("path", _FILES)
def test_ac14_every_test_function_declares_mutation(path):
    """У каждой функции-теста файла модуля есть строка «Ловит мутацию:».

    Ловит мутацию: свод перенёс тест без заявки (докстринг без «Ловит
    мутацию:», например только первая фраза прежнего) — функция
    перечислена, тест краснеет.
    """
    tests = _plan.module_tests(_ctx.head_trees()[path])
    assert tests, f"в {path} нет тестовых функций"
    without = [f.name for f in tests if "Ловит мутацию:" not in (ast.get_docstring(f) or "")]
    assert not without, "функции без «Ловит мутацию:»:\n" + "\n".join(without)
