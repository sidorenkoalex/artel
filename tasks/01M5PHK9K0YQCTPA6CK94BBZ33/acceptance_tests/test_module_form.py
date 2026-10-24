"""AC-8, AC-10, AC-11, AC-12, AC-17: форма сводного
`tests/test_outcome_gate_module.py` (и `tests/outcome_gate_sandbox.py`) против
трёх исходных файлов волны в базе ветки.

Группа: разовый
Красен до реализации: tests/test_outcome_gate_module.py и tests/outcome_gate_sandbox.py на ветке ещё нет — свод не сделан, чтение файла из HEAD даёт None.

Новые файлы читаются из HEAD рабочей копии (`git show HEAD:…`), исходные —
из базы ветки (`_pult.DIFF_BASE`): после свода их на ветке нет. Сравнение
статическое (ast): тест не исполняет ни новые, ни исходные тесты; состав
классов `tests/sandbox.py` берётся импортом в отдельном интерпретаторе
рабочей копии. Утверждения песочниц переносятся дословно в
`tests/outcome_gate_sandbox.py` и в класс `IdOutcomeGateSandbox`, поэтому
литералы и сравнения ищутся в обоих новых файлах.
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
# `skip`/`skipif` — и поле кода пульта (`project_profile.decide(...).skip`):
# пропуском теста считается только обращение через `pytest`/`mark`/`unittest`.
_AMBIGUOUS_SKIP = {"skip", "skipif"}
_SKIP_OWNERS = {"pytest", "mark", "unittest"}
_LIMIT_KWARGS = ("timeout", "delta", "places", "rel", "abs")
_ASSERTING = {"in_dev_task", "artel_in_dev_task", "operator_mandate",
              "refusal", "no_gate_refusal", "gate_refusal", "assert_no_gate",
              "assert_prepare", "id_no_gate_refusal"}


def _new_tree() -> ast.Module:
    text = _plan.show(CODE_ROOT, "HEAD", _plan.NEW_FILE)
    assert text is not None, f"{_plan.NEW_FILE} нет в HEAD ветки"
    return ast.parse(text)


def _sandbox_tree() -> ast.Module:
    text = _plan.show(CODE_ROOT, "HEAD", _plan.SANDBOX_FILE)
    assert text is not None, f"{_plan.SANDBOX_FILE} нет в HEAD ветки"
    return ast.parse(text)


def _base_trees() -> list:
    assert DIFF_BASE, "база диффа ветки задачи не определена при выкладке"
    trees = []
    for path in _plan.SOURCE_FILES:
        text = _plan.show(CODE_ROOT, DIFF_BASE, path)
        assert text is not None, f"{path} нет в базе ветки {DIFF_BASE}"
        trees.append(ast.parse(text))
    return trees


def _sandbox_testcase_names() -> set:
    res = subprocess.run(
        [sys.executable, "-c",
         "import unittest, tests.sandbox as s; print(repr(sorted("
         "n for n, v in vars(s).items() if isinstance(v, type) "
         "and issubclass(v, unittest.TestCase))))"],
        cwd=CODE_ROOT, capture_output=True, text=True, timeout=120)
    assert res.returncode == 0, f"импорт tests.sandbox не прошёл: {res.stderr}"
    return set(ast.literal_eval(res.stdout.strip()))


def _functions(tree) -> list:
    return [n for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _assertion_sites(func) -> list:
    """Строки утверждений в теле: `assert`, `pytest.raises`, `pytest.fail`,
    `<что-то>.assert*`."""
    found = []
    for sub in ast.walk(func):
        if isinstance(sub, ast.Assert):
            found.append(sub.lineno)
        elif isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) \
                and (sub.func.attr in ("fail", "raises")
                     or sub.func.attr.startswith("assert")):
            found.append(sub.lineno)
    return found


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


def _string_sets_of_constants(tree) -> dict:
    """{имя константы модуля: множество строк} для кортежей/списков строк
    (в том числе из имён строковых констант) и ключей словарей-литералов."""
    strings, found = {}, {}
    for node in tree.body:
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)):
            continue
        name, value = node.targets[0].id, node.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            strings[name] = value.value
        elif isinstance(value, (ast.Tuple, ast.List)):
            items = []
            for elt in value.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                    items.append(elt.value)
                elif isinstance(elt, ast.Name) and elt.id in strings:
                    items.append(strings[elt.id])
                else:
                    items = None
                    break
            if items:
                found[name] = set(items)
        elif isinstance(value, ast.Dict) and value.keys and all(
                isinstance(k, ast.Constant) and isinstance(k.value, str)
                for k in value.keys):
            found[name] = {k.value for k in value.keys}
    return found


# ------------------------------------------------------------------ AC-8

def test_ac8_tests_are_module_functions_without_test_classes_or_subtest():
    """Тесты нового файла — функции модуля: нет тестовых классов и `subTest`.

    В файле есть тестовые функции первого уровня модуля; ни один класс не
    несёт методов `test_*`; обращений `subTest` нет.

    Ловит мутацию: свод оставил `class Ac4PrepareTest(OutcomeGateSandbox)`
    с методами `test_…` или `with self.subTest(case=label, …)` в теле —
    класс/обращение найдено, тест краснеет с его именем.
    """
    tree = _new_tree()
    assert _plan.module_tests(tree), f"в {_plan.NEW_FILE} нет тестовых функций"
    problems = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            methods = [i.name for i in node.body
                       if isinstance(i, (ast.FunctionDef, ast.AsyncFunctionDef))
                       and i.name.startswith("test")]
            if methods:
                problems.append(f"класс {node.name} с тестовыми методами {methods}")
    problems += [f"subTest в строке {n.lineno}" for n in ast.walk(tree)
                 if isinstance(n, ast.Attribute) and n.attr == "subTest"]
    assert not problems, "\n".join(problems)


def test_ac8_only_testcase_subclass_is_id_sandbox():
    """Единственный наследник `unittest.TestCase` в файле — `IdOutcomeGateSandbox`.

    Наследование прослеживается через `TestCase`, классы
    `tests/sandbox.py`, `OutcomeGateSandbox` и классы самого файла; таких
    классов в файле ровно один — `IdOutcomeGateSandbox`.

    Ловит мутацию: свод завёл `class OutcomeBox(OutcomeGateSandbox)` с
    переопределением для одного сценария — второй наследник найден, тест
    краснеет с его именем.
    """
    tree = _new_tree()
    testcase = {"TestCase", "OutcomeGateSandbox"} | _sandbox_testcase_names()
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    derived = set()
    changed = True
    while changed:
        changed = False
        for node in classes:
            if node.name in derived:
                continue
            bases = {ast.unparse(b).rsplit(".", 1)[-1] for b in node.bases}
            if bases & (testcase | derived):
                derived.add(node.name)
                changed = True
    assert derived == {"IdOutcomeGateSandbox"}, (
        f"наследники unittest.TestCase в {_plan.NEW_FILE}: {sorted(derived)}")


def test_ac8_fixtures_hold_no_assertions_and_call_no_asserting_methods():
    """Фикстуры не содержат утверждений и не зовут методов с утверждениями.

    Ни одна функция с декоратором `pytest.fixture` не содержит `assert`,
    `pytest.raises`/`fail`, `<что-то>.assert*` и не вызывает (методом или
    голым именем) `in_dev_task`, `artel_in_dev_task`, `operator_mandate`,
    `refusal`, `no_gate_refusal`, `gate_refusal`, `assert_no_gate`,
    `assert_prepare`, `id_no_gate_refusal`.

    Ловит мутацию: фикстура стенда AC-11 сразу зовёт
    `box.operator_mandate(...)` (утверждение подготовки уходит в setup) —
    вызов найден, тест краснеет с именем фикстуры.
    """
    tree = _new_tree()
    problems = []
    for func in _functions(tree):
        if not _plan.is_fixture(func):
            continue
        problems += [f"фикстура {func.name}: утверждение в строке {line}"
                     for line in _assertion_sites(func)]
        for sub in ast.walk(func):
            if not isinstance(sub, ast.Call):
                continue
            called = sub.func.attr if isinstance(sub.func, ast.Attribute) else \
                getattr(sub.func, "id", None)
            if called in _ASSERTING:
                problems.append(f"фикстура {func.name}: вызов {called} в строке "
                                f"{sub.lineno}")
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-10

def test_ac10_assertion_literals_carried_verbatim():
    """Литералы утверждений исходных тестов есть в новых файлах дословно.

    Каждый строковый и числовой литерал смысловых аргументов `self.assert*`
    трёх исходных файлов (без аргумента msg) встречается литералом вне
    докстрингов в `tests/test_outcome_gate_module.py` или
    `tests/outcome_gate_sandbox.py`.

    Ловит мутацию: при переносе ожидание `"verifying"` переписано как
    `"verify"` или `["base", "head"]` — как `["head", "base"]` с потерей
    литерала… — исходного литерала в новых файлах нет, тест краснеет с ним.
    """
    new_lits = _plan.non_docstring_constants(_new_tree()) | \
        _plan.non_docstring_constants(_sandbox_tree())
    missing = set()
    for tree in _base_trees():
        missing |= {lit for lit in _plan.assertion_literals(tree)
                    if lit not in new_lits}
    assert not missing, ("литералы утверждений исходных тестов не найдены в "
                         "новых файлах:\n" + "\n".join(sorted(map(repr, missing))))


def test_ac10_assertion_constants_stay_constants():
    """Константы, с которыми сравнивали исходные утверждения, остались константами.

    Каждое имя константы модуля (`ВЕРХНИЙ_РЕГИСТР`) в смысловых аргументах
    `self.assert*` исходных файлов встречается именем (`Name`) в новых
    файлах — под своим именем или под именем после переименования
    (`GATE_ACTIONS` → `ID_GATE_ACTIONS`, `VITEST_KIND` → `ID_VITEST_KIND`).

    Ловит мутацию: `self.assertTrue(self.details(rows, PASSED_NOTE))`
    перенесён как `assert details(rows, "приёмочные тесты пройдены")` —
    имени `PASSED_NOTE` в новых файлах нет, тест краснеет с ним.
    """
    names = {n.id for tree in (_new_tree(), _sandbox_tree())
             for n in ast.walk(tree) if isinstance(n, ast.Name)}
    missing = set()
    for tree in _base_trees():
        for const in _plan.assertion_constant_names(tree):
            if const not in names and _plan.RENAMES.get(const) not in names:
                missing.add(const)
    assert not missing, ("константы утверждений исходных тестов не найдены "
                         "именем в новых файлах: " + ", ".join(sorted(missing)))


def test_ac10_equality_not_weakened_to_membership_or_inequality():
    """Равенство не заменено вхождением, точное число — неравенством.

    Литерал, который исходные файлы сравнивали `assertEqual` (и никогда —
    `assertIn`/`assertNotIn`), в новых файлах не стоит только в сравнениях
    `in`/`not in`; числовой литерал `assertEqual` не стоит только в
    сравнениях `<`, `<=`, `>`, `>=`: если он есть в таком сравнении, он
    есть и в сравнении `==`/`!=`/`is` или в `<стенд>.assertEqual`.

    Ловит мутацию: `assertEqual(self.state(t), "in_dev", …)` перенесён как
    `assert "in_dev" in box.state(t)`, или `assertEqual(len(calls), 2)` —
    как `assert len(calls) >= 2`, — тест краснеет с литералом.
    """
    equal, member = set(), set()
    for tree in _base_trees():
        eq, mem = _plan.equality_literals(tree)
        equal |= eq
        member |= mem
    compared = _plan.compare_operands(_new_tree()) + \
        _plan.compare_operands(_sandbox_tree())
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


def test_ac10_each_transferred_test_keeps_its_equality_literals():
    """Перенесённый тест сохраняет литералы своих сравнений на равенство и вхождение.

    Для каждого теста исходных файлов, у которого в новом файле есть
    функция того же имени (или имени с суффиксом): литералы смысловых
    аргументов его `assertEqual`/`assert*Equal` стоят в этой функции в
    сравнении `==`/`!=`/`is` или в `<стенд>.assertEqual`; литералы его
    `assertIn`/`assertNotIn` — в сравнении `in`/`not in` или на
    равенство. Тест без функции в новом файле — предмет AC-13.

    Ловит мутацию: в `test_ac3_full_suite_on_base_and_head_checkouts_fresh`
    оба `assertEqual(…, ["base", "head"], …)` перенесены как
    `assert "base" in …` — литерал `"head"` в равенствах этой функции
    пропал (хотя в файле он есть в других тестах), тест краснеет с именем
    функции.
    """
    new = _plan.module_functions(_new_tree())
    problems = []
    for tree in _base_trees():
        for cls in tree.body:
            if not isinstance(cls, ast.ClassDef):
                continue
            for method in cls.body:
                if not (isinstance(method, ast.FunctionDef)
                        and method.name.startswith("test")):
                    continue
                matches = [f for name, f in new.items()
                           if name == method.name or name.startswith(method.name + "_")]
                if not matches:
                    continue
                equal, member = _plan.equality_literals(method)
                compared = [pair for f in matches
                            for pair in _plan.compare_operands(f)]
                eq_lits = set().union(*[l for k, l in compared if k == "eq"] or [set()])
                in_lits = set().union(*[l for k, l in compared if k == "in"] or [set()])
                lost_eq = sorted(map(repr, equal - eq_lits))
                lost_in = sorted(map(repr, member - eq_lits - in_lits))
                if lost_eq or lost_in:
                    problems.append(f"{cls.name}::{method.name}: равенства без "
                                    f"{lost_eq}, вхождения без {lost_in}")
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-11

def test_ac11_raises_match_escaped_and_only_at_text_check_sites():
    """`pytest.raises(..., match=…)` — всегда `re.escape(...)` и не чаще проверок текста.

    Каждый `pytest.raises` с `match` передаёт `re.escape(...)`. Число
    `pytest.raises` с `match` не больше числа мест исходных файлов, где
    проверялся текст исключения (`assertRaises(...) as x` с чтением
    `x.exception`, `assertRaisesRegex`): голый `assertRaises(E)` переходит
    в `pytest.raises(E)` без `match`.

    Ловит мутацию: свод дописал `match="…"` сырым регулярным выражением
    (без `re.escape`) или добавил `match` на месте голого `assertRaises` —
    тест краснеет со строкой/числами.
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


