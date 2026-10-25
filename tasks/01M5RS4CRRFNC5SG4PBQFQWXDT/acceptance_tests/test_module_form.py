"""AC-7, AC-8, AC-9, AC-10, AC-11, AC-12, AC-13, AC-14, AC-15: форма
приёмников свода — `tests/prior_outcome_sandbox.py`,
`tests/test_outcome_prior_module.py` и сокращённого
`tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py` — против файла
волны и прежних версий в базе ветки.

Группа: разовый
Красен до реализации: на ветке нет tests/prior_outcome_sandbox.py и tests/test_outcome_prior_module.py, долгоживущий outcome_prior ещё несёт песочницы и 44 теста — свод не сделан.

Приёмники читаются из HEAD рабочей копии (`git show HEAD:…`), файл волны и
прежние версии — из базы ветки (`_pult.DIFF_BASE`). Сравнение статическое
(ast): тест не исполняет ни новые, ни исходные тесты, кроме сбора
`pytest --collect-only` сокращённого файла (AC-8).

Тест задачи сопоставляется функции нового модуля по имени (то же имя или
имя с суффиксом `_…`) и по строкам соответствия «до → после» PLAN
(докстринг `_plan.py`). Перевод тела по требованиям 16–17 SPEC (`self` →
`box`, `self.<помощник>(…)` → `<помощник>(box, …)`, `assertX` → `assert`
с сообщением вторым операндом, блок `subTest` → строка
`case = f"{label}, зерно {box.seed}: "` с `case` спереди сообщений и
`case=` в `refusal`/`no_gate_refusal`/`passed`; прежний цикл подслучаев
остаётся циклом) сверяется каноничным `ast.dump` с обезличенными
локальными именами (переименование локальной переменной сверку не
ломает). Сообщения помощников `passed` и `grant` — `case +` спереди
прежнего выражения сообщения дословно (решение Оператора ANSWER-1 п. 1).
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

_PRIOR_MODULE = "tests.prior_outcome_sandbox"
_GATE_MODULE = "tests.outcome_gate_sandbox"
_OTHER_SANDBOXES = ("tests.outcome_gate_sandbox", "tests.merge_outcome_sandbox",
                    "tests.components_outcome_sandbox")
_CONSTANTS = ("OLD", "SIDES", "OUTCOME_ACTION", "PREPARE_ACTION", "PASSED_ACTION",
              "SKIPPED", "PRIOR_RED", "PRIOR_UNSTABLE", "FLAKY", "PRIOR_LINE",
              "FILE_ERROR_MARK")
_FROM_PRIOR = ("PriorSandbox", "Moved", "Link", *_CONSTANTS)


def _module_tests_tree() -> ast.Module:
    return ast.Module(body=_plan.module_tests(_ctx.module_tree()), type_ignores=[])


def _source_tests_tree() -> ast.Module:
    return ast.Module(body=[t.func for t in _ctx.task_tests_in_order()], type_ignores=[])


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


def _removed_from_prior(tree) -> set:
    """Имена классов, удаляемых из долгоживущего файла (требование 11)."""
    return set(_plan.SANDBOX_CLASSES) | set(_plan.CLASSES)


# ------------------------------------------------------------------ AC-7

def test_ac7_sandbox_module_has_no_tests_or_claims():
    """В `tests/prior_outcome_sandbox.py` нет тестовых функций и методов и нет заявок «Ловит мутацию» в докстрингах.

    Ни одна функция или метод модуля не названа `test…`; ни один докстринг
    функции, метода или класса не несёт «Ловит мутацию» (константа `CLAIM`
    — не докстринг и законно переезжает дословно).

    Ловит мутацию: в модуль песочницы уехал класс `Ac3GreenPriorTest`
    вместе с `PriorSandbox` (или метод с заявкой) — имя `test_…` или
    докстринг с заявкой найдены, тест краснеет.
    """
    tree = _ctx.head_tree(_plan.SANDBOX)
    tests = [f"{n.name} в строке {n.lineno}" for n in ast.walk(tree)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
             and n.name.startswith("test")]
    assert not tests, f"тесты в {_plan.SANDBOX}: {tests}"
    claims = [f"{n.name} в строке {n.lineno}" for n in ast.walk(tree)
              if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
              and _plan.CLAIM in (ast.get_docstring(n) or "")]
    assert not claims, f"заявки «{_plan.CLAIM}» в {_plan.SANDBOX}: {claims}"


def test_ac7_sandbox_docstring_is_one_line():
    """Докстринг `tests/prior_outcome_sandbox.py` — одна непустая строка назначения.

    Ловит мутацию: в модуль перенесён многоабзацный докстринг старого файла
    (или докстринга нет) — тест краснеет.
    """
    doc = ast.get_docstring(_ctx.head_tree(_plan.SANDBOX))
    assert doc and doc.strip(), f"у {_plan.SANDBOX} нет докстринга"
    assert "\n" not in doc.strip(), f"докстринг не одной строкой:\n{doc}"


def test_ac7_sandbox_statements_equal_old_statements_in_order():
    """Операторы верхнего уровня модуля песочницы, кроме докстринга, по `ast.dump` равны в том же порядке операторам старого файла от `import contextlib` до `CLAIM` и классам `Moved`, `Link`, `PriorSandbox`, `ReplacementSandbox`, `StrictSandbox`.

    Ловит мутацию: при переносе выброшен неиспользуемый песочницам
    `import hashlib` или `TOKENS`, `StrictSandbox` поставлен до
    `ReplacementSandbox`, или в `PriorSandbox.grant` добавлен параметр
    `case` — дамп или порядок расходятся, тест краснеет с первым
    расхождением.
    """
    want = _plan.sandbox_statements(_ctx.base_tree(_plan.SOURCE))
    assert len(want) > len(_plan.SANDBOX_CLASSES), (
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


@pytest.mark.parametrize("path", ["tests/outcome_gate_sandbox.py",
                                  "tests/merge_outcome_sandbox.py",
                                  "tests/components_outcome_sandbox.py"])
def test_ac7_other_sandbox_unchanged(path):
    """Песочница прежних волн на HEAD побайтно равна базе.

    Ловит мутацию: `PriorSandbox` дописана в
    `tests/merge_outcome_sandbox.py` (или константа `OLD` — в
    `tests/outcome_gate_sandbox.py`) — текст расходится, тест краснеет.
    """
    assert _ctx.head_text(path) == _ctx.base_text(path), f"{path} изменён"


# ------------------------------------------------------------------ AC-8

def test_ac8_prior_has_no_moved_classes():
    """В сокращённом `outcome_prior` нет классов песочниц и 14 тестовых классов задачи.

    Ловит мутацию: из файла удалены тестовые классы, но оставлено
    определение `PriorSandbox` (второе определение рядом с импортом), или
    забыт класс `Ac30OutOfBoundsTest` — имя найдено, тест краснеет.
    """
    tree = _ctx.head_tree(_plan.SOURCE)
    left = sorted(n.name for n in tree.body if isinstance(n, ast.ClassDef)
                  and n.name in _removed_from_prior(tree))
    assert not left, f"в {_plan.SOURCE} остались классы: {left}"


def test_ac8_prior_new_import_after_merge_import_rest_equal_to_base():
    """Сразу после импорта `MergeOutcomeSandbox` стоит ровно один новый оператор `from tests.prior_outcome_sandbox import (Moved, ReplacementSandbox, StrictSandbox)`; каждый прочий оператор верхнего уровня по `ast.dump` равен оставшемуся оператору базы в том же порядке.

    Оставшиеся операторы базы — все операторы старого файла, кроме классов
    `Moved`, `Link`, `PriorSandbox`, `ReplacementSandbox`, `StrictSandbox`
    и 14 тестовых классов задачи (докстринг, импорты, константы,
    `env_lines`, 16 оставшихся классов, `unittest.main()`).

    Ловит мутацию: заодно вычищен ставший ненужным `import hashlib` или
    константа `REPL_MISSING`, импорт новой песочницы поставлен в конец
    импортов или несёт `PriorSandbox`, либо поправлен докстринг файла —
    дамп или место расходятся, тест краснеет с оператором.
    """
    base = _ctx.base_tree(_plan.SOURCE)
    removed = _removed_from_prior(base)
    kept = [n for n in base.body
            if not (isinstance(n, ast.ClassDef) and n.name in removed)]
    head = _ctx.head_tree(_plan.SOURCE).body
    at = next((i for i, n in enumerate(head) if isinstance(n, ast.ImportFrom)
               and n.module == _plan.MERGE_IMPORT_MODULE), None)
    assert at is not None, f"в {_plan.SOURCE} нет импорта из {_plan.MERGE_IMPORT_MODULE}"
    assert at + 1 < len(head), "после импорта MergeOutcomeSandbox операторов нет"
    want_import = ast.dump(ast.parse(_plan.NEW_IMPORT).body[0])
    assert ast.dump(head[at + 1]) == want_import, (
        f"после импорта MergeOutcomeSandbox стоит «{ast.unparse(head[at + 1])}», "
        f"ожидалось «{_plan.NEW_IMPORT}»")
    rest = head[:at + 1] + head[at + 2:]
    for i, (w, g) in enumerate(zip(kept, rest)):
        assert ast.dump(w) == ast.dump(g), (
            f"оператор {i + 1} ({_plan.bound_names(w) or type(w).__name__}, строка базы "
            f"{w.lineno}) не равен оператору HEAD в строке {g.lineno}")
    assert len(rest) == len(kept), (f"прочих операторов HEAD {len(rest)}, а оставшихся "
                                    f"операторов базы {len(kept)}")


def test_ac8_prior_collects_22_tests():
    """`pytest --collect-only` сокращённого `outcome_prior` на рабочей копии собирает 22 теста.

    Ловит мутацию: удаление классов задело `Ac27MergeProofTest` или новый
    импорт не несёт `StrictSandbox` (оставшиеся классы на нём не
    определяются) — сбор падает или тестов не 22, тест краснеет с выводом
    сбора.
    """
    res = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q",
         "-p", "no:cacheprovider", _plan.SOURCE],
        cwd=CODE_ROOT, capture_output=True, text=True, timeout=600)
    nodes = [line for line in res.stdout.splitlines() if "::" in line]
    assert res.returncode == 0 and len(nodes) == _plan.KEPT_COUNT, (
        f"сбор outcome_prior: код {res.returncode}, узлов {len(nodes)} вместо "
        f"{_plan.KEPT_COUNT}:\n{res.stdout[-3000:]}\n{res.stderr[-2000:]}")


# ------------------------------------------------------------------ AC-9

def test_ac9_no_test_classes_subtest_or_unittest():
    """В `tests/test_outcome_prior_module.py` нет тестовых классов, `subTest`, `unittest` и `unittest.main()`; тестовые функции есть.

    Ловит мутацию: свод оставил `class Ac8RestoredPathsTest(PriorSandbox)`
    с методами `test_…`, блок `with box.subTest(...)` или хвост
    `if __name__ == "__main__": unittest.main()` с `import unittest` — тест
    краснеет с находкой.
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


