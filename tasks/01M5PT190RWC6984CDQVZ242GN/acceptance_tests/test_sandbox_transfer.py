"""AC-6, AC-7, AC-11: перенос песочницы и помощников — `tests/report_outcome_sandbox.py`
дословно со строк 54–606 исходного файла, `PytestSpy`/`pytest_output`/`FLAGS`
в `tests/test_report_outcome_module.py`, помощники — функции модуля.

Группа: разовый
Красен до реализации: tests/report_outcome_sandbox.py и tests/test_report_outcome_module.py на ветке ещё нет — чтение файлов из HEAD даёт None.

Новые файлы читаются из HEAD рабочей копии (`git show HEAD:…`), исходный —
из базы ветки (`_pult.DIFF_BASE`): на ветке он сведён к переходному модулю.
Сравнение статическое (`ast.dump`); подкласс `unittest.TestCase`
проверяется импортом в отдельном интерпретаторе рабочей копии. Докстринги
помощников в сравнение тела не входят.
"""
import ast
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _plan  # noqa: E402
from _pult import CODE_ROOT, DIFF_BASE, artifact_text  # noqa: E402


def _head_tree(path: str) -> ast.Module:
    text = _plan.show(CODE_ROOT, "HEAD", path)
    assert text is not None, f"{path} нет в HEAD ветки"
    return ast.parse(text)


def _base_tree() -> ast.Module:
    assert DIFF_BASE, "база диффа ветки задачи не определена при выкладке"
    text = _plan.show(CODE_ROOT, DIFF_BASE, _plan.SOURCE_FILE)
    assert text is not None, f"{_plan.SOURCE_FILE} нет в базе ветки {DIFF_BASE}"
    return ast.parse(text)


def _plan_text() -> str:
    plan = artifact_text("PLAN.md")
    assert plan is not None, "PLAN.md в ссылке документов задачи нет"
    return plan


def _top(tree, name: str) -> list:
    return [n for n in tree.body if name in _plan.bound_names(n)]


def _names(nodes) -> list:
    return [",".join(_plan.bound_names(n)) or type(n).__name__ for n in nodes]


# ------------------------------------------------------------------ AC-6

def test_ac6_sandbox_module_has_no_tests_and_one_line_docstring():
    """`tests/report_outcome_sandbox.py` есть, тестов не содержит, докстринг — одна строка.

    В модуле нет функций `test_*` первого уровня и классов с методами
    `test_*`; докстринг модуля есть, непуст и умещается в одну строку.

    Ловит мутацию: разработчик перенёс в модуль песочницы и тестовый класс
    `JunitReportOutcomeTest` (строки с :611) или оставил прежний
    многострочный докстринг исходного файла — класс или перенос строки
    найден, тест краснеет.
    """
    tree = _head_tree(_plan.SANDBOX_FILE)
    problems = [f"функция {n.name}" for n in _plan.module_tests(tree)]
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            methods = [i.name for i in node.body
                       if isinstance(i, (ast.FunctionDef, ast.AsyncFunctionDef))
                       and i.name.startswith("test")]
            if methods:
                problems.append(f"класс {node.name} с тестами {methods}")
    doc = ast.get_docstring(tree)
    assert doc and doc.strip(), f"у {_plan.SANDBOX_FILE} нет докстринга модуля"
    assert "\n" not in doc.strip(), f"докстринг модуля не в одну строку: {doc!r}"
    assert not problems, "тесты в модуле песочницы:\n" + "\n".join(problems)