def test_ac11_bare_literal_loop_only_with_shared_state():
    """Голый цикл по литеральному набору — только в тесте с общим состоянием.

    Тестовая функция без фикстур (все её параметры — имена `parametrize`)
    общего состояния между итерациями не держит; в ней нет цикла `for` по
    литеральному списку/кортежу/множеству — такой перебор задаётся
    `parametrize`. Тесты на стенде (параметр-фикстура) цикл сохраняют
    законно.

    Ловит мутацию: `test_red_on_branch_kinds` (`tests/test_outcome_integrity.py`,
    `subTest` без песочницы) перенесён прежним `for case, red in ((…),
    …)` в теле функции — цикл найден, тест краснеет с именем функции.
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


def test_ac11_code_constant_iteration_not_frozen_into_literals():
    """Перебор по константе кода не заморожен литералами.

    Ни один столбец литералов `parametrize` и ни один литеральный набор
    цикла `for` в новом файле не равен по составу строковому набору
    константы модуля песочницы или самого файла (кортеж строк — в том
    числе `GATE_ACTIONS`/`ID_GATE_ACTIONS` из строковых констант — или
    ключи словаря-литерала вроде `VITEST_KIND`).

    Ловит мутацию: перебор действий гейта переписан в
    `@pytest.mark.parametrize("action", ["переход отклонён: …", …])`
    литералами текущего `GATE_ACTIONS` — столбец совпал с константой,
    тест краснеет.
    """
    tree = _new_tree()
    sets = _string_sets_of_constants(_sandbox_tree())
    sets.update(_string_sets_of_constants(tree))
    columns = _plan.parametrize_columns(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.For) and isinstance(node.iter, (ast.List, ast.Tuple)):
            try:
                columns.append(list(ast.literal_eval(node.iter)))
            except (ValueError, TypeError, SyntaxError):
                pass
    frozen = [(name, col) for col in columns
              if col and all(isinstance(v, str) for v in col)
              for name, values in sets.items()
              if len(values) > 1 and set(col) == values]
    assert not frozen, f"перебор константы заморожен литералами: {frozen}"


def test_ac11_random_choice_not_moved_into_parametrize():
    """Случайный выбор не вынесен в `parametrize`: аргументы декоратора не зовут `random`/`rng`.

    Ловит мутацию: случайные имена тестов песочницы вынесены в
    `@pytest.mark.parametrize("name", [rng.choice(…) …])` при сборе — имя
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


