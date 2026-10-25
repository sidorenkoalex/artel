"""AC-7 (раскладка и докстринг), AC-8 … AC-12, AC-13 (заявки):
`tests/test_merge_after_module.py` (HEAD) против шести файлов волны базы
ветки — разделы по файлам, импорты, стиль pytest без тестовых классов и
`subTest`, фикстуры стендов из тел `setUp`, помощники-функции с префиксом
файла, константы, дословные тела, ожидания и сообщения, циклы подслучаев
с ярлыком, глотание, подмены и замыкания.

Группа: разовый
Красен до реализации: тестов шести файлов волны в tests/test_merge_after_module.py ещё нет — фикстур, помощников, констант и разделов не найдено, свод не сделан.

Модуль читается из HEAD рабочей копии, исходные файлы и прежний модуль —
из базы ветки (`_pult.DIFF_BASE`). Сравнение статическое (ast): тест не
исполняет ни новые, ни исходные тесты. «Тело дословно» сверяется
деревом тела источника, переведённого правилами требований 9–11 SPEC:
`self.` → параметр стенда, `self.<метод>(…)` → `<префикс>_<метод>(<стенд>,
…)` (статический — без стенда), константы — новыми именами
(`_plan.CONST_RENAMES`), `self.assertX(…)` → `assert …`, `super().setUp()`
отброшен, у фикстуры — хвост `return <параметр>`; локальные `journal`/
`task` могут носить новое имя. «Функция, в которую перенесён тест» —
функция-тест модуля с его именем (`_plan.moved_to`); тест, названный в PLAN
удалённым дублем, не ищется.
"""
import ast
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _ctx  # noqa: E402
import _plan  # noqa: E402

_WAVE_MARK = "3м-2б"
_ADDED_IMPORTS = ["github_adapter", "guard", "re", "subprocess", "workspace"]
_BANNED_NAMES = ("tempfile", "Path", "RealGitSandbox", "InitializedTmpRootTest",
                 "TmpRootTest", "TmpDirTest")


def _removed() -> set:
    try:
        return _ctx.removed()
    except LookupError:
        return set()


def _context():
    return _ctx.base_trees(), _ctx.base_tests(), _ctx.head_tree(), _removed()


def _moved_pairs():
    base_trees, tests, head, removed = _context()
    return base_trees, head, _ctx.moved_pairs(tests, head, removed)


def _new_canon(base_trees, test, func):
    base_c = _plan.base_canon(base_trees[test.path], test.path)
    return base_c, _plan.new_canon(func, test.func, base_c)


def _marks(head_text: str, base_trees) -> dict:
    return _plan.section_marks(head_text, _ctx.base_end(), base_trees)


def _stand_name(path: str) -> str:
    return f"{_plan.PREFIX[path]}_stand"


# ------------------------------------------------------------------ AC-7

def test_ac7_one_section_per_file_in_order_with_class_and_file_comment():
    """Разделы — по одному на прежний файл в порядке `answer` … `new_declares`, каждый открыт комментарием с именем бывшего класса и файла.

    Ниже последнего определения прежнего модуля для каждого из шести
    файлов есть строка-комментарий `# …` с именем файла (без `.py`) и
    именем одного из его классов; строки идут в порядке файлов волны.
    Каждая перенесённая функция-тест, функция-помощник `<префикс>_…`,
    фикстура `<префикс>_stand` и константа файла стоит в разделе своего
    файла (между его комментарием и комментарием следующего); `CROCKFORD` —
    в разделе `spec_gate`, `WAIT_PREFIX` — `status_show`, `ids_of` —
    `answer`.

    Ловит мутацию: тесты `status_show` вставлены перед разделом `plan`,
    раздел помечен «# DependencyOutputSandbox» без имени файла, или
    `ids_of` определён в разделе `status_show` — порядок, комментарий или
    раздел другие, тест краснеет с именем.
    """
    base_trees, tests, head, removed = _context()
    text = _ctx.head_module_text()
    marks = _marks(text, base_trees)
    problems = [f"{p}: нет комментария раздела с именем файла и класса"
                for p in _plan.SOURCE_FILES if p not in marks]
    assert not problems, "\n".join(problems)
    order = [marks[p] for p in _plan.SOURCE_FILES]
    assert order == sorted(order), f"разделы не в порядке файлов волны: {order}"
    funcs = _plan.module_functions(head)
    where = {}
    for test in tests.values():
        if test.key not in removed:
            for func in _plan.moved_to(test.name, _plan.module_tests(head)):
                where[func.name] = (func.lineno, test.path)
    for name, (path, _cls, _m) in _plan.helper_sources(base_trees).items():
        if name in funcs:
            where[name] = (funcs[name].lineno, path)
    for path in _plan.SOURCE_FILES:
        if _stand_name(path) in funcs:
            where[_stand_name(path)] = (funcs[_stand_name(path)].lineno, path)
        for name in _plan.module_level_names(base_trees[path]):
            if name in dict(_plan.MODULE_SAME).get(path, ()):
                continue
            home = _plan.SHARED_HOME.get(name, path)
            new_name = _plan.CONST_RENAMES.get(path, {}).get(name, name)
            if name in _plan.SHARED_HOME and home != path:
                continue
            for node in _plan.top_level_defs(head, new_name):
                if node.lineno > _ctx.base_end():
                    where[new_name] = (node.lineno, home)
    for name, (line, path) in sorted(where.items()):
        owner = _plan.section_of(marks, line)
        if owner != path:
            problems.append(f"{name} (строка {line}): в разделе {owner}, ожидался {path}")
    assert not problems, "\n".join(problems)


