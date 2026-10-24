"""AC-6, AC-7, AC-8, AC-9, AC-10, AC-11, AC-12: форма сводного
`tests/test_report_outcome_module.py` против crg и модуля в базе ветки.

Группа: разовый
Красен до реализации: crg ещё не сведён — его тестов, определений, помощников и фикстуры checks_stand в модуле на HEAD нет, сам crg на ветке есть.

Модуль читается из HEAD рабочей копии (`git show HEAD:…`), crg и модуль до
свода — из базы ветки (`_pult.DIFF_BASE`): на ветке crg удалён. Сравнение
статическое (ast): тест не исполняет ни crg, ни модуль. Перенос «тест crg
→ функция модуля» и нормальная форма утверждения — докстринг `_plan.py`.
"""
import ast
import copy
import sys
from collections import defaultdict
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _plan  # noqa: E402
from _pult import CODE_ROOT, DIFF_BASE, artifact_text  # noqa: E402

_CHECKS_STAND_VALUE = "types.SimpleNamespace(tree=tmp_dir.tdir.resolve())"


def _base(path: str) -> str:
    assert DIFF_BASE, "база диффа ветки задачи не определена при выкладке"
    text = _plan.show(CODE_ROOT, DIFF_BASE, path)
    assert text is not None, f"{path} нет в базе ветки {DIFF_BASE}"
    return text


def _head_tree() -> ast.Module:
    text = _plan.show(CODE_ROOT, "HEAD", _plan.NEW_FILE)
    assert text is not None, f"{_plan.NEW_FILE} нет в HEAD ветки"
    return ast.parse(text)


def _crg_tree() -> ast.Module:
    return ast.parse(_base(_plan.SOURCE_FILE))


def _base_module_tree() -> ast.Module:
    return ast.parse(_base(_plan.NEW_FILE))


def _plan_text() -> str:
    plan = artifact_text("PLAN.md")
    assert plan is not None, "PLAN.md в ссылке документов задачи нет"
    return plan


def _base_tests() -> dict:
    return {t.key: t for t in _plan.base_tests(_base(_plan.SOURCE_FILE))}


def _moved(head=None) -> dict:
    plan = artifact_text("PLAN.md")
    return _plan.transferred(plan, _base_tests(), head or _head_tree(),
                             _base_module_tree())


def _pairs(head) -> list:
    """[(тест crg, функция модуля)] по всем переносам."""
    tests, funcs = _base_tests(), _plan.module_functions(head)
    return [(tests[key], funcs[name]) for key, names in sorted(_moved(head).items())
            for name in sorted(names)]


def _helpers(head) -> dict:
    """{имя функции модуля: метод-помощник crg}."""
    return {fname: method for method, fname
            in _plan.helper_function_names(_plan.module_functions(head)).items()}


def _stands(func) -> set:
    return set(_plan.STAND_NAMES) | set(_plan.fixture_params(func))


def _definition(tree, name: str) -> list:
    return [n for n in tree.body if name in _plan.bound_names(n)
            and not isinstance(n, (ast.Import, ast.ImportFrom))]


def _subtest_loop(func):
    """(цикл `for`, имена значений `subTest(...)`) метода crg."""
    for node in ast.walk(func):
        if not isinstance(node, ast.For):
            continue
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) \
                    and sub.func.attr == "subTest":
                names = {n.id for kw in sub.keywords for n in ast.walk(kw.value)
                         if isinstance(n, ast.Name)}
                return node, names
    return None, set()


# ------------------------------------------------------------------ AC-6

def test_ac6_crg_absent_on_branch():
    """Файла `tests/test_component_report_gates.py` на HEAD ветки нет.

    Ловит мутацию: свод перенёс тесты, но crg оставил (или оставил
    переходным модулем с импортом) — файл читается из HEAD, тест краснеет.
    """
    assert _plan.show(CODE_ROOT, "HEAD", _plan.SOURCE_FILE) is None, (
        f"{_plan.SOURCE_FILE} есть на HEAD ветки")