@pytest.mark.parametrize("name", list(_FROM_PRIOR))
def test_ac9_name_imported_from_prior_sandbox_only(name):
    """Имя импортировано из `tests.prior_outcome_sandbox` без переименования и ни из `tests.outcome_gate_sandbox`, `tests.merge_outcome_sandbox`, `tests.components_outcome_sandbox`.

    Ловит мутацию: `OUTCOME_ACTION` (или `PASSED_ACTION`, `PREPARE_ACTION`)
    взят из `tests.outcome_gate_sandbox`/`tests.components_outcome_sandbox`,
    где есть одноимённая константа, или `SIDES` переписан литералом в
    модуль — импорта из новой песочницы нет либо есть импорт из чужой, тест
    краснеет с именем.
    """
    tree = _ctx.module_tree()
    names = _imports_from(tree, _PRIOR_MODULE)
    assert name in names and names[name] in (None, name), (
        f"{name} не импортирован из {_PRIOR_MODULE}")
    elsewhere = [m for m in _OTHER_SANDBOXES if name in _imports_from(tree, m)]
    assert not elsewhere, f"{name} импортирован из {elsewhere}"


@pytest.mark.parametrize("name, module", [("flow", _GATE_MODULE),
                                          ("py_source", _GATE_MODULE),
                                          ("GATE_ACTIONS", _GATE_MODULE),
                                          ("_sandbox", "tests.fixtures")])
