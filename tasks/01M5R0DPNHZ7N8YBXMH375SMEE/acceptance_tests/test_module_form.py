"""AC-7, AC-8, AC-9, AC-10, AC-11, AC-12, AC-13, AC-14, AC-15: форма
приёмников свода — `tests/merge_outcome_sandbox.py`,
`tests/test_merge_outcome_module.py`, дописки `tests/test_outcome_gate_module.py`
и двух импортёров — против исходных файлов волны и прежних версий в базе
ветки.

Группа: разовый
Красен до реализации: на ветке нет tests/merge_outcome_sandbox.py и tests/test_merge_outcome_module.py, в tests/test_outcome_gate_module.py нет тестов added_lines, импортёры берут песочницу из удаляемого файла — свод не сделан.

Приёмники читаются из HEAD рабочей копии (`git show HEAD:…`), исходные
файлы и прежние версии — из базы ветки (`_pult.DIFF_BASE`). Сравнение
статическое (ast): тест не исполняет ни новые, ни исходные тесты, кроме
сбора `pytest --collect-only` импортёров (AC-8).

Тест исходного файла сопоставляется функции своего приёмника (группа М —
`tests/test_merge_outcome_module.py`, группа Д — новые функции
`tests/test_outcome_gate_module.py`) по имени (то же имя или имя с суффиксом
`_…`) и по строкам соответствия «до → после» PLAN (докстринг `_plan.py`).
Перевод тела «`self.` → имя стенда, `self.<метод>(…)` → `<функция>(<стенд>,
…)`» сверяется каноничным `ast.dump`.
"""
import ast
import copy
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _ctx  # noqa: E402
import _plan  # noqa: E402
from _pult import CODE_ROOT  # noqa: E402

_SEED = ", зерно {box.seed}"
_M, _D = _plan.GROUP_M, _plan.GROUP_D
_GROUPS = {"М": _M, "Д": _D}
# Классы, тесты которых берут стенд `two_sided_box` (AC-10).
_TWO_SIDED_CLASSES = ("Ac11TwoSidedErrorNameTest", "Ac12TwoSidedRetryTest",
                      "Ac14OutOfBoundsTest")
# Бывший `subTest` :134 `added_lines`, которому разрешён `parametrize` (AC-13).
_PARAMETRIZE_OK = "CodeExceptionRenameTest::test_rename_from_test_path_to_code_path_is_checked"


def _merge_tree() -> ast.Module:
    return _ctx.head_tree(_plan.MERGE_MODULE)


def _bindings(tree) -> dict:
    """{имя: [утверждения верхнего уровня, связывающие его]}."""
    found = {}
    for node in tree.body:
        for name in _plan.bound_names(node):
            found.setdefault(name, []).append(node)
    return found