def test_ac6_no_test_classes_subtest_main_or_import_unittest():
    """В модуле нет тестовых классов, `subTest`, блока `__main__` и `import unittest`.

    Ни один класс модуля не несёт методов `test_*`; обращений `subTest`
    нет; на верхнем уровне нет `if __name__ == "__main__"`; нет оператора
    `import unittest`.

    Ловит мутацию: свод оставил `class InstallLockTest(unittest.TestCase)`
    с методом, `with self.subTest(actor=actor)`, хвост
    `if __name__ == "__main__": unittest.main()` или импорт `unittest` —
    класс/обращение/блок/импорт найден, тест краснеет.
    """
    tree = _head_tree()
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
        if isinstance(node, ast.Import) and any(a.name == "unittest"
                                                for a in node.names):
            problems.append(f"import unittest в строке {node.lineno}")
    problems += [f"блок __main__ в строке {n.lineno}" for n in tree.body
                 if isinstance(n, ast.If) and "__name__" in ast.unparse(n.test)
                 and "__main__" in ast.unparse(n.test)]
    assert not problems, "\n".join(problems)


def test_ac6_names_of_module_not_imported_again():
    """Имена, определённые или импортированные в модуле до свода (в том числе `json`), повторно не импортируются.

    Каждое имя, связанное импортом на верхнем уровне модуля HEAD, связано
    импортом ровно один раз; имя, определённое в модуле базы не импортом
    (функция, класс, присваивание), импортом на HEAD не связано.

    Ловит мутацию: свод перенёс строку импорта crg целиком — второй
    `import json`, повторный `from orchestrator import acceptance, config, …`
    или `ENTRY_HEAD` в двух импортах — имя связано импортом дважды, тест
    краснеет с ним.
    """
    head = _head_tree()
    counts = defaultdict(int)
    for node in head.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for name in _plan.bound_names(node):
                counts[name] += 1
    twice = sorted(n for n, c in counts.items() if c > 1)
    defined = {name for node in _base_module_tree().body
               if not isinstance(node, (ast.Import, ast.ImportFrom))
               for name in _plan.bound_names(node)}
    shadowed = sorted(defined & set(counts))
    assert counts.get("json") == 1, f"json связан импортом {counts.get('json', 0)} раз"
    assert not twice, f"имена, импортированные повторно: {twice}"
    assert not shadowed, f"имена модуля базы, связанные импортом: {shadowed}"


def test_ac6_vitest_report_args_and_block_from_sandbox_module():
    """`VITEST_REPORT_ARGS` и `block` импортируются из `tests.report_outcome_sandbox`.

    Ловит мутацию: свод переопределил `block` копией функции в модуле или
    взял `VITEST_REPORT_ARGS` из другого модуля — имени нет в импорте из
    `tests.report_outcome_sandbox`, тест краснеет.
    """
    names = {a.name for node in _head_tree().body
             if isinstance(node, ast.ImportFrom) and node.module == _plan.SANDBOX_MODULE
             and node.level == 0 for a in node.names}
    missing = sorted({"VITEST_REPORT_ARGS", "block"} - names)
    assert not missing, f"не импортированы из {_plan.SANDBOX_MODULE}: {missing}"


# ------------------------------------------------------------------ AC-7

def _definition_dump(node, name: str) -> str:
    node = copy.deepcopy(node)
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        node.name = name
        return ast.dump(node)
    return ast.dump(node.value)


