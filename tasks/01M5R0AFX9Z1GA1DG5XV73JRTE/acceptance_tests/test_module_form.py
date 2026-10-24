"""AC-7 (раскладка), AC-8 … AC-12, AC-14 (заявки): три файла модулей
`tests/test_merge_lock_module.py`, `tests/test_merge_queue.py`,
`tests/test_merge_after_module.py` против пяти файлов волны базы ветки —
стиль pytest без тестовых классов и `subTest`, фикстуры стендов из тел
`setUp`, помощники-функции, константы, импорты, дословные ожидания и
сообщения, циклы подслучаев с ярлыком, глотание, подмены и замыкания.

Группа: разовый
Красен до реализации: tests/test_merge_after_module.py на ветке ещё нет, тестов mutex_by_project в файлах модулей 3м-1 нет — свод не сделан.

Файлы модулей читаются из HEAD рабочей копии, исходные — из базы ветки
(`_pult.DIFF_BASE`). Сравнение статическое (ast): тест не исполняет ни
новые, ни исходные тесты. «Тело дословно» сверяется `ast.dump` тела
источника, переведённого правилами требований 10–12 SPEC: `self.` →
параметр стенда, `self.<помощник>(…)` → `<функция>(<стенд>, …)` по
перечню переименований (`_plan.MUTEX_RENAME`, `_plan.AFTER_HELPERS`),
`self.assertX(…)` → `assert …` по соответствию требования 12,
`super().setUp()` отброшен, у фикстуры — хвост `return <параметр>`.
«Функция, в которую перенесён тест» — функция-тест его файла модуля с
его именем (`_plan.moved_to`).
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
_MUTEX_STEM = Path(_plan.MUTEX).stem
_WAVE_MARK = "3м-2"


def _context():
    return (_ctx.base_trees(), _ctx.base_tests(), _ctx.head_trees(), _ctx.removed())


def _moved_pairs():
    base_trees, tests, heads, removed = _context()
    return base_trees, heads, _ctx.moved_pairs(tests, heads, removed)


def _new_canon(base_trees, test, func):
    base_c = _plan.base_canon(base_trees[test.path], test.path, test.cls)
    return base_c, _plan.new_canon(func, test.func, base_c)


def _base_function_names(path: str) -> set:
    return set(_plan.module_functions(_ctx.base_module_trees()[path])) \
        if path in _plan.EXTENDED_FILES else set()


def _new_functions(path: str, tree) -> list:
    """Функции верхнего уровня файла модуля, которых нет в его базе."""
    old = _base_function_names(path)
    return [f for n, f in _plan.module_functions(tree).items() if n not in old]


# ------------------------------------------------------------------ AC-7

def test_ac7_each_source_test_lives_in_its_module_file_only():
    """Тесты классов замка — в файле замка, очереди — в файле очереди, четырёх файлов merge_after — в новом модуле.

    Для каждого исходного теста, не названного в PLAN удалённым дублем,
    функция с его именем есть в его файле модуля
    (`_plan.TARGET_OF_CLASS`) и нет в двух других.

    Ловит мутацию: `WaitTextsByProjectTest::test_ac10_single_project_texts_
    are_unchanged` положен в `tests/test_merge_lock_module.py` (или тест
    division — в файл очереди) — функция не в своём файле, тест краснеет
    с ней.
    """
    _base_trees, tests, heads, removed = _context()
    problems = []
    for test in tests.values():
        if test.key in removed:
            continue
        if not _plan.moved_to(test.name, _plan.module_tests(heads[test.target])):
            problems.append(f"{test.key}: нет в {test.target}")
        for other in _plan.MODULE_FILES:
            if other != test.target and \
                    _plan.moved_to(test.name, _plan.module_tests(heads[other])):
                problems.append(f"{test.key}: лежит в {other}")
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("path", list(_plan.EXTENDED_FILES))
def test_ac7_mutex_tests_at_end_with_section_comment_of_class_and_file(path):
    """Тесты mutex_by_project — в конце файла модуля 3м-1, раздел каждого бывшего класса отмечен комментарием с его именем и именем файла.

    Каждая функция, в которую перенесён тест mutex_by_project, стоит ниже
    последней функции-теста базы этого файла. Для каждого бывшего класса
    файла есть строка-комментарий `# …` с именем класса и именем бывшего
    файла (`test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project`) —
    ниже последнего теста базы и не ниже первой функции этого класса.

    Ловит мутацию: тесты вставлены перед `test_concurrent_acquire_on_free_
    lock_exactly_one_wins` (или раздел помечен «# AcquireByProjectTest» без
    имени файла) — строка теста выше границы или комментария нет, тест
    краснеет с классом.
    """
    _base_trees, tests, heads, removed = _context()
    tree = heads[path]
    lines = _ctx.head_text(path).split("\n")
    old_tests = {f.name for f in _plan.module_tests(_ctx.base_module_trees()[path])}
    head_funcs = _plan.module_functions(tree)
    boundary = max((head_funcs[n].end_lineno for n in old_tests if n in head_funcs),
                   default=0)
    problems = []
    for cls in [c for c, t in _plan.TARGET_OF_CLASS.items() if t == path]:
        funcs = [f for test in tests.values() if test.cls == cls
                 and test.key not in removed
                 for f in _plan.moved_to(test.name, _plan.module_tests(tree))]
        if not funcs:
            problems.append(f"{cls}: перенесённых функций нет")
            continue
        first = min(f.lineno for f in funcs)
        low = [f.name for f in funcs if f.lineno <= boundary]
        if low:
            problems.append(f"{cls}: функции {low} выше конца тестов базы "
                            f"(строка {boundary})")
        marks = [i + 1 for i, line in enumerate(lines)
                 if line.lstrip().startswith("#") and cls in line
                 and _MUTEX_STEM in line and boundary < i + 1 <= first]
        if not marks:
            problems.append(f"{cls}: нет комментария раздела с именем класса и "
                            f"файла между строками {boundary} и {first}")
    assert not problems, f"{path}:\n" + "\n".join(problems)


def test_ac7_after_module_docstring_names_four_files_and_specs():
    """Докстринг нового модуля называет четыре прежних файла и четыре SPEC, без строк «Группа:» и «Красен до реализации».

    В докстринге `tests/test_merge_after_module.py` есть имена
    `test_merge_after.py`, `test_merge_after_declared.py`,
    `test_01m4jc58gzfhz4pzhw254p22m2_division_merge_after.py`,
    `test_01m5fghnb29qa254fm07qr55ab_spec_gate_hint.py` и идентификаторы
    01M44EP0D47F498TEE08MNGBYT, 01M45D29BQJE8FJYJA4JQWSYFZ,
    01M4JC58GZFHZ4PZHW254P22M2, 01M5FGHNB29QA254FM07QR55AB; ни одна его
    строка не начинается с «Группа:», и в нём нет «Красен до реализации».

    Ловит мутацию: докстринг перенесён из долгоживущего division со
    строкой «Группа: долгоживущий» (или не назвал SPEC деления) — тест
    краснеет с находкой.
    """
    doc = ast.get_docstring(_ctx.head_trees()[_plan.AFTER_MODULE]) or ""
    problems = [f"нет имени {Path(p).name}" for p in _plan.MERGE_AFTER_SOURCES
                if Path(p).name not in doc]
    problems += [f"нет SPEC {s}" for s in _plan.SPEC_IDS if s not in doc]
    problems += [f"строка «{line.strip()}»" for line in doc.split("\n")
                 if line.strip().startswith("Группа:")]
    if "Красен до реализации" in doc:
        problems.append("есть «Красен до реализации»")
    assert not problems, "докстринг нового модуля:\n" + "\n".join(problems)


@pytest.mark.parametrize("path", list(_plan.EXTENDED_FILES))
def test_ac7_extended_module_docstring_gains_wave_paragraph(path):
    """Докстринг файла модуля 3м-1 дополнен абзацем о волне 3м-2.

    Докстринг HEAD начинается докстрингом базы и длиннее его; добавленная
    часть несёт «3м-2» и отделена пустой строкой (новый абзац).

    Ловит мутацию: тесты дописаны, а докстринг модуля оставлен прежним
    (или абзац о волне вписан в середину прежнего предложения) — «3м-2»
    нет или нет нового абзаца, тест краснеет.
    """
    old = ast.get_docstring(_ctx.base_module_trees()[path]) or ""
    new = ast.get_docstring(_ctx.head_trees()[path]) or ""
    assert new.startswith(old) and len(new) > len(old), (
        f"{path}: докстринг HEAD не продолжает докстринг базы")
    tail = new[len(old):]
    assert tail.startswith("\n\n"), f"{path}: добавка не новым абзацем: {tail[:80]!r}"
    assert _WAVE_MARK in tail, f"{path}: в добавке докстринга нет «{_WAVE_MARK}»"


# ------------------------------------------------------------------ AC-8

@pytest.mark.parametrize("path", _FILES)
def test_ac8_no_test_classes_subtest_unittest_sandbox_bases_main_or_unused_imports(path):
    """В файле модуля нет тестовых классов, `subTest`, `unittest`, `TmpRootTest`, `InitializedTmpRootTest`, `__main__`, неиспользуемых импортов и импорта соседних файлов модулей.

    Файл есть в HEAD и несёт тестовые функции; ни один класс не несёт
    методов `test_*` и не наследует `TestCase`; обращений `subTest` нет;
    нет `import unittest` и `from unittest import …` кроме `mock`; имён
    `TmpRootTest`, `InitializedTmpRootTest` нет; на верхнем уровне нет
    `if __name__ == "__main__"`; каждое имя, связанное импортом,
    используется; нет импорта `tests.test_merge_lock_module`,
    `tests.test_merge_queue`, `tests.test_merge_after_module`.

    Ловит мутацию: свод оставил `class MigrationTest(unittest.TestCase)`,
    импорт `InitializedTmpRootTest` из прежнего spec_gate_hint, хвост
    `unittest.main()` или файл очереди импортирует `refusal_pattern` из
    файла замка — находка перечислена, тест краснеет.
    """
    tree = _ctx.head_trees()[path]
    assert _plan.module_tests(tree), f"в {path} нет тестовых функций"
    stems = {Path(p).stem for p in _plan.MODULE_FILES}
    problems = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            bases = {ast.unparse(b).rsplit(".", 1)[-1] for b in node.bases}
            methods = [i.name for i in node.body if isinstance(i, ast.FunctionDef)
                       and i.name.startswith("test")]
            if methods or "TestCase" in bases:
                problems.append(f"тестовый класс {node.name} в строке {node.lineno}")
        if isinstance(node, ast.Attribute) and node.attr == "subTest":
            problems.append(f"subTest в строке {node.lineno}")
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "unittest" or (alias.name.startswith("unittest.")
                                                and alias.name != "unittest.mock"):
                    problems.append(f"import unittest в строке {node.lineno}")
                if alias.name.split(".")[-1] in stems:
                    problems.append(f"импорт файла модуля {alias.name}")
        if isinstance(node, ast.ImportFrom):
            if node.module == "unittest" and any(a.name != "mock" for a in node.names):
                problems.append(f"from unittest import … в строке {node.lineno}")
            if (node.module or "").split(".")[-1] in stems or (
                    node.module == "tests" and any(a.name in stems for a in node.names)):
                problems.append(f"импорт файла модуля в строке {node.lineno}")
            problems += [f"импорт {a.name} в строке {node.lineno}" for a in node.names
                         if a.name in ("TmpRootTest", "InitializedTmpRootTest")]
        if isinstance(node, ast.Name) and node.id in ("TmpRootTest",
                                                       "InitializedTmpRootTest"):
            problems.append(f"{node.id} в строке {node.lineno}")
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


def test_ac8_only_class_of_new_module_is_division_sandbox_with_task_title():
    """Единственный класс нового модуля — `DivisionSandbox(LightTransitionSandbox)` только с `TASK_TITLE` прежним литералом.

    В `tests/test_merge_after_module.py` ровно один класс; его база —
    `LightTransitionSandbox`; тело — (необязательный докстринг и)
    единственное присваивание `TASK_TITLE` литералу, равному
    `DivisionRewritesDependentsTest.TASK_TITLE` базы.

    Ловит мутацию: `DivisionSandbox` получил `setUp` с подготовкой деления
    (или заголовок подзадач изменён литералом «Родитель деления») — лишний
    узел тела или литерал другой, тест краснеет.
    """
    tree = _ctx.head_trees()[_plan.AFTER_MODULE]
    classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    assert [c.name for c in classes] == [_plan.DIVISION_SANDBOX], (
        f"классы нового модуля: {[c.name for c in classes]}")
    cls = classes[0]
    assert [ast.unparse(b) for b in cls.bases] == ["LightTransitionSandbox"], (
        f"базы {_plan.DIVISION_SANDBOX}: {[ast.unparse(b) for b in cls.bases]}")
    body = _plan.strip_docstring(cls.body)
    want = _plan.class_constant(_ctx.base_trees()[_plan.DIVISION],
                                "DivisionRewritesDependentsTest", "TASK_TITLE")
    assert len(body) == 1 and isinstance(body[0], ast.Assign), (
        f"тело {_plan.DIVISION_SANDBOX}: {[ast.unparse(s) for s in body]}")
    assert _plan.class_constant(tree, _plan.DIVISION_SANDBOX, "TASK_TITLE") == want


# ------------------------------------------------------------------ AC-9

def _setup_dump(base_trees, path: str, cls: str, param: str) -> str:
    tree = base_trees[path]
    owner = _plan.MUTEX_BASE if path == _plan.MUTEX else cls
    method = _plan.class_method(tree, owner, "setUp")
    assert method is not None, f"{path}::{owner}.setUp нет в базе"
    return _plan.translated_body(method, _plan.class_calls(tree, path, owner), param,
                                 drop_super=True)


def _fixture_problems(base_trees, path: str, func, param: str, sources) -> list:
    problems = []
    args = [a.arg for a in func.args.args]
    if args != [param]:
        problems.append(f"{func.name}: параметры {args}, ожидался ({param})")
        return problems
    problems += [f"{func.name}: утверждение в строке {n.lineno}"
                 for n in ast.walk(func) if _plan.is_assertion_node(n)]
    if _plan.trailing_return_name(func) != param:
        problems.append(f"{func.name}: тело не кончается `return {param}`")
    body = _plan.body_dump(func, drop_trailing_return=True)
    for src, cls in sources:
        if body != _setup_dump(base_trees, src, cls, param):
            problems.append(f"{func.name}: тело ≠ {cls}.setUp без super() с "
                            f"заменой self. на {param}")
    return problems


def test_ac9_project_mutex_stand_in_both_files_with_setup_body():
    """`project_mutex_stand(tmp_root)` есть в файлах замка и очереди, тело — `_ProjectMutexBase.setUp`, тела одинаковы.

    В каждом из двух файлов 3м-1 фикстура `project_mutex_stand` с
    единственным параметром `tmp_root`, без утверждений; её тело без
    хвоста `return tmp_root` равно телу `_ProjectMutexBase.setUp` без
    `super().setUp()` с заменой `self.` на `tmp_root` (вызов
    `self.new_project()` — вызов функции `new_project(tmp_root)`); тела
    двух фикстур равны.

    Ловит мутацию: фикстура очереди не печатает зерно (или берёт
    `random.Random(0)`), объявляет внешний проект литералом `"extone"`
    вместо `new_project`, либо фикстура заведена только в файле замка, а
    очередь её импортирует — тело другое или фикстуры нет, тест краснеет.
    """
    base_trees = _ctx.base_trees()
    heads = _ctx.head_trees()
    problems, dumps = [], set()
    for path in _plan.EXTENDED_FILES:
        found = [f for f in _plan.fixtures(heads[path]) if f.name == "project_mutex_stand"]
        if len(found) != 1:
            problems.append(f"{path}: фикстур project_mutex_stand {len(found)}")
            continue
        param, sources = _plan.STANDS[path]["project_mutex_stand"]
        problems += [f"{path}: {p}" for p in
                     _fixture_problems(base_trees, path, found[0], param, sources)]
        dumps.add(_plan.body_dump(found[0]))
    if len(dumps) > 1:
        problems.append("тела project_mutex_stand двух файлов расходятся")
    assert not problems, "\n".join(problems)


def test_ac9_after_module_stand_fixtures_with_setup_bodies():
    """Фикстуры нового модуля: `merge_after_stand(light_transition)`, `loss_stand(initialized_tmp_root)`, `declared_path_stand(light_transition)`, `division_stand(division_sandbox)` — тела `setUp`.

    Тело `merge_after_stand` равно и `MergeAfterDbSandbox.setUp`, и
    `DeclaredSandbox.setUp`; `loss_stand` — `LossRefusalTextTest.setUp`;
    `declared_path_stand` — `DeclaredPathTest.setUp` (`self.addCleanup(env.
    stop)` → вызов стенда); `division_stand` —
    `DivisionRewritesDependentsTest.setUp`. Тело каждой — без
    `super().setUp()`, `self.` заменено параметром, хвост `return
    <параметр>`, утверждений нет.

    Ловит мутацию: `declared_path_stand` останавливает подмену окружения
    `env.stop()` сразу (а не уборкой стенда), `loss_stand` теряет
    `counter = 0`, `division_stand` берёт `light_transition` вместо
    `division_sandbox` (заголовок подзадач не тот) — тело или параметр
    другие, тест краснеет с фикстурой.
    """
    base_trees = _ctx.base_trees()
    tree = _ctx.head_trees()[_plan.AFTER_MODULE]
    found = {f.name: f for f in _plan.fixtures(tree)}
    problems = []
    for name, (param, sources) in _plan.STANDS[_plan.AFTER_MODULE].items():
        if name not in found:
            problems.append(f"нет фикстуры {name}")
            continue
        problems += _fixture_problems(base_trees, _plan.AFTER_MODULE, found[name],
                                      param, sources)
    assert not problems, "\n".join(problems)


def test_ac9_division_sandbox_fixture_yields_sandbox_from_tests_fixtures():
    """`division_sandbox()` без параметров с телом `yield from _sandbox(DivisionSandbox)`; `_sandbox` импортирован из `tests.fixtures`.

    Ловит мутацию: фикстура строит песочницу сама (`DivisionSandbox();
    setUp()`, без уборки `addCleanup`) или `_sandbox` скопирован в модуль
    — тело другое или импорта нет, тест краснеет.
    """
    tree = _ctx.head_trees()[_plan.AFTER_MODULE]
    found = {f.name: f for f in _plan.fixtures(tree)}
    func = found.get(_plan.DIVISION_SANDBOX_FIXTURE)
    assert func is not None, f"нет фикстуры {_plan.DIVISION_SANDBOX_FIXTURE}"
    assert not func.args.args, f"{func.name}: параметры {[a.arg for a in func.args.args]}"
    want = [_plan.clean(s) for s in ast.parse("yield from _sandbox(DivisionSandbox)").body]
    got = [_plan.clean(s) for s in _plan.strip_docstring(func.body)]
    assert [ast.dump(s) for s in got] == [ast.dump(s) for s in want], (
        f"тело {func.name}: {[ast.unparse(s) for s in func.body]}")
    imports = [n for n in tree.body if isinstance(n, ast.ImportFrom)
               and n.module == "tests.fixtures"
               and any(a.name == "_sandbox" and a.asname is None for a in n.names)]
    assert imports, "нет `from tests.fixtures import _sandbox`"
    assert "_sandbox" not in _plan.module_functions(tree), "_sandbox определён в модуле"


def test_ac9_tests_of_task_id_form_and_migration_take_no_stand():
    """Функции тестов `TaskIdFormTest` и `MigrationTest` фикстур стенда не берут.

    Ловит мутацию: `test_migrate_adds_merge_after_to_old_tasks_table`
    получил `merge_after_stand` (тест теперь идёт в песочнице переходов) —
    у функции есть параметр, тест краснеет с ней.
    """
    _base_trees, _heads, pairs = _moved_pairs()
    seen = [test.cls for test, _f in pairs if test.cls in _plan.NO_STAND_CLASSES]
    assert sorted(set(seen)) == sorted(_plan.NO_STAND_CLASSES), (
        f"перенесённые тесты TaskIdFormTest/MigrationTest: {seen}")
    problems = [f"{func.name}: параметры {[a.arg for a in func.args.args]}"
                for test, func in pairs if test.cls in _plan.NO_STAND_CLASSES
                and func.args.args]
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("path", _FILES)
def test_ac9_fixture_names_unique_and_differ_from_shared_fixtures(path):
    """Имена фикстур файла модуля не совпадают с фикстурами `tests/fixtures.py` и между собой.

    Ловит мутацию: стенд назван `light_transition` (затеняет общую) или в
    файле замка вторая фикстура `project_stand` перекрыла прежнюю — имя
    совпало, тест краснеет с ним.
    """
    shared = {f.name for f in _plan.fixtures(ast.parse(_ctx.head_text(_plan.FIXTURES_FILE)))}
    assert shared, f"в {_plan.FIXTURES_FILE} не найдено фикстур"
    names = [f.name for f in _plan.fixtures(_ctx.head_trees()[path])]
    clash = sorted({n for n in names if n in shared or names.count(n) > 1})
    assert not clash, f"{path}: имена фикстур совпадают: {clash}"


# ------------------------------------------------------------------ AC-10

def _without_case(func):
    """Копия `wait_texts` без последнего параметра `case` и без `+ case` в
    сообщениях утверждений (сравнение с исходным телом — AC-12)."""
    node = _plan.clean(func)
    args = node.args
    if args.args and args.args[-1].arg == "case":
        args.args = args.args[:-1]
        if args.defaults:
            args.defaults = args.defaults[:-1]
    for sub in ast.walk(node):
        if isinstance(sub, ast.Assert) and isinstance(sub.msg, ast.BinOp) \
                and isinstance(sub.msg.op, ast.Add) \
                and isinstance(sub.msg.right, ast.Name) and sub.msg.right.id == "case":
            sub.msg = sub.msg.left
    return node


def _helper_problems(base_trees, path: str, tree) -> list:
    funcs = _plan.module_functions(tree)
    problems = []
    for name, (src, cls, method) in sorted(_plan.helper_sources(base_trees, path).items()):
        func = funcs.get(name)
        node = _plan.class_method(base_trees[src], cls, method)
        if func is None:
            problems.append(f"{path}: нет функции {name} (бывший {cls}.{method})")
            continue
        if name == "wait_texts":
            func = _without_case(func)
        calls = _plan.class_calls(base_trees[src], src, cls)
        bare = method in _plan.NO_STAND_FUNCS
        if bare:
            param = "self"
            if _plan.rest_args_dump(func.args, False) != _plan.rest_args_dump(node.args, True):
                problems.append(f"{path}::{name}: параметры ≠ {cls}.{method} без self")
        else:
            if not func.args.args:
                problems.append(f"{path}::{name}: нет параметра стенда")
                continue
            param = func.args.args[0].arg
            if _plan.rest_args_dump(func.args, True) != _plan.rest_args_dump(node.args, True):
                problems.append(f"{path}::{name}: параметры ≠ {cls}.{method}")
        if _plan.body_dump(func) != _plan.translated_body(node, calls, param):
            problems.append(f"{path}::{name}: тело ≠ {cls}.{method} с заменой self.")
        if (func.returns is None) != (node.returns is None) or (
                func.returns is not None and
                ast.dump(_plan.clean(func.returns)) != ast.dump(_plan.clean(node.returns))):
            problems.append(f"{path}::{name}: аннотация возврата ≠ {cls}.{method}")
    return problems


@pytest.mark.parametrize("path", _FILES)
def test_ac10_helpers_are_module_functions_with_verbatim_bodies(path):
    """Помощники стендов — функции модуля: первый параметр — стенд, тело дословно с заменой `self.`, имена по перечню SPEC.

    Для файла замка и очереди — методы `_ProjectMutexBase` (и
    `wait_texts`), нужные их тестам транзитивно (`_plan.mutex_needs`),
    кроме `lock_by_task`/`clear`; имена: `project_mutex_new_task`,
    `project_mutex_seed_lock`, `project_mutex_enqueue`,
    `project_mutex_actions`, прочие — прежние. Для нового модуля —
    `merge_after_db_insert`, `set_deps`, `declared_insert`,
    `spec_gate_declared_refusal_spec_text`, `new_task`, `msg`, `divide`,
    `stored_deps`, `journal`, `task`, `declared_path_note`, `run_cmd`,
    `live_task`, `declared_task`, `refusal`, `no_code_tree` (без параметра
    стенда). Остальные параметры и аннотация возврата — как у метода; тело
    — тело метода с заменой `self.` первым параметром, `self.<помощник>(…)`
    — вызовом функции, `self.assertX` — `assert …`.

    Ловит мутацию: `project_mutex_seed_lock` зовёт `stand.lock_by_task()`
    вместо `locks(stand)`, `declared_insert` потерял `target=
    config.DEFAULT_TARGET`, `divide` переведён без сообщения `msg(…)` у
    `assert`, или `no_code_tree(stand, branch, rel, …)` получил стенд —
    тело или параметры другие, тест краснеет с именем.
    """
    problems = _helper_problems(_ctx.base_trees(), path, _ctx.head_trees()[path])
    assert not problems, "\n".join(problems)


def test_ac10_mutex_helpers_and_constants_identical_in_both_files():
    """Помощники и константы mutex_by_project, нужные обоим файлам, одинаковы; `TS_FORMAT`, `TAKEOVER_ACTION`, `_ALPHABET`, `refusal_pattern` — с литералами базы; `OTHER_HOST` не переопределён.

    Функции перенесённых помощников с одним именем в файлах замка и
    очереди совпадают (параметры и тело). Каждое имя из
    `TS_FORMAT`, `TAKEOVER_ACTION`, `_ALPHABET`, `refusal_pattern`, которое
    читают помощники и тесты файла (`_plan.mutex_needs`), определено в
    файле верхним уровнем так же, как в mutex_by_project. `OTHER_HOST`
    присвоен в каждом файле ровно один раз — прежним литералом 3м-1.

    Ловит мутацию: `refusal_pattern` очереди потерял `^…$` (или
    `_ALPHABET` урезан), либо в файле замка добавлено второе `OTHER_HOST =
    …` — определение расходится или удвоено, тест краснеет с именем.
    """
    base_trees = _ctx.base_trees()
    base_mods = _ctx.base_module_trees()
    heads = _ctx.head_trees()
    tree = base_trees[_plan.MUTEX]
    problems = []
    lock_funcs = _plan.module_functions(heads[_plan.LOCK_MODULE])
    queue_funcs = _plan.module_functions(heads[_plan.QUEUE_MODULE])
    shared = set(_plan.helper_sources(base_trees, _plan.LOCK_MODULE)) & \
        set(_plan.helper_sources(base_trees, _plan.QUEUE_MODULE))
    for name in sorted(shared):
        left, right = lock_funcs.get(name), queue_funcs.get(name)
        if left is None or right is None or \
                ast.dump(_plan.clean(left)) != ast.dump(_plan.clean(right)):
            problems.append(f"{name}: в файлах замка и очереди разные или нет")
    for path in _plan.EXTENDED_FILES:
        classes = [c for c, t in _plan.TARGET_OF_CLASS.items() if t == path]
        _need, names = _plan.mutex_needs(tree, classes)
        for name in sorted(names):
            want, got = _plan.top_level(tree, name), _plan.top_level(heads[path], name)
            if got is None or ast.dump(_plan.clean(got)) != ast.dump(_plan.clean(want)):
                problems.append(f"{path}: {name} нет или не как в mutex_by_project")
        host = _plan.top_level_assignments(heads[path], "OTHER_HOST")
        old = _plan.top_level_assignments(base_mods[path], "OTHER_HOST")
        if len(host) != 1 or len(old) != 1 or \
                ast.dump(_plan.clean(host[0])) != ast.dump(_plan.clean(old[0])):
            problems.append(f"{path}: OTHER_HOST присвоен {len(host)} раз(а) или "
                            f"не прежним литералом")
    assert not problems, "\n".join(problems)


def test_ac10_lock_by_task_and_clear_not_moved_tests_use_module_locks_and_clear():
    """`lock_by_task` и `clear` `_ProjectMutexBase` не перенесены: в файлах 3м-1 нет `lock_by_task` и двойников, перенесённые тесты зовут `locks`/`clear` модуля.

    В файлах замка и очереди нет функций `lock_by_task`,
    `project_mutex_lock_by_task`, `project_mutex_clear`,
    `project_mutex_locks`; каждая функция, в которую перенесён тест
    mutex_by_project, звавший `self.lock_by_task()` (`self.clear()`),
    зовёт `locks(<стенд>)` (`clear(<стенд>)`).

    Ловит мутацию: свод перенёс `lock_by_task` отдельной функцией рядом с
    `locks` (тело то же — двойник), и тесты зовут его — функция найдена,
    тест краснеет с ней.
    """
    _base_trees, heads, pairs = _moved_pairs()
    problems = []
    for path in _plan.EXTENDED_FILES:
        funcs = _plan.module_functions(heads[path])
        problems += [f"{path}: есть {n}" for n in
                     ("lock_by_task", "project_mutex_lock_by_task",
                      "project_mutex_clear", "project_mutex_locks") if n in funcs]
    for test, func in pairs:
        if test.path != _plan.MUTEX:
            continue
        refs = _plan.self_refs(test.func)
        calls = {n.func.id for n in ast.walk(func) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name)}
        for method, name in (("lock_by_task", "locks"), ("clear", "clear")):
            if method in refs and name not in calls:
                problems.append(f"{func.name}: нет вызова {name}(…) вместо "
                                f"self.{method}()")
    assert not problems, "\n".join(problems)


def test_ac10_after_module_constants_and_functions_verbatim():
    """Константы и функции модулей четырёх файлов merge_after перенесены в новый модуль дословно.

    `MARKER`, `OTHER_TARGET`, `ZONE`, `DIVIDED_PREFIX`, `division_spec`,
    `FIELD`, `MANDATE`, `LOSS_START`, `OLD_TAIL`, `ZONES`, `SPEC_TEXT`,
    `spec_text`, `meta_of` — определения верхнего уровня, совпадающие с
    прежними (`ast.dump`, с докстрингом и комментарием-кодом).

    Ловит мутацию: `spec_text` spec_gate_hint переименован в
    `hint_spec_text` (или `ZONE` переписан под другой путь) — определения
    нет или оно другое, тест краснеет с именем.
    """
    base_trees = _ctx.base_trees()
    tree = _ctx.head_trees()[_plan.AFTER_MODULE]
    problems = []
    for path, names in _plan.AFTER_MODULE_NAMES.items():
        for name in names:
            want, got = _plan.top_level(base_trees[path], name), _plan.top_level(tree, name)
            if want is None:
                problems.append(f"{path}: {name} нет в базе — база прочитана не та")
            elif got is None or ast.dump(_plan.clean(got)) != ast.dump(_plan.clean(want)):
                problems.append(f"{name}: нет в новом модуле или не дословно")
    assert not problems, "\n".join(problems)


def _imported(tree) -> set:
    found = set()
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            found |= {(alias.asname or alias.name).split(".")[0] for alias in node.names}
    return found


@pytest.mark.parametrize("path,added", [
    ("tests/test_merge_lock_module.py", ["datetime", "random", "re", "timezone"]),
    ("tests/test_merge_queue.py", ["os", "random", "re"]),
])
def test_ac10_extended_files_add_only_missing_imports(path, added):
    """В файл 3м-1 добавлены ровно недостающие импорты: замку — `random`, `re`, `datetime`, `timezone`; очереди — `os`, `random`, `re`.

    Множество имён, связанных импортом верхнего уровня в HEAD, минус то же
    множество базы равно перечню критерия.

    Ловит мутацию: в файл замка добавлен `import time` и `patch_sleep`
    (нужные только тестам очереди) или очереди не добавлен `os` — разница
    другая, тест краснеет с ней.
    """
    new = _imported(_ctx.head_trees()[path]) - _imported(_ctx.base_module_trees()[path])
    assert sorted(new) == added, f"{path}: добавлены импорты {sorted(new)}, ожидались {added}"


@pytest.mark.parametrize("path", _FILES)
def test_ac10_helper_calls_are_function_calls_not_stand_methods(path):
    """Новые функции файла зовут перенесённые помощники функциями, а не `<стенд>.<помощник>(…)`.

    Ни в одной функции файла, которой нет в базе (перенесённые тесты,
    помощники, фикстуры), нет вызова `<параметр>.<имя>(…)`, где имя —
    помощник стенда пяти файлов (`token`, `new_task`, `seed_lock`, `msg`,
    `assert_fresh`, `wait_texts`, `insert`, `divide`, `declared_task`, …).

    Ловит мутацию: стенд получил методы-обёртки и тест зовёт
    `division_stand.divide()` или `stand.assert_fresh(…)` — вызов найден,
    тест краснеет с ним.
    """
    base_trees = _ctx.base_trees()
    names = set()
    for (_src, _cls), helpers in _plan.AFTER_HELPERS.items():
        names |= set(helpers)
    for cls in (_plan.MUTEX_BASE, "WaitTextsByProjectTest"):
        names |= {n for n in _plan.class_methods(base_trees[_plan.MUTEX], cls)
                  if not n.startswith("test") and n != "setUp"}
    tree = _ctx.head_trees()[path]
    problems = []
    for func in _new_functions(path, tree):
        params = {a.arg for a in func.args.args}
        for node in ast.walk(func):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr in names and isinstance(node.func.value, ast.Name) \
                    and node.func.value.id in params | {"self"}:
                problems.append(f"{func.name}: {ast.unparse(node.func)}(…) в строке "
                                f"{node.lineno}")
    assert not problems, "\n".join(problems)


def _note_renames(base_trees, pairs) -> dict:
    """{функция: новое имя локальной `note`} перенесённых `test_ac8`/`test_ac9`."""
    found = {}
    for test, func in pairs:
        if test.path != _plan.HINT:
            continue
        _base_c, canon = _new_canon(base_trees, test, func)
        for new, old in canon.locals.items():
            if old == "note":
                found[func.name] = new
    return found


def test_ac10_local_note_renamed_in_test_ac8_and_test_ac9():
    """Локальная `note` в перенесённых `test_ac8` и `test_ac9` spec_gate_hint переименована.

    В обеих функциях нет локального имени `note`, и присваивание прежнего
    значения `note` стоит под новым именем.

    Ловит мутацию: в `test_ac9` оставлена локальная `note`, затеняющая
    функцию `declared_path_note`-соседа (или переименование сделано только
    в `test_ac8`) — имя `note` найдено, тест краснеет с функцией.
    """
    base_trees, _heads, pairs = _moved_pairs()
    hint = [(t, f) for t, f in pairs if t.path == _plan.HINT]
    assert len(hint) == 2, f"перенесённых тестов spec_gate_hint: {[f.name for _t, f in hint]}"
    renames = _note_renames(base_trees, pairs)
    problems = []
    for _test, func in hint:
        stores = {n.id for n in ast.walk(func) if isinstance(n, ast.Name)
                  and isinstance(n.ctx, ast.Store)}
        if "note" in stores:
            problems.append(f"{func.name}: локальная note осталась")
        if func.name not in renames:
            problems.append(f"{func.name}: прежнее значение note не найдено под "
                            f"новым именем")
    assert not problems, "\n".join(problems)


def test_ac10_plan_lists_method_to_function_renames_and_body_twins():
    """PLAN называет перечень «метод → функция», переименования и совпадения тел.

    В PLAN словом стоят: имя каждой функции-помощника трёх файлов модулей
    (по перечню `_plan.helper_sources`), `lock_by_task`, `locks`, `clear`
    и новое имя локальной `note` в `test_ac8` и `test_ac9`.

    Ловит мутацию: PLAN перечислил помощники mutex_by_project, а
    переименования нового модуля (`declared_path_note`,
    `merge_after_db_insert`) или новое имя локальной `note` не назвал —
    имя не найдено, тест краснеет с ним.
    """
    plan = _ctx.plan_text()
    base_trees, _heads, pairs = _moved_pairs()
    names = set()
    for path in _plan.MODULE_FILES:
        names |= set(_plan.helper_sources(base_trees, path))
    names |= {"lock_by_task", "locks", "clear"}
    names |= set(_note_renames(base_trees, pairs).values())
    missing = sorted(n for n in names
                     if not re.search(rf"(?<![\w]){re.escape(n)}(?![\w])", plan))
    assert not missing, f"не названы в PLAN: {missing}"


# ------------------------------------------------------------------ AC-11

def test_ac11_every_source_assertion_carried_in_same_normal_form():
    """Каждое утверждение исходного теста есть в функции, в которую он перенесён, в той же форме `assert …`.

    Для каждого `self.assert*` исходного теста функция модуля несёт
    `assert` той же нормальной формы (`assertEqual(a, b)` ↔ `assert a ==
    b`, `assertIsNone(x)` ↔ `assert x is None`, `assertTrue(x)` ↔ `assert
    x`, `assertFalse(x)` ↔ `assert not x`, `assertRegex(t, p)` ↔ `assert
    re.search(p, t)`, `self.<помощник>()` ↔ функция, `self` ↔ стенд):
    литерал остаётся литералом, константа — константой, сравнение — тем
    же оператором; вызовов `self.assert*` в функции нет.

    Ловит мутацию: `assertEqual(sleeps, [], ctx)` перенесён как `assert
    not sleeps`, `assertIn(MARKER, out)` — как `assert "Зависимости
    мержа:" in out`, `assertGreaterEqual(len(sleeps), 1)` — как `assert
    len(sleeps) > 1` — формы нет в функции, тест краснеет с ней.
    """
    base_trees, _heads, pairs = _moved_pairs()
    assert pairs, "перенесённых тестов нет"
    problems = []
    for test, func in pairs:
        base_c, canon = _new_canon(base_trees, test, func)
        have = [_plan.normal_form(n, canon) for n in _plan.plain_assertions(func)]
        problems += [f"{func.name}: self.assert* в строке {n.lineno}"
                     for n in ast.walk(func) if _plan.is_self_assert(n)]
        for node in _plan.self_assertions(test.func):
            if _plan.normal_form(node, base_c) not in have:
                problems.append(f"{test.key} → {func.name}: нет "
                                f"{ast.unparse(node)[:110]}")
    assert not problems, "\n".join(problems)


def _assigns(func) -> dict:
    """{имя: значение} однократных присваиваний строкового выражения в функции."""
    seen = {}
    for node in ast.walk(func):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            seen.setdefault(node.targets[0].id, []).append(node.value)
    return {k: v[0] for k, v in seen.items() if len(v) == 1 and (
        isinstance(v[0], (ast.JoinedStr, ast.BinOp))
        or (isinstance(v[0], ast.Constant) and isinstance(v[0].value, str)))}


def _flat(node, assigns: dict, canon, seen=()) -> list:
    """Слагаемые сообщения по `+` с раскрытием однократных строковых имён."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        return _flat(node.left, assigns, canon, seen) + _flat(node.right, assigns, canon, seen)
    if isinstance(node, ast.Name) and node.id in assigns and node.id not in seen:
        return _flat(assigns[node.id], assigns, canon, (*seen, node.id))
    return [_plan.dump_canon(node, canon)]