def test_ac9_name_imported_from_its_module(name, module):
    """`flow`, `py_source`, `GATE_ACTIONS` импортированы из `tests.outcome_gate_sandbox`, `_sandbox` — из `tests.fixtures`, без переименования.

    Ловит мутацию: `flow`/`py_source` взяты транзитом из
    `tests.prior_outcome_sandbox` (куда они переехали импортом старого
    файла), или `_sandbox` переписан своей фикстурой — импорта нет, тест
    краснеет с именем.
    """
    names = _imports_from(_ctx.module_tree(), module)
    assert name in names and names[name] in (None, name), (
        f"{name} не импортирован из {module}")


@pytest.mark.parametrize("name", ["pytest", "os"])
def test_ac9_direct_module_import(name):
    """Модуль импортирован прямым `import <имя>` верхнего уровня без переименования.

    Ловит мутацию: `os` взят как `from os import path` (бывший
    `os.path.relpath` переписан) или транзитом, либо `import pytest`
    забыт — прямого импорта нет, тест краснеет с именем.
    """
    direct = [a for n in _ctx.module_tree().body if isinstance(n, ast.Import)
              for a in n.names if a.name == name and a.asname in (None, name)]
    assert direct, f"в {_plan.MODULE} нет «import {name}»"


def test_ac9_no_unused_imports():
    """Каждое имя, связанное импортом верхнего уровня модуля, используется в модуле.

    Имя, связанное импортом (`as`-имя или первый сегмент), встречается в
    модуле именем (`Name`) вне самих импортов.

    Ловит мутацию: свод перенёс импорты старого файла целиком —
    `contextlib`, `hashlib`, `SimpleNamespace`, `guard`, `mandate` тестами не
    используются — тест краснеет с именами.
    """
    tree = _ctx.module_tree()
    imported = {}
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                imported[(a.asname or a.name).split(".")[0]] = node.lineno
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    unused = sorted(name for name in imported if name not in used)
    assert not unused, f"неиспользуемые импорты: {unused}"


# ------------------------------------------------------------------ AC-10

