"""AC-5, AC-6, AC-8, AC-10: перенос песочниц и помощников — строки 47–899
`outcome_gate` дословно в `tests/outcome_gate_sandbox.py` и одна инструкция
импорта на их месте, `IdOutcomeGateSandbox` в `tests/test_outcome_gate_module.py`
с тремя переименованиями, помощники с утверждениями — функции модуля.

Группа: разовый
Красен до реализации: tests/outcome_gate_sandbox.py и tests/test_outcome_gate_module.py на ветке ещё нет, outcome_gate несёт песочницу сам — чтение новых файлов из HEAD даёт None.

Новые и изменённые файлы читаются из HEAD рабочей копии (`git show HEAD:…`),
исходные — из базы ветки (`_pult.DIFF_BASE`). Сравнение статическое
(`ast.dump`, построчное сравнение текста): тест ничего не исполняет.
Докстринги помощников в сравнение тела не входят; переименование
(`GATE_ACTIONS` → `ID_GATE_ACTIONS`, `VITEST_KIND` → `ID_VITEST_KIND`,
`spec_text` → `id_spec_text`) применяется к именам (`Name`) и имени
определения, атрибуты и импорты не трогает.
"""
import ast
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _plan  # noqa: E402
from _pult import CODE_ROOT, DIFF_BASE, artifact_text  # noqa: E402

_IMPORTS = (ast.Import, ast.ImportFrom)


def _head_text(path: str) -> str:
    text = _plan.show(CODE_ROOT, "HEAD", path)
    assert text is not None, f"{path} нет в HEAD ветки"
    return text


def _base_text(path: str) -> str:
    assert DIFF_BASE, "база диффа ветки задачи не определена при выкладке"
    text = _plan.show(CODE_ROOT, DIFF_BASE, path)
    assert text is not None, f"{path} нет в базе ветки {DIFF_BASE}"
    return text


def _head_tree(path: str) -> ast.Module:
    return ast.parse(_head_text(path))


def _base_tree(path: str) -> ast.Module:
    return ast.parse(_base_text(path))


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


def _same_in_outcome_sandbox() -> set:
    """Имена определений id-файла, чей `ast.dump` равен одноимённому
    определению строк 47–899 `outcome_gate` базы (одинаковый код)."""
    outcome = {}
    for node in _plan.top_level(_base_tree(_plan.OUTCOME_FILE), _plan.SANDBOX_LINES):
        for name in _plan.bound_names(node):
            outcome[name] = ast.dump(node)
    same = set()
    for node in _plan.top_level(_base_tree(_plan.ID_FILE), _plan.ID_LINES):
        names = _plan.bound_names(node)
        if len(names) == 1 and outcome.get(names[0]) == ast.dump(node):
            same.add(names[0])
    return same


def _word(name: str, text: str) -> bool:
    return re.search(rf"(?<![\w.]){re.escape(name)}(?!\w)", text) is not None


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


def test_ac5_sandbox_statements_equal_source_lines_47_899_in_order():
    """Операторы верхнего уровня модуля песочницы — те же и в том же порядке, `ast.dump` каждого равен исходному.

    Операторы верхнего уровня исходного `outcome_gate` базы, начинающиеся
    в строках 47–899 (импорты, константы, функции, `RunnerProc`,
    `OutcomeGateSandbox`), сравниваются по `ast.dump` попарно и по порядку
    с операторами нового модуля после докстринга; число их совпадает.

    Ловит мутацию: при переносе в `OutcomeGateSandbox.refusal` поправлено
    утверждение (или выброшен `TASKS_DIR`, или порядок констант изменён) —
    дамп пары расходится, тест краснеет с именем оператора.
    """
    source = _plan.top_level(_base_tree(_plan.OUTCOME_FILE), _plan.SANDBOX_LINES)
    body = _plan.strip_docstring(_head_tree(_plan.SANDBOX_FILE).body)

    def names(nodes):
        return [",".join(_plan.bound_names(n)) or type(n).__name__ for n in nodes]

    assert names(body) == names(source), (
        f"набор/порядок операторов расходится:\nновый: {names(body)}\n"
        f"исходный: {names(source)}")
    differ = [names([s])[0] for s, b in zip(source, body)
              if ast.dump(s) != ast.dump(b)]
    assert not differ, "ast.dump расходится у операторов:\n" + "\n".join(differ)


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