def test_ac6_sandbox_statements_equal_source_lines_54_606_in_order():
    """Операторы верхнего уровня модуля песочницы — те же 50 и в том же порядке, `ast.dump` каждого равен исходному.

    Операторы верхнего уровня исходного файла базы, начинающиеся в строках
    54–606 (их 50: импорты, константы, функции, `Fake`, `writable`,
    `ReportSandbox`), сравниваются по `ast.dump` попарно и по порядку с
    операторами нового модуля после докстринга; число их совпадает.

    Ловит мутацию: при переносе выброшен неиспользуемый песочницей импорт
    `hashlib`/`tests.fd_wait`, или в `ReportSandbox.assert_unknown`
    поправлено утверждение — набор или дамп пары расходится, тест краснеет
    с именем оператора.
    """
    source = _plan.top_level(_base_tree(), _plan.SANDBOX_LINES)
    assert len(source) == _plan.SANDBOX_STATEMENTS, (
        f"в строках {_plan.SANDBOX_LINES} базы операторов {len(source)}, а "
        f"критерий называет {_plan.SANDBOX_STATEMENTS} — база прочитана не та")
    body = _plan.strip_docstring(_head_tree(_plan.SANDBOX_FILE).body)
    assert _names(body) == _names(source), (
        f"набор/порядок операторов расходится:\nновый: {_names(body)}\n"
        f"исходный: {_names(source)}")
    differ = [_names([s])[0] for s, b in zip(source, body)
              if ast.dump(s) != ast.dump(b)]
    assert not differ, "ast.dump расходится у операторов:\n" + "\n".join(differ)


def test_ac6_report_sandbox_is_testcase_subclass():
    """`ReportSandbox` модуля песочницы — подкласс `unittest.TestCase`.

    Импорт `tests.report_outcome_sandbox` в отдельном интерпретаторе рабочей
    копии проходит, `issubclass(ReportSandbox, unittest.TestCase)` истинно.

    Ловит мутацию: песочница переписана простым классом-стендом без
    `RealGitSandbox` (под фикстуру) — подкласс-инвариант
    `tests/test_invariants.py` теряет `TestCase`, тест краснеет.
    """
    code = ("import unittest, tests.report_outcome_sandbox as m; "
            "print(issubclass(m.ReportSandbox, unittest.TestCase))")
    res = subprocess.run([sys.executable, "-c", code], cwd=CODE_ROOT,
                         capture_output=True, text=True, timeout=110)
    assert res.returncode == 0, f"импорт модуля песочницы упал:\n{res.stderr[-3000:]}"
    assert res.stdout.strip() == "True", f"ReportSandbox не TestCase: {res.stdout!r}"


def test_ac6_plan_carries_ast_dump_check_of_sandbox():
    """В PLAN приведена сверка `ast.dump` переноса песочницы.

    В PLAN есть строка вне таблиц, где стоят `ast.dump` и имя
    `report_outcome_sandbox`.

    Ловит мутацию: роль перенесла песочницу, но сверку в PLAN не записала —
    строки нет, тест краснеет.
    """
    plan = _plan_text()
    assert any("ast.dump" in line and "report_outcome_sandbox" in line
               for line in _plan.prose_lines(plan)), (
        "в PLAN нет строки со сверкой ast.dump переноса report_outcome_sandbox")


# ------------------------------------------------------------------ AC-7

@pytest.mark.parametrize("name", ["PytestSpy", "pytest_output"])
def test_ac7_spy_and_output_verbatim_in_test_module(name):
    """`PytestSpy` и `pytest_output` — в тестовом модуле одним определением с `ast.dump`, равным исходному.

    Ловит мутацию: при переносе в `PytestSpy.run` поправлен разбор argv
    (или `pytest_output` оставлен в модуле песочницы) — определения нет
    либо дамп расходится, тест краснеет с именем.
    """
    source = _top(_base_tree(), name)
    assert len(source) == 1, f"{name} в базе исходного файла: {len(source)}"
    found = _top(_head_tree(_plan.NEW_FILE), name)
    assert len(found) == 1, f"{name} в {_plan.NEW_FILE}: определений {len(found)}"
    assert ast.dump(found[0]) == ast.dump(source[0]), (
        f"{name}: ast.dump не равен исходному")