def test_ac10_module_docstring_purpose_source_tables_and_stand():
    """Докстринг модуля называет свод из прежнего файла (ADR-0020 п. 8, сокращение решением Оператора, задача 2а-2в-2, таблицы PLAN), стенд и сторону «прежние версии» по новым путям, без строк группы, красноты и абзаца о стабе.

    Докстринг непуст и содержит: имя прежнего файла
    `test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior`, `ADR-0020` с `п. 8`,
    «Оператор», «2а-2в-2», «таблиц» и `PLAN`, «прежние версии», пути стенда
    `tests.prior_outcome_sandbox.PriorSandbox`,
    `tests.merge_outcome_sandbox.MergeOutcomeSandbox` и
    `tests.outcome_gate_sandbox.OutcomeGateSandbox`; строк
    «Группа: долгоживущий», «Красен до реализации» и «Провалидировано
    временным стабом реализации» в нём нет.

    Ловит мутацию: свод перенёс прежний докстринг дословно — со строками
    «Группа: долгоживущий»/«Красен до реализации» и абзацем о стабе, без
    пути `tests.prior_outcome_sandbox.PriorSandbox`, — или написал одну
    строку назначения без свода и стенда — тест краснеет с недостающим.
    """
    raw = ast.get_docstring(_ctx.module_tree()) or ""
    doc = " ".join(raw.split())
    assert doc, f"у {_plan.MODULE} нет докстринга"
    missing = [w for w in ("test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior",
                           "Оператор", "2а-2в-2", "таблиц", "PLAN", "прежние версии",
                           "tests.prior_outcome_sandbox.PriorSandbox",
                           "tests.merge_outcome_sandbox.MergeOutcomeSandbox",
                           "tests.outcome_gate_sandbox.OutcomeGateSandbox")
               if w not in doc]
    if not re.search(r"ADR-0020\W{0,3}пп?\.\s?(?:\d+\s*(?:,|и)\s*)*8(?!\d)", doc):
        missing.append("ADR-0020 п. 8")
    assert not missing, f"докстринг модуля не называет: {missing}"
    present = [w for w in ("Группа: долгоживущий", "Красен до реализации",
                           "Провалидировано временным стабом реализации")
               if w in doc]
    assert not present, f"докстринг модуля несёт строки: {present}"


# ------------------------------------------------------------------ AC-11

def test_ac11_fixture_box_is_yield_from_sandbox_of_prior_sandbox():
    """Фикстура `box` — `yield from _sandbox(PriorSandbox)` и ничего больше: ни утверждений, ни иных вызовов.

    Тело фикстуры без докстринга — единственный оператор
    `yield from _sandbox(PriorSandbox)`.

    Ловит мутацию: фикстура `box` сразу зовёт `box.junit(...)` или
    построена на `MergeOutcomeSandbox` — лишний вызов или не тот класс,
    тест краснеет.
    """
    funcs = _ctx.module_functions()
    assert _plan.BOX in funcs, f"фикстуры {_plan.BOX} в {_plan.MODULE} нет"
    func = funcs[_plan.BOX]
    assert _plan.is_fixture(func), f"{_plan.BOX} не помечена pytest.fixture"
    body = _plan.strip_docstring(func.body)
    want = ast.dump(ast.parse(f"yield from _sandbox({_plan.FIXTURE_CLASS})").body[0])
    assert len(body) == 1 and ast.dump(body[0]) == want, (
        f"тело {_plan.BOX}: {[ast.unparse(s) for s in body]}, ожидалось "
        f"«yield from _sandbox({_plan.FIXTURE_CLASS})»")


def test_ac11_every_test_function_takes_box():
    """Каждая тестовая функция модуля берёт параметр `box`; функций — не меньше перенесённых тестов задачи.

    Ловит мутацию: бывшие тесты `Ac32` получили собственную фикстуру
    `conftest_box` на другом классе, а не `box` — функция без `box`
    перечислена, тест краснеет.
    """
    tests = _plan.module_tests(_ctx.module_tree())
    assert tests, f"тестовых функций в {_plan.MODULE} нет"
    without = [f.name for f in tests if _plan.BOX not in {a.arg for a in f.args.args}]
    assert not without, "функции без параметра box:\n" + "\n".join(without)


def test_ac11_fixtures_call_no_asserting_methods():
    """Ни одна фикстура модуля не содержит утверждений и не зовёт непосредственно методов и помощников с утверждениями.

    Ловит мутацию: свод завёл фикстуру `granted`, которая зовёт
    `grant(box, …)` или `box.in_dev_task(...)` — вызов найден, тест
    краснеет с именем.
    """
    asserting = set(_plan.ASSERTING)
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
def test_ac12_helper_signature_verbatim(name):
    """Помощник — функция модуля с сигнатурой критерия дословно (параметры, умолчания, аннотации, возвращаемый тип).

    Ловит мутацию: у `passed` нет параметра `case`, у `grant` умолчание
    `covered` другое или снято `-> None`, у `conftest_case` снята аннотация
    `dict | None` — тест краснеет с именем помощника.
    """
    func = _ctx.module_functions().get(name)
    assert func is not None, f"функции {name} в {_plan.MODULE} нет"
    assert _plan.signature_dump(func) == _plan.reference_signature(name), (
        f"сигнатура {name} не равна «{_plan.HELPER_SIGNATURES[name].splitlines()[0]}»")