def test_ac11_message_is_second_operand_of_assert_in_tests():
    """В тестовых функциях сообщение — второй операнд `assert`, а не `msg` метода.

    В функциях `test_*` нет вызовов `<что-то>.assert*(…)` (кроме
    `assertRaises*`); каждый вызов `explain(…)` в них стоит внутри
    сообщения (`msg`) оператора `assert`; хотя бы один `assert` тестовых
    функций несёт сообщение с `explain(…)`.

    Ловит мутацию: свод перенёс `self.assertEqual(self.state(t),
    "verifying", self.explain(rows, output))` как
    `box.assertEqual(box.state(t), "verifying", box.explain(rows, output))`
    или как `assert box.state(t) == "verifying"` с потерей пояснения —
    вызов метода найден или `explain` вне `msg`, тест краснеет со строкой.
    """
    tree = _new_tree()
    problems, with_explain = [], 0
    for func in _plan.module_tests(tree):
        in_msg = set()
        for sub in ast.walk(func):
            if isinstance(sub, ast.Assert) and sub.msg is not None:
                ids = {id(n) for n in ast.walk(sub.msg)}
                in_msg |= ids
                if any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                       and n.func.attr == "explain" for n in ast.walk(sub.msg)):
                    with_explain += 1
        for sub in ast.walk(func):
            if _plan.is_method_assert(sub):
                problems.append(f"{func.name}: {ast.unparse(sub.func)}(…) в "
                                f"строке {sub.lineno}")
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) \
                    and sub.func.attr == "explain" and id(sub) not in in_msg:
                problems.append(f"{func.name}: explain(…) вне msg assert в "
                                f"строке {sub.lineno}")
    assert not problems, "\n".join(problems)
    assert with_explain, "ни один assert тестовых функций не несёт explain(…)"