def _subtest_withs(func) -> list:
    """[(With подслучая, ключи-значения `subTest`)] исходного теста."""
    found = []
    for node in ast.walk(func):
        if isinstance(node, ast.With):
            for item in node.items:
                call = item.context_expr
                if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute) \
                        and call.func.attr == "subTest":
                    found.append((node, [(k.arg, k.value) for k in call.keywords]))
    return found


def _in_subtest(func) -> set:
    ids = set()
    for with_node, _kw in _subtest_withs(func):
        ids |= {id(n) for n in ast.walk(with_node)}
    return ids


def test_ac11_message_text_is_second_operand_of_assert():
    """Текст сообщения исходного утверждения — второй операнд `assert` той же формы; у подслучая — с суффиксом ярлыка.

    Для каждого исходного `self.assert*` с сообщением функция модуля несёт
    `assert` той же нормальной формы, чьё сообщение — то же выражение
    (вне подслучая) либо начинается тем же выражением, за которым по `+`
    идут слагаемые ярлыка (внутри `subTest`; слагаемые читаются через
    однократно присвоенные строковые имена функции).

    Ловит мутацию: `self.assertIsNone(refusal, ctx)` перенесён как `assert
    refusal is None` без сообщения, или `assertEqual(added, [], note)` — с
    сообщением `"добавки нет"` — пары нет, тест краснеет с функцией.
    """
    base_trees, _heads, pairs = _moved_pairs()
    problems = []
    for test, func in pairs:
        base_c, canon = _new_canon(base_trees, test, func)
        old_assigns, new_assigns = _assigns(test.func), _assigns(func)
        inside = _in_subtest(test.func)
        have = []
        for node in _plan.plain_assertions(func):
            if node.msg is not None:
                have.append((_plan.normal_form(node, canon),
                             _flat(node.msg, new_assigns, canon)))
        for node in _plan.self_assertions(test.func):
            msg = _plan.msg_arg(node)
            if msg is None:
                continue
            form = _plan.normal_form(node, base_c)
            want = _flat(msg, old_assigns, base_c)
            sub = id(node) in inside
            if not any(f == form and (m == want or (sub and m[:len(want)] == want
                                                    and len(m) > len(want)))
                       for f, m in have):
                problems.append(f"{test.key} → {func.name}: сообщение "
                                f"{ast.unparse(msg)[:80]} у {ast.unparse(node)[:60]} "
                                f"не вторым операндом assert")
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-12