def _called(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return getattr(call.func, "id", None)


def _assertion_sites(func) -> list:
    """Строки утверждений в теле: `assert`, `pytest.raises`/`fail`,
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


def _source_methods(group) -> list:
    """[BaseTest] тестов исходного файла группы в базе."""
    return _plan.base_tests(group.source, _ctx.base_text(group.source))


def _target_functions(group) -> dict:
    """{имя: функция} приёмника группы: для М — все функции модуля, для Д —
    функции, которых нет в модуле на базе."""
    if group is _M:
        return _plan.module_functions(_merge_tree())
    return _ctx.new_functions(group.target)


def _target_tree(group) -> ast.Module:
    """Модуль из функций приёмника группы (для Д — только новых)."""
    return ast.Module(body=list(_target_functions(group).values()), type_ignores=[])


def _source_tests_tree(group) -> ast.Module:
    return ast.Module(body=[t.func for t in _source_methods(group)], type_ignores=[])


def _shared_fixture_names() -> set:
    return {f.name for f in _plan.module_functions(
        _ctx.head_tree(_plan.FIXTURES_FILE)).values() if _plan.is_fixture(f)}


def _imports_from(tree, module: str) -> dict:
    """{имя: as-имя} инструкций верхнего уровня `from <module> import …`."""
    return {a.name: a.asname for n in tree.body
            if isinstance(n, ast.ImportFrom) and n.module == module
            for a in n.names}


def _class(tree, name: str):
    return next((n for n in tree.body
                 if isinstance(n, ast.ClassDef) and n.name == name), None)


# ------------------------------------------------------------------ AC-7

def test_ac7_sandbox_module_has_no_tests_or_claims():
    """В `tests/merge_outcome_sandbox.py` нет тестовых функций и методов и нет заявок «Ловит мутацию».

    Ловит мутацию: в модуль песочницы уехал тест `Ac13RetriedBaseRerunTest`
    вместе с классом (или докстринг теста с заявкой) — имя `test_…` или
    строка «Ловит мутацию» найдены, тест краснеет.
    """
    text = _ctx.head_text(_plan.MERGE_SANDBOX)
    tests = [f"{n.name} в строке {n.lineno}" for n in ast.walk(ast.parse(text))
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
             and n.name.startswith("test")]
    assert not tests, f"тесты в {_plan.MERGE_SANDBOX}: {tests}"
    assert _plan.CLAIM not in text, f"заявка «{_plan.CLAIM}» в {_plan.MERGE_SANDBOX}"


def test_ac7_sandbox_docstring_is_one_line():
    """Докстринг `tests/merge_outcome_sandbox.py` — одна непустая строка назначения.

    Ловит мутацию: в модуль перенесён многоабзацный докстринг старого файла
    (или докстринга нет) — тест краснеет.
    """
    doc = ast.get_docstring(_ctx.head_tree(_plan.MERGE_SANDBOX))
    assert doc and doc.strip(), f"у {_plan.MERGE_SANDBOX} нет докстринга"
    assert "\n" not in doc.strip(), f"докстринг не одной строкой:\n{doc}"


def test_ac7_sandbox_statements_equal_old_lines_in_order():
    """Операторы верхнего уровня модуля песочницы, кроме докстринга, по `ast.dump` равны операторам строк 42–99, 101–365 и 955–980 старого файла в том же порядке.

    Ловит мутацию: при переносе выброшен неиспользуемый `import unittest`,
    `TwoSidedSandbox` поставлен до констант, или в `MergeOutcomeSandbox.
    direct_task` правлено сообщение — дамп или порядок расходятся, тест
    краснеет с первым расхождением.
    """
    old = _ctx.base_tree(_plan.MERGE_SOURCE)
    want = [n for n in old.body if any(a <= n.lineno <= b for a, b in _plan.SANDBOX_LINES)]
    assert want, "в старом файле базы нет операторов строк песочницы"
    head = _ctx.head_tree(_plan.MERGE_SANDBOX).body
    got = _plan.strip_docstring(head)
    assert len(got) == len(head) - 1, "у модуля песочницы нет докстринга первым оператором"
    for i, (w, g) in enumerate(zip(want, got)):
        assert ast.dump(w) == ast.dump(g), (
            f"оператор {i + 1} ({_plan.bound_names(w)}, старая строка {w.lineno}) "
            f"не равен оператору модуля в строке {g.lineno}")
    assert len(got) == len(want), (f"операторов модуля {len(got)}, а строк песочницы "
                                   f"старого файла {len(want)}")


def test_ac7_outcome_gate_sandbox_unchanged():
    """`tests/outcome_gate_sandbox.py` на HEAD побайтно равен базе.

    Ловит мутацию: `FLAKY_ON_BASE`/`GATE_WORDS` песочницы мержа дописаны в
    `tests/outcome_gate_sandbox.py` (или поправлен метод `no_gate_refusal`)
    — текст расходится, тест краснеет.
    """
    assert _ctx.head_text(_plan.OUTCOME_SANDBOX) == _ctx.base_text(_plan.OUTCOME_SANDBOX), (
        f"{_plan.OUTCOME_SANDBOX} изменён")


# ------------------------------------------------------------------ AC-8

def _import_lines(text: str, module: str) -> set:
    """Номера строк (с 1) инструкций `from <module> import …`."""
    found = set()
    for node in ast.parse(text).body:
        if isinstance(node, ast.ImportFrom) and node.module == module:
            found |= set(range(node.lineno, (node.end_lineno or node.lineno) + 1))
    return found


@pytest.mark.parametrize("path", list(_plan.IMPORTERS))
def test_ac8_importer_changes_only_import_source(path):
    """В импортёре по сравнению с базой изменена только строка источника импорта, разбивка строк та же.

    Число строк одно; различаются только строки инструкции `from
    tests.test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate import (…)`
    базы, и каждая такая строка на HEAD — строка базы с заменой
    источника на `tests.merge_outcome_sandbox`; хотя бы одна строка
    изменена.

    Ловит мутацию: заодно поправлен докстринг :7 импортёра, имя
    `MergeOutcomeSandbox` взято под псевдонимом, или импорт переписан в одну
    строку — расходится строка вне импорта или разбивка, тест краснеет.
    """
    base, head = _ctx.base_text(path), _ctx.head_text(path)
    b, h = base.split("\n"), head.split("\n")
    assert len(b) == len(h), f"{path}: строк {len(h)} вместо {len(b)}"
    allowed = _import_lines(base, _plan.OLD_IMPORT)
    assert allowed, f"в {path} базы нет импорта из {_plan.OLD_IMPORT}"
    changed = [i + 1 for i, (x, y) in enumerate(zip(b, h)) if x != y]
    assert changed, f"{path} не изменён: импорт из {_plan.OLD_IMPORT} остался"
    wrong = [f"строка {n}: {h[n - 1]!r}" for n in changed
             if n not in allowed or h[n - 1] != b[n - 1].replace(
                 _plan.OLD_IMPORT, _plan.NEW_IMPORT)]
    assert not wrong, f"{path}: лишние правки:\n" + "\n".join(wrong)


def test_ac8_importers_collect_61_tests():
    """`pytest --collect-only` двух импортёров на рабочей копии собирает 61 тест.

    Ловит мутацию: импортёр взял из нового модуля имя, которого там нет
    (или новый модуль не импортируется), — сбор падает или тестов меньше,
    тест краснеет с выводом сбора.
    """
    res = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q",
         "-p", "no:cacheprovider", *_plan.IMPORTERS],
        cwd=CODE_ROOT, capture_output=True, text=True, timeout=600)
    nodes = [line for line in res.stdout.splitlines() if "::" in line]
    assert res.returncode == 0 and len(nodes) == _plan.IMPORTER_COUNT, (
        f"сбор импортёров: код {res.returncode}, узлов {len(nodes)} вместо "
        f"{_plan.IMPORTER_COUNT}:\n{res.stdout[-3000:]}\n{res.stderr[-2000:]}")


def test_ac8_plan_names_ci_result_for_importers():
    """PLAN называет итог CI кодовой ветки по обоим импортёрам.

    Для каждого импортёра (`outcome_prior`, `outcome_components`) в PLAN
    есть строка вне таблиц со словом `CI`, коротким именем импортёра и
    словом итога (зелёный/красный/пройден/упал, success/failure,
    passed/failed).

    Ловит мутацию: разработчик прогнал импортёры под ролью и не дождался
    CI ветки — строки с итогом CI по импортёру нет, тест краснеет с его
    именем.
    """
    result = re.compile(r"зел[её]н|красн|пройд|прош|упал|success|failure|passed|failed",
                        re.IGNORECASE)
    lines = [line for line in _plan.prose_lines(_ctx.plan_text())
             if "CI" in line and result.search(line)]
    missing = [short for short in ("outcome_prior", "outcome_components")
               if not any(short in line for line in lines)]
    assert not missing, f"в PLAN нет итога CI ветки по импортёрам: {missing}"


# ------------------------------------------------------------------ AC-9

def test_ac9_no_test_classes_subtest_or_unittest():
    """В `tests/test_merge_outcome_module.py` нет тестовых классов, `subTest`, `unittest` и `unittest.main()`; тестовые функции есть.

    Ловит мутацию: свод оставил `class Ac2MergeFindingTest(MergeOutcomeSandbox)`
    с методами `test_…`, `with box.subTest(case=label, seed=box.seed)` или
    хвост `if __name__ == "__main__": unittest.main()` с `import unittest`
    — тест краснеет с находкой.
    """
    tree = _merge_tree()
    assert _plan.module_tests(tree), f"в {_plan.MERGE_MODULE} нет тестовых функций"
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
        if isinstance(node, ast.Import) and any(a.name == "unittest" for a in node.names):
            problems.append(f"import unittest в строке {node.lineno}")
        if isinstance(node, ast.Name) and node.id == "unittest":
            problems.append(f"unittest в строке {node.lineno}")
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("name, module", [
    ("py_source", "tests.outcome_gate_sandbox"),
    ("GATE_ACTIONS", "tests.outcome_gate_sandbox"),
    ("MergeOutcomeSandbox", "tests.merge_outcome_sandbox"),
    ("TwoSidedSandbox", "tests.merge_outcome_sandbox"),
    ("FLAKY_ON_BASE", "tests.merge_outcome_sandbox"),
    ("PREPARE_ACTION", "tests.merge_outcome_sandbox"),
])
def test_ac9_name_imported_from_its_module(name, module):
    """Имя импортировано в `tests/test_merge_outcome_module.py` из названного критерием модуля без переименования.

    Ловит мутацию: `FLAKY_ON_BASE` взят из `tests.outcome_gate_sandbox`
    (там другое значение), `GATE_ACTIONS` — из песочницы мержа, или
    `PREPARE_ACTION` переписан литералом в модуль — импорта нет, тест
    краснеет с именем.
    """
    names = _imports_from(_merge_tree(), module)
    assert name in names and names[name] in (None, name), (
        f"{name} не импортирован из {module}")


def test_ac9_old_constants_come_only_from_merge_sandbox():
    """Константы строк 64–98 старого файла, нужные модулю, импортированы из `tests.merge_outcome_sandbox` и больше нигде не связаны.

    Для каждого имени, связанного в строках 64–98 старого файла базы и
    встречающегося в модуле: оно импортировано из
    `tests.merge_outcome_sandbox`, и других связываний верхнего уровня у
    него нет; `FLAKY_ON_BASE` не импортирован из `tests.outcome_gate_sandbox`.

    Ловит мутацию: свод скопировал `MERGE_OUTCOME_ACTION = "merge отклонён: …"`
    литералом в модуль или взял `FLAKY_ON_BASE` из песочницы гейта исходов —
    тест краснеет с именем.
    """
    old = _ctx.base_tree(_plan.MERGE_SOURCE)
    consts = {name for n in old.body if 64 <= n.lineno <= 98
              for name in _plan.bound_names(n)}
    tree = _merge_tree()
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    from_sandbox = _imports_from(tree, _plan.NEW_IMPORT)
    bindings = _bindings(tree)
    problems = []
    for name in sorted(consts & used):
        if name not in from_sandbox:
            problems.append(f"{name} не импортирован из {_plan.NEW_IMPORT}")
        if len(bindings.get(name, [])) != 1:
            problems.append(f"{name}: связываний верхнего уровня "
                            f"{len(bindings.get(name, []))}, ожидалось одно (импорт)")
    if "FLAKY_ON_BASE" in _imports_from(tree, "tests.outcome_gate_sandbox"):
        problems.append("FLAKY_ON_BASE импортирован из tests.outcome_gate_sandbox")
    assert not problems, "\n".join(problems)


def test_ac9_js_source_and_unused_names_not_imported():
    """`js_source` не импортирован, и каждое импортированное имя модуля в нём используется.

    Имя, связанное импортом верхнего уровня (`as`-имя или первый сегмент),
    встречается в модуле именем (`Name`) вне самих импортов.

    Ловит мутацию: свод перенёс импорты старого файла целиком — `hashlib`
    используется, а `unittest`, `refusal_classes`… — нет, или оставил
    `js_source` (уточнение 2 ТЗ) — тест краснеет с именами.
    """
    tree = _merge_tree()
    imported = {}
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                imported[(a.asname or a.name).split(".")[0]] = node.lineno
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert "js_source" not in imported, "js_source импортирован"
    unused = sorted(name for name in imported if name not in used)
    assert not unused, f"неиспользуемые импорты: {unused}"


def test_ac9_module_docstring_names_purpose_source_and_stand():
    """Докстринг модуля называет свод из прежнего файла (ADR-0020 п. 8) и стенд по нынешним адресам, без устаревшего адреса.

    Докстринг непуст и содержит: имя прежнего файла
    `test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate`, `ADR-0020`,
    адреса стенда `merge_outcome_sandbox` и `outcome_gate_sandbox`, слова
    описания стенда прежнего докстринга `cmd_approve` и `branch_status`;
    устаревшего адреса `test_01m5cjvb5b5v55pqqvr2qrhwzn` в нём нет (решение
    Оператора ANSWER-1, п. 4).

    Ловит мутацию: свод перенёс прежний докстринг дословно — со
    «`tests.test_01m5cjvb…_outcome_gate.OutcomeGateSandbox`» и без слова о
    своде, — или написал одну строку назначения без описания стенда — тест
    краснеет с недостающим.
    """
    doc = " ".join((ast.get_docstring(_merge_tree()) or "").split())
    assert doc, f"у {_plan.MERGE_MODULE} нет докстринга"
    missing = [w for w in ("test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate",
                           "ADR-0020", "merge_outcome_sandbox",
                           "outcome_gate_sandbox", "cmd_approve", "branch_status")
               if w not in doc]
    assert not missing, f"докстринг модуля не называет: {missing}"
    assert "test_01m5cjvb5b5v55pqqvr2qrhwzn" not in doc, (
        "докстринг называет устаревший адрес стенда")


# ------------------------------------------------------------------ AC-10

@pytest.mark.parametrize("name, cls", [("box", "MergeOutcomeSandbox"),
                                       ("two_sided_box", "TwoSidedSandbox")])
def test_ac10_fixture_only_creates_stand(name, cls):
    """Фикстура только создаёт стенд: единственный вызов тела — `_sandbox(<класс>)`, утверждений нет.

    Ловит мутацию: фикстура `box` сразу зовёт `box.direct_task(...)` или
    `two_sided_box` построена на `MergeOutcomeSandbox` — лишний вызов или
    не тот класс, тест краснеет.
    """
    funcs = _plan.module_functions(_merge_tree())
    assert name in funcs, f"фикстуры {name} в {_plan.MERGE_MODULE} нет"
    func = funcs[name]
    assert _plan.is_fixture(func), f"{name} не помечена pytest.fixture"
    problems = [f"утверждение в строке {line}" for line in _assertion_sites(func)]
    creates = 0
    for sub in ast.walk(ast.Module(body=func.body, type_ignores=[])):
        if not isinstance(sub, ast.Call):
            continue
        if _called(sub) == "_sandbox" and [ast.unparse(a) for a in sub.args] == [cls] \
                and not sub.keywords:
            creates += 1
        else:
            problems.append(f"вызов {ast.unparse(sub)} в строке {sub.lineno}")
    if creates != 1:
        problems.append(f"вызовов _sandbox({cls}): {creates}, ожидался 1")
    assert not problems, f"{name} не только создаёт стенд:\n" + "\n".join(problems)


def test_ac10_fixtures_call_no_asserting_methods():
    """Ни одна фикстура модуля не содержит утверждений и не зовёт методов и помощников с утверждениями.

    Ловит мутацию: свод завёл фикстуру `merge_gate_task`, которая зовёт
    `box.direct_task(project, "merge_gate")`, или фикстуру с
    `box.verifying_task(...)` — вызов найден, тест краснеет с именем.
    """
    problems = []
    for func in ast.walk(_merge_tree()):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                or not _plan.is_fixture(func):
            continue
        problems += [f"фикстура {func.name}: утверждение в строке {line}"
                     for line in _assertion_sites(func)]
        problems += [f"фикстура {func.name}: вызов {_called(sub)} в строке {sub.lineno}"
                     for sub in ast.walk(func)
                     if isinstance(sub, ast.Call) and _called(sub) in _plan.ASSERTING]
    assert not problems, "\n".join(problems)


def test_ac10_two_sided_box_only_for_former_ac11_ac12_ac14():
    """Стенд `two_sided_box` берут ровно функции бывших `Ac11`, `Ac12`, `Ac14`, прочие тесты — `box`.

    Для каждого теста исходного файла группы М, перенесённого в модуль:
    функции бывших `Ac11TwoSidedErrorNameTest`, `Ac12TwoSidedRetryTest`,
    `Ac14OutOfBoundsTest` берут параметр `two_sided_box` и не берут `box`;
    функции прочих классов берут `box` и не берут `two_sided_box`.

    Ловит мутацию: свод отдал всем тестам `two_sided_box` (или бывшему
    `Ac13RetriedBaseRerunTest`, чей класс — `MergeOutcomeSandbox`), либо
    бывшему `Ac11` — `box` без `two_sided` — тест краснеет с именем.
    """
    funcs = _plan.module_functions(_merge_tree())
    transfer = _plan.transfer_map(_ctx.plan_or_empty())
    problems, seen = [], 0
    for test in _source_methods(_M):
        for func in _ctx.matches(funcs, _M.target, test.cls, test.func.name, transfer):
            seen += 1
            params = {a.arg for a in func.args.args}
            want, other = (("two_sided_box", "box") if test.cls in _TWO_SIDED_CLASSES
                           else ("box", "two_sided_box"))
            if want not in params or other in params:
                problems.append(f"{test.key} → {func.name}: параметры {sorted(params)}, "
                                f"ожидался {want} без {other}")
    assert seen, "ни один тест группы М не найден в модуле"
    assert not problems, "\n".join(problems)


def test_ac10_fixture_names_differ_from_shared_fixtures():
    """Имена фикстур модуля не совпадают с фикстурами `tests/fixtures.py`.

    Ловит мутацию: стенд назван `real_git` или `tmp_root` — он затеняет
    общую фикстуру корневого `conftest.py`, тест краснеет с именем.
    """
    own = {f.name for f in _plan.module_functions(_merge_tree()).values()
           if _plan.is_fixture(f)}
    shared = _shared_fixture_names()
    assert shared, f"в {_plan.FIXTURES_FILE} не найдено фикстур"
    assert not own & shared, f"имена общих фикстур: {sorted(own & shared)}"


# ------------------------------------------------------------------ AC-11

def test_ac11_no_gate_refusal_equal_to_gate_module_function():
    """`no_gate_refusal(box, rows: list, output: str, case: str = "") -> None` модуля по `ast.dump` равна одноимённой функции `tests/test_outcome_gate_module.py`.

    Ловит мутацию: свод перенёс метод `OutcomeGateSandbox.no_gate_refusal`
    без `case` (или с `case`, не приписанным к сообщению) — дамп расходится,
    тест краснеет.
    """
    want = _plan.module_functions(_ctx.base_tree(_plan.GATE_MODULE)).get("no_gate_refusal")
    assert want is not None, f"в {_plan.GATE_MODULE} базы нет no_gate_refusal"
    got = _plan.module_functions(_merge_tree()).get("no_gate_refusal")
    assert got is not None, f"функции no_gate_refusal в {_plan.MERGE_MODULE} нет"
    assert ast.dump(got) == ast.dump(want), (
        "no_gate_refusal модуля не равна функции tests/test_outcome_gate_module.py")


def test_ac11_no_gate_refusal_called_by_bare_name():
    """Тесты зовут `no_gate_refusal` голым именем: вызовов `<что-то>.no_gate_refusal(…)` в модуле нет, голый вызов есть.

    Ловит мутацию: бывший `Ac13RetriedBaseRerunTest` оставил
    `box.no_gate_refusal(rows, output)` метода песочницы — guard не видит
    утверждения, тест краснеет со строкой.
    """
    tree = _merge_tree()
    by_attr = [sub.lineno for sub in ast.walk(tree) if isinstance(sub, ast.Call)
               and isinstance(sub.func, ast.Attribute)
               and sub.func.attr == "no_gate_refusal"]
    by_name = [sub.lineno for sub in ast.walk(tree) if isinstance(sub, ast.Call)
               and isinstance(sub.func, ast.Name) and sub.func.id == "no_gate_refusal"]
    assert not by_attr, f"no_gate_refusal вызван методом стенда в строках {by_attr}"
    assert by_name, "no_gate_refusal ни разу не вызван голым именем"


@pytest.mark.parametrize("path, cls, old_path", [
    (_plan.MERGE_SANDBOX, "MergeOutcomeSandbox", _plan.MERGE_SOURCE),
    (_plan.MERGE_SANDBOX, "TwoSidedSandbox", _plan.MERGE_SOURCE),
    (_plan.OUTCOME_SANDBOX, "OutcomeGateSandbox", _plan.OUTCOME_SANDBOX),
])
def test_ac11_sandbox_class_unchanged(path, cls, old_path):
    """Класс песочницы на HEAD по `ast.dump` равен своему классу в базе.

    Ловит мутацию: под функцию модуля в `OutcomeGateSandbox.no_gate_refusal`
    добавлен параметр `case`, или из `MergeOutcomeSandbox.verifying_task`
    убрано утверждение подготовки — дамп расходится, тест краснеет.
    """
    want = _class(_ctx.base_tree(old_path), cls)
    got = _class(_ctx.head_tree(path), cls)
    assert want is not None, f"{cls} нет в {old_path} базы"
    assert got is not None, f"{cls} нет в {path} на HEAD"
    assert ast.dump(got) == ast.dump(want), f"{cls} в {path} изменён"


# ------------------------------------------------------------------ AC-12

def _is_self_assert_any(node) -> bool:
    return _plan.is_method_assert(node)


@pytest.mark.parametrize("letter", ["М", "Д"])
def test_ac12_assertion_literals_carried_verbatim(letter):
    """Литералы утверждений исходных тестов группы есть в приёмнике дословно.

    Каждый строковый и числовой литерал смысловых аргументов `self.assert*`
    тестовых методов исходного файла (без аргумента сообщения) встречается
    литералом вне докстрингов в функциях приёмника группы.

    Ловит мутацию: при переносе ожидание `"escalated"` переписано как
    `"escalate"`, или `assertEqual(number, 2)` — как `assert number == 3`
    — исходного литерала в приёмнике нет, тест краснеет с ним.
    """
    group = _GROUPS[letter]
    new_lits = _plan.non_docstring_constants(_target_tree(group))
    missing = {lit for lit in _plan.assertion_literals(_source_tests_tree(group))
               if lit not in new_lits}
    assert not missing, ("литералы утверждений исходных тестов не найдены в "
                         "приёмнике:\n" + "\n".join(sorted(map(repr, missing))))


@pytest.mark.parametrize("letter", ["М", "Д"])
def test_ac12_assertion_constants_stay_constants(letter):
    """Константы, с которыми сравнивали исходные утверждения группы, остались константами.

    Каждое имя константы (`ВЕРХНИЙ_РЕГИСТР`) в смысловых аргументах
    `self.assert*` исходных тестов встречается именем (`Name`) в функциях
    приёмника.

    Ловит мутацию: `assertEqual(…, OPERATOR_FIXES)` перенесён как
    `assert … == "чинит Оператор"` — имени `OPERATOR_FIXES` в приёмнике
    нет, тест краснеет с ним.
    """
    group = _GROUPS[letter]
    names = {n.id for n in ast.walk(_target_tree(group)) if isinstance(n, ast.Name)}
    missing = sorted(c for c in _plan.assertion_constant_names(_source_tests_tree(group))
                     if c not in names)
    assert not missing, ("константы утверждений исходных тестов не найдены "
                         "именем в приёмнике: " + ", ".join(missing))


@pytest.mark.parametrize("letter", ["М", "Д"])
def test_ac12_equality_not_weakened_to_membership_or_inequality(letter):
    """Равенство не заменено вхождением, точное число — неравенством.

    Литерал, который исходные тесты группы сравнивали `assertEqual` (и
    никогда — `assertIn`/`assertNotIn`), в приёмнике не стоит только в
    сравнениях `in`/`not in`; числовой литерал `assertEqual` не стоит только
    в сравнениях `<`, `<=`, `>`, `>=`.

    Ловит мутацию: `assertEqual(self.state(t), "escalated", …)` перенесён как
    `assert "escalated" in box.state(t)`, или `assertEqual(len(added["app.js"]),
    1)` — как `assert len(…) >= 1` — тест краснеет с литералом.
    """
    group = _GROUPS[letter]
    equal, member = _plan.equality_literals(_source_tests_tree(group))
    compared = _plan.compare_operands(_target_tree(group))
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


def _check_count(func) -> int:
    """Утверждения функции: `assert`, `pytest.raises`, `<что-то>.assert*`."""
    return len(_assertion_sites(func))


@pytest.mark.parametrize("letter", ["М", "Д"])
def test_ac12_each_transferred_test_keeps_its_checks(letter):
    """Перенесённый тест сохраняет литералы своих равенств и вхождений и не теряет утверждений.

    Для каждого теста исходного файла группы, у которого в приёмнике есть
    функция (по имени или по соответствию «до → после» PLAN): литералы его
    `assertEqual`/`assert*Equal` стоят в этой функции в сравнении
    `==`/`!=`/`is`; литералы его `assertIn`/`assertNotIn` — в сравнении
    `in`/`not in` или на равенство; утверждений (`assert`, `pytest.raises`)
    в функции не меньше, чем `self.assert*`/`assertRaises` в исходном тесте.

    Ловит мутацию: в бывшем `Ac1ProofLineTest` выпало
    `assertEqual(fingerprint, wanted, …)`, или в бывшем
    `test_quoted_path_latin1_text_and_no_final_newline` равенство
    `[(1, "const x = 1;"), …]` сведено к `assert odd in added` — тест
    краснеет с именем теста.
    """
    group = _GROUPS[letter]
    funcs = _target_functions(group)
    transfer = _plan.transfer_map(_ctx.plan_or_empty())
    problems, seen = [], 0
    for test in _source_methods(group):
        found = _ctx.matches(funcs, group.target, test.cls, test.func.name, transfer)
        if not found:
            continue
        seen += 1
        equal, member = _plan.equality_literals(test.func)
        compared = [pair for f in found for pair in _plan.compare_operands(f)]
        eq_lits = set().union(*[l for k, l in compared if k == "eq"] or [set()])
        in_lits = set().union(*[l for k, l in compared if k == "in"] or [set()])
        lost_eq = sorted(map(repr, equal - eq_lits))
        lost_in = sorted(map(repr, member - eq_lits - in_lits))
        if lost_eq or lost_in:
            problems.append(f"{test.key}: равенства без {lost_eq}, вхождения без {lost_in}")
        want = sum(1 for n in ast.walk(test.func) if isinstance(n, ast.Call)
                   and isinstance(n.func, ast.Attribute)
                   and n.func.attr.startswith("assert"))
        got = sum(_check_count(f) for f in found)
        if got < want:
            problems.append(f"{test.key}: утверждений {got}, в исходном {want}")
    assert seen, f"ни один тест группы {letter} не найден в приёмнике"
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("letter", ["М", "Д"])
def test_ac12_raises_only_where_source_had_them_without_match(letter):
    """`pytest.raises` — только на месте `assertRaises`, без `match` там, где исходник текст не проверял.

    Число `pytest.raises` в функциях приёмника группы не больше числа
    `assertRaises*` исходных тестов; `pytest.raises` с `match` — не больше
    числа мест, где исходник проверял текст исключения; у группы Д есть
    `pytest.raises(outcome_integrity._Prepare)`.

    Ловит мутацию: свод переписал `with self.assertRaises(outcome_integrity._Prepare)`
    как `pytest.raises(outcome_integrity._Prepare, match="заголовок")` или
    как `pytest.raises(Exception)` — тест краснеет.
    """
    group = _GROUPS[letter]
    tree, source = _target_tree(group), _source_tests_tree(group)
    calls = [n for n in ast.walk(tree) if _plan.is_pytest_raises(n)]
    with_match = [n for n in calls if any(kw.arg == "match" for kw in n.keywords)]
    source_raises = sum(1 for n in ast.walk(source) if isinstance(n, ast.Call)
                        and isinstance(n.func, ast.Attribute)
                        and n.func.attr.startswith("assertRaises"))
    assert len(calls) <= source_raises, (
        f"pytest.raises {len(calls)}, а assertRaises в исходных тестах {source_raises}")
    assert len(with_match) <= _plan.text_raises_sites(source), (
        f"pytest.raises с match {len(with_match)} там, где исходник текст не проверял")
    if group is _D:
        assert any(n.args and ast.unparse(n.args[0]) == "outcome_integrity._Prepare"
                   for n in calls), "нет pytest.raises(outcome_integrity._Prepare)"


@pytest.mark.parametrize("letter", ["М", "Д"])
def test_ac12_form_is_assert_with_message_as_second_operand(letter):
    """В тестовых функциях приёмника нет `<что-то>.assert*(…)`; `explain(…)`/`note(…)` стоят только в сообщении `assert`.

    В тестовых функциях приёмника группы (помощник `no_gate_refusal` —
    дословная копия функции модуля гейта исходов по AC-11, вне проверки) нет
    вызовов метода `assert*` (кроме `assertRaises*`); каждый вызов `explain(…)`/`note(…)` в тестовой функции
    стоит в сообщении оператора `assert` или аргументе `pytest.fail(…)` —
    прямо либо через локальное имя (`context`), которое туда входит; у
    группы М хотя бы одно сообщение несёт `explain(…)`.

    Ловит мутацию: свод перенёс `self.assertEqual(self.state(t), "done",
    context)` как `box.assertEqual(…)` или как `assert box.state(t) ==
    "done"` с потерей пояснения — тест краснеет со строкой.
    """
    group = _GROUPS[letter]
    funcs = {n: f for n, f in _target_functions(group).items() if n.startswith("test")}
    problems, with_explain = [], 0
    for func in funcs.values():
        for sub in ast.walk(func):
            if _plan.is_method_assert(sub):
                problems.append(f"{func.name}: {ast.unparse(sub.func)}(…) в строке "
                                f"{sub.lineno}")
        messages = [sub.msg for sub in ast.walk(func)
                    if isinstance(sub, ast.Assert) and sub.msg is not None]
        messages += [arg for sub in ast.walk(func)
                     if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                     and sub.func.attr == "fail" for arg in sub.args]
        used = {n.id for msg in messages for n in ast.walk(msg) if isinstance(n, ast.Name)}
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
            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) \
                    and sub.func.attr in ("explain", "note") and id(sub) not in allowed:
                problems.append(f"{func.name}: {sub.func.attr}(…) вне сообщения в "
                                f"строке {sub.lineno}")
    assert funcs, f"функций приёмника группы {letter} нет"
    assert not problems, "\n".join(problems)
    if group is _M:
        assert with_explain, "ни одно сообщение тестов группы М не несёт explain(…)"


# ------------------------------------------------------------------ AC-13

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


def _is_subtest(item) -> bool:
    return isinstance(item.context_expr, ast.Call) and \
        isinstance(item.context_expr.func, ast.Attribute) and \
        item.context_expr.func.attr == "subTest"


def _source_counts(method) -> dict:
    """{"labels": [ярлыки subTest], "asserts_in", "asserts_out",
    "helpers_in", "helpers_out"} — прямые `self.assert*` и вызовы помощников
    исхода внутри тел `subTest` и вне их."""
    counts = {"labels": [], "asserts_in": 0, "asserts_out": 0,
              "helpers_in": {}, "helpers_out": {}}
    inside = set()
    for node in ast.walk(method):
        if isinstance(node, ast.With):
            for item in node.items:
                if _is_subtest(item):
                    labels = [kw.value for kw in item.context_expr.keywords
                              if kw.arg != "seed"]
                    counts["labels"].append(labels[0] if labels else None)
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
        elif attr.startswith("assert") and not attr.startswith("assertRaises"):
            counts[f"asserts_{where}"] += 1
    return counts


def _tagged_names(func, is_tagged) -> set:
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


def _carries(node, labels: list, names: set, need_seed: bool) -> bool:
    """Выражение несёт ярлык одного из подслучаев (и зерно `….seed`, если
    нужно) — прямо или через имя из `names`."""
    subs = list(ast.walk(node))
    if any(isinstance(n, ast.Name) and n.id in names for n in subs):
        return True
    seed = not need_seed or any(isinstance(n, ast.Attribute) and n.attr == "seed"
                                for n in subs)
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


def _wanted_case(label, need_seed: bool) -> set:
    tail = _SEED if need_seed else ""
    wanted = {"{" + ast.unparse(label) + "}" + tail}
    if isinstance(label, ast.Constant) and isinstance(label.value, str):
        wanted.add(label.value + tail)
    return wanted


def _literal_parametrize(func) -> bool:
    for deco in _plan.parametrize_decorators(func):
        if len(deco.args) < 2:
            return False
        try:
            ast.literal_eval(deco.args[1])
        except (ValueError, TypeError, SyntaxError):
            return False
    return bool(_plan.parametrize_decorators(func))


@pytest.mark.parametrize("letter", ["М", "Д"])
def test_ac13_each_former_subtest_in_one_function_with_label(letter):
    """Бывший `subTest` — в одной функции; прямые утверждения подслучая несут ярлык (у группы М — и зерно), помощник получает их через `case`.

    Для каждого теста исходного файла группы с `subTest` (кроме удалённых
    дублей PLAN) в приёмнике ровно одна функция без `parametrize` (у
    `CodeExceptionRenameTest::test_rename_from_test_path_to_code_path_is_checked`
    допустим `parametrize` литералами — тогда ярлык в сообщении не
    требуется). В ней операторов `assert`, чьё сообщение несёт ярлык
    подслучая (тот же литерал или то же выражение, что у `subTest`; у группы
    М — и `….seed`), не меньше, чем прямых `self.assert*` внутри тел
    `subTest` исходника, а прочих `assert` — не больше, чем вне этих тел;
    вызовов помощника исхода с `case=f"{<ярлык>}, зерно {box.seed}"` не
    меньше, чем внутри тел `subTest`.

    Ловит мутацию: в перенесённом цикле `for label in ("сломан", "исчез")`
    сообщение `assert …, box.explain(rows, output)` потеряло ярлык и зерно,
    или подслучаи `noprefix` разнесены `parametrize` по отдельным стендам —
    тест краснеет с именем теста.
    """
    group = _GROUPS[letter]
    need_seed = group is _M
    funcs = _target_functions(group)
    plan = _ctx.plan_or_empty()
    transfer, removed = _plan.transfer_map(plan), _ctx.removed_keys(plan)
    problems, seen = [], 0
    for test in _source_methods(group):
        counts = _source_counts(test.func)
        if not counts["labels"]:
            continue
        seen += 1
        if test.key in removed:
            continue
        found = _ctx.matches(funcs, group.target, test.cls, test.func.name, transfer)
        if len(found) != 1:
            problems.append(f"{test.key}: функций в приёмнике {[f.name for f in found]}, "
                            f"ожидалась одна")
            continue
        func = found[0]
        if _plan.parametrize_decorators(func):
            if test.key == _PARAMETRIZE_OK and _literal_parametrize(func):
                continue
            problems.append(f"{test.key}: подслучаи вынесены в parametrize ({func.name})")
            continue
        labels = counts["labels"]
        wanted = set().union(*[_wanted_case(l, need_seed) for l in labels if l is not None])
        msg_names = _tagged_names(func, lambda node, names: _carries(
            node, labels, names, need_seed))
        case_names = _tagged_names(func, lambda node, names: (
            isinstance(node, ast.Name) and node.id in names) or _template(node) in wanted)
        asserts = [n for n in ast.walk(func) if isinstance(n, ast.Assert)]
        tagged = sum(1 for n in asserts if n.msg is not None
                     and _carries(n.msg, labels, msg_names, need_seed))
        if tagged < counts["asserts_in"]:
            problems.append(f"{test.key} → {func.name}: assert с ярлыком {tagged}, а "
                            f"прямых утверждений в subTest {counts['asserts_in']}")
        if len(asserts) - tagged > counts["asserts_out"]:
            problems.append(f"{test.key} → {func.name}: assert без ярлыка "
                            f"{len(asserts) - tagged}, а вне subTest {counts['asserts_out']}")
        for helper in _plan.OUTCOME_HELPERS:
            calls = [n for n in ast.walk(func) if isinstance(n, ast.Call)
                     and isinstance(n.func, ast.Name) and n.func.id == helper]
            cased = sum(1 for c in calls if any(
                kw.arg == _plan.CASE and ((isinstance(kw.value, ast.Name)
                                           and kw.value.id in case_names)
                                          or _template(kw.value) in wanted)
                for kw in c.keywords))
            if cased < counts["helpers_in"].get(helper, 0):
                problems.append(f"{test.key} → {func.name}: {helper} с case — {cased}, "
                                f"а в subTest {counts['helpers_in'][helper]}")
    assert seen, f"в исходном файле группы {letter} нет subTest — база прочитана не та"
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("name", list(_plan.NESTED))
def test_ac13_nested_function_stays_nested_verbatim(name):
    """Вложенная функция (`checkout_head`, `full`, `edit`) осталась вложенной в тестовую функцию модуля, тело — дословно с `self` → имя фикстуры.

    В модуле нет функции верхнего уровня `name`; внутри тестовой функции
    есть вложенное определение `name`, и его дамп равен дампу вложенного
    определения исходного теста, где `self` заменён первым параметром
    объемлющей тестовой функции.

    Ловит мутацию: `edit` вынесена на уровень модуля, или в ней
    `self.hexword(40)` переписано как `random_hex(40)` — тест краснеет.
    """
    source = None
    for test in _source_methods(_M):
        for node in ast.walk(test.func):
            if isinstance(node, ast.FunctionDef) and node.name == name:
                source = node
    assert source is not None, f"вложенной {name} в исходном файле базы нет"
    tree = _merge_tree()
    assert name not in _plan.module_functions(tree), f"{name} — функция верхнего уровня"
    found = []
    for func in _plan.module_tests(tree):
        for node in ast.walk(func):
            if node is not func and isinstance(node, ast.FunctionDef) and node.name == name:
                found.append((func, node))
    assert found, f"вложенной {name} в тестовых функциях модуля нет"
    func, node = found[0]
    param = func.args.args[0].arg if func.args.args else "box"
    want = _plan._SelfToParam(param, {}).visit(copy.deepcopy(source))
    assert ast.dump(node) == ast.dump(want), (
        f"{name} в {func.name}: тело не равно исходному с self → {param}")


@pytest.mark.parametrize("letter", ["М", "Д"])
def test_ac13_locals_do_not_shadow_module_functions_or_fixtures(letter):
    """Локальные имена функций приёмника не совпадают с функциями и фикстурами модуля и с `tests/fixtures.py`.

    Имена, которым в функциях приёмника группы присваивается значение
    (присваивание, цель `for`/`with`), не совпадают с именами функций
    верхнего уровня приёмника на HEAD и фикстур `tests/fixtures.py`.

    Ловит мутацию: бывший `test_rename_between_test_paths_is_not_checked`
    оставил `files = outcome_integrity._Files(…)` (исходные :150–152) —
    локальное имя затеняет функцию `files`, тест краснеет с ним.
    """
    group = _GROUPS[letter]
    taken = set(_plan.module_functions(_ctx.head_tree(group.target))) | _shared_fixture_names()
    problems = []
    for func in _target_functions(group).values():
        stored = {n.id for n in ast.walk(func)
                  if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)}
        problems += [f"{func.name}: локальное {name}" for name in sorted(stored & taken)]
    assert not problems, "\n".join(problems)


def test_ac13_renamed_locals_listed_in_plan():
    """PLAN перечисляет переименованные локальные имена: каждое имя исходных тестов, совпавшее с функцией или фикстурой приёмника, и `files`.

    Для каждой группы — локальные имена тестовых методов исходного файла,
    совпадающие с функцией верхнего уровня приёмника на HEAD или фикстурой
    `tests/fixtures.py`, плюс `files` (критерий называет его явно): каждое
    стоит в PLAN в обратных кавычках.

    Ловит мутацию: разработчик переименовал `files` в `rename_files`, но не
    записал перечень в PLAN — имени нет, тест краснеет с ним.
    """
    plan = _ctx.plan_text()
    shared = _shared_fixture_names()
    wanted = {"files"}
    for group in _plan.GROUPS:
        taken = set(_plan.module_functions(_ctx.head_tree(group.target))) | shared
        for test in _source_methods(group):
            wanted |= {n.id for n in ast.walk(test.func)
                       if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)
                       and n.id in taken}
    missing = sorted(name for name in wanted if f"`{name}`" not in plan)
    assert not missing, f"в PLAN нет перечня переименованных локальных: {missing}"


def test_ac13_id_sandbox_unchanged():
    """`IdOutcomeGateSandbox` модуля гейта исходов (с его локальными `files`) на HEAD по `ast.dump` равен базе.

    Ловит мутацию: заодно с `files` теста переименованы локальные `files`
    методов `IdOutcomeGateSandbox` — дамп расходится, тест краснеет.
    """
    want = _class(_ctx.base_tree(_plan.GATE_MODULE), "IdOutcomeGateSandbox")
    got = _class(_ctx.head_tree(_plan.GATE_MODULE), "IdOutcomeGateSandbox")
    assert want is not None and got is not None, "IdOutcomeGateSandbox не найден"
    assert ast.dump(got) == ast.dump(want), "IdOutcomeGateSandbox изменён"


# ------------------------------------------------------------------ AC-14

def _is_outcome_import(node) -> bool:
    return isinstance(node, ast.ImportFrom) and \
        node.module == "orchestrator.advance_gates" and \
        any(a.name == "outcome_integrity" and a.asname is None for a in node.names)


def _split_gate_module():
    """(база без докстринга, HEAD без докстринга и импорта
    `outcome_integrity`, хвост HEAD после операторов базы)."""
    base = _plan.strip_docstring(_ctx.base_tree(_plan.GATE_MODULE).body)
    head = [n for n in _plan.strip_docstring(_ctx.head_tree(_plan.GATE_MODULE).body)
            if not _is_outcome_import(n)]
    return base, head, head[len(base):]


def test_ac14_base_module_kept_and_section_appended_at_end():
    """Операторы модуля на базе — на HEAD теми же дампами в том же порядке, новые — после них, отдельным разделом.

    HEAD без докстринга и без импорта `outcome_integrity` начинается
    операторами базы (кроме докстринга) с равными `ast.dump`; после них
    есть хвост, в нём шесть тестов `added_lines` (по имени или соответствию
    PLAN); между последним оператором базы и первым оператором хвоста
    стоит строка комментария.

    Ловит мутацию: тесты `added_lines` вставлены в середину модуля, тест
    волны 2а-1б переписан под новый помощник, или имя `id_no_gate_refusal`
    поправлено — дамп или порядок расходятся, тест краснеет с номером.
    """
    base, head, tail = _split_gate_module()
    for i, (b, h) in enumerate(zip(base, head)):
        assert ast.dump(b) == ast.dump(h), (
            f"оператор базы {i + 1} ({_plan.bound_names(b)}) на HEAD изменён или "
            f"сдвинут (строка HEAD {h.lineno})")
    assert len(head) > len(base), "после операторов базы ничего не дописано"
    funcs = {n.name: n for n in tail if isinstance(n, ast.FunctionDef)}
    transfer = _plan.transfer_map(_ctx.plan_or_empty())
    removed = _ctx.removed_keys(_ctx.plan_or_empty())
    lost = [t.key for t in _source_methods(_D) if t.key not in removed
            and not _ctx.matches(funcs, _D.target, t.cls, t.func.name, transfer)]
    assert not lost, f"тестов added_lines нет в хвосте модуля: {lost}"
    lines = _ctx.head_text(_plan.GATE_MODULE).split("\n")
    between = lines[head[len(base) - 1].end_lineno:tail[0].lineno - 1]
    assert any(line.lstrip().startswith("#") for line in between), (
        "между прежним модулем и разделом added_lines нет строки комментария")


def test_ac14_docstring_extended_with_line_about_added_lines():
    """Докстринг модуля сохранил текст базы, дополнен и называет `test_outcome_integrity_added_lines`.

    Ловит мутацию: свод оставил докстринг как был (или заменил абзац волны
    2а-1б) — добавки нет или текст базы не найден, тест краснеет.
    """
    base = " ".join((ast.get_docstring(_ctx.base_tree(_plan.GATE_MODULE)) or "").split())
    head = " ".join((ast.get_docstring(_ctx.head_tree(_plan.GATE_MODULE)) or "").split())
    assert base and base in head, "докстринг модуля базы не сохранён на HEAD"
    assert len(head) > len(base), "докстринг модуля не дополнен"
    assert "test_outcome_integrity_added_lines" in head, (
        "дополнение докстринга не называет исходный файл added_lines")


def test_ac14_outcome_integrity_imported_next_to_gate_alias():
    """`from orchestrator.advance_gates import outcome_integrity` стоит в блоке импортов рядом с `… as gate`.

    Ловит мутацию: импорт дописан перед разделом `added_lines` в конце
    модуля (или под псевдонимом) — его нет рядом с `as gate`, тест
    краснеет.
    """
    body = _ctx.head_tree(_plan.GATE_MODULE).body
    at = [i for i, n in enumerate(body) if _is_outcome_import(n)]
    gate = [i for i, n in enumerate(body) if isinstance(n, ast.ImportFrom)
            and n.module == "orchestrator.advance_gates"
            and any(a.name == "outcome_integrity" and a.asname == "gate" for a in n.names)]
    assert len(at) == 1, f"импортов outcome_integrity без псевдонима: {len(at)}"
    assert gate and abs(at[0] - gate[0]) == 1, (
        "импорт outcome_integrity не рядом с импортом as gate")


def test_ac14_added_lines_tests_use_outcome_integrity_not_gate():
    """Тесты `added_lines` обращаются к `outcome_integrity`, имени `gate` в них нет.

    Ловит мутацию: свод заменил `outcome_integrity._added_lines` на
    `gate._added_lines` — имя `gate` найдено, тест краснеет с функцией.
    """
    funcs = {n: f for n, f in _ctx.new_functions(_plan.GATE_MODULE).items()
             if n.startswith("test")}
    assert funcs, "новых тестовых функций в модуле гейта исходов нет"
    problems = [f"{n}: имя gate" for n, f in funcs.items()
                if any(isinstance(x, ast.Name) and x.id == "gate" for x in ast.walk(f))]
    assert not problems, "\n".join(problems)
    assert all(any(isinstance(x, ast.Name) and x.id == "outcome_integrity"
                   for x in ast.walk(f)) for f in funcs.values()), (
        "не каждый тест added_lines обращается к outcome_integrity")


def test_ac14_names_of_base_module_not_reimported():
    """Имя, связанное в модуле на базе (`os`, `subprocess`, `mock`, `project_profile`, `pytest`, …), на HEAD связано столько же раз.

    Ловит мутацию: свод перенёс импорты `added_lines` целиком — `import os`,
    `import subprocess`, `from unittest import mock`, `from orchestrator
    import project_profile` — имена связаны дважды, тест краснеет с ними.
    """
    base = _bindings(_ctx.base_tree(_plan.GATE_MODULE))
    head = _bindings(_ctx.head_tree(_plan.GATE_MODULE))
    for name in ("os", "subprocess", "mock", "project_profile", "pytest"):
        assert name in base, f"{name} не связан в модуле на базе — база прочитана не та"
    twice = sorted(f"{name}: {len(head.get(name, []))} вместо {len(nodes)}"
                   for name, nodes in base.items() if len(head.get(name, [])) > len(nodes))
    assert not twice, "имена базы связаны повторно:\n" + "\n".join(twice)


def _old_method(cls: str, name: str):
    return _plan.class_method(_ctx.base_tree(_plan.ADDED_SOURCE), cls, name)


def test_ac14_added_repo_fixture_is_setup_body_over_tmp_dir():
    """Фикстура `added_repo(tmp_dir)` — тело `setUp` без `super().setUp()`, `self` → `tmp_dir`, `self.git(…)` → `git(tmp_dir, …)`, без утверждений, стенд отдаётся.

    Ловит мутацию: фикстура строится поверх `tmp_root` или своего
    `tempfile`, коммит базы вынесен в тест, или фикстура не отдаёт стенд —
    дамп тела или параметр расходятся, тест краснеет.
    """
    func = _ctx.new_functions(_plan.GATE_MODULE).get("added_repo")
    assert func is not None, "фикстуры added_repo в модуле нет"
    assert _plan.is_fixture(func), "added_repo не помечена pytest.fixture"
    assert [a.arg for a in func.args.args] == ["tmp_dir"], (
        f"параметры added_repo {[a.arg for a in func.args.args]}, ожидался tmp_dir")
    assert not _assertion_sites(func), "утверждения в added_repo"
    body = _plan.strip_docstring(func.body)
    assert body, "тело added_repo пусто"
    last = body[-1]
    gives = (isinstance(last, ast.Return) and isinstance(last.value, ast.Name)
             and last.value.id == "tmp_dir") or (
        isinstance(last, ast.Expr) and isinstance(last.value, ast.Yield)
        and isinstance(last.value.value, ast.Name) and last.value.value.id == "tmp_dir")
    assert gives, "added_repo не отдаёт стенд tmp_dir последним оператором"
    setup = _old_method("AddedLinesTest", "setUp")
    old = [s for s in setup.body if not (
        isinstance(s, ast.Expr) and isinstance(s.value, ast.Call)
        and ast.unparse(s.value) == "super().setUp()")]
    want = _plan._SelfToParam("tmp_dir", {"git": "git"}).visit(
        ast.Module(body=copy.deepcopy(old), type_ignores=[]))
    got = ast.Module(body=body[:-1], type_ignores=[])
    assert ast.dump(got) == ast.dump(want), "тело added_repo не равно телу setUp"


@pytest.mark.parametrize("name, cls, first", [("git", "AddedLinesTest", "box"),
                                              ("commit", "AddedLinesTest", "box"),
                                              ("files", "CodeExceptionRenameTest", None)])
def test_ac14_helper_function_has_verbatim_body(name, cls, first):
    """`git(box, *args)`, `commit(box)`, `files(tests=())` — функции модуля с телом метода-источника, `self.` → `box`, вызовы методов — вызовы функций.

    Параметры функции после стенда (у `files` — все) равны параметрам
    метода после `self` (с аннотациями, умолчаниями и `*args`); каноничный
    дамп тела без докстринга равен телу метода с `self` → `box` и
    `self.git(…)` → `git(box, …)`.

    Ловит мутацию: `git` перенесён без `-c user.email=…` или с
    `check=False`, `commit` зовёт `box.git(…)` метода, `files` потерял
    умолчание `tests=()` — тест краснеет с именем функции.
    """
    func = _ctx.new_functions(_plan.GATE_MODULE).get(name)
    assert func is not None, f"функции {name} в модуле нет"
    source = _old_method(cls, name)
    assert source is not None, f"{cls}.{name} нет в {_plan.ADDED_SOURCE} базы"
    if first is None:
        assert _plan.params(func.args) == _plan.params(source.args), (
            f"{name}: параметры не равны параметрам {cls}.{name}")
        want = _plan.strip_docstring(copy.deepcopy(source).body)
        param = None
    else:
        assert func.args.args and func.args.args[0].arg == first, (
            f"{name}: первый параметр не {first}")
        param = first
        assert _plan.params(func.args)[1:] == _plan.params(source.args)[1:], (
            f"{name}: параметры после стенда не равны параметрам метода")
        want = _plan.strip_docstring(_plan._SelfToParam(param, {"git": "git"}).visit(
            copy.deepcopy(source)).body)
    vararg = (func.args.vararg.arg if func.args.vararg else None,
              source.args.vararg.arg if source.args.vararg else None)
    assert vararg[0] == vararg[1], f"{name}: *{vararg[0]} вместо *{vararg[1]}"
    assert _plan.body_dump(func) == _plan._canonical(want), (
        f"{name}: тело не равно телу {cls}.{name}"
        + (f" с self → {param}" if param else ""))


# ------------------------------------------------------------------ AC-15

@pytest.mark.parametrize("letter", ["М", "Д"])
def test_ac15_every_transferred_function_declares_mutation(letter):
    """У каждой тестовой функции приёмника группы есть строка «Ловит мутацию:».

    Ловит мутацию: свод перенёс тест с докстрингом, укороченным до первой
    фразы, без заявки — функция перечислена, тест краснеет.
    """
    tests = [f for n, f in _target_functions(_GROUPS[letter]).items()
             if n.startswith("test")]
    assert tests, f"тестовых функций приёмника группы {letter} нет"
    without = [f.name for f in tests if "Ловит мутацию:" not in (ast.get_docstring(f) or "")]
    assert not without, "функции без «Ловит мутацию:»:\n" + "\n".join(without)


@pytest.mark.parametrize("letter", ["М", "Д"])
def test_ac15_every_source_test_transferred_or_listed_as_removed_duplicate(letter):
    """Каждый из тестов исходного файла группы перенесён в приёмник либо перечислен в PLAN удалённым дублем.

    Тест исходного файла базы, не перечисленный в разделе «…дубл…» PLAN,
    сопоставлен функции приёмника (по имени или соответствию PLAN).

    Ловит мутацию: при своде пропал бывший `Ac10NoPythonSectionTest` (не
    перенесён и не записан дублем) — тест краснеет с его именем.
    """
    group = _GROUPS[letter]
    funcs = _target_functions(group)
    plan = _ctx.plan_or_empty()
    transfer, removed = _plan.transfer_map(plan), _ctx.removed_keys(plan)
    lost = [t.key for t in _source_methods(group) if t.key not in removed
            and not _ctx.matches(funcs, group.target, t.cls, t.func.name, transfer)]
    assert not lost, ("тесты не перенесены и не перечислены удалёнными дублями:\n"
                      + "\n".join(lost))
