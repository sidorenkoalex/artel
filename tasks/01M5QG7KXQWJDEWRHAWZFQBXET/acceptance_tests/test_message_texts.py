"""AC-13: тексты сообщений модуля — `pytest.fail(box.note("запись в node_modules"))`
в `test_ac16_…`, параметр `case` функции `assert_unknown` и ярлыки в её
трёх вызовах; утверждения 26 существующих тестов и
`ReportSandbox.assert_unknown` не изменены.

Группа: разовый
Красен до реализации: в модуле на HEAD у assert_unknown нет параметра case, вызовы не передают ярлык, блок pytest.raises(OSError) без pytest.fail — правки требования 13 нет.

Модуль и песочница читаются из HEAD рабочей копии, их вид до задачи — из
базы ветки (`_pult.DIFF_BASE`). Сравнение статическое (ast).
"""
import ast
import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _plan  # noqa: E402
from _pult import CODE_ROOT, DIFF_BASE  # noqa: E402

_NODE_MODULES_TEST = "test_ac16_node_modules_read_only_shared_and_substitution_refused"
_FAIL_LINE = 'pytest.fail(box.note("запись в node_modules"))'


def _tree(revision: str, path: str) -> ast.Module:
    assert revision, "база диффа ветки задачи не определена при выкладке"
    text = _plan.show(CODE_ROOT, revision, path)
    assert text is not None, f"{path} нет в ревизии {revision}"
    return ast.parse(text)


def _funcs(revision: str) -> dict:
    return _plan.module_functions(_tree(revision, _plan.NEW_FILE))


def _dump(source: str) -> str:
    return ast.dump(ast.parse(source, mode="eval").body)


class _DropCase(ast.NodeTransformer):
    """`<…> + case` → `<…>`."""

    def visit_BinOp(self, node):
        self.generic_visit(node)
        if isinstance(node.op, ast.Add) and isinstance(node.right, ast.Name) \
                and node.right.id == "case":
            return node.left
        return node


def _forms(func) -> list[str]:
    """Нормальные формы утверждений функции по порядку текста, без
    сообщений: `assert` — выражение; `<…>.assert*` — вызов без аргумента
    сообщения; `pytest.raises` — вызов; `pytest.fail` не входит."""
    found = []
    for node in ast.walk(func):
        if isinstance(node, ast.Assert):
            found.append((node.lineno, node.col_offset, ast.dump(node.test)))
        elif _plan.is_method_assert(node):
            call = copy.deepcopy(node)
            call.keywords = [k for k in call.keywords if k.arg != "msg"]
            keep = 1 if call.func.attr in ("assertTrue", "assertFalse",
                                           "assertIsNone", "assertIsNotNone") else 2
            call.args = call.args[:keep]
            found.append((node.lineno, node.col_offset, ast.dump(call)))
        elif _plan.is_pytest_raises(node):
            found.append((node.lineno, node.col_offset, ast.dump(node)))
    return [form for _l, _c, form in sorted(found)]


def _fails(func) -> int:
    return sum(1 for n in ast.walk(func) if _plan.is_pytest_fail(n))


def test_ac13_node_modules_raises_block_ends_with_fail_note():
    """В `test_ac16_…` блок `pytest.raises(OSError)` последней строкой несёт `pytest.fail(box.note("запись в node_modules"))`.

    Ловит мутацию: текст возвращён в `match="запись в node_modules"` или
    строка `pytest.fail(...)` поставлена до записи в каталог — последней
    строки блока с этим вызовом нет, тест краснеет.
    """
    func = _funcs("HEAD").get(_NODE_MODULES_TEST)
    assert func is not None, f"{_NODE_MODULES_TEST} нет в модуле HEAD"
    blocks = [n for n in ast.walk(func) if isinstance(n, ast.With)
              and any(_plan.is_pytest_raises(i.context_expr)
                      and [ast.unparse(a) for a in i.context_expr.args] == ["OSError"]
                      for i in n.items)]
    assert len(blocks) == 1, f"блоков pytest.raises(OSError): {len(blocks)}"
    last = blocks[0].body[-1]
    assert isinstance(last, ast.Expr) and ast.dump(last.value) == _dump(_FAIL_LINE), (
        f"последняя строка блока: {ast.unparse(last)}, ожидалась {_FAIL_LINE}")