def test_ac7_module_docstring_gains_wave_paragraph_with_files_and_specs():
    """Докстринг модуля дополнен абзацем о волне 3м-2б: шесть прежних файлов и SPEC 01M44EP0D47F498TEE08MNGBYT и 01M45D29BQJE8FJYJA4JQWSYFZ, без «Группа:» и «Красен до реализации».

    Докстринг HEAD начинается докстрингом базы и длиннее его; добавленная
    часть отделена пустой строкой (новый абзац), несёт «3м-2б», имена
    шести прежних файлов и оба идентификатора SPEC; ни одна строка
    докстринга не начинается с «Группа:», в нём нет «Красен до
    реализации».

    Ловит мутацию: тесты дописаны, а докстринг оставлен прежним, абзац не
    назвал `…new_declares_merge_after.py` (или SPEC
    01M45D29BQJE8FJYJA4JQWSYFZ), либо в него перенесена строка «Группа:
    долгоживущий» прежнего файла — тест краснеет с находкой.
    """
    old = ast.get_docstring(_ctx.base_module_tree()) or ""
    new = ast.get_docstring(_ctx.head_tree()) or ""
    assert new.startswith(old) and len(new) > len(old), (
        "докстринг HEAD не продолжает докстринг базы")
    tail = new[len(old):]
    problems = []
    if not tail.startswith("\n\n"):
        problems.append(f"добавка не новым абзацем: {tail[:80]!r}")
    if _WAVE_MARK not in tail:
        problems.append(f"в добавке нет «{_WAVE_MARK}»")
    problems += [f"нет имени {Path(p).name}" for p in _plan.SOURCE_FILES
                 if Path(p).name not in tail]
    problems += [f"нет SPEC {s}" for s in _plan.SPEC_IDS if s not in tail]
    problems += [f"строка «{line.strip()}»" for line in new.split("\n")
                 if line.strip().startswith("Группа:")]
    if "Красен до реализации" in new:
        problems.append("есть «Красен до реализации»")
    assert not problems, "докстринг модуля:\n" + "\n".join(problems)


# ------------------------------------------------------------------ AC-8

def _bound_imports(tree) -> list:
    found = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            found += [(alias.asname or alias.name).split(".")[0] for alias in node.names]
    return found


def test_ac8_added_only_missing_imports_and_none_repeated():
    """Добавлены ровно недостающие импорты `re`, `subprocess`, `github_adapter`, `workspace` (из `orchestrator`), `guard` (из `scripts`); ни одно имя не связано дважды.

    Множество имён, связанных импортом верхнего уровня в HEAD, минус то же
    множество базы равно перечню критерия; `github_adapter` и `workspace`
    импортированы из `orchestrator`, `guard` — из `scripts`; ни одно имя не
    связано импортом больше одного раза.

    Ловит мутацию: свод перенёс `import unittest`/`import tempfile`, повторил
    `from orchestrator import config` второй строкой или взял `guard` из
    `orchestrator.advance_gates` — разница, источник или повтор другие,
    тест краснеет.
    """
    head = _ctx.head_tree()
    names = _bound_imports(head)
    new = set(names) - set(_bound_imports(_ctx.base_module_tree()))
    assert sorted(new) == _ADDED_IMPORTS, (
        f"добавлены импорты {sorted(new)}, ожидались {_ADDED_IMPORTS}")
    repeated = sorted({n for n in names if names.count(n) > 1})
    assert not repeated, f"имена, импортированные повторно: {repeated}"
    sources = {}
    for node in head.body:
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                sources[alias.asname or alias.name] = node.module
    problems = [f"{n} из {sources.get(n)}, ожидался {want}"
                for n, want in (("github_adapter", "orchestrator"),
                                ("workspace", "orchestrator"), ("guard", "scripts"))
                if sources.get(n) != want]
    assert not problems, "\n".join(problems)


def test_ac8_no_unittest_tempfile_path_sandbox_bases_main_subtest_or_test_classes():
    """В модуле нет `unittest`, `tempfile`, `Path`, `RealGitSandbox`, `InitializedTmpRootTest`, `__main__`, `subTest` и тестовых классов; единственный класс — `DivisionSandbox`.

    Нет `import unittest` и `from unittest import …` кроме `mock`; имён
    `tempfile`, `Path`, `RealGitSandbox`, `InitializedTmpRootTest`,
    `TmpRootTest`, `TmpDirTest` нет; на верхнем уровне нет `if __name__ ==
    "__main__"`; обращений `subTest` нет; классы модуля — ровно
    `DivisionSandbox`.

    Ловит мутацию: свод оставил `class AnswerMandateSandbox(RealGitSandbox)`
    со `setUp`, перенёс `tempfile.TemporaryDirectory()` стенда `guard`
    вместо `tmp_dir` или хвост `unittest.main()` — находка перечислена,
    тест краснеет.
    """
    tree = _ctx.head_tree()
    problems = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "subTest":
            problems.append(f"subTest в строке {node.lineno}")
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "unittest" or (alias.name.startswith("unittest.")
                                                and alias.name != "unittest.mock"):
                    problems.append(f"import unittest в строке {node.lineno}")
                if alias.name in _BANNED_NAMES:
                    problems.append(f"import {alias.name} в строке {node.lineno}")
        if isinstance(node, ast.ImportFrom):
            if node.module == "unittest" and any(a.name != "mock" for a in node.names):
                problems.append(f"from unittest import … в строке {node.lineno}")
            problems += [f"импорт {a.name} в строке {node.lineno}" for a in node.names
                         if (a.asname or a.name) in _BANNED_NAMES]
        if isinstance(node, ast.Name) and node.id in _BANNED_NAMES:
            problems.append(f"{node.id} в строке {node.lineno}")
    problems += [f"блок __main__ в строке {n.lineno}" for n in tree.body
                 if isinstance(n, ast.If) and "__main__" in ast.unparse(n.test)]
    classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    if classes != ["DivisionSandbox"]:
        problems.append(f"классы модуля: {classes}")
    assert not problems, "\n".join(problems)