@pytest.mark.parametrize("name", ["profile", "check", "UNKNOWN", "GREEN", "Reached"])
def test_ac7_definition_carried_verbatim_with_prefix_only_on_collision(name):
    """Определение crg лежит в модуле одним определением с `ast.dump`, равным исходному; префикс — только при совпадении имени.

    Если имя совпадает с именем верхнего уровня модуля базы (определённым
    или импортированным), в модуле HEAD есть ровно одно определение
    `crg_<имя>`/`CRG_<имя>`; иначе — ровно одно определение с голым
    именем. `ast.dump` определения (имя приведено к исходному; у
    присваивания — значение) равен исходному из crg базы.

    Ловит мутацию: при переносе в `profile` выброшено поле
    `from_components=True` или в `UNKNOWN` путь лога `/tmp/l.log` заменён,
    либо `check` назван `crg_check` без совпадения — определения нет или
    дамп расходится, тест краснеет с именем.
    """
    source = _definition(_crg_tree(), name)
    assert len(source) == 1, f"{name} в crg базы: определений {len(source)}"
    head = _head_tree()
    collides = name in _plan.top_names(_base_module_tree())
    wanted = ([f"crg_{name}", f"CRG_{name}"] if collides else [name])
    found = [(n, w) for w in wanted for n in _definition(head, w)]
    assert len(found) == 1, (f"определений {wanted} в {_plan.NEW_FILE}: "
                             f"{len(found)} (совпадение с модулем базы: {collides})")
    node, actual = found[0]
    assert _definition_dump(node, name) == _definition_dump(source[0], name), (
        f"{actual}: ast.dump не равен исходному {name} из crg")


def test_ac7_renamed_definitions_listed_in_plan():
    """Каждое определение crg, получившее префикс `crg_`/`CRG_`, названо в PLAN.

    Ловит мутацию: роль переименовала `profile` в `crg_profile`, а перечень
    переименований PLAN его не называет — имени нет в PLAN, тест краснеет.
    """
    plan = _plan_text()
    names = _plan.top_names(_head_tree())
    renamed = sorted(f"{p}{n}" for n in _plan.DEFINITIONS for p in ("crg_", "CRG_")
                     if f"{p}{n}" in names)
    missing = [n for n in renamed if n not in plan]
    assert not missing, "переименования не перечислены в PLAN: " + ", ".join(missing)


def test_ac7_locals_of_26_existing_tests_not_renamed():
    """Локальные переменные 26 существующих тестов модуля не переименованы.

    Каждая тестовая функция модуля базы есть на HEAD под тем же именем, и
    множество её локальных имён (параметры и цели присваивания) то же.

    Ловит мутацию: ради переноса `profile` без префикса свод переименовал
    локальную `profile` в `test_ac6_pult_pytest_and_no_report_records_by_code_and_text`
    в `prof` — множество локальных имён расходится, тест краснеет с функцией.
    """
    head = _plan.module_functions(_head_tree())
    base = _plan.module_tests(_base_module_tree())
    assert len(base) == _plan.EXISTING_TESTS, (
        f"тестов в модуле базы {len(base)}, критерий называет {_plan.EXISTING_TESTS}")
    problems = []
    for func in base:
        if func.name not in head:
            problems.append(f"{func.name}: нет на HEAD")
            continue
        lost = _plan.local_names(func) - _plan.local_names(head[func.name])
        new = _plan.local_names(head[func.name]) - _plan.local_names(func)
        if lost or new:
            problems.append(f"{func.name}: пропали {sorted(lost)}, появились {sorted(new)}")
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-8

def test_ac8_checks_stand_fixture_returns_tree_namespace():
    """Фикстура `checks_stand(tmp_dir)` возвращает `types.SimpleNamespace(tree=tmp_dir.tdir.resolve())`.

    В модуле есть функция `checks_stand` с декоратором `pytest.fixture`,
    единственным параметром `tmp_dir`, и её `return`/`yield` отдаёт ровно
    это выражение.

    Ловит мутацию: фикстура отдаёт `tmp_dir.tdir` без `.resolve()` (путь
    через символическую ссылку `/var` → `/private/var`) или строит стенд
    своим `tempfile.TemporaryDirectory()` — выражение расходится, тест
    краснеет.
    """
    funcs = _plan.module_functions(_head_tree())
    assert "checks_stand" in funcs, "фикстуры checks_stand в модуле нет"
    func = funcs["checks_stand"]
    assert _plan.is_fixture(func), "checks_stand без декоратора pytest.fixture"
    assert [a.arg for a in func.args.args] == ["tmp_dir"], (
        f"параметры checks_stand: {[a.arg for a in func.args.args]}")
    want = ast.dump(ast.parse(_CHECKS_STAND_VALUE, mode="eval").body)
    values = [ast.dump(n.value) for n in ast.walk(func)
              if isinstance(n, (ast.Return, ast.Yield)) and n.value is not None]
    assert values == [want], (f"checks_stand отдаёт "
                              f"{[ast.unparse(n.value) for n in ast.walk(func) if isinstance(n, (ast.Return, ast.Yield)) and n.value is not None]}, "
                              f"ожидалось {_CHECKS_STAND_VALUE}")


