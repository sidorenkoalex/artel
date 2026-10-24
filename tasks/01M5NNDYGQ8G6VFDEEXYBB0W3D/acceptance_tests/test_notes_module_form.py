"""AC-3, AC-4, AC-5, AC-10: форма сводного `tests/test_notes_module.py` против
четырёх исходных файлов волны в базе ветки.

Группа: разовый
Красен до реализации: tests/test_notes_module.py на ветке ещё нет — свод не сделан, чтение файла из HEAD даёт None.

Новый файл читается из HEAD рабочей копии (`git show HEAD:…`), исходные —
из базы ветки (`_pult.DIFF_BASE`): после свода их на ветке нет. Сравнение
статическое (ast): тест не исполняет ни новый, ни исходные тесты.
"""
import ast
import re
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


def _window_states() -> tuple:
    res = subprocess.run(
        [sys.executable, "-c", "from orchestrator import config; "
         "print(repr(tuple(config.NOTE_SILENCE_WINDOW_STATES)))"],
        cwd=CODE_ROOT, capture_output=True, text=True, timeout=120)
    assert res.returncode == 0, f"config не импортирован: {res.stderr}"
    return ast.literal_eval(res.stdout.strip())


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


# ------------------------------------------------------------------ AC-3

def test_ac3_module_level_pytest_functions_without_testcase_or_subtest():
    """Тесты нового файла — функции модуля, без `unittest.TestCase` и `subTest`.

    В файле есть тестовые функции первого уровня модуля; ни один класс не
    наследует `TestCase`; тестовых методов внутри классов нет; обращений
    `subTest` нет.

    Ловит мутацию: свод оставил класс-наследник `unittest.TestCase` (или
    `SchemaTmpRootTest`) с методами `test_…` и `with self.subTest(...)` —
    класс/обращение найдено, тест краснеет с его именем.
    """
    tree = _new_tree()
    assert _plan.module_tests(tree), f"в {_plan.NEW_FILE} нет тестовых функций"
    problems = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            bases = [ast.unparse(b) for b in node.bases]
            if any("TestCase" in b or "TmpRootTest" in b or "Sandbox" in b
                   for b in bases):
                problems.append(f"класс {node.name}({', '.join(bases)})")
            methods = [i.name for i in node.body
                       if isinstance(i, (ast.FunctionDef, ast.AsyncFunctionDef))
                       and i.name.startswith("test")]
            if methods:
                problems.append(f"класс {node.name} с тестовыми методами {methods}")
        if isinstance(node, ast.Attribute) and node.attr == "subTest":
            problems.append(f"subTest в строке {node.lineno}")
    assert not problems, "\n".join(problems)


def test_ac3_schema_fixture_declared_and_fixtures_hold_no_assertions():
    """Замена `SchemaTmpRootTest` — фикстура файла; в фикстурах нет утверждений.

    Среди функций файла с декоратором `pytest.fixture` есть фикстура,
    готовящая схему БД (`store.create_schema`, как `SchemaTmpRootTest.
    setUp`); ни одна фикстура не содержит `assert`, `pytest.fail` или
    `self.assert*` — помощники с утверждениями остаются функциями модуля.

    Ловит мутацию: помощник сверки строк копилки с `assert` внутри оформлен
    фикстурой, либо схема создаётся в теле каждого теста без фикстуры —
    тест краснеет с именем фикстуры или отсутствием замены.
    """
    tree = _new_tree()
    fixtures = [n for n in ast.walk(tree)
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and _plan.is_fixture(n)]
    schema = [f.name for f in fixtures
              if any((isinstance(s, ast.Attribute) and s.attr == "create_schema")
                     or (isinstance(s, ast.Name) and s.id == "SchemaTmpRootTest")
                     for s in ast.walk(f))]
    assert schema, (f"в {_plan.NEW_FILE} нет фикстуры-замены SchemaTmpRootTest "
                    f"(фикстура с store.create_schema)")
    asserting = []
    for fixture in fixtures:
        for sub in ast.walk(fixture):
            if isinstance(sub, ast.Assert) or (
                    isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                    and (sub.func.attr == "fail"
                         or sub.func.attr.startswith("assert"))):
                asserting.append(f"{fixture.name}: строка {sub.lineno}")
    assert not asserting, ("утверждения в фикстурах (помощники с "
                           "утверждениями — функции модуля):\n"
                           + "\n".join(asserting))