# ------------------------------------------------------------------ AC-9

@pytest.mark.parametrize("path", list(_plan.SOURCE_FILES))
def test_ac9_stand_fixture_body_is_setup_body(path):
    """Фикстура `<префикс>_stand(<общая фикстура>)` — тело исходного `setUp` без `super().setUp()` с заменой `self.` и хвостом `return <параметр>`.

    `answer_stand(real_git)`, `guard_stand(tmp_dir)` (только три первые
    строки `setUp`: зерно, `print`, `rng`), `plan_stand(light_transition)`
    (с `light_transition.in_repo_handlers.append(plan_branch_not_behind)`),
    `spec_gate_stand`, `status_show_stand`, `new_declares_stand`
    (`light_transition`, вложенная `ensure` — вложенной дословно).
    Единственный параметр — общая фикстура; утверждений нет; тело без
    хвостового `return <параметр>` равно телу `setUp`, переведённому
    правилами требования 10 (вызов `self.role_env("")` — `answer_role_env(
    real_git, "")`).

    Ловит мутацию: `guard_stand` переносит `tempfile.TemporaryDirectory()`
    и `self.tdir` (строки :63–65), `plan_stand` добавляет обработчик как
    `light_transition.branch_not_behind`, `answer_stand` не снимает
    окружение роли, или `ensure` вынесена из `new_declares_stand` —
    параметр или тело другие, тест краснеет с фикстурой.
    """
    base_trees = _ctx.base_trees()
    tree = _ctx.head_tree()
    found = [f for f in _plan.fixtures(tree) if f.name == _stand_name(path)]
    assert len(found) == 1, f"фикстур {_stand_name(path)}: {len(found)}"
    func = found[0]
    param = _plan.STAND_PARAM[path]
    args = [a.arg for a in func.args.args]
    assert args == [param], f"{func.name}: параметры {args}, ожидался ({param})"
    asserts = [n.lineno for n in ast.walk(func) if _plan.is_assertion_node(n)]
    assert not asserts, f"{func.name}: утверждения в строках {asserts}"
    body, tail = _plan.body_without_tail_return(func)
    assert tail == param, f"{func.name}: тело не кончается `return {param}`"
    want = _plan.setup_body(path, base_trees[path], param)
    got = [_plan.clean(s) for s in body]
    assert [ast.dump(s) for s in got] == [ast.dump(s) for s in want], (
        f"{func.name}: тело ≠ {_plan.SETUP_CLASS[path]}.setUp:\n"
        + "\n".join(ast.unparse(s) for s in want) + "\nв модуле:\n"
        + "\n".join(ast.unparse(s) for s in got))


def test_ac9_fixture_names_unique_and_differ_from_shared_and_module_fixtures():
    """Имена новых фикстур не совпадают с фикстурами `tests/fixtures.py`, прежнего модуля и между собой.

    Ловит мутацию: стенд `plan` назван `light_transition` (затеняет общую)
    или `merge_after_stand` (затеняет стенд волны 3м-2) — имя совпало, тест
    краснеет с ним.
    """
    shared = {f.name for f in _plan.fixtures(ast.parse(_ctx.head_text(_plan.FIXTURES_FILE)))}
    assert shared, f"в {_plan.FIXTURES_FILE} не найдено фикстур"
    old = [f.name for f in _plan.fixtures(_ctx.base_module_tree())]
    names = [f.name for f in _plan.fixtures(_ctx.head_tree())]
    added = list(names)
    for name in old:
        if name in added:
            added.remove(name)
    clash = sorted({n for n in added if n in shared or n in old or names.count(n) > 1})
    assert not clash, f"имена фикстур совпадают: {clash}"


# ------------------------------------------------------------------ AC-10

def test_ac10_field_zones_not_redefined_and_shared_defined_once_verbatim():
    """`FIELD` и `ZONES` не переопределены; `CROCKFORD`, `WAIT_PREFIX`, `ids_of` определены по разу — дословно, как в первом по порядку прежнем файле.

    `FIELD`, `ZONES` присвоены в модуле ровно один раз — прежним
    определением модуля; `CROCKFORD` (как в `spec_gate`), `WAIT_PREFIX`
    (как в `status_show`), `ids_of` (тело с докстрингом из `answer`) —
    ровно одно определение верхнего уровня, совпадающее с исходным.

    Ловит мутацию: в разделе `guard` повторено `FIELD = "merge_after"`,
    `ids_of` взят из `status_show` без докстринга или определён второй раз
    в разделе `plan` — число или вид определений другие, тест краснеет с
    именем.
    """
    base_trees = _ctx.base_trees()
    head = _ctx.head_tree()
    old = _ctx.base_module_tree()
    problems = []
    for name in ("FIELD", "ZONES"):
        defs = _plan.top_level_defs(head, name)
        was = _plan.top_level_defs(old, name)
        if len(defs) != 1 or len(was) != 1 or \
                ast.dump(_plan.clean(defs[0])) != ast.dump(_plan.clean(was[0])):
            problems.append(f"{name}: определений {len(defs)} или не прежнее")
    for name, home in _plan.SHARED_HOME.items():
        defs = _plan.top_level_defs(head, name)
        want = _plan.top_level(base_trees[home], name)
        if len(defs) != 1:
            problems.append(f"{name}: определений {len(defs)}")
        elif ast.dump(_plan.clean(defs[0])) != ast.dump(_plan.clean(want)):
            problems.append(f"{name}: не как в {Path(home).name}")
    assert not problems, "\n".join(problems)


