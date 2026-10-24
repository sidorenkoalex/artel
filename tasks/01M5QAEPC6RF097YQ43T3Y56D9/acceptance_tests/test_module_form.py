"""AC-6, AC-7, AC-8, AC-9, AC-10, AC-11, AC-14: форма сводного
`tests/test_outcome_gate_module.py` против исходного
`tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py`, модуля и песочницы
`tests/outcome_gate_sandbox.py` в базе ветки.

Группа: разовый
Красен до реализации: в tests/test_outcome_gate_module.py на ветке нет ни фикстуры box, ни функций refusal/assert_prepare/…, ни перенесённых 42 тестов — свод не сделан.

Модуль читается из HEAD рабочей копии (`git show HEAD:…`), исходный файл,
модуль и песочница на базе — из базы ветки (`_pult.DIFF_BASE`): исходного
файла на ветке после свода нет. Сравнение статическое (ast): тест не
исполняет ни новые, ни исходные тесты.

Сверка тела помощника (AC-8) — каноничный `ast.dump` без докстринга:
`self` → имя первого параметра функции; `self.<помощник>(…)` →
`<функция>(<стенд>, …)`; у помощника исхода — `case + <текст>` на месте
каждого текста сообщения `<стенд>.assert*` (позиционного после смысловых
аргументов или `msg=`) и `case=case` во вложенном вызове помощника исхода
(решение Оператора ANSWER-1, п. 1); цепочки `+` сравниваются без учёта
скобок. Тест, перенесённый из исходного файла, сопоставляется функции
модуля по имени (то же имя или имя с суффиксом `_…`) и по строкам
соответствия «до → после» PLAN (докстринг `_plan.py`).
"""
import ast
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _plan  # noqa: E402
from _pult import CODE_ROOT, DIFF_BASE, artifact_text  # noqa: E402

_SKIP_NAMES = {"skip", "skipif", "xfail", "skipTest", "importorskip",
               "skipIf", "skipUnless", "expectedFailure"}
# `skip`/`skipif` — и поле кода пульта (`project_profile.decide(...).skip`):
# пропуском теста считается только обращение через `pytest`/`mark`/`unittest`.
_AMBIGUOUS_SKIP = {"skip", "skipif"}
_SKIP_OWNERS = {"pytest", "mark", "unittest"}
_LIMITS = ("timeout", "delta", "places", "rel", "abs", "full_suite_timeout_sec")
_SEED = ", зерно {box.seed}"


def _new_tree() -> ast.Module:
    text = _plan.show(CODE_ROOT, "HEAD", _plan.NEW_FILE)
    assert text is not None, f"{_plan.NEW_FILE} нет в HEAD ветки"
    return ast.parse(text)


def _base_tree(path: str) -> ast.Module:
    assert DIFF_BASE, "база диффа ветки задачи не определена при выкладке"
    text = _plan.show(CODE_ROOT, DIFF_BASE, path)
    assert text is not None, f"{path} нет в базе ветки {DIFF_BASE}"
    return ast.parse(text)


def _source_tree() -> ast.Module:
    return _base_tree(_plan.OUTCOME_FILE)


def _bindings(tree) -> dict:
    """{имя: [утверждения верхнего уровня, связывающие его]}."""
    found = {}
    for node in tree.body:
        for name in _plan.bound_names(node):
            found.setdefault(name, []).append(node)
    return found


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


