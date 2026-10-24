"""AC-5, AC-7, AC-9: перенос песочниц и помощников — `tests/outcome_gate_sandbox.py`
дословно со строк 47–899 исходного файла, `IdOutcomeGateSandbox` в
`tests/test_outcome_gate_module.py` с тремя переименованиями, помощники с
утверждениями — функции модуля.

Группа: разовый
Красен до реализации: tests/outcome_gate_sandbox.py и tests/test_outcome_gate_module.py на ветке ещё нет — чтение файлов из HEAD даёт None.

Новые файлы читаются из HEAD рабочей копии (`git show HEAD:…`), исходные —
из базы ветки (`_pult.DIFF_BASE`): после свода их на ветке нет. Сравнение
статическое (`ast.dump`): тест ничего не исполняет. Докстринги помощников
в сравнение тела не входят; переименование (`GATE_ACTIONS` →
`ID_GATE_ACTIONS`, `VITEST_KIND` → `ID_VITEST_KIND`, `spec_text` →
`id_spec_text`) применяется к именам (`Name`) и имени определения,
атрибуты и импорты не трогает.
"""
import ast
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _plan  # noqa: E402
from _pult import CODE_ROOT, DIFF_BASE, artifact_text  # noqa: E402

_IMPORTS = (ast.Import, ast.ImportFrom)


def _head_tree(path: str) -> ast.Module:
    text = _plan.show(CODE_ROOT, "HEAD", path)
    assert text is not None, f"{path} нет в HEAD ветки"
    return ast.parse(text)


def _base_tree(path: str) -> ast.Module:
    assert DIFF_BASE, "база диффа ветки задачи не определена при выкладке"
    text = _plan.show(CODE_ROOT, DIFF_BASE, path)
    assert text is not None, f"{path} нет в базе ветки {DIFF_BASE}"
    return ast.parse(text)


def _plan_text() -> str:
    plan = artifact_text("PLAN.md")
    assert plan is not None, "PLAN.md в ссылке документов задачи нет"
    return plan


def _bindings(tree) -> dict:
    """{имя: [утверждения верхнего уровня, связывающие его]}."""
    found = {}
    for node in tree.body:
        for name in _plan.bound_names(node):
            found.setdefault(name, []).append(node)
    return found


# ------------------------------------------------------------------ AC-5