def _loop_key(loop, canon) -> tuple:
    return (_plan.dump_canon(loop.target, canon), _plan.dump_canon(loop.iter, canon))


def _enclosing_loop(func, node):
    """Самый внутренний цикл `for` функции, содержащий узел."""
    best = None
    for loop in ast.walk(func):
        if isinstance(loop, ast.For) and any(n is node for n in ast.walk(loop)):
            if best is None or loop.lineno >= best.lineno:
                best = loop
    return best


def _label_dump(keywords, canon) -> str:
    values = []
    for i, (key, value) in enumerate(keywords):
        values.append(ast.Constant(value=(", " if i else "") + f"{key}="))
        values.append(ast.FormattedValue(value=value, conversion=ord("r"),
                                         format_spec=None))
    return _plan.dump_canon(ast.JoinedStr(values=values), canon)


def test_ac12_subtest_sets_kept_as_loops_with_label_suffix_in_every_message():
    """Все 17 наборов `subTest` — прежним циклом в одной функции; сообщение каждого утверждения подслучая — `<прежнее> + "; " + f"<ключ>={<значение>!r}, …"`.

    Для каждого исходного теста с `subTest` есть ровно одна функция модуля
    без `parametrize`; в ней есть цикл с той же целью и перебираемым
    выражением, что цикл, объемлющий `with self.subTest(…)`. У каждого
    `assert` внутри этого цикла слагаемые сообщения кончаются `"; "` и
    f-строкой ярлыка с ключами и значениями прежнего `subTest` (`!r`); у
    утверждения без прежнего сообщения (declared :41) сообщение — сама
    f-строка ярлыка. Вызовы `assert_fresh`/`wait_texts` внутри цикла несут
    `"; "` и ярлык в аргументе.

    Ловит мутацию: набор `test_ac6` разложен в `@pytest.mark.parametrize`
    (общее состояние стенда потеряно), ярлык `a_first` пропал из
    сообщения `assert rows[b_task] == before[b_task]`, или ярлык собран
    `f"{ctx} holder={holder_target}"` без `!r` — тест краснеет с функцией.
    """
    base_trees, _heads, pairs = _moved_pairs()
    problems, seen = [], 0
    by_test = {}
    for test, func in pairs:
        by_test.setdefault(test.key, (test, []))[1].append(func)
    for key, (test, funcs) in sorted(by_test.items()):
        withs = _subtest_withs(test.func)
        if not withs:
            continue
        seen += len(withs)
        if len(funcs) != 1:
            problems.append(f"{key}: функций модуля {len(funcs)}, нужна одна")
            continue
        func = funcs[0]
        if any(isinstance(d, ast.Call) and ast.unparse(d.func).endswith("parametrize")
               for d in func.decorator_list):
            problems.append(f"{func.name}: parametrize вместо цикла")
        base_c, canon = _new_canon(base_trees, test, func)
        new_assigns = _assigns(func)
        semi = _plan.dump_canon(ast.Constant(value="; "), canon)
        for with_node, keywords in withs:
            loop = _enclosing_loop(test.func, with_node)
            label = _label_dump(keywords, base_c)
            match = [n for n in ast.walk(func) if isinstance(n, ast.For)
                     and _loop_key(n, canon) == _loop_key(loop, base_c)]
            if not match:
                problems.append(f"{func.name}: нет цикла "
                                f"`for {ast.unparse(loop.target)} in "
                                f"{ast.unparse(loop.iter)}`")
                continue
            no_msg = {_plan.normal_form(n, base_c) for n in ast.walk(with_node)
                      if _plan.is_self_assert(n) and _plan.msg_arg(n) is None}
            for node in ast.walk(match[0]):
                if isinstance(node, ast.Assert):
                    flat = _flat(node.msg, new_assigns, canon) if node.msg else []
                    if _plan.normal_form(node, canon) in no_msg:
                        ok = flat == [label]
                    else:
                        ok = len(flat) >= 3 and flat[-2:] == [semi, label]
                    if not ok:
                        problems.append(f"{func.name}:{node.lineno}: сообщение без "
                                        f"суффикса ярлыка {ast.unparse(loop.target)}")
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                        and node.func.id in ("assert_fresh", "wait_texts"):
                    flats = [_flat(a, new_assigns, canon) for a in node.args]
                    if not any(f[-2:] == [semi, label] for f in flats):
                        problems.append(f"{func.name}:{node.lineno}: "
                                        f"{node.func.id} без ярлыка подслучая")
    assert seen == _plan.SUBTEST_COUNT, (
        f"наборов subTest в исходных тестах {seen}, SPEC называет {_plan.SUBTEST_COUNT}")
    assert not problems, "\n".join(problems)