# ------------------------------------------------------------------ AC-6

def test_ac6_outcome_gate_lines_47_899_replaced_by_one_import_of_27_names():
    """В `outcome_gate` на месте строк 47–899 — одна инструкция импорта 27 имён; докстринг и строки 900–2493 не изменены.

    На HEAD строки 1–46 файла равны строкам базы; оператор, начинающийся
    в строке 47, — `from tests.outcome_gate_sandbox import (…)` ровно с 27
    именами требования 7 (без `as`); строки после его конца равны строкам
    900–2493 базы построчно; других импортов из `tests.outcome_gate_sandbox`
    в файле нет.

    Ловит мутацию: разработчик импортировал заодно `spec_text` (28 имён),
    оставил в файле `import os` рядом с импортом или поправил тестовый
    класс после строки 900 — список имён или строки расходятся, тест
    краснеет.
    """
    base_lines = _base_text(_plan.OUTCOME_FILE).splitlines()
    head = _head_text(_plan.OUTCOME_FILE)
    head_lines = head.splitlines()
    last = _plan.OUTCOME_DOC_LAST
    assert head_lines[:last] == base_lines[:last], (
        f"строки 1–{last} (докстринг) {_plan.OUTCOME_FILE} изменены")
    tree = ast.parse(head)
    at_47 = [n for n in tree.body if n.lineno == last + 1]
    assert at_47 and isinstance(at_47[0], ast.ImportFrom) \
        and at_47[0].module == _plan.NEW_MODULE, (
        f"в строке {last + 1} {_plan.OUTCOME_FILE} не инструкция "
        f"from {_plan.NEW_MODULE} import (…)")
    node = at_47[0]
    names = [a.name for a in node.names]
    aliased = [a.name for a in node.names if a.asname]
    assert not aliased, f"имена импорта с переименованием: {aliased}"
    assert len(names) == len(_plan.OUTCOME_IMPORT_NAMES) and \
        set(names) == set(_plan.OUTCOME_IMPORT_NAMES), (
        f"имена импорта {sorted(names)} ≠ 27 именам требования 7 "
        f"{sorted(_plan.OUTCOME_IMPORT_NAMES)}")
    others = [n.lineno for n in tree.body if isinstance(n, ast.ImportFrom)
              and n.module == _plan.NEW_MODULE and n is not node]
    assert not others, f"ещё импорты из {_plan.NEW_MODULE} в строках {others}"
    end = _plan.SANDBOX_LINES[1]
    assert head_lines[node.end_lineno:] == base_lines[end:], (
        f"строки {_plan.OUTCOME_FILE} после импорта не равны строкам "
        f"{end + 1}–{len(base_lines)} базы")


def test_ac6_plan_lists_27_import_names():
    """В PLAN перечислены все 27 имён импорта `outcome_gate`.

    Каждое из 27 имён требования 7 встречается в PLAN отдельным словом.

    Ловит мутацию: роль записала в PLAN перечень без констант действий
    (`REWORK_ACTION`, `TEXT_GATE_SKIP` не упомянуты) — имени нет, тест
    краснеет с ним.
    """
    plan = _plan_text()
    missing = [n for n in _plan.OUTCOME_IMPORT_NAMES if not _word(n, plan)]
    assert not missing, "имена импорта не упомянуты в PLAN: " + ", ".join(missing)


# ------------------------------------------------------------------ AC-8

