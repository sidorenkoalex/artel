"""AC-5, AC-6, AC-7, AC-8, AC-14: форма сводного
`tests/test_doc_commit_module.py` против шести исходных файлов волны в базе
ветки.

Группа: разовый
Красен до реализации: tests/test_doc_commit_module.py на ветке ещё нет — свод не сделан, чтение файла из HEAD даёт None.

Новый файл читается из HEAD рабочей копии (`git show HEAD:…`), исходные —
из базы ветки (`_pult.DIFF_BASE`): после свода их на ветке нет. Сравнение
статическое (ast): тест не исполняет ни новый, ни исходные тесты; значения
констант кода и состав классов `tests/sandbox.py` берутся импортом в
отдельном интерпретаторе рабочей копии.
"""
import ast
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _plan  # noqa: E402
from _pult import CODE_ROOT, DIFF_BASE  # noqa: E402

_SKIP_NAMES = {"skip", "skipif", "xfail", "skipTest", "importorskip",
               "skipIf", "skipUnless", "expectedFailure"}
_LIMIT_KWARGS = ("timeout", "delta", "places", "rel", "abs")
_SEED_WORD = "зерно"


def _new_tree() -> ast.Module:
    text = _plan.show(CODE_ROOT, "HEAD", _plan.NEW_FILE)
    assert text is not None, f"{_plan.NEW_FILE} нет в HEAD ветки"
    return ast.parse(text)


def _base_trees() -> list:
    assert DIFF_BASE, "база диффа ветки задачи не определена при выкладке"
    trees = []
    for path in _plan.SOURCE_FILES:
        text = _plan.show(CODE_ROOT, DIFF_BASE, path)
        assert text is not None, f"{path} нет в базе ветки {DIFF_BASE}"
        trees.append(ast.parse(text))
    return trees


def _python_value(code: str):
    res = subprocess.run([sys.executable, "-c", code], cwd=CODE_ROOT,
                         capture_output=True, text=True, timeout=120)
    assert res.returncode == 0, f"импорт в рабочей копии не прошёл: {res.stderr}"
    return ast.literal_eval(res.stdout.strip())


def _config_paths() -> tuple:
    return _python_value("from orchestrator import notes; "
                         "print(repr(tuple(notes.DOC_COMMIT_CONFIG_PATHS)))")


def _sandbox_testcase_names() -> set:
    return set(_python_value(
        "import unittest, tests.sandbox as s; print(repr(sorted("
        "n for n, v in vars(s).items() if isinstance(v, type) "
        "and issubclass(v, unittest.TestCase))))"))


def _functions(tree) -> list:
    return [n for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _assertion_sites(func) -> list:
    """Строки утверждений в теле: `assert`, `pytest.raises`, `pytest.fail`,
    `self.assert*`."""
    found = []
    for sub in ast.walk(func):
        if isinstance(sub, ast.Assert):
            found.append(sub.lineno)
        elif isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) \
                and (sub.func.attr in ("fail", "raises")
                     or sub.func.attr.startswith("assert")):
            found.append(sub.lineno)
    return found


def _seed_print(func) -> bool:
    for sub in ast.walk(func):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) \
                and sub.func.id == "print" \
                and any(isinstance(c, str) and _SEED_WORD in c
                        for c in _plan.constants(sub)):
            return True
    return False


def _creates_rng(func) -> bool:
    for sub in ast.walk(func):
        if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) \
                and sub.func.attr in ("SystemRandom", "Random") \
                and isinstance(sub.func.value, ast.Name) \
                and sub.func.value.id == "random":
            return True
    return False


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

def test_ac5_module_level_pytest_functions_without_testcase_or_subtest():
    """Тесты нового файла — функции модуля, без наследников `unittest.TestCase` и `subTest`.

    В файле есть тестовые функции первого уровня модуля; ни один класс файла
    не наследует (прямо, через классы `tests/sandbox.py` или через другой
    класс файла) `unittest.TestCase`; тестовых методов внутри классов нет;
    обращений `subTest` нет.

    Ловит мутацию: свод оставил `class SuiteGateSandbox(DocCommitSandbox)`
    поверх `RealGitSandbox` с методами `test_…` и `with self.subTest(...)` —
    класс/обращение найдено, тест краснеет с его именем.
    """
    tree = _new_tree()
    assert _plan.module_tests(tree), f"в {_plan.NEW_FILE} нет тестовых функций"
    testcase = {"TestCase"} | _sandbox_testcase_names()
    classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    changed = True
    while changed:
        changed = False
        for node in classes:
            if node.name in testcase:
                continue
            bases = {ast.unparse(b).rsplit(".", 1)[-1] for b in node.bases}
            if bases & testcase:
                testcase.add(node.name)
                changed = True
    problems = []
    for node in classes:
        if node.name in testcase:
            problems.append(f"класс {node.name} — наследник unittest.TestCase")
        methods = [i.name for i in node.body
                   if isinstance(i, (ast.FunctionDef, ast.AsyncFunctionDef))
                   and i.name.startswith("test")]
        if methods:
            problems.append(f"класс {node.name} с тестовыми методами {methods}")
    problems += [f"subTest в строке {n.lineno}" for n in ast.walk(tree)
                 if isinstance(n, ast.Attribute) and n.attr == "subTest"]
    assert not problems, "\n".join(problems)