# ------------------------------------------------------------------ AC-12

def test_ac12_every_test_function_declares_mutation():
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


# ------------------------------------------------------------------ AC-17

@pytest.mark.parametrize("path", [_plan.NEW_FILE, _plan.SANDBOX_FILE])
def test_ac17_no_skip_or_xfail_in_new_files(path):
    """В новых файлах нет `skip`/`xfail` ни в каком виде.

    Ни обращений `pytest.mark.skip`/`skipif`/`xfail`, `pytest.skip`,
    `unittest.skip*`, `skipTest`, `importorskip`, ни импорта этих имён.

    Ловит мутацию: неперенесённый тест помечен
    `@pytest.mark.skip(reason="…")` или `pytest.xfail(...)` — имя найдено,
    тест краснеет со строкой.
    """
    text = _plan.show(CODE_ROOT, "HEAD", path)
    assert text is not None, f"{path} нет в HEAD ветки"
    tree = ast.parse(text)
    found = [f"{ast.unparse(n)} в строке {n.lineno}" for n in ast.walk(tree)
             if isinstance(n, ast.Attribute) and n.attr in _SKIP_NAMES
             and (n.attr not in _AMBIGUOUS_SKIP
                  or ast.unparse(n.value).rsplit(".", 1)[-1] in _SKIP_OWNERS)]
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            found += [f"импорт {a.name}" for a in node.names if a.name in _SKIP_NAMES]
    assert not found, f"skip/xfail в {path}:\n" + "\n".join(found)