def test_ac13_assert_unknown_has_case_param_and_note_plus_case_messages():
    """`assert_unknown` модуля: последний параметр `case: str = ""`, каждое сообщение — `box.note(…) + case`, прочее тело — как в базе.

    Последний позиционный параметр — `case` с аннотацией `str` и значением
    по умолчанию `""`; прочие параметры — как в базе. Каждый вызов
    `<стенд>.assert*` тела несёт сообщение `<стенд>.note(…) + case`; тело,
    в котором `<…> + case` заменено на `<…>`, по `ast.dump` равно телу
    базы.

    Ловит мутацию: ярлык приклеен только ко второму сообщению или
    передан внутрь `box.note(f"{context}{case}: {run}")` (зерно оказывается
    перед ярлыком), либо `case` без значения по умолчанию — тело или
    параметры расходятся, тест краснеет.
    """
    head = _funcs("HEAD").get("assert_unknown")
    base = _funcs(DIFF_BASE).get("assert_unknown")
    assert head is not None and base is not None, "assert_unknown нет в модуле"
    args = head.args
    assert args.args and args.args[-1].arg == "case", (
        f"последний параметр: {args.args[-1].arg if args.args else None}")
    assert args.args[-1].annotation is not None and \
        ast.unparse(args.args[-1].annotation) == "str", "у case нет аннотации str"
    assert args.defaults and isinstance(args.defaults[-1], ast.Constant) \
        and args.defaults[-1].value == "", "у case нет значения по умолчанию \"\""
    trimmed = copy.deepcopy(args)
    trimmed.args, trimmed.defaults = trimmed.args[:-1], trimmed.defaults[:-1]
    assert ast.dump(trimmed) == ast.dump(base.args), "прочие параметры изменены"
    stand = args.args[0].arg
    calls = [n for n in ast.walk(head) if _plan.is_method_assert(n)]
    assert calls, "в assert_unknown нет утверждений"
    bad = []
    for call in calls:
        msg = call.args[-1] if call.args else None
        ok = (isinstance(msg, ast.BinOp) and isinstance(msg.op, ast.Add)
              and isinstance(msg.right, ast.Name) and msg.right.id == "case"
              and isinstance(msg.left, ast.Call)
              and isinstance(msg.left.func, ast.Attribute)
              and msg.left.func.attr == "note"
              and isinstance(msg.left.func.value, ast.Name)
              and msg.left.func.value.id == stand)
        if not ok:
            bad.append(f"строка {call.lineno}: {ast.unparse(call)}")
    assert not bad, "сообщения не вида box.note(…) + case:\n" + "\n".join(bad)
    body = _DropCase().visit(copy.deepcopy(head))
    assert _plan.body_dump(body) == _plan.body_dump(base), (
        "тело assert_unknown без «+ case» отличается от базы")