@pytest.mark.parametrize("name", list(_plan.GATE_HELPERS))
def test_ac12_gate_helper_equal_to_gate_module_function(name):
    """`refusal`/`no_gate_refusal` модуля по `ast.dump` равны одноимённым функциям `tests/test_outcome_gate_module.py`.

    Ловит мутацию: в `refusal` выпала проверка `state_of(rows) == "in_dev"`
    или `GATE_ACTIONS` заменён перечнем своих констант — дамп расходится,
    тест краснеет.
    """
    want = _plan.module_functions(_ctx.base_tree(_plan.GATE_TESTS)).get(name)
    assert want is not None, f"{name} нет в {_plan.GATE_TESTS} базы"
    got = _ctx.module_functions().get(name)
    assert got is not None, f"функции {name} в {_plan.MODULE} нет"
    assert ast.dump(got) == ast.dump(want), f"{name} не равна функции {_plan.GATE_TESTS}"


@pytest.mark.parametrize("name", list(_plan.HELPER_SOURCE))
def test_ac12_helper_body_equal_to_source_method_after_replacements(name):
    """Тело `passed`, `grant`, `conftest_case` по AST равно телу исходного метода после замен требования 14.

    Ожидаемое тело — тело метода базы без докстринга (`PriorSandbox.passed`,
    `PriorSandbox.grant`, `Ac32AddedFilesRemovedTest.conftest_case`), где
    `self` → `box`, `self.refusal(…)` → `refusal(box, …)`; у `passed` и
    `grant` текст сообщения каждого `box.assert*` — `case +` спереди
    прежнего выражения (ANSWER-1 п. 1: у `grant` — `case +
    box.note(f"answer отказала: {output}")`).

    Ловит мутацию: в `grant` сообщение переписано на `case + f"…" +
    box.explain(...)`, в `passed` утверждение переписано в `assert found,
    …`, в `conftest_case` выпало `box.watch_old = (conftest,)` — тест
    краснеет с именем помощника.
    """
    cls, with_case = _plan.HELPER_SOURCE[name]
    method = _plan.class_method(_ctx.base_tree(_plan.SOURCE), cls, name)
    assert method is not None, f"{cls}.{name} нет в базе"
    func = _ctx.module_functions().get(name)
    assert func is not None, f"функции {name} в {_plan.MODULE} нет"
    assert _plan.actual_helper_body(func) == \
        _plan.expected_helper_body(method, _plan.BOX, with_case), (
            f"тело {name} не равно телу {cls}.{name} после замен")


@pytest.mark.parametrize("name", list(_plan.HELPER_SOURCE))
def test_ac12_helper_assertions_are_box_assert_calls(name):
    """Утверждения `passed`, `grant`, `conftest_case` — вызовы `box.assertX(...)`, операторов `assert` в них нет; у `passed` и `grant` сообщение начинается с `case +`.

    Ловит мутацию: свод переписал утверждение помощника в `assert ok, …`
    (guard увидел бы его иначе), или сообщение `grant` — `box.note(…) +
    case` — тест краснеет.
    """
    func = _ctx.module_functions().get(name)
    assert func is not None, f"функции {name} в {_plan.MODULE} нет"
    statements = [n.lineno for n in ast.walk(func) if isinstance(n, ast.Assert)]
    assert not statements, f"в {name} операторы assert в строках {statements}"
    calls = [n for n in ast.walk(func) if _plan.is_method_assert(n)
             and isinstance(n.func.value, ast.Name) and n.func.value.id == _plan.BOX]
    assert calls, f"в {name} нет вызова box.assert*(...)"
    if _plan.HELPER_SOURCE[name][1]:
        wrong = [n.lineno for n in calls
                 if not (isinstance(_plan.leftmost_add(_plan.message_arg(n)), ast.Name)
                         and _plan.leftmost_add(_plan.message_arg(n)).id == _plan.CASE)]
        assert not wrong, f"в {name} сообщение не начинается с «case +» в строках {wrong}"


# ------------------------------------------------------------------ AC-13