def test_ac8_transferred_functions_take_stand_of_their_class():
    """Функция переноса берёт стенд своего бывшего класса.

    Из `AcceptanceSuiteChecksLocalTest` — параметр `checks_stand`; из
    классов на `ReportSandbox` — `box`; из `InstallLockTest` — `tmp_dir`;
    из `SuiteRunParseReportedTest` — без параметров-фикстур (параметры
    только имена `parametrize`). У каждого теста crg, перенесённого в
    модуль, проверяется каждая его функция переноса.

    Ловит мутацию: тест `InstallLockTest` переведён на `box` (песочница
    `ReportSandbox` с git ради одного `addCleanup`) или
    `SuiteRunParseReportedTest` получил `tmp_dir` — параметры расходятся,
    тест краснеет с функцией.
    """
    pairs = _pairs(_head_tree())
    assert pairs, "ни один тест crg не перенесён в модуль"
    problems = []
    for test, func in pairs:
        stand = _plan.STANDS[test.cls]
        params = _plan.fixture_params(func)
        if stand is None and params:
            problems.append(f"{func.name} ({test.key}): параметры-фикстуры {params}")
        elif stand is not None and stand not in params:
            problems.append(f"{func.name} ({test.key}): нет параметра {stand}, есть {params}")
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("method", ["suite", "approve"])
def test_ac8_suite_and_approve_take_stand_tree(method):
    """Помощники `suite`/`approve` берут дерево из `<стенд>.tree`.

    Функция модуля помощника (голое имя или с префиксом
    `AcceptanceSuiteChecksLocalTest`) обращается к атрибуту `tree` своего
    первого параметра и не обращается к `self`.

    Ловит мутацию: помощник `suite` взял дерево из глобальной переменной
    модуля или из `box.root` вместо `stand.tree` — обращения
    `<стенд>.tree` нет, тест краснеет.
    """
    funcs = _plan.module_functions(_head_tree())
    name = _plan.helper_function_names(funcs).get(method)
    assert name, f"функции модуля помощника {method} нет"
    func = funcs[name]
    assert func.args.args, f"{name}: нет первого параметра"
    param = func.args.args[0].arg
    uses = [n for n in ast.walk(func) if isinstance(n, ast.Attribute)
            and n.attr == "tree" and isinstance(n.value, ast.Name)
            and n.value.id == param]
    assert uses, f"{name}: нет обращения {param}.tree"
    assert not any(isinstance(n, ast.Name) and n.id == "self" for n in ast.walk(func)), (
        f"{name}: обращение к self")


# ------------------------------------------------------------------ AC-9