def test_ac7_flags_module_constant_equal_to_class_attribute():
    """`FLAGS` — константа верхнего уровня тестового модуля, выражение равно `ArtelUnchangedTest.FLAGS`.

    В исходном классе `ArtelUnchangedTest` базы есть присваивание `FLAGS`;
    в новом модуле — одно присваивание верхнего уровня `FLAGS = …` с
    `ast.dump` значения, равным исходному.

    Ловит мутацию: `FLAGS` перенесён с литералом `timeout=120` вместо
    `stack.PER_TEST_TIMEOUT_SEC` (или оставлен атрибутом класса-обёртки) —
    выражение расходится либо константы нет, тест краснеет.
    """
    cls = [n for n in _base_tree().body
           if isinstance(n, ast.ClassDef) and n.name == "ArtelUnchangedTest"]
    assert cls, "ArtelUnchangedTest нет в базе исходного файла"
    source = [n for n in cls[0].body if isinstance(n, ast.Assign)
              and [ast.unparse(t) for t in n.targets] == ["FLAGS"]]
    assert len(source) == 1, "ArtelUnchangedTest.FLAGS нет в базе"
    found = [n for n in _head_tree(_plan.NEW_FILE).body
             if isinstance(n, (ast.Assign, ast.AnnAssign))
             and "FLAGS" in _plan.bound_names(n)]
    assert len(found) == 1, f"FLAGS верхнего уровня в {_plan.NEW_FILE}: {len(found)}"
    assert ast.dump(found[0].value) == ast.dump(source[0].value), (
        f"FLAGS: {ast.unparse(found[0].value)} ≠ {ast.unparse(source[0].value)}")


# ------------------------------------------------------------------ AC-11

def _check_helper(func, source) -> list:
    problems = []
    if not func.args.args:
        return [f"{func.name}: нет первого параметра (стенда)"]
    param = func.args.args[0].arg
    if _plan.rest_args_dump(func.args, True) != _plan.rest_args_dump(source.args, True):
        problems.append(f"{func.name}: параметры после стенда не совпадают с исходными")
    if _plan.body_dump(func) != _plan.expected_helper_body(source, param):
        problems.append(f"{func.name}: тело не равно исходному с заменой self. → {param}")
    return problems


@pytest.mark.parametrize("name", sorted(_plan.HELPERS))
def test_ac11_helper_is_module_function_with_verbatim_body(name):
    """Помощник — функция модуля нового файла: первый параметр — стенд, тело — исходное с `self.` → стенд.

    `ReportSandbox.assert_unknown`, `ResultKeyTest.key_case`,
    `ArtelUnchangedTest.main_head` переводятся: `self` → имя первого
    параметра функции. Функция модуля того же имени есть, прочие параметры
    совпадают с исходными, `ast.dump` тела (без докстринга) равен
    переведённому.

    Ловит мутацию: в `key_case` утверждение «дерево клона не снято»
    переписано как `assert tree is not None` (или выброшено) — дамп тела
    расходится, тест краснеет с именем помощника.
    """
    cls, method = _plan.HELPERS[name]
    source = _plan.class_method(_base_tree(), cls, method)
    assert source is not None, f"{cls}.{method} нет в базе исходного файла"
    funcs = _plan.module_functions(_head_tree(_plan.NEW_FILE))
    assert name in funcs, f"функции модуля {name} в {_plan.NEW_FILE} нет"
    problems = _check_helper(funcs[name], source)
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("cls,method", [list(p) for p in _plan.PREFIXED])
def test_ac11_colliding_helper_carries_class_prefix(cls, method):
    """Помощник с совпадающим именем — функция модуля с префиксом бывшего класса и дословным телом.

    Для `VitestReporterTest.full_vitest`, `InstallAndDepsTest.full_vitest`
    и `ArtelUnchangedTest.channels` в новом файле есть ровно одна функция
    модуля, имя которой — имя метода с непустым префиксом своего класса
    (префикс без подчёркиваний и регистра входит в имя класса), а тело и
    параметры — исходные с `self.` → стенд; функции модуля с голым именем
    метода нет.

    Ловит мутацию: свод оставил одну функцию `full_vitest` (тело
    `VitestReporterTest`) для обоих классов или назвал `channels` голым
    именем, переименовав локальную переменную теста, — функции с
    префиксом нет или голое имя найдено, тест краснеет.
    """
    source = _plan.class_method(_base_tree(), cls, method)
    assert source is not None, f"{cls}.{method} нет в базе исходного файла"
    funcs = _plan.module_functions(_head_tree(_plan.NEW_FILE))
    assert method not in funcs, f"функция модуля с голым именем {method} есть"
    matches = [f for name, f in funcs.items() if _plan.class_prefixed(name, method, cls)]
    assert len(matches) == 1, (f"функций модуля «<префикс {cls}>{method}»: "
                               f"{[f.name for f in matches]}")
    problems = _check_helper(matches[0], source)
    assert not problems, "\n".join(problems)