def test_ac13_test_bodies_equal_source_after_replacements():
    """Тело каждой перенесённой тестовой функции по AST равно телу исходного метода после замен требований 16–17.

    Ожидаемое тело — тело метода базы без докстринга, где
    `self.<помощник>(…)` → `<помощник>(box, …)`, `self` → `box`,
    `self.assertEqual(a, b[, m])` → `assert a == b[, m]`, `assertTrue` →
    `assert x`, `assertFalse` → `assert not x`, `assertIn` → `in`,
    `assertNotIn` → `not in`, `assertGreaterEqual` → `>=`; блок
    `with self.subTest(case=X, …)` → `case = f"{X}, зерно {box.seed}: "`
    (у литерала — литерал вместо `{X}`) и тело с `case +` спереди каждого
    сообщения и `case=case` в вызовах `refusal`/`no_gate_refusal`/`passed`;
    локальные имена обезличены по порядку появления. Каноничные дампы
    совпадают.

    Ловит мутацию: в бывшем `test_ac7_tests_change_runs_only_changed_files`
    выбор `changed` зафиксирован литералом, в бывшем
    `test_ac4_prior_red_thrice_refuses_outcome` выпало
    `assert "; база: " in lines[0], …`, `assertGreaterEqual(runs, 1, …)`
    перенесён как `assert runs > 0, …`, или вложенная `third` вынесена на
    уровень модуля — тест краснеет с именем.
    """
    problems, seen = [], 0
    for test, func in _ctx.pairs():
        seen += 1
        if _plan.actual_test_body(func) != _plan.expected_test_body(test.func, _plan.BOX):
            problems.append(f"{test.key} → {func.name}: тело не равно исходному после замен")
    assert seen, "ни один тест задачи не найден в модуле"
    assert not problems, "\n".join(problems)


def test_ac13_assertion_literals_carried_verbatim():
    """Литералы утверждений исходных тестов есть в тестовых функциях модуля дословно.

    Каждый строковый и числовой литерал смысловых аргументов `self.assert*`
    22 тестов задачи (без аргумента сообщения) встречается литералом вне
    докстрингов в тестовых функциях модуля.

    Ловит мутацию: при переносе ожидание `"verifying"` переписано как
    `"verified"`, или `assertEqual(len(lines), 1, …)` — как
    `assert len(lines) == 2, …` — исходного литерала нет, тест краснеет с
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

    Ловит мутацию: `assertIn(f"{FLAKY}: {cid}", …)` перенесён как
    `assert f"нестабилен и на базе: {cid}" in …` — имени `FLAKY` нет, тест
    краснеет с ним.
    """
    names = {n.id for n in ast.walk(_module_tests_tree()) if isinstance(n, ast.Name)}
    missing = sorted(c for c in _plan.assertion_constant_names(_source_tests_tree())
                     if c not in names)
    assert not missing, ("константы утверждений исходных тестов не найдены "
                         "именем в модуле: " + ", ".join(missing))


def test_ac13_equality_not_weakened_and_message_is_second_operand():
    """Перенесённый тест: литералы равенств — в `==`, вхождений — в `in`; число `assert` с сообщением и без равно числу `self.assert*` с сообщением и без; `<что-то>.assert*` в тестовых функциях нет.

    Ловит мутацию: `assertEqual(self.state(t), "verifying", …)` перенесён
    как `assert "verifying" in box.state(t), …`, сообщение
    `box.explain(rows, output)` потеряно, или утверждение осталось
    `box.assertTrue(...)` — тест краснеет с именем.
    """
    problems, seen = [], 0
    for test, func in _ctx.pairs():
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
    assert seen, "ни один тест задачи не найден в модуле"
    assert not problems, "\n".join(problems)


def test_ac13_helpers_by_bare_name_with_box_and_stand_methods_via_box():
    """Тесты зовут помощников голым именем с `box` первым аргументом, методы стенда — через `box`.

    Вызовов `<что-то>.refusal/no_gate_refusal/passed/grant/conftest_case(…)`
    в модуле нет; у каждого голого вызова помощника первый аргумент —
    `box`; в модуле нет функций верхнего уровня и голых вызовов с именами
    прочих методов `PriorSandbox` базы (кроме самих помощников).

    Ловит мутацию: бывший `Ac8` оставил `box.grant(t, paths=[gone])`, вызов
    `refusal(rows, output, …)` без `box`, или метод `old_files` вынесен в
    функцию модуля `old_files(box)` — тест краснеет.
    """
    tree = _ctx.module_tree()
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)]
    problems = []
    for helper in _plan.HELPERS:
        if any(isinstance(c.func, ast.Attribute) and c.func.attr == helper for c in calls):
            problems.append(f"{helper} вызван методом")
        for c in calls:
            if isinstance(c.func, ast.Name) and c.func.id == helper and not (
                    c.args and isinstance(c.args[0], ast.Name) and c.args[0].id == _plan.BOX):
                problems.append(f"{helper} в строке {c.lineno}: первый аргумент не box")
    base = _ctx.base_tree(_plan.SOURCE)
    methods = _plan.class_method_names(base, "PriorSandbox") - set(_plan.HELPERS)
    assert methods, "методов PriorSandbox в базе не найдено"
    problems += [f"функция модуля {n}" for n in sorted(set(_ctx.module_functions()) & methods)]
    problems += [f"голый вызов {c.func.id} в строке {c.lineno}" for c in calls
                 if isinstance(c.func, ast.Name) and c.func.id in methods]
    assert not problems, "\n".join(problems)