@pytest.mark.parametrize("method", sorted(_plan.HELPERS))
def test_ac9_helper_is_module_function_with_verbatim_body(method):
    """Метод-помощник crg — функция модуля: первый параметр — стенд, тело — исходное с `self.` → стенд.

    Функция модуля с голым именем метода или с префиксом бывшего класса;
    если голое имя совпадает с именем верхнего уровня модуля базы — только
    с префиксом. Прочие параметры совпадают с исходными; `ast.dump` тела
    (без докстринга) равен исходному, где `self` → имя первого параметра,
    `self.<помощник>(…)` → `<функция помощника>(<стенд>, …)`.

    Ловит мутацию: в `checked_case` вызов `self.check_script()` оставлен
    как `box.check_script()` или в `two_components` предел
    `full_suite_timeout_sec` записан всегда — дамп тела расходится, тест
    краснеет с именем помощника.
    """
    cls = _plan.HELPERS[method]
    source = _plan.class_method(_crg_tree(), cls, method)
    assert source is not None, f"{cls}.{method} нет в crg базы"
    funcs = _plan.module_functions(_head_tree())
    names = _plan.helper_function_names(funcs)
    assert method in names, f"функции модуля помощника {cls}.{method} нет"
    name = names[method]
    if method in _plan.top_names(_base_module_tree()):
        assert name != method, (f"{method} совпадает с именем модуля базы — "
                                f"нужен префикс {cls}")
    func = funcs[name]
    assert func.args.args, f"{name}: нет первого параметра (стенда)"
    param = func.args.args[0].arg
    assert _plan.rest_args_dump(func.args) == _plan.rest_args_dump(source.args), (
        f"{name}: параметры после стенда не совпадают с исходными")
    assert _plan.body_dump(func) == _plan.expected_helper_body(source, param, names), (
        f"{name}: тело не равно исходному с заменой self. → {param}")


def test_ac9_tree_and_fake_stay_nested_and_locals_not_renamed():
    """`tree` и `fake` остаются вложенными, локальные имена перенесённых тестов не переименованы.

    На верхнем уровне модуля нет функций `tree` и `fake`; функция переноса
    `MergeGateComponentsTest::test_each_component_runs_with_its_own_limit`
    содержит вложенную функцию `fake`; у каждой пары «тест crg — функция
    переноса» локальные имена теста (кроме `self`) есть среди локальных
    имён функции.

    Ловит мутацию: свод вынес `fake` на уровень модуля или переименовал
    локальную `run` в `result` ради несовпадения имён — функция найдена на
    верхнем уровне или локального имени нет, тест краснеет.
    """
    head = _head_tree()
    funcs = _plan.module_functions(head)
    problems = [f"функция {n} на верхнем уровне" for n in ("tree", "fake") if n in funcs]
    pairs = _pairs(head)
    assert pairs, "ни один тест crg не перенесён в модуль"
    owner = "MergeGateComponentsTest::test_each_component_runs_with_its_own_limit"
    for test, func in pairs:
        if test.key == owner and not any(
                isinstance(n, ast.FunctionDef) and n.name == "fake"
                for n in ast.walk(func) if n is not func):
            problems.append(f"{func.name}: нет вложенной функции fake")
        lost = _plan.local_names(test.func) - {"self"} - _plan.local_names(func)
        if lost:
            problems.append(f"{func.name} ({test.key}): нет локальных {sorted(lost)}")
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-10

def test_ac10_expectations_of_transferred_tests_carried_verbatim():
    """Каждое утверждение теста crg есть в функции переноса в той же нормальной форме.

    Для каждой пары «тест crg — функция переноса» мультимножество
    нормальных форм `self.assert*`/`assertRaises` теста (докстринг
    `_plan.py`: `assertEqual(a, b)` → `a == b`, сообщение отброшено,
    стенд — метка) входит в мультимножество нормальных форм утверждений
    функции. Литерал остаётся литералом, константа — константой: замена
    меняет форму.

    Ловит мутацию: при переносе `self.assertEqual(results[0][1],
    ["node_modules"])` записано как `assert "node_modules" in results[0][1]`,
    или `acceptance.FULL_SUITE_RED` — литералом `"красный прогон"`, или
    `assertEqual(..., 1)` — как `>= 1` — формы нет в функции, тест
    краснеет с тестом и утверждением.
    """
    head = _head_tree()
    helpers = _helpers(head)
    pairs = _pairs(head)
    assert pairs, "ни один тест crg не перенесён в модуль"
    problems = []
    for test, func in pairs:
        want = _plan.canon_counter(test.func, {"self"})
        have = _plan.canon_counter(func, _stands(func), helpers)
        lost = want - have
        if lost:
            problems.append(f"{test.key} → {func.name}: нет утверждений "
                            f"{[ast.unparse(_plan._expression(n)) for n in _plan.assertion_nodes(test.func) if _plan.canon(n, {'self'}) in lost]}")
    assert not problems, "\n".join(problems)