def test_ac10_prefixed_constants_with_verbatim_values():
    """`ANSWER_MARKER`, `GUARD_SPEC_TEXT`, `PLAN_SPEC_TEXT`, `SPEC_GATE_SPEC_TEXT`, `STATUS_SHOW_SPEC_TEXT`, `STATUS_SHOW_UNFINISHED_STATES`, `NEW_DECLARES_UNFINISHED_STATES` — прежние значения дословно; `ANSWER_MARKER` — литерал.

    Для каждой пары «прежнее имя → новое имя» в модуле ровно одно
    присваивание нового имени, его значение совпадает (`ast.dump`) с
    прежним; значение `ANSWER_MARKER` — строковый литерал, а не `MANDATE`
    или `MARKER` модуля.

    Ловит мутацию: `ANSWER_MARKER = MANDATE` (литерал совпадает), из
    `NEW_DECLARES_UNFINISHED_STATES` выпал `spec_writing` или
    `GUARD_SPEC_TEXT` получил текст `spec_gate` — значение другое, тест
    краснеет с именем.
    """
    base_trees = _ctx.base_trees()
    head = _ctx.head_tree()
    problems = []
    for path, renames in _plan.CONST_RENAMES.items():
        for old_name, new_name in renames.items():
            want = _plan.top_level(base_trees[path], old_name)
            defs = _plan.top_level_defs(head, new_name)
            if want is None:
                problems.append(f"{path}: {old_name} нет в базе — база не та")
            elif len(defs) != 1 or not isinstance(defs[0], ast.Assign):
                problems.append(f"{new_name}: присваиваний {len(defs)}")
            elif ast.dump(_plan.clean(defs[0].value)) != ast.dump(_plan.clean(want.value)):
                problems.append(f"{new_name}: значение не как {old_name} "
                                f"{Path(path).name}")
    marker = _plan.top_level_defs(head, "ANSWER_MARKER")
    if marker and not (isinstance(marker[0], ast.Assign)
                       and isinstance(marker[0].value, ast.Constant)
                       and isinstance(marker[0].value.value, str)):
        problems.append("ANSWER_MARKER — не строковый литерал")
    assert not problems, "\n".join(problems)


def test_ac10_other_constants_and_module_functions_verbatim_with_same_names():
    """Остальные константы и функции модулей прежних файлов перенесены дословно прежними именами.

    Для каждого имени верхнего уровня прежнего файла, кроме не
    переопределяемых (`FIELD`, `ZONES`), общих (`CROCKFORD`, `WAIT_PREFIX`,
    `ids_of`) и переименованных, в модуле ровно одно определение того же
    имени, совпадающее с прежним (`ast.dump`): `DOCS_REF_PREFIX`, `ARROW`,
    `REPEAT_WORDS`, `PLAN_TEXT`, `JUSTIFIED`, `UNJUSTIFIED`, `SHOW_PREFIX`,
    `WAITING_STATES`, `OTHER_STATES`, `DECLARED_ACTION`, `NOT_CREATED`,
    `SUFFIX_PREFIX`, `SHOW_MARK`, `GIT_WRITES`, `BAD_ELEMENTS`.

    Ловит мутацию: `ARROW` переписан строкой `"→"` вместо `re.compile`,
    `BAD_ELEMENTS` урезан или `DECLARED_ACTION` заменён на
    `merge_after.DECLARED_ACTION` (литерал стал выражением) — определение
    другое, тест краснеет с именем.
    """
    base_trees = _ctx.base_trees()
    head = _ctx.head_tree()
    problems = []
    for path in _plan.SOURCE_FILES:
        for name in _plan.module_level_names(base_trees[path]):
            if name in _plan.MODULE_SAME.get(path, ()) or name in _plan.SHARED_HOME \
                    or name in _plan.CONST_RENAMES.get(path, {}):
                continue
            want = _plan.top_level(base_trees[path], name)
            defs = _plan.top_level_defs(head, name)
            if len(defs) != 1:
                problems.append(f"{name} ({Path(path).name}): определений {len(defs)}")
            elif ast.dump(_plan.clean(defs[0])) != ast.dump(_plan.clean(want)):
                problems.append(f"{name} ({Path(path).name}): не дословно")
    assert not problems, "\n".join(problems)


def test_ac10_methods_are_prefixed_functions_not_merged_or_replaced():
    """Каждый метод песочниц и тестовых классов — функция `<префикс>_<метод>`; помощники волны 3м-2 не зовутся; `plan_branch_not_behind(repo, *args)`.

    Для каждого метода (кроме `test*` и `setUp`) шести файлов в модуле есть
    функция верхнего уровня `<префикс файла>_<метод>`;
    `plan_branch_not_behind` — параметры `(repo, *args)` без стенда; ни одна
    новая функция модуля не зовёт функции волны 3м-2 (`new_task`, `msg`,
    `journal`, `live_task`, `declared_path_note`, …).

    Ловит мутацию: `spec_gate_unique_prefix` и `new_declares_unique_prefix`
    сведены в одну функцию, `plan_new_task` заменён на `new_task(stand,
    title)` волны 3м-2 или `plan_branch_not_behind` получил стенд первым
    параметром — функции нет, вызов найден или параметры другие, тест
    краснеет с именем.
    """
    base_trees = _ctx.base_trees()
    head = _ctx.head_tree()
    funcs = _plan.module_functions(head)
    problems = [f"нет функции {name} (бывший {cls}.{method} {Path(path).name})"
                for name, (path, cls, method) in sorted(_plan.helper_sources(base_trees).items())
                if name not in funcs]
    static = funcs.get("plan_branch_not_behind")
    if static is not None:
        args = [a.arg for a in static.args.args]
        vararg = static.args.vararg.arg if static.args.vararg else None
        if args != ["repo"] or vararg != "args":
            problems.append(f"plan_branch_not_behind: параметры {args} *{vararg}")
    for func in _ctx.new_functions(head):
        for node in ast.walk(func):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                    and node.func.id in _plan.WAVE_3M2_HELPERS:
                problems.append(f"{func.name}: зовёт {node.func.id} волны 3м-2 "
                                f"в строке {node.lineno}")
    assert not problems, "\n".join(problems)