def test_ac13_stand_attribute_assignments_same_order():
    """Присваивания атрибутам стенда (`git_fail`, `timeout_when`, `watch_old`, `cases[…]`) идут через `box` дословно и тем же порядком.

    Для каждого перенесённого теста: последовательность целей присваиваний
    атрибутам стенда в функции равна последовательности целей `self.…` в
    методе, где `self` заменён на `box`.

    Ловит мутацию: в бывшем `test_ac11_third_checkout_failure_refuses_prepare`
    сброс `box.git_fail = None` поставлен после `refusal(...)` или
    выброшен, `cases[...]` присвоен через локальную переменную — тест
    краснеет с именем теста.
    """
    problems, seen = [], 0
    for test, func in _ctx.pairs():
        want = [t.replace("self", _plan.BOX, 1)
                for t in _plan.attribute_assignments(test.func, "self")]
        if want:
            seen += 1
        got = _plan.attribute_assignments(func, _plan.BOX)
        if got != want:
            problems.append(f"{test.key} → {func.name}: присваивания {got}, ожидались {want}")
    assert seen, "в перенесённых тестах не найдено присваиваний атрибутам стенда"
    assert not problems, "\n".join(problems)


def test_ac13_nested_functions_and_lambdas_stay_nested():
    """Вложенные функции (`third`) и лямбды перенесённых тестов остались вложенными в той же функции: имена вложенных функций и число лямбд те же.

    Ловит мутацию: `third` бывшего `Ac11` вынесен на уровень модуля, или
    лямбды правил бывшего `Ac12` заменены функциями модуля — набор
    вложенных имён или число лямбд расходится, тест краснеет с именем.
    """
    problems, seen = [], 0
    for test, func in _ctx.pairs():
        def nested(node):
            return sorted(n.name for n in ast.walk(node)
                          if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                          and n is not node)

        def lambdas(node):
            return sum(isinstance(n, ast.Lambda) for n in ast.walk(node))

        want = (nested(test.func), lambdas(test.func))
        if want != ([], 0):
            seen += 1
        got = (nested(func), lambdas(func))
        if got != want:
            problems.append(f"{test.key} → {func.name}: вложенные/лямбды {got}, "
                            f"в исходном {want}")
    assert seen, "в перенесённых тестах не найдено вложенных функций и лямбд"
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-14

def _subtest_labels(method) -> list:
    found = [(n.lineno, label) for n in ast.walk(method)
             for label in [_plan.subtest_label(n, "self")] if label is not None]
    return [label for _line, label in sorted(found, key=lambda x: x[0])]


def _parents(tree) -> dict:
    found = {}
    for node in ast.walk(tree):
        for field, value in ast.iter_fields(node):
            if isinstance(value, list):
                for i, child in enumerate(value):
                    if isinstance(child, ast.AST):
                        found[id(child)] = (node, field, i)
    return found


@pytest.mark.parametrize("name", list(_plan.SUBTEST_TESTS))
def test_ac14_subcase_starts_with_case_line_and_case_prefixes_messages(name):
    """Функция бывшего `subTest`: у каждого подслучая строка `case = f"{label}, зерно {box.seed}: "` (у одиночных блоков `Ac9` — литерал ярлыка), в цикле — первой строкой тела; `case` спереди сообщения каждого утверждения подслучая и `case=case` в каждом вызове `refusal`/`no_gate_refusal`/`passed`.

    Строк `case = …` столько же, сколько блоков `subTest` в исходном
    методе, и каждая по `ast.dump` равна ожидаемой для ярлыка своего блока
    по порядку; строка в теле цикла `for` стоит в нём первой. Каждое
    `assert` с сообщением после первой строки `case` несёт сообщение
    `case + …`; каждый вызов помощника исхода после неё несёт `case=case`.

    Ловит мутацию: ярлык подслучая записан как `f"{label}: "` без зерна,
    `case` приписан в конец сообщения, строка `case` поставлена после
    `box.junit(...)`, или `no_gate_refusal(box, rows, output)` в подслучае
    вызван без `case=` — тест краснеет с функцией.
    """
    test = next((t for t in _ctx.task_tests_in_order() if t.func.name == name), None)
    assert test is not None, f"{name} нет среди тестов задачи в базе"
    func = _ctx.module_functions().get(name)
    assert func is not None, f"функции {name} в {_plan.MODULE} нет"
    labels = _subtest_labels(test.func)
    assert labels, f"в {test.key} базы нет блоков subTest"
    parents = _parents(func)
    lines = [n for n in ast.walk(func) if isinstance(n, ast.Assign)
             and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)
             and n.targets[0].id == _plan.CASE]
    lines.sort(key=lambda n: (n.lineno, n.col_offset))
    assert len(lines) == len(labels), (f"{name}: строк case {len(lines)}, блоков subTest "
                                       f"в исходном {len(labels)}")
    problems = []
    for got, label in zip(lines, labels):
        want = _plan.case_line(label, _plan.BOX)
        if ast.dump(got) != ast.dump(want):
            problems.append(f"строка {got.lineno}: «{ast.unparse(got)}», ожидалась "
                            f"«{ast.unparse(want)}»")
        parent, field, index = parents[id(got)]
        if isinstance(parent, ast.For) and field == "body" and index != 0:
            problems.append(f"строка {got.lineno}: case не первой строкой тела цикла")
    first = lines[0].lineno
    for node in ast.walk(func):
        if isinstance(node, ast.Assert) and node.lineno > first and node.msg is not None:
            left = _plan.leftmost_add(node.msg)
            if not (isinstance(left, ast.Name) and left.id == _plan.CASE):
                problems.append(f"assert в строке {node.lineno}: сообщение не «case + …»")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id in _plan.CASE_CALLS and node.lineno > first:
            kw = [k for k in node.keywords if k.arg == _plan.CASE]
            if not (kw and isinstance(kw[0].value, ast.Name) and kw[0].value.id == _plan.CASE):
                problems.append(f"{node.func.id} в строке {node.lineno}: нет case=case")
    assert not problems, f"{name}:\n" + "\n".join(problems)