def test_ac10_raises_match_only_at_text_checks_and_msg_as_last_fail():
    """`pytest.raises` с `match=re.escape(...)` — только на месте проверки текста; `msg=` — последней строкой `pytest.fail(box.note(…))`.

    Для каждой пары: число `pytest.raises(..., match=…)` функции не больше
    числа мест теста, где проверялся текст исключения (`assertRaisesRegex`,
    `assertRaises(...) as x` с чтением `x.exception`), каждый `match` —
    `re.escape(...)`; число блоков `pytest.raises`, последний оператор
    которых — `pytest.fail(<…>.note(…))`, не меньше числа
    `assertRaises(..., msg=…)` теста.

    Ловит мутацию: на месте голого `self.assertRaises(Reached)` свод
    поставил `pytest.raises(Reached, match="Reached")` — `match` без
    проверки текста в исходнике, тест краснеет с функцией.
    """
    pairs = _pairs(_head_tree())
    assert pairs, "ни один тест crg не перенесён в модуль"
    problems = []
    for test, func in pairs:
        read = {n.value.id for n in ast.walk(test.func)
                if isinstance(n, ast.Attribute) and n.attr == "exception"
                and isinstance(n.value, ast.Name)}
        text_sites, msg_sites = 0, 0
        for node in ast.walk(test.func):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in ("assertRaisesRegex", "assertRaisesRegexp"):
                    text_sites += 1
                if node.func.attr == "assertRaises" and any(
                        k.arg == "msg" for k in node.keywords):
                    msg_sites += 1
            if isinstance(node, ast.With):
                for item in node.items:
                    call = item.context_expr
                    if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) \
                            and call.func.attr == "assertRaises" \
                            and isinstance(item.optional_vars, ast.Name) \
                            and item.optional_vars.id in read:
                        text_sites += 1
        matches, failing = 0, 0
        for node in ast.walk(func):
            if _plan.is_pytest_raises(node):
                for kw in node.keywords:
                    if kw.arg != "match":
                        continue
                    matches += 1
                    v = kw.value
                    if not (isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute)
                            and v.func.attr == "escape"):
                        problems.append(f"{func.name}: match без re.escape в строке {node.lineno}")
            if isinstance(node, ast.With) and any(_plan.is_pytest_raises(i.context_expr)
                                                  for i in node.items):
                last = node.body[-1]
                if isinstance(last, ast.Expr) and _plan.is_pytest_fail(last.value) \
                        and any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                                and n.func.attr == "note" for n in ast.walk(last.value)):
                    failing += 1
        if matches > text_sites:
            problems.append(f"{func.name}: match у {matches} pytest.raises, "
                            f"проверок текста в {test.key} — {text_sites}")
        if failing < msg_sites:
            problems.append(f"{func.name}: pytest.fail(…note(…)) последней строкой — "
                            f"{failing}, assertRaises с msg в {test.key} — {msg_sites}")
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-11