def test_ac12_wait_texts_differs_only_by_case_parameter():
    """`wait_texts` очереди отличается от исходной только последним параметром `case: str = ""` и `… + case` в сообщении.

    Функция `wait_texts` файла очереди: последний параметр — `case` с
    аннотацией `str` и умолчанием `""`; её `assert` несёт сообщение
    `<прежнее сообщение> + case`; без этих двух отличий параметры и тело
    равны `WaitTextsByProjectTest.wait_texts` с заменой `self.`.

    Ловит мутацию: ярлык подслучая передан в `wait_texts` позиционно без
    умолчания (`case: str`), склеен внутри f-строки (`f"{caller} получил
    окно{case}"`) или параметр назван `label` — форма другая, тест
    краснеет.
    """
    func = _plan.module_functions(_ctx.head_trees()[_plan.QUEUE_MODULE]).get("wait_texts")
    assert func is not None, f"в {_plan.QUEUE_MODULE} нет функции wait_texts"
    last = func.args.args[-1] if func.args.args else None
    assert last is not None and last.arg == "case", (
        f"последний параметр wait_texts: {last.arg if last else None}")
    assert last.annotation is not None and ast.unparse(last.annotation) == "str", (
        "у case нет аннотации str")
    assert func.args.defaults and isinstance(func.args.defaults[-1], ast.Constant) \
        and func.args.defaults[-1].value == "", "у case нет умолчания \"\""
    asserts = _plan.plain_assertions(func)
    assert asserts and all(isinstance(a.msg, ast.BinOp) and isinstance(a.msg.op, ast.Add)
                           and isinstance(a.msg.right, ast.Name) and a.msg.right.id == "case"
                           for a in asserts), (
        f"сообщения assert wait_texts: {[ast.unparse(a.msg) for a in asserts if a.msg]}")
    problems = _helper_problems(_ctx.base_trees(), _plan.QUEUE_MODULE,
                                ast.Module(body=[func], type_ignores=[]))
    problems = [p for p in problems if "::wait_texts" in p]
    assert not problems, "\n".join(problems)