def test_ac5_assertion_helpers_are_module_functions_not_fixtures():
    """Утверждения — только в функциях модуля: ни в фикстурах, ни в методах классов.

    Ни одна функция с декоратором `pytest.fixture` и ни один метод класса
    файла не содержит `assert`, `pytest.raises`, `pytest.fail` или
    `self.assert*`; функции первого уровня модуля, кроме фикстур, могут
    их содержать.

    Ловит мутацию: помощник `assert_refused` (или `assert_nothing_sent`)
    оформлен фикстурой либо оставлен методом класса-песочницы — строка
    утверждения найдена в нём, тест краснеет с именем помощника.
    """
    tree = _new_tree()
    problems = []
    for func in _functions(tree):
        if _plan.is_fixture(func):
            problems += [f"фикстура {func.name}: утверждение в строке {line}"
                         for line in _assertion_sites(func)]
    for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
        for item in cls.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                problems += [f"метод {cls.name}.{item.name}: утверждение в "
                             f"строке {line}" for line in _assertion_sites(item)]
    assert not problems, ("утверждения вне функций модуля (помощники с "
                          "утверждениями — функции модуля):\n"
                          + "\n".join(problems))


# ------------------------------------------------------------------ AC-6

def test_ac6_raises_match_escaped_and_only_at_text_check_sites():
    """`pytest.raises(..., match=…)` — всегда `re.escape(...)` и не чаще проверок текста.

    Каждый `pytest.raises` с `match` передаёт `re.escape(...)`. Число
    `pytest.raises` с `match` не больше числа мест исходных файлов, где
    проверялся текст исключения (`assertRaises(...) as x` с чтением
    `x.exception`, `assertRaisesRegex`): голый `assertRaises(E)` переходит
    в `pytest.raises(E)` без `match`.

    Ловит мутацию: свод дописал `match="…"` сырым регулярным выражением
    (без `re.escape`) или добавил `match` на месте голого
    `assertRaises(SystemExit)` (`tests/test_doc_commit.py`,
    `test_path_added_in_origin_after_pin_refuses`) — тест краснеет со
    строкой/числами.
    """
    tree = _new_tree()
    sites = sum(_plan.text_raises_sites(t) for t in _base_trees())
    with_match, raw = 0, []
    for node in ast.walk(tree):
        if not _plan.is_pytest_raises(node):
            continue
        for kw in node.keywords:
            if kw.arg != "match":
                continue
            with_match += 1
            value = kw.value
            if not (isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute)
                    and value.func.attr == "escape"
                    and isinstance(value.func.value, ast.Name)
                    and value.func.value.id == "re"):
                raw.append(f"строка {node.lineno}: match={ast.unparse(value)}")
    assert not raw, "match без re.escape(...):\n" + "\n".join(raw)
    assert with_match <= sites, (
        f"pytest.raises с match — {with_match}, а мест проверки текста "
        f"исключения в исходных файлах — {sites}: match стоит на месте голого "
        f"assertRaises")