def test_ac11_helpers_called_by_bare_name_and_absent_from_sandbox_module():
    """Помощники зовутся голым именем, локальные переменные не переименованы, в модуле песочницы их нет.

    В тестовых функциях нового файла нет вызовов `<что-то>.<помощник>(…)`
    для `assert_unknown`, `key_case`, `main_head`, `full_vitest`,
    `channels`; каждая функция-помощник вызывается голым именем хотя бы
    раз; в тестах есть присваивание `clone, channels = <…>(…)` (локальная
    переменная `channels` сохранена); в `tests/report_outcome_sandbox.py`
    функций модуля с именами помощников нет.

    Ловит мутацию: тест зовёт `box.assert_unknown(run, out)` метода
    песочницы вместо функции модуля `assert_unknown(box, …)` — вызов
    атрибута найден, тест краснеет со строкой.
    """
    tree = _head_tree(_plan.NEW_FILE)
    funcs = _plan.module_functions(tree)
    helpers = set(_plan.HELPERS) | {
        name for cls, method in _plan.PREFIXED for name in funcs
        if _plan.class_prefixed(name, method, cls)}
    by_attr, by_name, local_channels = [], set(), False
    for func in _plan.module_tests(tree):
        for sub in ast.walk(func):
            if isinstance(sub, ast.Call):
                if isinstance(sub.func, ast.Attribute) and \
                        sub.func.attr in set(_plan.HELPER_METHODS) | helpers:
                    by_attr.append(f"{func.name}, строка {sub.lineno}: "
                                   f"{ast.unparse(sub.func)}(…)")
                elif isinstance(sub.func, ast.Name) and sub.func.id in helpers:
                    by_name.add(sub.func.id)
            if isinstance(sub, ast.Assign) and any(
                    isinstance(t, ast.Tuple) and [ast.unparse(e) for e in t.elts]
                    == ["clone", "channels"] for t in sub.targets):
                local_channels = True
    assert not by_attr, "помощники вызваны методом стенда:\n" + "\n".join(by_attr)
    uncalled = sorted(helpers - by_name)
    assert not uncalled, f"помощники ни разу не вызваны голым именем: {uncalled}"
    assert local_channels, "локальной переменной `clone, channels = …` в тестах нет"
    in_sandbox = sorted(set(_plan.HELPER_METHODS) & set(
        _plan.module_functions(_head_tree(_plan.SANDBOX_FILE))))
    assert not in_sandbox, f"помощники — функции модуля песочницы: {in_sandbox}"


def test_ac11_plan_lists_renames():
    """PLAN перечисляет переименования помощников с префиксом бывшего класса.

    Имя каждой функции модуля нового файла с префиксом бывшего класса
    (`full_vitest` обоих классов, `channels`) встречается в PLAN.

    Ловит мутацию: роль переименовала `channels` в
    `artel_unchanged_channels`, но в перечне PLAN назвала только
    `full_vitest` — имени нет, тест краснеет с ним.
    """
    plan = _plan_text()
    funcs = _plan.module_functions(_head_tree(_plan.NEW_FILE))
    renamed = sorted(name for cls, method in _plan.PREFIXED for name in funcs
                     if _plan.class_prefixed(name, method, cls))
    assert len(renamed) == len(_plan.PREFIXED), (
        f"функций с префиксом класса в новом файле: {renamed}")
    missing = [name for name in renamed if name not in plan]
    assert not missing, "переименования не перечислены в PLAN: " + ", ".join(missing)