def test_ac5_sandbox_module_has_no_tests_and_one_line_docstring():
    """`tests/outcome_gate_sandbox.py` есть, тестов не содержит, докстринг — одна строка.

    В модуле нет функций `test_*` первого уровня и классов с методами
    `test_*`; докстринг модуля есть, непуст и умещается в одну строку.

    Ловит мутацию: разработчик перенёс в модуль песочницы и тестовый класс
    `Ac1OutOfBoundsTest` (строки с :904) или оставил прежний многострочный
    докстринг исходного файла — класс или перенос строки найден, тест
    краснеет.
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


def test_ac5_sandbox_definitions_equal_source_lines_47_899_in_order():
    """Определения верхнего уровня модуля песочницы — те же и в том же порядке, `ast.dump` каждого равен исходному.

    Утверждения верхнего уровня исходного файла, начинающиеся в строках
    47–899 (импорты, константы, функции, `RunnerProc`,
    `OutcomeGateSandbox`), сравниваются по `ast.dump` попарно и по порядку
    с утверждениями нового модуля после докстринга; число их совпадает.

    Ловит мутацию: при переносе в `OutcomeGateSandbox.refusal` поправлено
    утверждение (или выброшен `TASKS_DIR`, или порядок констант изменён) —
    дамп пары расходится, тест краснеет с именем определения.
    """
    source = _plan.top_level(_base_tree(_plan.OUTCOME_FILE), _plan.SANDBOX_LINES)
    tree = _head_tree(_plan.SANDBOX_FILE)
    body = _plan.strip_docstring(tree.body)
    names = lambda nodes: [",".join(_plan.bound_names(n)) or type(n).__name__
                           for n in nodes]
    assert names(body) == names(source), (
        f"набор/порядок определений расходится:\nновый: {names(body)}\n"
        f"исходный: {names(source)}")
    differ = [names([s])[0] for s, b in zip(source, body)
              if ast.dump(s) != ast.dump(b)]
    assert not differ, "ast.dump расходится у определений:\n" + "\n".join(differ)


def test_ac5_plan_carries_ast_dump_check_of_sandbox():
    """В PLAN приведена сверка `ast.dump` переноса песочницы.

    В PLAN есть строка вне таблиц, где стоят `ast.dump` и имя
    `outcome_gate_sandbox`.

    Ловит мутацию: роль перенесла песочницу, но сверку в PLAN не записала —
    строки нет, тест краснеет.
    """
    plan = _plan_text()
    assert any("ast.dump" in line and "outcome_gate_sandbox" in line
               for line in _plan.prose_lines(plan)), (
        "в PLAN нет строки со сверкой ast.dump переноса outcome_gate_sandbox")


# ------------------------------------------------------------------ AC-7

def test_ac7_id_sandbox_definitions_verbatim_with_three_renames():
    """`IdOutcomeGateSandbox`, её константы и функции (строки 47–516) — в новом файле дословно с тремя переименованиями.

    Каждое неимпортное определение верхнего уровня строк 47–516
    id-файла, кроме 17 имён, совпадающих с модулем песочницы, после
    переименования (`GATE_ACTIONS` → `ID_GATE_ACTIONS`, `VITEST_KIND` →
    `ID_VITEST_KIND`, `spec_text` → `id_spec_text` с употреблениями)
    находится в новом файле ровно одним определением своего (нового) имени
    с равным `ast.dump`.

    Ловит мутацию: в теле `IdOutcomeGateSandbox.no_gate_refusal` оставлен
    `GATE_ACTIONS` (значение outcome-песочницы) вместо `ID_GATE_ACTIONS`,
    или `spec_text(tid, n)` в `in_dev_task` не переименован — дамп класса
    расходится, тест краснеет с именем.
    """
    source = _plan.top_level(_base_tree(_plan.ID_FILE), _plan.ID_LINES)
    binds = _bindings(_head_tree(_plan.NEW_FILE))
    problems = []
    for node in source:
        if isinstance(node, _IMPORTS):
            continue
        names = _plan.bound_names(node)
        if set(names) & set(_plan.SHARED_NAMES):
            continue
        want = _plan.renamed(node)
        new_name = _plan.bound_names(want)[0]
        found = binds.get(new_name, [])
        if len(found) != 1:
            problems.append(f"{new_name}: определений в новом файле "
                            f"{len(found)}, ожидалось 1")
        elif ast.dump(found[0]) != ast.dump(want):
            problems.append(f"{new_name}: ast.dump не равен исходному с "
                            f"переименованием")
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("old", sorted(_plan.RENAMES))
def test_ac7_old_names_of_renamed_not_bound_to_id_definitions(old):
    """Имя до переименования не связано в новом файле с определением id-песочницы.

    Определение `GATE_ACTIONS`/`VITEST_KIND`/`spec_text` верхнего уровня
    нового файла не равно по `ast.dump` определению id-файла под прежним
    именем (импорт из `tests.outcome_gate_sandbox` под прежним именем
    законен).

    Ловит мутацию: разработчик оставил `VITEST_KIND = {...}` id-файла под
    прежним именем (затенив импорт из песочницы) — определение найдено,
    тест краснеет с именем.
    """
    source = [n for n in _plan.top_level(_base_tree(_plan.ID_FILE), _plan.ID_LINES)
              if old in _plan.bound_names(n)]
    assert source, f"{old} нет в строках {_plan.ID_LINES} базы {_plan.ID_FILE}"
    binds = _bindings(_head_tree(_plan.NEW_FILE)).get(old, [])
    bad = [n.lineno for n in binds if ast.dump(n) == ast.dump(source[0])]
    assert not bad, (f"{old}: определение id-файла под прежним именем в "
                     f"строках {bad} нового файла")


def test_ac7_shared_names_bound_once_by_copy_or_import():
    """Каждое из 17 совпадающих имён определено в новом файле один раз — копией или импортом.

    Для каждого имени: ровно одно связывание верхнего уровня; это либо
    импорт из `tests.outcome_gate_sandbox` без переименования, либо
    определение с `ast.dump`, равным определению id-файла.

    Ловит мутацию: `ulid` и скопирован, и импортирован из песочницы (или
    `CLAIM` переименован в `ID_CLAIM`) — связываний два или ноль, тест
    краснеет с именем.
    """
    source = {}
    for node in _plan.top_level(_base_tree(_plan.ID_FILE), _plan.ID_LINES):
        for name in _plan.bound_names(node):
            source[name] = node
    binds = _bindings(_head_tree(_plan.NEW_FILE))
    problems = []
    for name in _plan.SHARED_NAMES:
        found = binds.get(name, [])
        if len(found) != 1:
            problems.append(f"{name}: связываний {len(found)}, ожидалось 1")
            continue
        node = found[0]
        if isinstance(node, ast.ImportFrom):
            alias = [a for a in node.names if (a.asname or a.name) == name]
            if node.module != _plan.NEW_MODULE or alias[0].name != name:
                problems.append(f"{name}: импорт не из {_plan.NEW_MODULE} "
                                f"или с переименованием")
        elif name not in source or ast.dump(node) != ast.dump(source[name]):
            problems.append(f"{name}: копия не равна определению id-файла")
    assert not problems, "\n".join(problems)


def test_ac7_two_sandboxes_not_merged():
    """Песочницы не объединены: `IdOutcomeGateSandbox` — в новом файле, `OutcomeGateSandbox` — только в модуле песочницы.

    В новом файле нет определения класса `OutcomeGateSandbox`, в модуле
    песочницы нет `IdOutcomeGateSandbox`; база `IdOutcomeGateSandbox` в
    новом файле — `GitignoreCommittedRealGitSandbox`.

    Ловит мутацию: `IdOutcomeGateSandbox` переписан наследником
    `OutcomeGateSandbox` — база класса другая, тест краснеет.
    """
    new = _head_tree(_plan.NEW_FILE)
    sandbox = _head_tree(_plan.SANDBOX_FILE)
    classes = {n.name: n for n in new.body if isinstance(n, ast.ClassDef)}
    assert "OutcomeGateSandbox" not in classes, (
        "OutcomeGateSandbox определён в новом файле")
    assert not any(isinstance(n, ast.ClassDef) and n.name == "IdOutcomeGateSandbox"
                   for n in sandbox.body), (
        "IdOutcomeGateSandbox определён в модуле песочницы")
    assert "IdOutcomeGateSandbox" in classes, "IdOutcomeGateSandbox нет в новом файле"
    bases = [ast.unparse(b) for b in classes["IdOutcomeGateSandbox"].bases]
    assert bases == ["GitignoreCommittedRealGitSandbox"], (
        f"база IdOutcomeGateSandbox: {bases}")


def test_ac7_plan_lists_renames_and_choice_for_shared_names():
    """PLAN перечисляет три переименования и выбор по каждому из 17 совпадающих имён.

    В PLAN встречаются новые имена `ID_GATE_ACTIONS`, `ID_VITEST_KIND`,
    `id_spec_text` и каждое из 17 совпадающих имён.

    Ловит мутацию: роль записала в PLAN переименования, но не выбор
    «копия/импорт» по совпадающим именам (`MATRIX_HEADERS` не упомянут) —
    имени нет, тест краснеет с ним.
    """
    plan = _plan_text()
    missing = [n for n in (*_plan.RENAMES.values(), *_plan.SHARED_NAMES)
               if n not in plan]
    assert not missing, "имена не упомянуты в PLAN: " + ", ".join(missing)


# ------------------------------------------------------------------ AC-9

@pytest.mark.parametrize("name", sorted(_plan.HELPERS))
def test_ac9_helper_is_module_function_with_verbatim_body(name):
    """Помощник — функция модуля нового файла: первый параметр — стенд, тело — исходное с `self.` → стенд.

    Исходный метод (`OutcomeGateSandbox.refusal`/`no_gate_refusal`,
    `Ac1OutOfBoundsTest.assert_no_gate`, `Ac4PrepareTest.assert_prepare`/
    `prepared`, `Ac11MandateTest.broken_task`,
    `IdOutcomeGateSandbox.gate_refusal`/`no_gate_refusal` →
    `id_no_gate_refusal`) переводится: `self` → имя первого параметра
    функции; `self.<помощник перечня>(…)` → `<функция>(<стенд>, …)`; в
    помощниках id-песочницы — ещё и три переименования. Функция модуля
    `name` есть, прочие параметры совпадают с исходными, `ast.dump` тела
    (без докстринга) равен переведённому.

    Ловит мутацию: в `assert_prepare` оставлен `t.refusal(rows, …)`
    вместо `refusal(t, rows, …)`, или в `id_no_gate_refusal` оставлен
    `GATE_ACTIONS` вместо `ID_GATE_ACTIONS` — дамп тела расходится, тест
    краснеет с именем помощника.
    """
    path, cls, method = _plan.HELPERS[name]
    source = _plan.class_method(_base_tree(path), cls, method)
    assert source is not None, f"{cls}.{method} нет в базе {path}"
    funcs = _plan.module_functions(_head_tree(_plan.NEW_FILE))
    assert name in funcs, f"функции модуля {name} в {_plan.NEW_FILE} нет"
    func = funcs[name]
    assert func.args.args, f"{name}: нет первого параметра (стенда)"
    param = func.args.args[0].arg
    is_id = path == _plan.ID_FILE
    calls = _plan.ID_HELPER_CALLS if is_id else _plan.OUTCOME_HELPER_CALLS
    mapping = _plan.RENAMES if is_id else None
    assert _plan.rest_args_dump(func.args, True) == \
        _plan.rest_args_dump(source.args, True), (
        f"{name}: параметры после стенда не совпадают с {cls}.{method}")
    assert _plan.body_dump(func) == _plan.expected_helper_body(
        source, param, calls, mapping), (
        f"{name}: тело не равно телу {cls}.{method} с заменой self. → {param}")


def test_ac9_helpers_called_by_bare_name_and_absent_from_sandbox_module():
    """Помощники зовутся голым именем и не лежат функциями модуля песочницы.

    В новом файле вне класса `IdOutcomeGateSandbox` нет вызовов
    `<что-то>.<помощник>(…)` для имён перечня (`refusal`,
    `no_gate_refusal`, `assert_no_gate`, `assert_prepare`, `prepared`,
    `broken_task`, `gate_refusal`, `id_no_gate_refusal`); каждый помощник
    вызывается голым именем хотя бы раз; в `tests/outcome_gate_sandbox.py`
    функций модуля с этими именами нет.

    Ловит мутацию: тест зовёт `box.refusal(rows, output, OUTCOME_ACTION)`
    метода песочницы вместо функции модуля `refusal(box, …)` — вызов
    атрибута найден, тест краснеет со строкой.
    """
    tree = _head_tree(_plan.NEW_FILE)
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
    in_sandbox = sorted(helpers & set(_plan.module_functions(
        _head_tree(_plan.SANDBOX_FILE))))
    assert not in_sandbox, f"помощники — функции модуля песочницы: {in_sandbox}"