def _called(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return getattr(call.func, "id", None)


def _source_methods() -> list:
    """[(класс, метод)] тестов исходного файла базы."""
    return [(t.cls, t.func) for t in
            _plan.base_tests(_plan.OUTCOME_FILE,
                             _plan.show(CODE_ROOT, DIFF_BASE, _plan.OUTCOME_FILE))]


def _plan_or_empty() -> str:
    try:
        return artifact_text("PLAN.md") or ""
    except Exception:  # noqa: BLE001 — нет PLAN: сопоставление только по имени
        return ""


def _removed_keys(plan: str) -> set:
    removed = set()
    for text in _plan.sections(plan, "дубл"):
        for line in _plan.prose_lines(text):
            removed |= _plan.test_keys(line)
    return removed


def _matches(new: dict, cls: str, method: str, mapping: dict) -> list:
    """Функции модуля, в которые перенесён `cls::method`."""
    names = {n for n in new if n == method or n.startswith(method + "_")}
    names |= mapping.get(f"{cls}::{method}", set()) & set(new)
    return [new[n] for n in sorted(names)]


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


def _raises_counts(tree) -> tuple[int, int]:
    """(все `pytest.raises`, `pytest.raises` с `match`)."""
    calls = [n for n in ast.walk(tree) if _plan.is_pytest_raises(n)]
    return len(calls), sum(1 for n in calls
                           if any(kw.arg == "match" for kw in n.keywords))


# ------------------------------------------------------------- subTest

def _template(node) -> str | None:
    """Текст f-строки с подстановками `{выражение}`; иначе None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if not isinstance(node, ast.JoinedStr):
        return None
    parts = []
    for value in node.values:
        if isinstance(value, ast.Constant):
            parts.append(str(value.value))
        elif isinstance(value, ast.FormattedValue):
            parts.append("{" + ast.unparse(value.value) + "}")
    return "".join(parts)


def _wanted_case(label) -> set:
    """Допустимые тексты `case=f"{<ярлык>}, зерно {box.seed}"`."""
    wanted = {"{" + ast.unparse(label) + "}" + _SEED}
    if isinstance(label, ast.Constant) and isinstance(label.value, str):
        wanted.add(label.value + _SEED)
    return wanted


def _subtest_label(call: ast.Call):
    labels = [kw.value for kw in call.keywords if kw.arg != "seed"]
    return labels[0] if labels else None


def _is_subtest(item) -> bool:
    return isinstance(item.context_expr, ast.Call) and \
        isinstance(item.context_expr.func, ast.Attribute) and \
        item.context_expr.func.attr == "subTest"


def _source_counts(method) -> dict:
    """Счёт исходного теста: {"labels": [ярлыки subTest], "asserts_in",
    "asserts_out", "helpers_in": {помощник: n}, "helpers_out": {…}} —
    прямые `self.assert*` и вызовы помощников исхода внутри тел `subTest`
    и вне их."""
    counts = {"labels": [], "asserts_in": 0, "asserts_out": 0,
              "helpers_in": {}, "helpers_out": {}}
    inside = set()
    for node in ast.walk(method):
        if isinstance(node, ast.With):
            for item in node.items:
                if _is_subtest(item):
                    counts["labels"].append(_subtest_label(item.context_expr))
                    for stmt in node.body:
                        inside |= {id(n) for n in ast.walk(stmt)}
    for node in ast.walk(method):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        where = "in" if id(node) in inside else "out"
        attr = node.func.attr
        if attr in _plan.OUTCOME_HELPERS:
            bucket = counts[f"helpers_{where}"]
            bucket[attr] = bucket.get(attr, 0) + 1
        elif attr.startswith("assert") and not attr.startswith("assertRaises") \
                and attr not in _plan.HELPERS:
            counts[f"asserts_{where}"] += 1
    return counts


def _tagged_names(func, is_tagged) -> set:
    """Локальные имена функции, связанные с выражением, которое
    `is_tagged` признаёт (замыкание по присваиваниям)."""
    tagged, changed = set(), True
    assigns = [n for n in ast.walk(func) if isinstance(n, ast.Assign)]
    while changed:
        changed = False
        for node in assigns:
            if not is_tagged(node.value, tagged):
                continue
            for target in node.targets:
                for name in ast.walk(target):
                    if isinstance(name, ast.Name) and name.id not in tagged:
                        tagged.add(name.id)
                        changed = True
    return tagged


def _carries(node, labels: list, names: set) -> bool:
    """Выражение несёт ярлык одного из подслучаев и зерно (`….seed`) —
    прямо или через имя из `names`."""
    subs = list(ast.walk(node))
    if any(isinstance(n, ast.Name) and n.id in names for n in subs):
        return True
    seed = any(isinstance(n, ast.Attribute) and n.attr == "seed" for n in subs)
    dumps = {ast.dump(n) for n in subs}
    texts = [_template(n) or "" for n in subs]
    for label in labels:
        if label is None:
            continue
        if ast.dump(label) in dumps:
            return seed
        if isinstance(label, ast.Constant) and isinstance(label.value, str) \
                and any(label.value in t for t in texts):
            return seed
    return False


# ------------------------------------------------------------------ AC-6

def test_ac6_no_test_classes_subtest_or_unittest_main():
    """В модуле нет тестовых классов, обращений `subTest` и вызова `unittest.main()`.

    Ни один класс модуля не несёт методов `test_*`; атрибута `subTest` в
    файле нет; вызова `unittest.main(…)` нет; тестовые функции первого
    уровня есть.

    Ловит мутацию: свод оставил `class Ac4PrepareTest(OutcomeGateSandbox)`
    с методами `test_…`, `with box.subTest(case=label, seed=box.seed)` в
    теле или перенёс хвост `if __name__ == "__main__": unittest.main()` —
    класс/обращение найдено, тест краснеет с ним.
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
        if isinstance(node, ast.Attribute) and node.attr == "subTest":
            problems.append(f"subTest в строке {node.lineno}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "main" \
                and ast.unparse(node.func.value) == "unittest":
            problems.append(f"unittest.main() в строке {node.lineno}")
    assert not problems, "\n".join(problems)


def test_ac6_names_of_base_module_not_reimported():
    """Имя, определённое или импортированное в модуле на базе, связано на HEAD столько же раз, сколько на базе.

    Для каждого имени верхнего уровня модуля на базе (импорты, константы,
    функции, классы) число связываний верхнего уровня на HEAD равно числу
    на базе: повторный импорт (`OUTCOME_ACTION`, `ulid`, `flow`,
    `arg_value`, `js_source`, `os`, `Path`, …) добавил бы связывание.

    Ловит мутацию: свод перенёс импорт исходного файла целиком —
    `from tests.outcome_gate_sandbox import (Path, …, OUTCOME_ACTION, ulid,
    js_source, …)` — имена базы связаны дважды, тест краснеет с ними.
    """
    base = _bindings(_base_tree(_plan.NEW_FILE))
    head = _bindings(_new_tree())
    twice = sorted(f"{name}: {len(head.get(name, []))} вместо {len(nodes)}"
                   for name, nodes in base.items()
                   if len(head.get(name, [])) > len(nodes))
    assert not twice, "имена базы связаны повторно:\n" + "\n".join(twice)


@pytest.mark.parametrize("name", ["OutcomeGateSandbox", "GATE_ACTIONS"])
def test_ac6_name_imported_from_sandbox_module(name):
    """`OutcomeGateSandbox` и `GATE_ACTIONS` импортируются из `tests.outcome_gate_sandbox`.

    На HEAD среди инструкций верхнего уровня есть `from
    tests.outcome_gate_sandbox import …` с именем `name` без
    переименования.

    Ловит мутацию: свод скопировал `GATE_ACTIONS = (…)` литералом в модуль
    (или взял его из модуля `tests.test_01m5cjvb…`) вместо импорта из
    песочницы — импорта имени нет, тест краснеет с ним.
    """
    found = [a for n in _new_tree().body
             if isinstance(n, ast.ImportFrom) and n.module == _plan.SANDBOX_MODULE
             for a in n.names if a.name == name and a.asname in (None, name)]
    assert found, f"{name} не импортирован из {_plan.SANDBOX_MODULE}"


def test_ac6_module_docstring_extended():
    """Докстринг модуля дополнен: текст базы сохранён, добавлен рассказ о переносе исходного файла.

    Докстринг модуля на HEAD (с точностью до пробелов и переносов строк)
    содержит докстринг базы целиком, длиннее его и называет исходный файл
    `test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate`.

    Ловит мутацию: свод оставил докстринг модуля как был (или заменил его
    новым текстом, выбросив абзац волны 2а-1а) — добавки нет или текст
    базы не найден, тест краснеет.
    """
    base = " ".join((ast.get_docstring(_base_tree(_plan.NEW_FILE)) or "").split())
    head = " ".join((ast.get_docstring(_new_tree()) or "").split())
    assert base, "у модуля на базе нет докстринга"
    assert base in head, "докстринг модуля базы не сохранён на HEAD"
    assert len(head) > len(base), "докстринг модуля не дополнен"
    assert "test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate" in head, (
        "дополнение докстринга не называет исходный файл")


def test_ac6_id_names_and_wave_2a1a_tests_unchanged():
    """Имена `id_`/`ID_` и 11 тестов волны 2а-1а — на HEAD теми же определениями.

    Каждое определение верхнего уровня модуля на базе, имя которого
    начинается с `id_`/`ID_`, и каждая из его тестовых функций на HEAD
    связаны ровно одним определением с тем же `ast.dump`.

    Ловит мутацию: под общий помощник `refusal(box, …)` переписан
    `gate_refusal`-тест волны 2а-1а или `id_no_gate_refusal` получил
    параметр `case` — дамп расходится, тест краснеет с именем.
    """
    base = _base_tree(_plan.NEW_FILE)
    tests = _plan.module_tests(base)
    assert len(tests) == _plan.BASE_MODULE_TESTS, (
        f"тестов модуля на базе {len(tests)}, критерий называет "
        f"{_plan.BASE_MODULE_TESTS} — база прочитана не та")
    keep = [n for n in base.body if any(
        name.startswith(("id_", "ID_")) for name in _plan.bound_names(n))
        and not isinstance(n, (ast.Import, ast.ImportFrom))] + tests
    head = _bindings(_new_tree())
    problems = []
    for node in keep:
        name = _plan.bound_names(node)[0]
        found = head.get(name, [])
        if len(found) != 1:
            problems.append(f"{name}: определений на HEAD {len(found)}, ожидалось 1")
        elif ast.dump(found[0]) != ast.dump(node):
            problems.append(f"{name}: определение изменено")
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-7

def test_ac7_box_fixture_only_creates_outcome_sandbox():
    """Фикстура `box` только создаёт песочницу `_sandbox(OutcomeGateSandbox)`.

    В модуле есть функция `box` с декоратором `pytest.fixture`;
    единственный вызов в её теле — `_sandbox(OutcomeGateSandbox)`;
    утверждений (`assert`, `pytest.raises`/`fail`, `<что-то>.assert*`) в
    ней нет.

    Ловит мутацию: фикстура стенда сразу зовёт `box.in_dev_task(project)`
    или `box.operator_mandate(...)` (утверждение подготовки уходит в
    setup, его падение — «ошибка setup», не убийство) — лишний вызов
    найден, тест краснеет с ним.
    """
    funcs = _plan.module_functions(_new_tree())
    assert "box" in funcs, f"фикстуры box в {_plan.NEW_FILE} нет"
    func = funcs["box"]
    assert _plan.is_fixture(func), "box не помечена pytest.fixture"
    problems = [f"утверждение в строке {line}" for line in _assertion_sites(func)]
    creates = 0
    for sub in ast.walk(ast.Module(body=func.body, type_ignores=[])):
        if not isinstance(sub, ast.Call):
            continue
        args = [ast.unparse(a) for a in sub.args]
        if _called(sub) == "_sandbox" and args == ["OutcomeGateSandbox"] \
                and not sub.keywords:
            creates += 1
        else:
            problems.append(f"вызов {ast.unparse(sub)} в строке {sub.lineno}")
    if creates != 1:
        problems.append(f"вызовов _sandbox(OutcomeGateSandbox): {creates}, "
                        f"ожидался 1")
    assert not problems, "box не только создаёт песочницу:\n" + "\n".join(problems)


def test_ac7_fixtures_hold_no_assertions_and_call_no_asserting_methods():
    """Ни одна фикстура модуля не содержит утверждений и не зовёт методов и помощников с утверждениями.

    Ни одна функция с декоратором `pytest.fixture` не содержит `assert`,
    `pytest.raises`/`fail`, `<что-то>.assert*` и не вызывает (методом или
    голым именем) `in_dev_task`, `artel_in_dev_task`, `operator_mandate`,
    `refusal`, `no_gate_refusal`, `assert_no_gate`, `assert_prepare`.

    Ловит мутацию: свод завёл фикстуру `mandated_box`, которая зовёт
    `box.operator_mandate(...)` для тестов AC-11 — вызов найден, тест
    краснеет с именем фикстуры.
    """
    problems = []
    for func in _functions(_new_tree()):
        if not _plan.is_fixture(func):
            continue
        problems += [f"фикстура {func.name}: утверждение в строке {line}"
                     for line in _assertion_sites(func)]
        problems += [f"фикстура {func.name}: вызов {_called(sub)} в строке "
                     f"{sub.lineno}" for sub in ast.walk(func)
                     if isinstance(sub, ast.Call) and _called(sub) in _plan.ASSERTING]
    assert not problems, "\n".join(problems)


def test_ac7_preparation_methods_called_through_stand():
    """Методы подготовки с утверждениями тесты зовут через стенд, а не функциями модуля.

    В модуле нет функции верхнего уровня `in_dev_task`,
    `artel_in_dev_task` или `operator_mandate`, и ни один вызов этих имён
    не сделан голым именем; вызовы методом стенда есть.

    Ловит мутацию: свод перенёс `operator_mandate` функцией модуля
    `operator_mandate(box, …)` (её утверждения guard стал бы считать
    утверждениями исхода) — функция или вызов голым именем найдены, тест
    краснеет с ними.
    """
    prep = {"in_dev_task", "artel_in_dev_task", "operator_mandate"}
    tree = _new_tree()
    problems = [f"функция модуля {name}" for name in
                sorted(prep & set(_plan.module_functions(tree)))]
    by_attr = 0
    for sub in ast.walk(tree):
        if not isinstance(sub, ast.Call) or _called(sub) not in prep:
            continue
        if isinstance(sub.func, ast.Name):
            problems.append(f"вызов {sub.func.id} голым именем в строке {sub.lineno}")
        else:
            by_attr += 1
    assert not problems, "\n".join(problems)
    assert by_attr, "ни одного вызова метода подготовки через стенд"


# ------------------------------------------------------------------ AC-8

@pytest.mark.parametrize("name", ["refusal", "no_gate_refusal", "assert_no_gate",
                                  "assert_prepare", "prepared", "broken_task"])
def test_ac8_helper_is_module_function_with_verbatim_body(name):
    """Помощник — функция модуля: первый параметр — стенд, тело — исходное по правилу перевода, у помощника исхода — `case`.

    Исходный метод (`OutcomeGateSandbox.refusal`/`no_gate_refusal` в
    песочнице базы, `Ac1OutOfBoundsTest.assert_no_gate`,
    `Ac4PrepareTest.assert_prepare`/`prepared`, `Ac11MandateTest.broken_task`
    исходного файла) переводится правилом докстринга модуля. Функция
    модуля `name` есть; её параметры после стенда — параметры метода после
    `self` (у помощника исхода — и последним `case: str = ""`); каноничный
    дамп тела равен переведённому.

    Ловит мутацию: в `assert_prepare` оставлен `box.refusal(rows, …)`
    вместо `refusal(box, rows, …, case=case)`, у `assert_no_gate` к одному
    из трёх сообщений не приписан `case`, или `prepared` получил лишний
    параметр `case` — параметры или дамп тела расходятся, тест краснеет с
    именем помощника.
    """
    path, cls, method = _plan.HELPERS[name]
    source = _plan.class_method(_base_tree(path), cls, method)
    assert source is not None, f"{cls}.{method} нет в базе {path}"
    funcs = _plan.module_functions(_new_tree())
    assert name in funcs, f"функции модуля {name} в {_plan.NEW_FILE} нет"
    func = funcs[name]
    assert func.args.args, f"{name}: нет первого параметра (стенда)"
    param = func.args.args[0].arg
    with_case = name in _plan.OUTCOME_HELPERS
    want = _plan.params(source.args)[1:] + ([_plan.CASE_PARAM] if with_case else [])
    got = _plan.params(func.args)[1:]
    assert got == want, (f"{name}: параметры после стенда {[p[0] for p in got]} "
                         f"не равны {[p[0] for p in want]} (с аннотациями и "
                         f"умолчаниями)")
    assert _plan.body_dump(func) == _plan.expected_helper_body(
        source, param, _plan.HELPER_CALLS, with_case), (
        f"{name}: тело не равно телу {cls}.{method} по правилу перевода "
        f"(self. → {param}, помощники голым именем"
        + (", case спереди к сообщениям" if with_case else "") + ")")


def test_ac8_helpers_called_by_bare_name():
    """Помощники зовутся голым именем: вызовов `<что-то>.<помощник>(…)` вне класса id-песочницы нет.

    В модуле вне класса `IdOutcomeGateSandbox` нет вызовов атрибута с
    именем `refusal`, `no_gate_refusal`, `assert_no_gate`,
    `assert_prepare`, `prepared`, `broken_task`; каждый из них вызывается
    голым именем хотя бы раз.

    Ловит мутацию: тест зовёт `box.refusal(rows, output, OUTCOME_ACTION)`
    метода песочницы вместо функции модуля `refusal(box, …)` — guard не
    прослеживает утверждения, вызов атрибута найден, тест краснеет со
    строкой.
    """
    tree = _new_tree()
    helpers = set(_plan.HELPERS)
    by_attr, by_name = [], set()
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "IdOutcomeGateSandbox":
            continue
        for sub in ast.walk(node):
            if not isinstance(sub, ast.Call):
                continue
            if isinstance(sub.func, ast.Attribute) and sub.func.attr in helpers:
                by_attr.append(f"строка {sub.lineno}: {ast.unparse(sub.func)}(…)")
            elif isinstance(sub.func, ast.Name) and sub.func.id in helpers:
                by_name.add(sub.func.id)
    assert not by_attr, "помощники вызваны методом стенда:\n" + "\n".join(by_attr)
    uncalled = sorted(helpers - by_name)
    assert not uncalled, f"помощники ни разу не вызваны голым именем: {uncalled}"


@pytest.mark.parametrize("method", ["refusal", "no_gate_refusal"])
def test_ac8_sandbox_method_unchanged(method):
    """Метод `OutcomeGateSandbox.<method>` в `tests/outcome_gate_sandbox.py` на HEAD тот же, что на базе.

    Ловит мутацию: под функцию модуля в методе песочницы добавлен параметр
    `case` (или метод удалён как перенесённый) — дамп расходится или
    метода нет, тест краснеет.
    """
    base = _plan.class_method(_base_tree(_plan.SANDBOX_FILE), "OutcomeGateSandbox",
                              method)
    text = _plan.show(CODE_ROOT, "HEAD", _plan.SANDBOX_FILE)
    assert text is not None, f"{_plan.SANDBOX_FILE} нет в HEAD ветки"
    head = _plan.class_method(ast.parse(text), "OutcomeGateSandbox", method)
    assert base is not None, f"OutcomeGateSandbox.{method} нет в базе"
    assert head is not None, f"OutcomeGateSandbox.{method} нет на HEAD"
    assert ast.dump(head) == ast.dump(base), f"OutcomeGateSandbox.{method} изменён"


def test_ac8_locals_do_not_shadow_module_functions():
    """Ни одна функция модуля не связывает локальное имя, совпадающее с функцией модуля.

    Имена, которым в телах функций верхнего уровня присваивается значение
    (присваивание, цель `for`/`with`), не совпадают с именами функций
    верхнего уровня (`vitest`, `refusal`, …).

    Ловит мутацию: перенесённый тест оставил `vitest = …` (исходная :693)
    или `refusal = box.details(…)` (исходная :146) — локальное имя затеняет
    функцию модуля, тест краснеет с ним.
    """
    tree = _new_tree()
    funcs = set(_plan.module_functions(tree))
    problems = []
    for func in tree.body:
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        stored = {n.id for n in ast.walk(func)
                  if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
        problems += [f"{func.name}: локальное {name}" for name in sorted(stored & funcs)]
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-9

def test_ac9_assertion_literals_carried_verbatim():
    """Литералы утверждений исходных тестов есть в модуле дословно.

    Каждый строковый и числовой литерал смысловых аргументов `self.assert*`
    исходного файла (без аргумента сообщения) встречается литералом вне
    докстрингов в `tests/test_outcome_gate_module.py`.

    Ловит мутацию: при переносе ожидание `"verifying"` переписано как
    `"verify"`, или `assertIn("стал красным", detail)` — как
    `assert "красным" in detail` — исходного литерала в модуле нет, тест
    краснеет с ним.
    """
    new_lits = _plan.non_docstring_constants(_new_tree())
    missing = {lit for lit in _plan.assertion_literals(_source_tree())
               if lit not in new_lits}
    assert not missing, ("литералы утверждений исходных тестов не найдены в "
                         "модуле:\n" + "\n".join(sorted(map(repr, missing))))


def test_ac9_assertion_constants_stay_constants():
    """Константы, с которыми сравнивали исходные утверждения, остались константами.

    Каждое имя константы модуля (`ВЕРХНИЙ_РЕГИСТР`) в смысловых аргументах
    `self.assert*` исходного файла встречается именем (`Name`) в модуле.

    Ловит мутацию: `self.assertTrue(self.details(rows, PASSED_NOTE))`
    перенесён как `assert box.details(rows, "приёмочные тесты пройдены")`
    — имени `PASSED_NOTE` в модуле нет, тест краснеет с ним.
    """
    names = {n.id for n in ast.walk(_new_tree()) if isinstance(n, ast.Name)}
    missing = sorted(c for c in _plan.assertion_constant_names(_source_tree())
                     if c not in names)
    assert not missing, ("константы утверждений исходных тестов не найдены "
                         "именем в модуле: " + ", ".join(missing))


def test_ac9_equality_not_weakened_to_membership_or_inequality():
    """Равенство не заменено вхождением, точное число — неравенством.

    Литерал, который исходный файл сравнивал `assertEqual` (и никогда —
    `assertIn`/`assertNotIn`), в модуле не стоит только в сравнениях
    `in`/`not in`; числовой литерал `assertEqual` не стоит только в
    сравнениях `<`, `<=`, `>`, `>=`: если он есть в таком сравнении, он
    есть и в сравнении `==`/`!=`/`is` или в `<стенд>.assertEqual`.

    Ловит мутацию: `assertEqual(self.state(t), "in_dev", …)` перенесён как
    `assert "in_dev" in box.state(t)`, или `assertEqual(len(calls), 2)` —
    как `assert len(calls) >= 2`, — тест краснеет с литералом.
    """
    equal, member = _plan.equality_literals(_source_tree())
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


def test_ac9_each_transferred_test_keeps_its_equality_literals():
    """Перенесённый тест сохраняет литералы своих сравнений на равенство и вхождение.

    Для каждого теста исходного файла, у которого в модуле есть функция
    (по имени или по соответствию «до → после» PLAN): литералы смысловых
    аргументов его `assertEqual`/`assert*Equal` стоят в этой функции в
    сравнении `==`/`!=`/`is` или в `<стенд>.assertEqual`; литералы его
    `assertIn`/`assertNotIn` — в сравнении `in`/`not in` или на
    равенство. Тест без функции в модуле — предмет AC-11.

    Ловит мутацию: в тесте AC-3 `assertEqual(…, ["base", "head"], …)`
    перенесён как `assert "base" in …` — литерал `"head"` в равенствах этой
    функции пропал (хотя в модуле он есть в других тестах), тест краснеет
    с именем функции.
    """
    new = _plan.module_functions(_new_tree())
    mapping = _plan.transfer_map(_plan_or_empty())
    problems = []
    for cls, method in _source_methods():
        matches = _matches(new, cls, method.name, mapping)
        if not matches:
            continue
        equal, member = _plan.equality_literals(method)
        compared = [pair for f in matches for pair in _plan.compare_operands(f)]
        eq_lits = set().union(*[l for k, l in compared if k == "eq"] or [set()])
        in_lits = set().union(*[l for k, l in compared if k == "in"] or [set()])
        lost_eq = sorted(map(repr, equal - eq_lits))
        lost_in = sorted(map(repr, member - eq_lits - in_lits))
        if lost_eq or lost_in:
            problems.append(f"{cls}::{method.name}: равенства без {lost_eq}, "
                            f"вхождения без {lost_in}")
    assert not problems, "\n".join(problems)


def test_ac9_raises_only_where_source_had_them_match_escaped():
    """`pytest.raises` добавлен только на месте `assertRaises`, `match` — только на месте проверки текста и через `re.escape`.

    Каждый `pytest.raises` с `match` передаёт `re.escape(...)`. Прирост
    числа `pytest.raises` против модуля на базе не больше числа
    `assertRaises*` исходного файла; прирост числа `pytest.raises` с
    `match` — не больше числа мест, где исходник проверял текст исключения
    (`assertRaises(...) as x` с чтением `x.exception`, `assertRaisesRegex`).

    Ловит мутацию: свод переписал проверку отказа `assertIn(…, detail)` как
    `with pytest.raises(SystemExit, match="…")` или дописал `match=` сырым
    регулярным выражением — прирост или строка без `re.escape` найдены,
    тест краснеет.
    """
    tree, source = _new_tree(), _source_tree()
    raw = []
    for node in ast.walk(tree):
        if not _plan.is_pytest_raises(node):
            continue
        for kw in node.keywords:
            value = kw.value
            if kw.arg == "match" and not (
                    isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute)
                    and value.func.attr == "escape"
                    and isinstance(value.func.value, ast.Name)
                    and value.func.value.id == "re"):
                raw.append(f"строка {node.lineno}: match={ast.unparse(value)}")
    assert not raw, "match без re.escape(...):\n" + "\n".join(raw)
    head_all, head_match = _raises_counts(tree)
    base_all, base_match = _raises_counts(_base_tree(_plan.NEW_FILE))
    source_raises = sum(1 for n in ast.walk(source) if isinstance(n, ast.Call)
                        and isinstance(n.func, ast.Attribute)
                        and n.func.attr.startswith("assertRaises"))
    sites = _plan.text_raises_sites(source)
    assert head_all - base_all <= source_raises, (
        f"pytest.raises прибавилось {head_all - base_all}, а assertRaises в "
        f"исходном файле — {source_raises}")
    assert head_match - base_match <= sites, (
        f"pytest.raises с match прибавилось {head_match - base_match}, а мест "
        f"проверки текста исключения в исходном файле — {sites}")


def test_ac9_message_is_second_operand_of_assert_in_tests():
    """В тестовых функциях текст сообщения — второй операнд `assert`, а не аргумент метода.

    В функциях `test_*` нет вызовов `<что-то>.assert*(…)` (кроме
    `assertRaises*`); каждый вызов `explain(…)`/`note(…)` в них стоит в
    сообщении оператора `assert` или аргументе `pytest.fail(…)` — прямо
    либо через локальное имя, которое туда входит; хотя бы одно сообщение
    тестовых функций несёт `explain(…)`.

    Ловит мутацию: свод перенёс `self.assertEqual(self.state(t),
    "verifying", self.explain(rows, output))` как `box.assertEqual(…)` или
    как `assert box.state(t) == "verifying"` с потерей пояснения — вызов
    метода найден или `explain` вне сообщения, тест краснеет со строкой.
    """
    problems, with_explain = [], 0
    for func in _plan.module_tests(_new_tree()):
        messages = [sub.msg for sub in ast.walk(func)
                    if isinstance(sub, ast.Assert) and sub.msg is not None]
        messages += [arg for sub in ast.walk(func)
                     if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                     and sub.func.attr == "fail" for arg in sub.args]
        used = {n.id for msg in messages for n in ast.walk(msg)
                if isinstance(n, ast.Name)}
        allowed = set()
        for msg in messages:
            allowed |= {id(n) for n in ast.walk(msg)}
            if any(isinstance(n, ast.Call) and _called(n) == "explain"
                   for n in ast.walk(msg)):
                with_explain += 1
        for node in ast.walk(func):
            if isinstance(node, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id in used for t in node.targets):
                allowed |= {id(n) for n in ast.walk(node.value)}
        for sub in ast.walk(func):
            if _plan.is_method_assert(sub):
                problems.append(f"{func.name}: {ast.unparse(sub.func)}(…) в "
                                f"строке {sub.lineno}")
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) \
                    and sub.func.attr in ("explain", "note") and id(sub) not in allowed:
                problems.append(f"{func.name}: {sub.func.attr}(…) вне сообщения "
                                f"в строке {sub.lineno}")
    assert not problems, "\n".join(problems)
    assert with_explain, "ни одно сообщение тестовых функций не несёт explain(…)"


# ------------------------------------------------------------------ AC-10

def test_ac10_each_former_subtest_in_one_function_with_label_and_seed():
    """Бывший `subTest` — в одной функции; прямые утверждения подслучая несут ярлык и зерно, помощники получают `case=f"{<ярлык>}, зерно {box.seed}"`.

    Для каждого теста исходного файла с `subTest` (кроме удалённых дублей
    раздела «…дубл…» PLAN) в модуле ровно одна функция (по имени или по
    соответствию PLAN), без `parametrize`. В ней:
    - операторов `assert`, чьё сообщение несёт ярлык подслучая (тот же
      литерал или то же выражение, что у `subTest`) и зерно (`….seed`) —
      прямо или через локальное имя, — не меньше, чем прямых `self.assert*`
      внутри тел `subTest` исходника, а прочих `assert` — не больше, чем
      прямых `self.assert*` вне этих тел;
    - вызовов каждого помощника исхода с `case=` вида
      `f"{<ярлык>}, зерно {box.seed}"` (прямо или через локальное имя) не
      меньше, чем его вызовов внутри тел `subTest`, а вызовов без такого
      `case` — не больше, чем вне этих тел.

    Ловит мутацию: в перенесённом цикле `for label, … in …` сообщение
    `assert … , box.explain(rows, output)` потеряло ярлык и зерно, или
    `refusal(box, rows, output, PREPARE_ACTION)` вызван без `case=` — счёт
    расходится, тест краснеет с именем теста; подслучаи разнесены
    `parametrize` по отдельным стендам — тоже краснеет.
    """
    new = _plan.module_functions(_new_tree())
    plan = _plan_or_empty()
    mapping, removed = _plan.transfer_map(plan), _removed_keys(plan)
    problems, seen = [], 0
    for cls, method in _source_methods():
        counts = _source_counts(method)
        if not counts["labels"]:
            continue
        seen += 1
        key = f"{cls}::{method.name}"
        if key in removed:
            continue
        matches = _matches(new, cls, method.name, mapping)
        if len(matches) != 1:
            problems.append(f"{key}: функций в модуле {[f.name for f in matches]}, "
                            f"ожидалась одна")
            continue
        func = matches[0]
        if _plan.parametrize_decorators(func):
            problems.append(f"{key}: подслучаи вынесены в parametrize ({func.name})")
        labels = counts["labels"]
        wanted = set().union(*[_wanted_case(l) for l in labels if l is not None])

        def tagged_msg(node, names):
            return _carries(node, labels, names)

        def tagged_case(node, names):
            return (isinstance(node, ast.Name) and node.id in names) or \
                _template(node) in wanted

        msg_names = _tagged_names(func, tagged_msg)
        case_names = _tagged_names(func, tagged_case)
        asserts = [n for n in ast.walk(func) if isinstance(n, ast.Assert)]
        tagged = sum(1 for n in asserts
                     if n.msg is not None and _carries(n.msg, labels, msg_names))
        if tagged < counts["asserts_in"]:
            problems.append(f"{key} → {func.name}: assert с ярлыком и зерном "
                            f"{tagged}, а прямых утверждений в subTest "
                            f"{counts['asserts_in']}")
        if len(asserts) - tagged > counts["asserts_out"]:
            problems.append(f"{key} → {func.name}: assert без ярлыка и зерна "
                            f"{len(asserts) - tagged}, а прямых утверждений вне "
                            f"subTest {counts['asserts_out']}")
        for helper in _plan.OUTCOME_HELPERS:
            calls = [n for n in ast.walk(func) if isinstance(n, ast.Call)
                     and isinstance(n.func, ast.Name) and n.func.id == helper]
            cased = sum(1 for c in calls if any(
                kw.arg == _plan.CASE and tagged_case(kw.value, case_names)
                for kw in c.keywords))
            need_in = counts["helpers_in"].get(helper, 0)
            need_out = counts["helpers_out"].get(helper, 0)
            if cased < need_in:
                problems.append(f"{key} → {func.name}: {helper} с case=ярлык, "
                                f"зерно — {cased}, а в subTest {need_in}")
            if len(calls) - cased > need_out:
                problems.append(f"{key} → {func.name}: {helper} без case=ярлык, "
                                f"зерно — {len(calls) - cased}, а вне subTest "
                                f"{need_out}")
    assert seen, "в исходном файле базы нет тестов с subTest — база прочитана не та"
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-11

def test_ac11_every_test_function_declares_mutation():
    """У каждой тестовой функции модуля есть строка «Ловит мутацию:».

    Ловит мутацию: свод перенёс тест без заявки (докстринг без строки
    «Ловит мутацию:», например укороченный до первой фразы) — функция
    перечислена, тест краснеет.
    """
    tests = _plan.module_tests(_new_tree())
    assert len(tests) > _plan.BASE_MODULE_TESTS, (
        f"в {_plan.NEW_FILE} нет перенесённых тестов")
    without = [f.name for f in tests
               if "Ловит мутацию:" not in (ast.get_docstring(f) or "")]
    assert not without, "функции без «Ловит мутацию:»:\n" + "\n".join(without)


# ------------------------------------------------------------------ AC-14

def test_ac14_no_skip_or_xfail_in_module():
    """В модуле нет `skip`/`xfail` ни в каком виде.

    Ни обращений `pytest.mark.skip`/`skipif`/`xfail`, `pytest.skip`,
    `unittest.skip*`, `skipTest`, `importorskip`, ни импорта этих имён.

    Ловит мутацию: тест, упавший после свода, помечен
    `@pytest.mark.skip(reason="…")` или `pytest.xfail(...)` — имя найдено,
    тест краснеет со строкой.
    """
    tree = _new_tree()
    found = [f"{ast.unparse(n)} в строке {n.lineno}" for n in ast.walk(tree)
             if isinstance(n, ast.Attribute) and n.attr in _SKIP_NAMES
             and (n.attr not in _AMBIGUOUS_SKIP
                  or ast.unparse(n.value).rsplit(".", 1)[-1] in _SKIP_OWNERS)]
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            found += [f"импорт {a.name}" for a in node.names if a.name in _SKIP_NAMES]
    assert not found, f"skip/xfail в {_plan.NEW_FILE}:\n" + "\n".join(found)


@pytest.mark.parametrize("name", ["timeout", "delta", "places", "rel", "abs",
                                  "full_suite_timeout_sec"])
def test_ac14_limits_not_raised_against_source(name):
    """Пределы (`timeout`, допуски, `full_suite_timeout_sec`) в модуле не подняты.

    Каждое числовое значение предела `name` в модуле (именованный аргумент,
    `mark.timeout(<n>)`, ключ словаря-литерала) не больше наибольшего
    значения того же предела в исходном файле и модуле на базе; предела,
    которого там не было, в модуле нет; `pytest.approx` есть, только если
    он был там.

    Ловит мутацию: свод добавил `@pytest.mark.timeout(600)` долгому тесту
    AC-7 или поднял `timeout=` вызова песочницы — значение выше исходного
    (или новое), тест краснеет с ним.
    """
    base, base_approx = {}, False
    for tree in (_source_tree(), _base_tree(_plan.NEW_FILE)):
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