def _carried_nodes(func) -> list:
    """Глотание (`try`), замыкания (`lambda`, вложенные функции) и подмены
    (`with mock.…`/`patch_sleep`) тела."""
    found = []
    for node in ast.walk(func):
        if isinstance(node, (ast.Try, ast.Lambda)):
            found.append(node)
        elif isinstance(node, ast.FunctionDef) and node is not func:
            found.append(node)
        elif isinstance(node, ast.With) and any(
                "patch" in ast.unparse(i.context_expr.func if isinstance(
                    i.context_expr, ast.Call) else i.context_expr)
                for i in node.items):
            found.append(node)
    return found


def test_ac12_swallowing_substitutions_and_closures_carried_verbatim():
    """Глотание `sqlite3.Error`/`SystemExit`, подмены (`mock.patch…`) и замыкания перенесены дословно.

    Для каждого `try`, `lambda`, вложенной функции и блока `with` с
    подменой (`mock.patch…`, `patch_sleep`) исходного теста функция
    модуля несёт узел с той же общей формой (`self.<помощник>` ↔ функция,
    `self` ↔ стенд); то же для помощника `run_wait` очереди (вложенная
    `fake_sleep`, подмена `time.monotonic` и паузы); глотаний `sqlite3.Error`
    и `SystemExit` в перенесённых тестах не меньше двух.

    Ловит мутацию: `except sqlite3.Error: pass` в `test_migrate_adds_
    merge_after_to_old_tasks_table` заменён на `pytest.raises`, лямбды
    `test_ac6` превращены в прямые вызовы, `on_sleep` потерял
    `store.dequeue_merge_wait` — узла нет, тест краснеет с функцией.
    """
    base_trees, heads, pairs = _moved_pairs()
    problems, swallowed = [], 0
    for test, func in pairs:
        base_c, canon = _new_canon(base_trees, test, func)
        have = {_plan.dump_canon(n, canon) for n in _carried_nodes(func)}
        for node in _carried_nodes(test.func):
            if _plan.dump_canon(node, base_c) not in have:
                problems.append(f"{test.key} → {func.name}: нет "
                                f"{ast.unparse(node).splitlines()[0][:90]}")
        swallowed += sum(1 for n in ast.walk(func) if isinstance(n, ast.ExceptHandler)
                         and n.type is not None
                         and ast.unparse(n.type) in ("sqlite3.Error", "SystemExit"))
    run_wait = _plan.module_functions(heads[_plan.QUEUE_MODULE]).get("run_wait")
    base_run = _plan.class_method(base_trees[_plan.MUTEX], _plan.MUTEX_BASE, "run_wait")
    if run_wait is None or not run_wait.args.args:
        problems.append("в файле очереди нет функции run_wait(<стенд>, …)")
    else:
        stand = run_wait.args.args[0].arg
        calls = _plan.class_calls(base_trees[_plan.MUTEX], _plan.MUTEX, _plan.MUTEX_BASE)
        base_c = _plan.Canon(set(), calls)
        canon = _plan.Canon({stand}, {})
        have = {_plan.dump_canon(n, canon) for n in _carried_nodes(run_wait)}
        problems += [f"run_wait: нет {ast.unparse(n).splitlines()[0][:90]}"
                     for n in _carried_nodes(base_run)
                     if _plan.dump_canon(n, base_c) not in have]
    if swallowed < 2:
        problems.append(f"глотаний sqlite3.Error/SystemExit в перенесённых тестах "
                        f"{swallowed}, в исходных два")
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