@pytest.mark.parametrize("name", list(_LIMIT_KWARGS))
def test_ac17_limits_not_raised_against_source_files(name):
    """Пределы (`timeout`, допуски `delta`/`places`/`rel`/`abs`) не подняты.

    Каждое числовое значение предела `name` в двух новых файлах не больше
    наибольшего значения того же предела в исходных файлах; предела,
    которого в исходных файлах не было, в новых файлах нет;
    `pytest.approx` есть, только если он был в исходных файлах.

    Ловит мутацию: свод добавил `@pytest.mark.timeout(600)` долгому тесту
    AC-7 или `pytest.approx(..., rel=0.1)` вместо точного сравнения —
    значение выше исходного (или новое), тест краснеет с ним.
    """
    base = {}
    base_approx = False
    for tree in _base_trees():
        for key, values in _limits(tree).items():
            base.setdefault(key, []).extend(values)
        base_approx |= any(isinstance(n, ast.Attribute) and n.attr == "approx"
                           for n in ast.walk(tree))
    new = []
    approx = []
    for tree in (_new_tree(), _sandbox_tree()):
        new += _limits(tree).get(name, [])
        approx += [n.lineno for n in ast.walk(tree)
                   if isinstance(n, ast.Attribute) and n.attr == "approx"]
    ceiling = max(base.get(name, []), default=None)
    raised = [v for v in new if ceiling is None or v > ceiling]
    assert not raised, (f"предел {name}: значения {raised} при исходном "
                        f"наибольшем {ceiling}")
    if not base_approx:
        assert not approx, f"pytest.approx в строках {approx}, в исходных его не было"