def test_ac8_id_sandbox_definitions_verbatim_with_three_renames():
    """`IdOutcomeGateSandbox`, её константы и функции (строки 53–516) — в новом файле дословно с тремя переименованиями.

    Каждый оператор верхнего уровня строк 53–516 id-файла базы после
    переименования (`GATE_ACTIONS` → `ID_GATE_ACTIONS`, `VITEST_KIND` →
    `ID_VITEST_KIND`, `spec_text` → `id_spec_text` с употреблениями)
    связан в новом файле ровно одним оператором своего (нового) имени с
    равным `ast.dump`. Имя, чьё определение в id-файле по `ast.dump` равно
    одноимённому определению песочницы `outcome_gate` (одинаковый код),
    может вместо копии прийти импортом из `tests.outcome_gate_sandbox` без
    переименования.

    Ловит мутацию: в теле `IdOutcomeGateSandbox.no_gate_refusal` оставлен
    `GATE_ACTIONS` вместо `ID_GATE_ACTIONS`, или `spec_text(...)` в
    `in_dev_task` не переименован, или `HINT` переписан — дамп расходится,
    тест краснеет с именем.
    """
    source = _plan.top_level(_base_tree(_plan.ID_FILE), _plan.ID_LINES)
    binds = _bindings(_head_tree(_plan.NEW_FILE))
    same = _same_in_outcome_sandbox()
    problems = []
    for node in source:
        if isinstance(node, _IMPORTS):
            continue
        want = _plan.renamed(node)
        new_name = _plan.bound_names(want)[0]
        found = binds.get(new_name, [])
        if len(found) != 1:
            problems.append(f"{new_name}: связываний в новом файле "
                            f"{len(found)}, ожидалось 1")
            continue
        got = found[0]
        if isinstance(got, ast.ImportFrom) and new_name in same:
            alias = [a for a in got.names if (a.asname or a.name) == new_name]
            if got.module != _plan.NEW_MODULE or alias[0].name != new_name:
                problems.append(f"{new_name}: импорт не из {_plan.NEW_MODULE} "
                                f"или с переименованием")
        elif ast.dump(got) != ast.dump(want):
            problems.append(f"{new_name}: ast.dump не равен исходному с "
                            f"переименованием")
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("old", ["GATE_ACTIONS", "VITEST_KIND", "spec_text"])
def test_ac8_old_names_of_renamed_not_bound_to_id_definitions(old):
    """Имя до переименования не связано в новом файле с определением id-песочницы.

    Определение `GATE_ACTIONS`/`VITEST_KIND`/`spec_text` верхнего уровня
    нового файла не равно по `ast.dump` определению id-файла под прежним
    именем.

    Ловит мутацию: разработчик оставил `VITEST_KIND = {...}` id-файла под
    прежним именем и добавил копию `ID_VITEST_KIND` — определение найдено,
    тест краснеет с именем.
    """
    source = [n for n in _plan.top_level(_base_tree(_plan.ID_FILE), _plan.ID_LINES)
              if old in _plan.bound_names(n)]
    assert source, f"{old} нет в строках {_plan.ID_LINES} базы {_plan.ID_FILE}"
    binds = _bindings(_head_tree(_plan.NEW_FILE)).get(old, [])
    bad = [n.lineno for n in binds if ast.dump(n) == ast.dump(source[0])]
    assert not bad, (f"{old}: определение id-файла под прежним именем в "
                     f"строках {bad} нового файла")


def test_ac8_two_sandboxes_not_merged():
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


def test_ac8_plan_lists_renames():
    """PLAN перечисляет три переименования — прежние и новые имена.

    В PLAN встречаются отдельными словами `GATE_ACTIONS`, `VITEST_KIND`,
    `spec_text` и `ID_GATE_ACTIONS`, `ID_VITEST_KIND`, `id_spec_text`.

    Ловит мутацию: роль записала в PLAN только `ID_GATE_ACTIONS`, а
    переименование `spec_text` → `id_spec_text` не назвала — имени нет,
    тест краснеет с ним.
    """
    plan = _plan_text()
    missing = [n for pair in _plan.RENAMES.items() for n in pair
               if not _word(n, plan)]
    assert not missing, "имена переименований не упомянуты в PLAN: " + ", ".join(missing)


# ------------------------------------------------------------------ AC-10