def test_ac6_config_paths_iteration_not_frozen_into_literals():
    """Перебор по `notes.DOC_COMMIT_CONFIG_PATHS` не заморожен литералами.

    Исходный тест перебирал `notes.DOC_COMMIT_CONFIG_PATHS`; новый файл
    обращается к константе, и ни один столбец литералов `parametrize`, ни
    литеральный набор цикла `for` не равен по составу значению константы на
    текущем коде.

    Ловит мутацию: свод переписал перебор в
    `@pytest.mark.parametrize("path", ["roles.yaml", "gates.yaml", …])`
    литералами текущего набора — столбец совпал с константой, тест краснеет.
    """
    tree = _new_tree()
    paths = set(_config_paths())
    names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} \
        | {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert "DOC_COMMIT_CONFIG_PATHS" in names, (
        f"{_plan.NEW_FILE} не обращается к notes.DOC_COMMIT_CONFIG_PATHS")
    columns = _plan.parametrize_columns(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.For) and isinstance(node.iter, (ast.List, ast.Tuple)):
            try:
                columns.append(list(ast.literal_eval(node.iter)))
            except (ValueError, TypeError, SyntaxError):
                pass
    frozen = [col for col in columns
              if all(isinstance(v, str) for v in col) and set(col) == paths]
    assert not frozen, f"перебор константы заморожен литералами: {frozen}"


def test_ac6_bare_literal_loop_only_with_shared_state():
    """Голый цикл по литеральному набору — только в тесте с общим состоянием.

    Тестовая функция без фикстур (все её параметры — имена `parametrize`)
    общего состояния между итерациями не держит; в ней нет цикла `for` по
    литеральному списку/кортежу/множеству — такой перебор задаётся
    `parametrize`. (Все `subTest` исходных файлов идут внутри песочницы с
    общим состоянием либо по нелитеральному набору — их цикл законен и
    здесь не проверяется; отсутствие `subTest` — AC-5.)

    Ловит мутацию: тест допустимых путей `doc-commit` без песочницы
    перенесён прежним `for rel in ("docs/roadmap.md", "roles.yaml", …)` в
    теле функции — цикл найден, тест краснеет с именем функции.
    """
    tree = _new_tree()
    problems = []
    for func in _plan.module_tests(tree):
        params = {a.arg for a in func.args.args + func.args.kwonlyargs}
        if params - _plan.parametrize_names(func):
            continue
        for sub in ast.walk(func):
            if isinstance(sub, ast.For) and \
                    isinstance(sub.iter, (ast.List, ast.Tuple, ast.Set)):
                problems.append(f"{func.name}: цикл по литеральному набору в "
                                f"строке {sub.lineno}")
    assert not problems, "\n".join(problems)


def test_ac6_random_choice_not_moved_into_parametrize():
    """Случайный выбор не вынесен в `parametrize`: аргументы декоратора не зовут `random`/`rng`.

    Ловит мутацию: случайные пути песочницы `knowledge/…` вынесены в
    `@pytest.mark.parametrize("rel", [rng.choice(…) …])` при сборе — имя
    `random`/`rng` в аргументах декоратора, тест краснеет с функцией.
    """
    tree = _new_tree()
    problems = []
    for func in _functions(tree):
        for deco in _plan.parametrize_decorators(func):
            used = {n.id for n in ast.walk(deco) if isinstance(n, ast.Name)} \
                | {n.attr for n in ast.walk(deco) if isinstance(n, ast.Attribute)}
            if used & {"random", "rng", "SystemRandom", "Random"}:
                problems.append(f"{func.name}: parametrize в строке "
                                f"{deco.lineno} зовёт случайный выбор")
    assert not problems, "\n".join(problems)


def test_ac6_seed_printed_where_random_sandbox_is_built():
    """Зерно печатается там, где строится случайная песочница, а не в теле теста.

    В исходных файлах зерно печатала подготовка случайной песочницы
    (`setUp`: `random.SystemRandom()` и `print(f"зерно: …")`). В новом
    файле есть функция подготовки (не тестовая), печатающая зерно; каждая
    функция, создающая генератор (`random.SystemRandom`/`random.Random`),
    печатает зерно; тестовые функции зерно сами не печатают.

    Ловит мутацию: при переносе `HeldBaseSandbox.setUp` в фикстуру строка
    `print(f"зерно: {seed}")` потеряна — функция с генератором без печати,
    тест краснеет с её именем.
    """
    tree = _new_tree()
    tests = {id(f) for f in _plan.module_tests(tree)}
    funcs = _functions(tree)
    printers = [f.name for f in funcs if _seed_print(f) and id(f) not in tests]
    assert printers, (f"в {_plan.NEW_FILE} нет функции подготовки, печатающей "
                      f"зерно")
    silent = [f.name for f in funcs if _creates_rng(f) and not _seed_print(f)]
    in_tests = [f.name for f in funcs if id(f) in tests and _seed_print(f)]
    assert not silent, f"генератор строится без печати зерна: {silent}"
    assert not in_tests, f"зерно печатает тестовая функция: {in_tests}"


# ------------------------------------------------------------------ AC-7

def test_ac7_assertion_literals_carried_verbatim():
    """Литералы утверждений исходных тестов есть в новом файле дословно.

    Каждый строковый и числовой литерал смысловых аргументов `self.assert*`
    шести исходных файлов (без аргумента msg) встречается литералом в
    новом файле вне докстрингов.

    Ловит мутацию: при переносе ожидание `"test_seed_always_red"` переписано
    как `"seed_always_red"` или укорочено до части текста — исходного
    литерала в новом файле нет, тест краснеет с ним.
    """
    new_lits = _plan.non_docstring_constants(_new_tree())
    missing = set()
    for tree in _base_trees():
        missing |= {lit for lit in _plan.assertion_literals(tree)
                    if lit not in new_lits}
    assert not missing, ("литералы утверждений исходных тестов не найдены в "
                         "новом файле:\n" + "\n".join(sorted(map(repr, missing))))


def test_ac7_equality_not_weakened_to_membership_or_inequality():
    """Равенство не заменено вхождением, точное число — неравенством.

    Литерал, который исходные файлы сравнивали `assertEqual` (и никогда —
    `assertIn`/`assertNotIn`), в новом файле не стоит только в сравнениях
    `in`/`not in`; числовой литерал `assertEqual` не стоит только в
    сравнениях `<`, `<=`, `>`, `>=`: если он есть в таком сравнении, он
    есть и в сравнении `==`/`!=`/`is`.

    Ловит мутацию: `assertEqual(cfg, "config: gates.yaml — порог")`
    перенесён как `assert "config: gates.yaml — порог" in cfg`, или
    `assertEqual(len(x), 2)` — как `assert len(x) >= 2`, — тест краснеет с
    литералом.
    """
    equal, member = set(), set()
    for tree in _base_trees():
        eq, mem = _plan.equality_literals(tree)
        equal |= eq
        member |= mem
    compared = _plan.compare_operands(_new_tree())
    eq_lits = set().union(*[l for k, l in compared if k == "eq"] or [set()])
    in_lits = set().union(*[l for k, l in compared if k == "in"] or [set()])
    order_lits = set().union(*[l for k, l in compared if k == "order"] or [set()])
    to_in = sorted(repr(l) for l in equal - member
                   if isinstance(l, str) and l in in_lits and l not in eq_lits)
    to_order = sorted(repr(l) for l in equal
                      if isinstance(l, (int, float)) and l in order_lits
                      and l not in eq_lits)
    assert not to_in, "равенство заменено вхождением: " + ", ".join(to_in)
    assert not to_order, "точное число заменено неравенством: " + ", ".join(to_order)


# ------------------------------------------------------------------ AC-8

def test_ac8_every_test_function_declares_mutation():
    """У каждой тестовой функции нового файла есть строка «Ловит мутацию:».

    Ловит мутацию: свод перенёс тест без заявки (докстринг без строки
    «Ловит мутацию:», например укороченный до первой фразы) — функция
    перечислена, тест краснеет.
    """
    tests = _plan.module_tests(_new_tree())
    assert tests, f"в {_plan.NEW_FILE} нет тестовых функций"
    without = [f.name for f in tests
               if "Ловит мутацию:" not in (ast.get_docstring(f) or "")]
    assert not without, "функции без «Ловит мутацию:»:\n" + "\n".join(without)


# ------------------------------------------------------------------ AC-14

def test_ac14_no_skip_or_xfail_in_new_file():
    """В новом файле нет `skip`/`xfail` ни в каком виде.

    Ни обращений `pytest.mark.skip`/`skipif`/`xfail`, `pytest.skip`,
    `unittest.skip*`, `skipTest`, `importorskip`, ни импорта этих имён.

    Ловит мутацию: неперенесённый тест помечен
    `@pytest.mark.skip(reason="…")` или `pytest.xfail(...)` — имя найдено,
    тест краснеет со строкой.
    """
    tree = _new_tree()
    found = [f"{n.attr} в строке {n.lineno}" for n in ast.walk(tree)
             if isinstance(n, ast.Attribute) and n.attr in _SKIP_NAMES]
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            found += [f"импорт {a.name}" for a in node.names if a.name in _SKIP_NAMES]
    assert not found, "skip/xfail в новом файле:\n" + "\n".join(found)


@pytest.mark.parametrize("name", list(_LIMIT_KWARGS))
def test_ac14_limits_not_raised_against_source_files(name):
    """Пределы (`timeout`, допуски `delta`/`places`/`rel`/`abs`) не подняты.

    Каждое числовое значение предела `name` в новом файле не больше
    наибольшего значения того же предела в исходных файлах; предела, которого
    в исходных файлах не было, в новом файле нет; `pytest.approx` есть,
    только если он был в исходных файлах.

    Ловит мутацию: свод добавил `@pytest.mark.timeout(600)` или
    `pytest.approx(..., rel=0.1)` вместо точного сравнения — значение выше
    исходного (или новое), тест краснеет с ним.
    """
    base = {}
    base_approx = False
    for tree in _base_trees():
        for key, values in _limits(tree).items():
            base.setdefault(key, []).extend(values)
        base_approx |= any(isinstance(n, ast.Attribute) and n.attr == "approx"
                           for n in ast.walk(tree))
    tree = _new_tree()
    new = _limits(tree).get(name, [])
    ceiling = max(base.get(name, []), default=None)
    raised = [v for v in new if ceiling is None or v > ceiling]
    assert not raised, (f"предел {name}: значения {raised} при исходном "
                        f"наибольшем {ceiling}")
    if not base_approx:
        approx = [n.lineno for n in ast.walk(tree)
                  if isinstance(n, ast.Attribute) and n.attr == "approx"]
        assert not approx, f"pytest.approx в строках {approx}, в исходных его не было"