def test_ac10_set_state_only_as_module_functions():
    """Методов `set_state(task_id, state)` у стендов нет: тесты зовут `status_show_set_state`/`new_declares_set_state`, вызова `<стенд>.set_state(<id>, <состояние>)` нет.

    В новых функциях модуля нет вызова `<имя>.set_state(…)` с двумя
    аргументами; функции перенесённых тестов `status_show` и
    `new_declares`, чьи исходники звали `self.set_state`, зовут
    `<префикс>_set_state`.

    Ловит мутацию: стенд получил атрибут `set_state` с перекрытием и тест
    зовёт `status_show_stand.set_state(dep, "done")` — вызов найден, тест
    краснеет с ним.
    """
    _base_trees, _head, pairs = _moved_pairs()
    problems = []
    for func in _ctx.new_functions():
        for node in ast.walk(func):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and node.func.attr == "set_state" and len(node.args) == 2:
                problems.append(f"{func.name}: {ast.unparse(node)} в строке {node.lineno}")
    for test, func in pairs:
        if test.path not in (_plan.STATUS_SHOW, _plan.NEW_DECLARES):
            continue
        if "set_state" in _plan.self_refs(test.func):
            want = f"{_plan.PREFIX[test.path]}_set_state"
            if not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                       and n.func.id == want for n in ast.walk(func)):
                problems.append(f"{func.name}: нет вызова {want}(…)")
    assert not problems, "\n".join(problems)


def _renamed_locals(base_trees, pairs) -> dict:
    """{(функция, прежнее имя): новое имя} локальных `journal`/`task`
    перенесённых тестов (по тому же значению присваивания)."""
    found = {}
    for test, func in pairs:
        _base_c, canon = _new_canon(base_trees, test, func)
        for new, old in canon.locals.items():
            if old in _plan.LOCALS_TO_RENAME:
                found[(func.name, old)] = new
    return found


def _helper_free_renames(base_trees, head) -> dict:
    """{(функция, прежнее имя): новое имя} локальных `journal`/`task`
    помощников (по совпадению дерева тела)."""
    found = {}
    funcs = _plan.module_functions(head)
    for name, (path, cls, method) in _plan.helper_sources(base_trees).items():
        func = funcs.get(name)
        if func is None:
            continue
        ok, mapping = _helper_matches(base_trees, path, cls, method, func)
        if ok:
            for old, new in mapping.items():
                found[(name, old)] = new
    return found


def test_ac10_local_journal_and_task_renamed_field_errors_keyword_kept():
    """Локальные `journal` и `task` переименованы; параметр только по имени `task` у `guard_field_errors` и аргументы `task=` её вызовов прежние.

    В перенесённых тестах `answer`, `plan`, `guard`, `spec_gate`,
    `new_declares` и в `spec_gate_assert_refused` нет локального имени
    `journal`/`task` (присваивания), а прежнее значение стоит под новым
    именем; `guard_field_errors` несёт параметр только по имени `task`;
    каждый её вызов передаёт `task=`.

    Ловит мутацию: в `test_ac9_justified_plan_value_replaces_db_value`
    оставлена локальная `journal`, затеняющая функцию модуля `journal`,
    или параметр `task` переименован в `task_id` — имя найдено или
    аргумента нет, тест краснеет с функцией.
    """
    base_trees, head, pairs = _moved_pairs()
    problems = []
    renamed = _renamed_locals(base_trees, pairs)
    helper_names = {"spec_gate_assert_refused"}
    funcs = _plan.module_functions(head)
    targets = [(test.func, func) for test, func in pairs]
    src = _plan.helper_sources(base_trees)
    for name in helper_names:
        path, cls, method = src[name]
        if name in funcs:
            targets.append((_plan.class_method(base_trees[path], cls, method), funcs[name]))
    helper_renamed = _helper_free_renames(base_trees, head)
    for base_func, func in targets:
        base_locals = _plan.local_names(base_func)
        stores = _plan.local_names(func)
        for old in _plan.LOCALS_TO_RENAME:
            if old not in base_locals:
                continue
            if old in stores:
                problems.append(f"{func.name}: локальная {old} осталась")
            elif (func.name, old) not in renamed and (func.name, old) not in helper_renamed:
                problems.append(f"{func.name}: прежнее значение {old} не найдено под "
                                f"новым именем")
    field_errors = funcs.get("guard_field_errors")
    if field_errors is None or "task" not in [a.arg for a in field_errors.args.kwonlyargs]:
        problems.append("guard_field_errors: нет параметра только по имени task")
    for func in _ctx.new_functions(head):
        for node in ast.walk(func):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                    and node.func.id == "guard_field_errors" \
                    and "task" not in [k.arg for k in node.keywords]:
                problems.append(f"{func.name}:{node.lineno}: вызов guard_field_errors "
                                f"без task=")
    assert not problems, "\n".join(problems)


