"""Правка теста по мандату ANSWER-1: из `GH_CALLS` прежнего теста удалены ровно четыре ключа MR, утверждения метода не тронуты.

Группа: разовый
Красен до реализации: в `GH_CALLS` файла `tests/test_01m5wcxbm7wcmrwcbwnchmar3t_gitlab_forge.py` на голове ветки ещё есть ключи `open_mr`, `undraft_mr`, `assign_mr`, `mr_status` — правки по мандату нет.

Факт этой задачи — разница файла прежнего теста на голове ветки
(`HEAD` рабочей копии кода) с базой диффа задачи (`DIFF_BASE` помощника
пульта — точка расхождения с `origin/main`); после мержа сравнивать не
с чем. Разбор — модулем `ast`, без импорта файла.
"""
import ast
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pult import CODE_ROOT, DIFF_BASE  # noqa: E402

REL = "tests/test_01m5wcxbm7wcmrwcbwnchmar3t_gitlab_forge.py"
METHOD = "test_ac13_github_other_functions_refuse"
REMOVED = {"open_mr", "undraft_mr", "assign_mr", "mr_status"}
KEPT = {"job_result", "job_test_report", "token_user", "token_expiry",
        "protections", "project_info", "branch_pipeline"}
SKIP_NAMES = {"skip", "skipif", "xfail", "skipTest", "expectedFailure"}


def revision_text(revision: str) -> str:
    """Текст файла прежнего теста на ревизии `revision` рабочей копии кода."""
    res = subprocess.run(["git", "-C", CODE_ROOT, "show", f"{revision}:{REL}"],
                         capture_output=True, text=True, timeout=60,
                         start_new_session=True)
    if res.returncode != 0:
        raise RuntimeError(f"git show {revision}:{REL}: {res.stderr.strip()}")
    return res.stdout


def gh_calls_keys(tree: ast.Module) -> set:
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "GH_CALLS" for t in node.targets):
            return {k.value for k in node.value.keys if isinstance(k, ast.Constant)}
    raise LookupError("GH_CALLS не найден")


def method(tree: ast.Module) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == METHOD:
            return node
    raise LookupError(f"{METHOD} не найден")


def asserts(node: ast.FunctionDef) -> list:
    return [ast.dump(n) for n in ast.walk(node) if isinstance(n, ast.Assert)]


def skip_marks(node: ast.FunctionDef) -> list:
    """Имена skip/xfail в декораторах и вызовах тела метода."""
    found = []
    for sub in [*node.decorator_list, *node.body]:
        for n in ast.walk(sub):
            name = n.attr if isinstance(n, ast.Attribute) else (
                n.id if isinstance(n, ast.Name) else None)
            if name in SKIP_NAMES:
                found.append(name)
    return found


def test_ac17_gh_calls_four_keys_removed_asserts_unchanged():
    """`GH_CALLS` на голове ветки — без четырёх ключей MR и с прежними семью; утверждения `test_ac13_github_other_functions_refuse` — как на базе; skip/xfail нет.

    Сценарий: файл прежнего теста читается на `HEAD` рабочей копии кода и
    на базе диффа задачи. На `HEAD`: ключи `GH_CALLS` не содержат
    `open_mr`, `undraft_mr`, `assign_mr`, `mr_status` и содержат семь
    прежних; список утверждений метода (дерево `ast` каждого `assert`)
    совпадает с базой; у метода нет декоратора или вызова `skip`/`xfail`.

    Ловит мутацию: удалён лишний ключ (`token_user`) или один из четырёх
    оставлен; утверждение метода ослаблено (снята проверка шпиона `gh`);
    метод помечен `skip`/`xfail` вместо правки словаря.
    """
    assert DIFF_BASE, "база диффа задачи не определена при выкладке планки"
    head = ast.parse(revision_text("HEAD"))
    base = ast.parse(revision_text(DIFF_BASE))
    keys = gh_calls_keys(head)
    assert not keys & REMOVED, f"в GH_CALLS остались ключи {sorted(keys & REMOVED)}"
    assert KEPT <= keys, f"из GH_CALLS пропали ключи {sorted(KEPT - keys)}"
    assert asserts(method(head)) == asserts(method(base)), \
        f"утверждения {METHOD} отличаются от базы {DIFF_BASE}"
    assert skip_marks(method(head)) == [], \
        f"у {METHOD} пометки {skip_marks(method(head))}"