@pytest.mark.parametrize("key", list(_plan.PARAMETRIZED))
def test_ac11_literal_subtest_sets_become_parametrize(key):
    """Литеральные наборы `subTest` (:81, :96) — `parametrize` теми же литералами, без цикла.

    Функция переноса теста несёт `@pytest.mark.parametrize` с именем
    переменной цикла `subTest` и значениями — тем же набором литералов;
    цикла `for` по этому набору и `subTest` в ней нет.

    Ловит мутацию: свод оставил `for actor in ("operator", "fsm"):` в теле
    функции или параметризовал одним `"operator"` — декоратора/значения
    нет либо цикл найден, тест краснеет.
    """
    test = _base_tests()[key]
    loop, _labels = _subtest_loop(test.func)
    assert loop is not None, f"в {key} базы нет цикла subTest"
    var = ast.unparse(loop.target)
    values = set(ast.literal_eval(loop.iter))
    funcs = _plan.module_functions(_head_tree())
    names = _moved().get(key, set())
    assert names, f"{key}: функции переноса нет"
    problems = []
    for name in sorted(names):
        func = funcs[name]
        columns = []
        for deco in _plan.parametrize_decorators(func):
            if len(deco.args) >= 2 and isinstance(deco.args[0], ast.Constant) \
                    and deco.args[0].value == var:
                try:
                    columns.append(set(ast.literal_eval(deco.args[1])))
                except ValueError:
                    columns.append(None)
        if columns != [values]:
            problems.append(f"{name}: parametrize({var!r}, …) — {columns}, ожидалось {values}")
        if any(isinstance(n, ast.For) and ast.unparse(n.target) == var
               for n in ast.walk(func)):
            problems.append(f"{name}: цикл for {var} остался")
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("key", list(_plan.LOOPED))
def test_ac11_shared_state_subtest_sets_stay_loop_with_label_in_messages(key):
    """Наборы :178, :334, :396 — прежний цикл в одной функции, ярлык подслучая в сообщении каждого утверждения.

    Функция переноса содержит цикл `for` с той же целью и тем же
    выражением набора, что цикл `subTest` теста; не параметризована по
    переменной цикла; каждый `assert` в теле цикла несёт сообщение, в
    котором есть каждое имя ярлыка `subTest` (`command`, `base`, `actor`);
    утверждений методом `<стенд>.assert*` в теле цикла нет.

    Ловит мутацию: свод перевёл набор `(False, True)` с общим `case` в
    `parametrize` (стенд строится заново на каждый вариант) или оставил
    `assert key is not None` без `base` в сообщении — цикла нет либо ярлыка
    в сообщении нет, тест краснеет с функцией и строкой.
    """
    test = _base_tests()[key]
    loop, labels = _subtest_loop(test.func)
    assert loop is not None and labels, f"в {key} базы нет цикла subTest с ярлыком"
    funcs = _plan.module_functions(_head_tree())
    names = _moved().get(key, set())
    assert len(names) == 1, f"{key}: функций переноса {sorted(names)}, ожидалась одна"
    func = funcs[next(iter(names))]
    var_names = {n.id for n in ast.walk(loop.target) if isinstance(n, ast.Name)}
    problems = []
    if var_names & _plan.parametrize_names(func):
        problems.append(f"{func.name}: параметризована по {sorted(var_names)}")
    loops = [n for n in ast.walk(func) if isinstance(n, ast.For)
             and ast.dump(n.target) == ast.dump(loop.target)
             and ast.dump(n.iter) == ast.dump(loop.iter)]
    if len(loops) != 1:
        problems.append(f"{func.name}: циклов «for {ast.unparse(loop.target)} in "
                        f"{ast.unparse(loop.iter)}» — {len(loops)}")
    for found in loops:
        asserts = [n for s in found.body for n in ast.walk(s) if isinstance(n, ast.Assert)]
        if not asserts:
            problems.append(f"{func.name}: в цикле нет assert")
        for node in asserts:
            used = {n.id for n in ast.walk(node.msg) if isinstance(n, ast.Name)} \
                if node.msg is not None else set()
            if not labels <= used:
                problems.append(f"{func.name}, строка {node.lineno}: в сообщении нет "
                                f"ярлыка {sorted(labels - used)}")
        problems += [f"{func.name}, строка {n.lineno}: {ast.unparse(n.func)}(…)"
                     for s in found.body for n in ast.walk(s) if _plan.is_method_assert(n)]
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-12