# ------------------------------------------------------------------ AC-15

def test_ac15_every_test_function_declares_mutation():
    """У каждой тестовой функции модуля есть строка «Ловит мутацию:».

    Ловит мутацию: свод перенёс тест с докстрингом, укороченным до первой
    фразы, без заявки — функция перечислена, тест краснеет.
    """
    tests = _plan.module_tests(_ctx.module_tree())
    assert tests, f"тестовых функций в {_plan.MODULE} нет"
    without = [f.name for f in tests if "Ловит мутацию:" not in (ast.get_docstring(f) or "")]
    assert not without, "функции без «Ловит мутацию:»:\n" + "\n".join(without)


def test_ac15_locals_do_not_shadow_module_functions_or_fixtures():
    """Локальные имена функций модуля не совпадают с функциями и фикстурами модуля и с фикстурами `tests/fixtures.py`.

    Ловит мутацию: бывший тест оставил локальное `box = …` или
    `passed = …`, затеняющее фикстуру или помощника модуля — тест краснеет
    с именем.
    """
    funcs = _ctx.module_functions()
    taken = set(funcs) | _shared_fixture_names()
    problems = []
    for func in funcs.values():
        stored = {n.id for n in ast.walk(func)
                  if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
        problems += [f"{func.name}: локальное {name}" for name in sorted(stored & taken)]
    assert not problems, "\n".join(problems)


def test_ac15_renamed_locals_listed_in_plan():
    """PLAN перечисляет переименованные локальные имена: каждое имя исходных тестов задачи, совпавшее с функцией или фикстурой модуля.

    Локальные имена тестовых методов задачи, совпадающие с функцией
    верхнего уровня модуля на HEAD или фикстурой `tests/fixtures.py`: каждое
    стоит в PLAN в обратных кавычках. Совпадений нет — перечень пуст.

    Ловит мутацию: разработчик переименовал локальное имя, совпавшее с
    помощником модуля, но не записал перечень в PLAN — имени нет, тест
    краснеет с ним.
    """
    taken = set(_ctx.module_functions()) | _shared_fixture_names()
    wanted = set()
    for test in _ctx.task_tests_in_order():
        wanted |= {n.id for n in ast.walk(test.func)
                   if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)
                   and n.id in taken}
    if not wanted:
        return
    plan = _ctx.plan_text()
    missing = sorted(name for name in wanted if f"`{name}`" not in plan)
    assert not missing, f"в PLAN нет перечня переименованных локальных: {missing}"


def test_ac15_every_task_test_transferred_or_listed_as_removed_duplicate():
    """Каждый из 22 тестов задачи перенесён в модуль либо перечислен в PLAN удалённым дублем.

    Тест задачи базы, не перечисленный в разделе «…дубл…» PLAN,
    сопоставлен функции модуля (по имени или соответствию PLAN).

    Ловит мутацию: при своде пропал бывший
    `test_ac8_type_changed_file_in_set` (не перенесён и не записан дублем)
    — тест краснеет с его именем.
    """
    funcs = _ctx.module_functions()
    plan = _ctx.plan_or_empty()
    transfer, removed = _plan.transfer_map(plan), _ctx.removed_keys(plan)
    tests = _ctx.task_tests_in_order()
    assert len(tests) == _plan.CLAIMS, f"тестов задачи в базе {len(tests)}"
    lost = [t.key for t in tests if t.key not in removed
            and not _ctx.matches(funcs, t.cls, t.func.name, transfer)]
    assert not lost, ("тесты не перенесены и не перечислены удалёнными дублями:\n"
                      + "\n".join(lost))