@pytest.mark.parametrize("name", ["gate_refusal", "id_no_gate_refusal"])
def test_ac10_helper_is_module_function_with_verbatim_body(name):
    """Помощник — функция модуля нового файла: первый параметр — стенд, тело — исходное с `self.` → стенд.

    Исходный метод (`IdOutcomeGateSandbox.gate_refusal` → `gate_refusal`,
    `IdOutcomeGateSandbox.no_gate_refusal` → `id_no_gate_refusal`)
    переводится: `self` → имя первого параметра функции, три
    переименования. Функция модуля `name` есть, прочие параметры совпадают
    с исходными, `ast.dump` тела (без докстринга) равен переведённому.

    Ловит мутацию: в `id_no_gate_refusal` оставлен `GATE_ACTIONS` вместо
    `ID_GATE_ACTIONS` (перебор чужих действий), или в `gate_refusal`
    ослаблено `assertEqual(…, "in_dev", …)` — дамп тела расходится, тест
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
    assert _plan.rest_args_dump(func.args, True) == \
        _plan.rest_args_dump(source.args, True), (
        f"{name}: параметры после стенда не совпадают с {cls}.{method}")
    assert _plan.body_dump(func) == _plan.expected_helper_body(
        source, param, _plan.ID_HELPER_CALLS, _plan.RENAMES), (
        f"{name}: тело не равно телу {cls}.{method} с заменой self. → {param}")


def test_ac10_id_no_gate_refusal_reads_id_gate_actions():
    """Тело `id_no_gate_refusal` читает `ID_GATE_ACTIONS`, а не `GATE_ACTIONS`.

    Ловит мутацию: функция модуля перебирает `GATE_ACTIONS` (импорт из
    песочницы `outcome_gate`, другие действия) — имени `ID_GATE_ACTIONS` в
    теле нет, тест краснеет.
    """
    funcs = _plan.module_functions(_head_tree(_plan.NEW_FILE))
    assert "id_no_gate_refusal" in funcs, (
        f"функции модуля id_no_gate_refusal в {_plan.NEW_FILE} нет")
    used = {n.id for n in ast.walk(funcs["id_no_gate_refusal"])
            if isinstance(n, ast.Name)}
    assert "ID_GATE_ACTIONS" in used, "id_no_gate_refusal не читает ID_GATE_ACTIONS"
    assert "GATE_ACTIONS" not in used, "id_no_gate_refusal читает GATE_ACTIONS"


def test_ac10_helpers_called_by_bare_name_outside_sandbox_class():
    """Тесты зовут помощников голым именем, не методом стенда.

    В новом файле вне класса `IdOutcomeGateSandbox` нет вызовов
    `<что-то>.gate_refusal(…)`/`.no_gate_refusal(…)`/
    `.id_no_gate_refusal(…)`; `gate_refusal` и `id_no_gate_refusal`
    вызываются голым именем хотя бы раз; в `tests/outcome_gate_sandbox.py`
    функций модуля с этими именами нет.

    Ловит мутацию: тест `HintTest` перенесён с вызовом
    `id_box.gate_refusal(rows, output)` метода песочницы — guard не видит
    утверждения помощника; вызов атрибута найден, тест краснеет со
    строкой.
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
            if isinstance(sub.func, ast.Attribute) and \
                    sub.func.attr in helpers | {"no_gate_refusal"}:
                by_attr.append(f"строка {sub.lineno}: {ast.unparse(sub.func)}(…)")
            elif isinstance(sub.func, ast.Name) and sub.func.id in helpers:
                by_name.add(sub.func.id)
    assert not by_attr, "помощники вызваны методом стенда:\n" + "\n".join(by_attr)
    uncalled = sorted(helpers - by_name)
    assert not uncalled, f"помощники ни разу не вызваны голым именем: {uncalled}"
    in_sandbox = sorted(helpers & set(_plan.module_functions(
        _head_tree(_plan.SANDBOX_FILE))))
    assert not in_sandbox, f"помощники — функции модуля песочницы: {in_sandbox}"


@pytest.mark.parametrize("method", ["gate_refusal", "no_gate_refusal"])
def test_ac10_sandbox_methods_unchanged(method):
    """Методы `gate_refusal`/`no_gate_refusal` остаются в `IdOutcomeGateSandbox` без изменений.

    Метод класса в новом файле по `ast.dump` равен исходному методу
    id-файла базы с тремя переименованиями (употребление `GATE_ACTIONS`
    в `no_gate_refusal` → `ID_GATE_ACTIONS`).

    Ловит мутацию: разработчик, вынеся помощника в функцию модуля, удалил
    метод из класса или превратил его в обёртку `return gate_refusal(self,
    …)` — метода нет или дамп расходится, тест краснеет.
    """
    source = _plan.class_method(_base_tree(_plan.ID_FILE), "IdOutcomeGateSandbox",
                                method)
    assert source is not None, f"IdOutcomeGateSandbox.{method} нет в базе"
    got = _plan.class_method(_head_tree(_plan.NEW_FILE), "IdOutcomeGateSandbox",
                             method)
    assert got is not None, f"IdOutcomeGateSandbox.{method} нет в {_plan.NEW_FILE}"
    assert ast.dump(got) == ast.dump(_plan.renamed(source)), (
        f"IdOutcomeGateSandbox.{method} изменён при переносе")