def test_ac10_plan_lists_renames_and_body_twins():
    """PLAN называет перечень «прежнее имя → новое имя» (с новыми именами локальных) и совпадения тел.

    В PLAN словом стоят: имя каждой функции-помощника `<префикс>_<метод>`,
    имя каждой фикстуры стенда, каждое новое имя константы
    (`ANSWER_MARKER` …), новые имена локальных `journal`/`task` и слово
    «совпад…» (совпадения тел).

    Ловит мутацию: PLAN перечислил помощники `answer`, а помощники
    `new_declares` или новое имя локальной `journal` не назвал — имя не
    найдено, тест краснеет с ним.
    """
    plan = _ctx.plan_text()
    base_trees, head, pairs = _moved_pairs()
    names = set(_plan.helper_sources(base_trees))
    names |= {_stand_name(p) for p in _plan.SOURCE_FILES}
    names |= {n for r in _plan.CONST_RENAMES.values() for n in r.values()}
    names |= set(_renamed_locals(base_trees, pairs).values())
    names |= {v for (f, _o), v in _helper_free_renames(base_trees, head).items()
              if f == "spec_gate_assert_refused"}
    missing = sorted(n for n in names
                     if not re.search(rf"(?<![\w]){re.escape(n)}(?![\w])", plan))
    if not re.search(r"совпад", plan, re.IGNORECASE):
        missing.append("«совпадения тел»")
    assert not missing, f"не названы в PLAN: {missing}"


# ------------------------------------------------------------------ AC-11

def _helper_matches(base_trees, path, cls, method, func) -> tuple[bool, dict]:
    """(тело и параметры функции `func` = метод `cls.method` с заменой
    `self.`, карта переименованных локальных)."""
    tree = base_trees[path]
    node = _plan.class_method(tree, cls, method)
    name = func.name
    if name in _plan.LABEL_HELPERS:
        func = _plan.strip_case(func, "label", set(_plan.CASE_HELPERS))
    elif name in _plan.CASE_HELPERS:
        func = _plan.strip_case(func, "case", set(_plan.CASE_HELPERS))
    else:
        func = _plan.clean(func)
    bare = method in _plan.bare_methods(path)
    if bare:
        param = "self"
        rest_new, rest_old = func.args, copy_args(node.args, drop_first=False)
    else:
        if not func.args.args:
            return False, {}
        param = func.args.args[0].arg
        rest_new, rest_old = copy_args(func.args, True), copy_args(node.args, True)
    if ast.dump(_plan.clean(rest_new)) != ast.dump(_plan.clean(rest_old)):
        return False, {}
    if (func.returns is None) != (node.returns is None) or (
            func.returns is not None and
            ast.dump(_plan.clean(func.returns)) != ast.dump(_plan.clean(node.returns))):
        return False, {}
    want = _plan.translate(path, tree, node, param)
    mapping = {}
    ok = _plan.match_nodes([_plan.clean(s) for s in _plan.strip_docstring(want.body)],
                           [_plan.clean(s) for s in _plan.strip_docstring(func.body)],
                           set(_plan.LOCALS_TO_RENAME), mapping)
    return ok, {k: v for k, v in mapping.items() if k != v}


def copy_args(args, drop_first: bool):
    node = _plan.clean(args)
    if drop_first:
        node.args = node.args[1:]
    return node


def test_ac11_methods_moved_as_functions_with_verbatim_bodies():
    """Методы перенесены функциями: первый параметр — стенд, остальные параметры и аннотация — как у метода, тело дословно с заменой `self.`.

    Для каждого помощника `<префикс>_<метод>`: тело (без докстринга) равно
    телу метода, переведённому правилами требований 9–11 (`self.<метод>`
    файла → функция модуля со стендом, методы и атрибуты песочницы — через
    стенд, константы — новыми именами, `self.assertX` → `assert`); у
    помощников с ярлыком подслучая сверка — без параметра `case`/`label`,
    его передачи и `+ case`/`+ label`; локальная `journal`
    `spec_gate_assert_refused` может носить новое имя.

    Ловит мутацию: `answer_run_answer` перестал глотать `SystemExit` с
    кодом 0, `new_declares_assert_refused_without_traces` потерял сверку
    `ensure_calls`, `status_show_with_dependencies` зовёт `self.capture`
    модульной функцией, или `spec_gate_insert` потерял `target=
    config.DEFAULT_TARGET` — тело или параметры другие, тест краснеет с
    именем.
    """
    base_trees = _ctx.base_trees()
    funcs = _plan.module_functions(_ctx.head_tree())
    problems = []
    for name, (path, cls, method) in sorted(_plan.helper_sources(base_trees).items()):
        func = funcs.get(name)
        if func is None:
            problems.append(f"нет функции {name} (бывший {cls}.{method})")
            continue
        ok, mapping = _helper_matches(base_trees, path, cls, method, func)
        if not ok:
            problems.append(f"{name}: тело или параметры ≠ {cls}.{method} "
                            f"{Path(path).name} с заменой self.")
        bad = {k: v for k, v in mapping.items() if v in funcs}
        if bad:
            problems.append(f"{name}: локальные переименованы в имена функций "
                            f"модуля {bad}")
    assert not problems, "\n".join(problems)