def _section_rows(plan: str, title: str) -> dict:
    texts = _plan.sections(plan, title)
    assert texts, f"в PLAN нет раздела «{title}»"
    found, errors = _plan.tables("\n".join(texts))
    assert found and not errors, f"раздел «{title}»: таблицы нет или шапка битая {errors}"
    return _plan.last_rows(found[-1:])


def _removed(plan: str) -> dict:
    removed = defaultdict(set)
    for text in _plan.sections(plan, "дубл"):
        for line in _plan.prose_lines(text):
            for key in _plan.test_keys(line):
                removed[key] |= _plan.refs(line)
    return removed


def test_ac12_each_transferred_function_declares_mutation():
    """У каждой функции переноса теста crg есть строка «Ловит мутацию:».

    Ловит мутацию: свод перенёс тест с укороченным до первой фразы
    докстрингом — строки «Ловит мутацию:» нет, тест краснеет с функцией.
    """
    pairs = _pairs(_head_tree())
    assert pairs, "ни один тест crg не перенесён в модуль"
    without = sorted({f.name for _t, f in pairs
                      if "Ловит мутацию:" not in (ast.get_docstring(f) or "")})
    assert not without, "функции без «Ловит мутацию:»:\n" + "\n".join(without)


def test_ac12_untransferred_test_is_listed_duplicate_meeting_conditions():
    """Тест crg без функции переноса — удалённый дубль PLAN с мутациями, условия (а) и (б) выполнены.

    Каждый тест crg без функции переноса перечислен в разделе «…дубл…»
    PLAN со ссылками на свои мутации. Для каждого перечисленного: его
    мутации есть и «до» убиты (тест, чью мутацию не убил никто, не
    удаляется); (а) каждую из них «до» убивает и сохраняемый тест crg;
    (б) среди сохраняемых, убивающих их все, есть тест, у которого
    литералы и виды `self.assert*` покрывают литералы и виды удалённого.

    Ловит мутацию: удалён как дубль тест, чью мутацию «до» убивал только он
    сам, или тест не перенесён и не записан дублем — перечень непуст,
    тест краснеет с именем.
    """
    plan = _plan_text()
    tests = _base_tests()
    moved = _moved()
    removed = _removed(plan)
    lost = sorted(k for k, names in moved.items() if not names and k not in removed)
    problems = [f"{k}: не перенесён и не перечислен удалённым дублем" for k in lost]
    rows = _section_rows(plan, "Мутации до")
    proof = _plan.killed(rows)
    killers = {n: {_plan.node_key(x) for x in nodes} for n, nodes in proof.items()}
    for key, numbers in sorted(removed.items()):
        if key not in tests:
            problems.append(f"{key}: в crg базы такого теста нет")
            continue
        if moved.get(key):
            continue
        if not numbers:
            problems.append(f"{key}: удалён без перечня своих мутаций")
            continue
        claimed = {n for line in _plan.prose_lines(plan)
                   if key in _plan.test_keys(line) for n in _plan.refs(line)}
        unkilled = sorted(n for n in claimed | numbers if n not in proof)
        if unkilled:
            problems.append(f"{key}: удалён, а его мутации {unkilled} «до» не убиты")
            continue
        kept = None
        for number in numbers:
            others = killers[number] - {key} - set(removed)
            kept = others if kept is None else kept & others
            if not others:
                problems.append(f"{key}: мутацию {number} не убивает ни один "
                                f"сохраняемый тест")
        lits = _plan.assertion_literals(tests[key].func)
        kinds = _plan.assertion_kinds(tests[key].func)
        covering = [k for k in sorted(kept or ()) if k in tests
                    and lits <= _plan.assertion_literals(tests[k].func)
                    and kinds <= _plan.assertion_kinds(tests[k].func)]
        if not covering:
            problems.append(f"{key}: среди сохраняемых тестов, убивающих "
                            f"{sorted(numbers)}, нет теста с его литералами "
                            f"{sorted(map(repr, lits))} и видами {sorted(kinds)}")
    assert not problems, "\n".join(problems)