@pytest.mark.parametrize("name,case", [
    ("test_ac1_outcome_follows_report_not_runner_output",
     '"; " + f"stdout={stdout!r}; report={label!r}"'),
    ("test_ac2_empty_or_unreadable_report_is_unknown",
     '"; " + f"report={label!r}"'),
    ("test_ac4_ac6_sled_record_default_report_args_outcome_from_report",
     '"; " + f"report={label!r}"'),
])
def test_ac13_assert_unknown_call_sites_pass_label(name, case):
    """Вызов `assert_unknown` на месте :260/:290/:442 передаёт ярлык подслучая, прочие аргументы — как в базе.

    В функции один вызов `assert_unknown(…)`, как в базе; его аргументы
    базы сохранены, а ярлык — следующим позиционным аргументом или
    `case=` — по `ast.dump` равен ожидаемому выражению.

    Ловит мутацию: у вызова в `test_ac1_…` ярлык без `stdout=…` (только
    `report=`) или ярлык не передан у `test_ac4_ac6_sled_…` — выражение
    расходится, тест краснеет с функцией.
    """
    head, base = _funcs("HEAD").get(name), _funcs(DIFF_BASE).get(name)
    assert head is not None and base is not None, f"{name} нет в модуле"

    def calls(func):
        return [n for n in ast.walk(func) if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Name) and n.func.id == "assert_unknown"]

    old, new = calls(base), calls(head)
    assert len(old) == 1 and len(new) == 1, (
        f"{name}: вызовов assert_unknown в базе {len(old)}, на HEAD {len(new)}")
    old, new = old[0], new[0]
    passed = [k.value for k in new.keywords if k.arg == "case"]
    args = list(new.args)
    if not passed and len(args) == len(old.args) + 1:
        passed = [args.pop()]
    assert [ast.dump(a) for a in args] == [ast.dump(a) for a in old.args], (
        f"{name}: аргументы вызова изменены: {ast.unparse(new)}")
    assert len(passed) == 1 and ast.dump(passed[0]) == _dump(case), (
        f"{name}: ярлык {[ast.unparse(p) for p in passed]}, ожидалось {case}")


def test_ac13_assertions_of_26_existing_tests_unchanged():
    """Вид и операнды утверждений 26 существующих тестов, кроме текстов сообщений, не изменены.

    Для каждой тестовой функции модуля базы та же функция HEAD несёт ту же
    последовательность нормальных форм утверждений (сообщение отброшено);
    число вызовов `pytest.fail` то же, у `test_ac16_…` — на один больше.

    Ловит мутацию: заодно с ярлыками `assert run.outcome ==
    acceptance.FULL_SUITE_RED` в `test_ac4_ac6_sled_…` заменён на `assert not
    run.green` или в `test_ac1_…` выброшено `assert bad in run.detail` —
    последовательность форм расходится, тест краснеет с функцией.
    """
    head = _funcs("HEAD")
    base = _plan.module_tests(_tree(DIFF_BASE, _plan.NEW_FILE))
    assert len(base) == _plan.EXISTING_TESTS, (
        f"тестов в модуле базы {len(base)}, критерий называет {_plan.EXISTING_TESTS}")
    problems = []
    for func in base:
        new = head.get(func.name)
        if new is None:
            problems.append(f"{func.name}: нет на HEAD")
            continue
        if _forms(new) != _forms(func):
            problems.append(f"{func.name}: утверждения изменены")
        extra = 1 if func.name == _NODE_MODULES_TEST else 0
        if _fails(new) != _fails(func) + extra:
            problems.append(f"{func.name}: pytest.fail {_fails(new)}, ожидалось "
                            f"{_fails(func) + extra}")
    assert not problems, "\n".join(problems)


def test_ac13_sandbox_assert_unknown_unchanged():
    """Метод песочницы `ReportSandbox.assert_unknown` на HEAD равен базе по `ast.dump`.

    Ловит мутацию: параметр `case` добавлен и в метод песочницы (или его
    сообщения переписаны) — дамп метода расходится, тест краснеет.
    """
    base = _plan.class_method(_tree(DIFF_BASE, _plan.SANDBOX_FILE),
                              "ReportSandbox", "assert_unknown")
    head = _plan.class_method(_tree("HEAD", _plan.SANDBOX_FILE),
                              "ReportSandbox", "assert_unknown")
    assert base is not None, "ReportSandbox.assert_unknown нет в базе"
    assert head is not None, "ReportSandbox.assert_unknown нет на HEAD"
    assert ast.dump(head) == ast.dump(base), "ReportSandbox.assert_unknown изменён"