def test_ac11_moved_tests_take_stand_and_call_helpers_as_functions():
    """Перенесённый тест берёт фикстуру своего стенда и зовёт помощники функциями, а не `<стенд>.<метод>(…)`.

    Функция каждого перенесённого теста несёт параметр `<префикс>_stand`
    своего файла, не несёт `self`; ни в одной новой функции модуля нет
    вызова `<параметр>.<метод>(…)`, где метод — помощник одного из шести
    файлов (`accepted`, `note`, `element`, `with_dependencies`, …), а
    помощники с утверждениями (`answer_accepted`, …,
    `new_declares_status_line`) зовутся голым именем.

    Ловит мутацию: стенд получил методы-обёртки и тест зовёт
    `answer_stand.accepted(…)` или `stand.status_line(task_id)`, либо тест
    `plan` берёт `light_transition` вместо `plan_stand` — вызов найден или
    параметра нет, тест краснеет с функцией.
    """
    base_trees, head, pairs = _moved_pairs()
    methods = set()
    for path in _plan.SOURCE_FILES:
        methods |= set(_plan.helper_methods(base_trees[path]))
    problems = []
    for test, func in pairs:
        params = [a.arg for a in func.args.args]
        if _stand_name(test.path) not in params or "self" in params:
            problems.append(f"{func.name}: параметры {params}, нужен "
                            f"{_stand_name(test.path)}")
    for func in _ctx.new_functions(head):
        params = {a.arg for a in func.args.args}
        for node in ast.walk(func):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and isinstance(node.func.value, ast.Name) \
                    and node.func.value.id in params | {"self"} \
                    and (node.func.attr in methods
                         or node.func.attr in _plan.ASSERTING_HELPERS):
                problems.append(f"{func.name}: {ast.unparse(node.func)}(…) в строке "
                                f"{node.lineno}")
    assert not problems, "\n".join(problems)