def test_ac3_raises_match_escaped_and_only_at_text_check_sites():
    """`pytest.raises(..., match=…)` — всегда `re.escape(...)` и не чаще проверок текста.

    Каждый `pytest.raises` с `match` передаёт `re.escape(...)`. Число
    `pytest.raises` с `match` не больше числа мест исходных файлов, где
    проверялся текст исключения (`assertRaises(...) as x` с чтением
    `x.exception`, `assertRaisesRegex`): голый `assertRaises(E)` переходит
    в `pytest.raises(E)` без `match`.

    Ловит мутацию: свод дописал `match="…"` сырым регулярным выражением
    (без `re.escape`) или добавил `match` на месте голого
    `assertRaises(SystemExit)` — тест краснеет со строкой/числами.
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


def test_ac3_code_constant_iteration_not_frozen_into_literals():
    """Перебор по `config.NOTE_SILENCE_WINDOW_STATES` не заморожен литералами.

    Исходные тесты перебирали `config.NOTE_SILENCE_WINDOW_STATES` и
    производную `OUTSIDE_WINDOW`; новый файл обращается к константе, и ни
    один столбец литералов `parametrize`, ни литеральный кортеж цикла `for`
    не равен по составу значению константы или `OUTSIDE_WINDOW` на текущем
    `config`.

    Ловит мутацию: свод переписал перебор окна в
    `@pytest.mark.parametrize("state", ["queued", …])` литералами текущего
    набора — столбец совпал с константой, тест краснеет.
    """
    tree = _new_tree()
    states = _window_states()
    outside = tuple(s for s in ("done", "killed", "escalated") if s not in states)
    names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert "NOTE_SILENCE_WINDOW_STATES" in names, (
        f"{_plan.NEW_FILE} не обращается к config.NOTE_SILENCE_WINDOW_STATES")
    columns = _plan.parametrize_columns(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.For) and isinstance(node.iter, (ast.List, ast.Tuple)):
            try:
                columns.append(list(ast.literal_eval(node.iter)))
            except ValueError:
                pass
    frozen = [col for col in columns
              if all(isinstance(v, str) for v in col)
              and (set(col) == set(states) or (outside and set(col) == set(outside)))]
    assert not frozen, f"перебор константы заморожен литералами: {frozen}"


# ------------------------------------------------------------------ AC-4

def test_ac4_assertion_literals_carried_verbatim():
    """Литералы утверждений исходных тестов есть в новом файле дословно.

    Каждый строковый и числовой литерал смысловых аргументов `self.assert*`
    четырёх исходных файлов (без аргумента msg) встречается литералом в
    новом файле вне докстрингов.

    Ловит мутацию: при переносе ожидание `"22.09"` переписано как
    `"22.9"` или укорочено до части текста — исходного литерала в новом
    файле нет, тест краснеет с ним.
    """
    new_lits = _plan.non_docstring_constants(_new_tree())
    missing = set()
    for tree in _base_trees():
        missing |= {lit for lit in _plan.assertion_literals(tree)
                    if lit not in new_lits}
    assert not missing, ("литералы утверждений исходных тестов не найдены в "
                         "новом файле:\n" + "\n".join(sorted(map(repr, missing))))


def test_ac4_equality_not_weakened_to_membership_or_inequality():
    """Равенство не заменено вхождением, точное число — неравенством.

    Литерал, который исходные файлы сравнивали `assertEqual` (и никогда —
    `assertIn`/`assertNotIn`), в новом файле не стоит только в сравнениях
    `in`/`not in`; числовой литерал `assertEqual` не стоит только в
    сравнениях `<`, `<=`, `>`, `>=`: если он есть в таком сравнении, он
    есть и в сравнении `==`/`!=`/`is`.

    Ловит мутацию: `assertEqual(row, "| П2 | … |")` перенесён как
    `assert "| П2 |" in row`… с тем же литералом, или `assertEqual(len(x),
    2)` — как `assert len(x) >= 2`, — тест краснеет с литералом.
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


# ------------------------------------------------------------------ AC-5

def test_ac5_every_test_function_declares_mutation():
    """У каждой тестовой функции нового файла есть строка «Ловит мутацию:».

    Ловит мутацию: свод перенёс один из 26 тестов `tests/test_notes.py`
    без заявки (докстринг без строки «Ловит мутацию:») — функция
    перечислена, тест краснеет.
    """
    tests = _plan.module_tests(_new_tree())
    assert tests, f"в {_plan.NEW_FILE} нет тестовых функций"
    without = [f.name for f in tests
               if "Ловит мутацию:" not in (ast.get_docstring(f) or "")]
    assert not without, "функции без «Ловит мутацию:»:\n" + "\n".join(without)


# ------------------------------------------------------------------ AC-10

def test_ac10_no_skip_or_xfail_in_new_file():
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
def test_ac10_limits_not_raised_against_source_files(name):
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