def test_ac11_every_source_assertion_carried_in_same_normal_form():
    """Каждое утверждение исходного теста есть в функции, в которую он перенесён, в той же форме `assert …`.

    Для каждого `self.assert*` исходного теста функция модуля несёт
    `assert` той же нормальной формы (`assertEqual(a, b)` ↔ `assert a ==
    b`, `assertNotEqual` ↔ `!=`, `assertIsNone(x)` ↔ `assert x is None`,
    `assertIsNotNone(x)` ↔ `assert x is not None`, `assertIn`/`assertNotIn`
    ↔ `in`/`not in`, `assertTrue(x)` ↔ `assert x`, `assertFalse(x)` ↔
    `assert not x`, `assertRegex(t, p)` ↔ `assert re.search(p, t)`,
    `self.<помощник>()` ↔ функция, `self` ↔ стенд): литерал остаётся
    литералом, константа — константой, сравнение — тем же оператором;
    вызовов `self.assert*` в функции нет.

    Ловит мутацию: `assertEqual(self.deps(task_id), deps, context)`
    перенесён как `assert set(plan_deps(…)) == set(deps)`, `assertIn(f"{dep}
    ({state})", suffix)` — как `assert dep in suffix`, или
    `assertNotEqual(row["state"], "spec_gate")` — как `assert row["state"]
    == "in_dev"` — формы нет в функции, тест краснеет с ней.
    """
    base_trees, _head, pairs = _moved_pairs()
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

    Ловит мутацию: `self.assertEqual(self.deps(task_id), [], context)`
    перенесён как `assert … == []` без сообщения, или сообщение
    `self.note(line)` заменено строкой `"добавки нет"` — пары нет, тест
    краснеет с функцией.
    """
    base_trees, _head, pairs = _moved_pairs()
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


def _carried_nodes(func) -> list:
    """Глотание (`try`), замыкания (`lambda`, вложенные функции) и подмены
    (`with mock.…`, `mock.patch…` вызовом) тела."""
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
        elif isinstance(node, ast.Call) and "mock.patch" in ast.unparse(node.func):
            found.append(node)
    return found


def test_ac11_swallowing_substitutions_and_closures_carried_verbatim():
    """Глотание `SystemExit`, подмены (`mock.patch…`) и замыкания перенесены дословно.

    Для каждого `try`, `lambda`, вложенной функции и подмены (`mock.patch…`)
    исходного метода — теста, помощника или `setUp` — функция модуля, в
    которую он перенесён, несёт узел той же общей формы (`self.<помощник>`
    ↔ функция, `self` ↔ стенд); обработчиков `except SystemExit` в новых
    функциях модуля не меньше, чем в шести файлах волны.

    Ловит мутацию: `except SystemExit` в `new_declares_run_new` заменён на
    `pytest.raises(SystemExit)`, лямбда `ensure_draft_mr` `plan_stand`
    превращена в `mock.Mock()`, или подмена `mock.patch.dict(os.environ,
    …)` `answer_role_env` снята — узла нет, тест краснеет с функцией.
    """
    base_trees, head, pairs = _moved_pairs()
    funcs = _plan.module_functions(head)
    targets = [(test.path, test.func, func) for test, func in pairs]
    for name, (path, cls, method) in _plan.helper_sources(base_trees).items():
        if name in funcs:
            targets.append((path, _plan.class_method(base_trees[path], cls, method),
                            funcs[name]))
    for path in _plan.SOURCE_FILES:
        setup = _plan.class_method(base_trees[path], _plan.SETUP_CLASS[path], "setUp")
        if _stand_name(path) in funcs and setup is not None:
            targets.append((path, setup, funcs[_stand_name(path)]))
    problems = []
    for path, base_func, func in targets:
        base_c = _plan.base_canon(base_trees[path], path)
        static = base_func.name in _plan.bare_methods(path)
        stand = set() if static or not func.args.args else {func.args.args[0].arg}
        canon = _plan.Canon(stand, {})
        have = {_plan.dump_canon(n, canon) for n in _carried_nodes(func)}
        for node in _carried_nodes(base_func):
            if _plan.dump_canon(node, base_c) not in have:
                problems.append(f"{base_func.name} → {func.name}: нет "
                                f"{ast.unparse(node).splitlines()[0][:90]}")

    def swallowed(trees) -> int:
        return sum(1 for t in trees for n in ast.walk(t)
                   if isinstance(n, ast.ExceptHandler) and n.type is not None
                   and ast.unparse(n.type) == "SystemExit")

    before = swallowed(base_trees.values())
    after = swallowed(_ctx.new_functions(head))
    if after < before:
        problems.append(f"глотаний SystemExit в новых функциях {after}, в "
                        f"исходных {before}")
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
    """Все 8 наборов `subTest` — прежним циклом в одной функции; сообщение каждого утверждения подслучая — `<прежнее> + "; " + f"<ключ>={<значение>!r}"`.

    Для каждого исходного теста с `subTest` есть ровно одна функция модуля
    без `parametrize`; в ней есть цикл с той же целью и перебираемым
    выражением, что цикл, объемлющий `with self.subTest(…)`. У каждого
    `assert` внутри этого цикла слагаемые сообщения кончаются `"; "` и
    f-строкой ярлыка с ключом и значением прежнего `subTest` (`!r`).
    Вызовы помощников с утверждениями внутри цикла (`answer_accepted`,
    `answer_assert_refused`, `plan_prepared_task`, `plan_rejected_case`,
    `new_declares_declared`, `new_declares_assert_refused_without_traces`)
    несут `"; "` и ярлык в аргументе.

    Ловит мутацию: набор `test_ac6_invalid_dependency_refused_without_traces`
    разложен в `@pytest.mark.parametrize` (общее состояние стенда
    потеряно), ярлык `case` не передан в
    `new_declares_assert_refused_without_traces`, или ярлык собран
    `f"case={case}"` без `!r` — тест краснеет с функцией.
    """
    base_trees, _head, pairs = _moved_pairs()
    problems, seen = [], 0
    by_test = {}
    for test, func in pairs:
        by_test.setdefault(test.key, (test, []))[1].append(func)
    labelled = set(_plan.CASE_HELPERS) | set(_plan.LABEL_HELPERS)
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
                        and node.func.id in labelled:
                    flats = [_flat(a, new_assigns, canon)
                             for a in [*node.args, *(k.value for k in node.keywords)]]
                    if not any(f[-2:] == [semi, label] for f in flats):
                        problems.append(f"{func.name}:{node.lineno}: "
                                        f"{node.func.id} без ярлыка подслучая")
    assert seen == _plan.SUBTEST_COUNT, (
        f"наборов subTest в исходных тестах {seen}, SPEC называет {_plan.SUBTEST_COUNT}")
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("name,param", [
    ("answer_accepted", "case"),
    ("answer_assert_refused", "case"),
    ("plan_approve_spec", "case"),
    ("plan_prepared_task", "case"),
    ("new_declares_declared", "case"),
    ("new_declares_assert_refused_without_traces", "case"),
    ("plan_rejected_case", "label"),
])
def test_ac12_labelled_helper_differs_only_by_last_optional_parameter(name, param):
    """Помощник с ярлыком подслучая отличается от исходного только последним `<param>: str = ""`, передачей его дальше и `… + <param>` в сообщениях.

    Последний параметр функции — `case` (у `plan_rejected_case` — `label`)
    с аннотацией `str` и умолчанием `""`; у каждого её `assert` сообщение
    — `<прежнее> + <param>`; каждый её вызов помощника с ярлыком
    (`plan_prepared_task`/`plan_rejected_case` → `plan_approve_spec`)
    передаёт `<param>` последним аргументом; без этих отличий тело и
    параметры равны исходному методу с заменой `self.`.

    Ловит мутацию: ярлык передан в `answer_accepted` позиционным без
    умолчания (`case: str`), склеен внутри f-строки (`f"… {case}"`),
    `plan_prepared_task` не передаёт `case` в `plan_approve_spec`, или
    параметр `plan_rejected_case` назван `case` (затеняет имя варианта) —
    форма другая, тест краснеет.
    """
    base_trees = _ctx.base_trees()
    func = _plan.module_functions(_ctx.head_tree()).get(name)
    assert func is not None, f"в модуле нет функции {name}"
    last = func.args.args[-1] if func.args.args else None
    assert last is not None and last.arg == param, (
        f"последний параметр {name}: {last.arg if last else None}")
    assert last.annotation is not None and ast.unparse(last.annotation) == "str", (
        f"у {param} нет аннотации str")
    assert func.args.defaults and isinstance(func.args.defaults[-1], ast.Constant) \
        and func.args.defaults[-1].value == "", f"у {param} нет умолчания \"\""
    for node in _plan.plain_assertions(func):
        assert isinstance(node.msg, ast.BinOp) and isinstance(node.msg.op, ast.Add) \
            and isinstance(node.msg.right, ast.Name) and node.msg.right.id == param, (
                f"{name}:{node.lineno}: сообщение не `… + {param}`")
    for node in ast.walk(func):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id in _plan.CASE_HELPERS:
            passed = (node.args and isinstance(node.args[-1], ast.Name)
                      and node.args[-1].id == param) or any(
                isinstance(k.value, ast.Name) and k.value.id == param
                for k in node.keywords)
            assert passed, f"{name}:{node.lineno}: {node.func.id} без {param}"
    path, cls, method = _plan.helper_sources(base_trees)[name]
    ok, _mapping = _helper_matches(base_trees, path, cls, method, func)
    assert ok, f"{name}: кроме {param} отличается от {cls}.{method}"


# ------------------------------------------------------------------ AC-13

def test_ac13_every_test_function_declares_mutation():
    """У каждой функции-теста модуля есть строка «Ловит мутацию:».

    Ловит мутацию: свод перенёс тест без заявки (докстринг без «Ловит
    мутацию:», например только первая фраза прежнего) — функция
    перечислена, тест краснеет.
    """
    tests = _plan.module_tests(_ctx.head_tree())
    assert len(tests) > _plan.MODULE_BASE_TESTS, (
        f"в модуле {len(tests)} тестов — перенесённых нет")
    without = [f.name for f in tests if "Ловит мутацию:" not in (ast.get_docstring(f) or "")]
    assert not without, "функции без «Ловит мутацию:»:\n" + "\n".join(without)
