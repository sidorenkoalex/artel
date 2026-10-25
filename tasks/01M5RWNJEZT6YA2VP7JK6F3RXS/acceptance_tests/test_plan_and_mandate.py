"""Факты задачи: счёт вызовов git в PLAN.md и правка существующего теста по
мандату Оператора (AC-14, AC-15).

Группа: разовый

Красен до реализации: PLAN.md задачи ещё не написан, а `tests/test_review_package.py::CmdRunReviewPackageTest::test_developer_step_has_no_package` совпадает с базой — два элемента ожидаемого списка не перенесены, фраза комментария прежняя.

PLAN.md читается помощником пульта `_pult.artifact_text`; версии файла
теста — из git рабочей копии кода: база диффа задачи (`_pult.DIFF_BASE`) и
HEAD.
"""
import ast
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _pult import CODE_ROOT, DIFF_BASE, artifact_text  # noqa: E402

TEST_FILE = "tests/test_review_package.py"
TEST_CLASS = "CmdRunReviewPackageTest"
TEST_NAME = "test_developer_step_has_no_package"
MERGE_TEST = "Ac5ProofMismatchTest"

# Точки досрочной досылки требования 3 SPEC — адреса разбора в PLAN.
SEND_POINTS = ("origin_sync_refusal", "fetch_from_origin",
               "fetch_all_from_origin", "ensure_draft_mr",
               "ensure_head_in_origin", "_sync_main_or_wait",
               "_spawn_and_wait", "spawn_agent", "commit_closing",
               "_wait_for_branch_ci_green", "_await_main_ci",
               "_full_suite_or_refuse")

INT = re.compile(r"(?<![\w.-])\d+(?![\w.])")


def show(rev: str, rel: str) -> str:
    res = subprocess.run(["git", "-C", str(CODE_ROOT), "show", f"{rev}:{rel}"],
                         capture_output=True, text=True, encoding="utf-8")
    return res.stdout if res.returncode == 0 else ""


def counts_line(section: list, word: str) -> tuple | None:
    """(до, после) — два первых целых числа первой строки раздела, где есть
    слово `word` и хотя бы два числа; нет такой строки — None."""
    pattern = re.compile(rf"(?<![\w-]){re.escape(word)}(?![\w-])", re.IGNORECASE)
    for line in section:
        match = pattern.search(line)
        if not match:
            continue
        numbers = INT.findall(line[match.end():])
        if len(numbers) >= 2:
            return int(numbers[0]), int(numbers[1])
    return None


def test_ac14_plan_counts_git_calls_on_merge_outcome_test():
    """PLAN.md несёт счёт вызовов git на `Ac5ProofMismatchTest` до и после.

    Сценарий: текст PLAN.md из ссылки документов. После первого упоминания
    `Ac5ProofMismatchTest` есть строки «всего», `push` и `remote`, каждая
    с двумя числами — до и после (строка таблицы `| push | 40 | 28 |` или
    `push: до 40, после 28`). Если отправок (`push`) меньше на 6 и менее,
    тот же раздел называет хотя бы одну точку досылки требования 3.

    Ловит мутацию: PLAN без счёта на названном тесте (или без строки
    `remote`/`push`) — нет строки с двумя числами, тест краснеет.
    Ловит мутацию: сокращение отправок меньше 6 без разбора по точкам
    досылки — ни одна точка требования 3 в разделе не названа.
    """
    plan = artifact_text("PLAN.md")
    assert plan is not None, "PLAN.md задачи нет в ссылке документов"
    assert MERGE_TEST in plan, f"PLAN.md не называет {MERGE_TEST}"
    section = plan[plan.index(MERGE_TEST):].splitlines()
    found = {word: counts_line(section, word)
             for word in ("всего", "push", "remote")}
    missing = [word for word, pair in found.items() if pair is None]
    assert not missing, (f"нет строки счёта «до/после» для {missing} после "
                         f"упоминания {MERGE_TEST}")
    before, after = found["push"]
    if before - after < 6:
        text = "\n".join(section)
        assert any(point in text for point in SEND_POINTS), (
            f"отправок меньше на {before - after} (< 6), а разбора по точкам "
            f"досылки требования 3 нет")


def method_node(tree: ast.Module) -> ast.FunctionDef | None:
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == TEST_CLASS:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == TEST_NAME:
                    return item
    return None


def expected_calls(fn: ast.FunctionDef) -> ast.List | None:
    """Литерал ожидаемого списка вызовов: второй аргумент
    `self.assertEqual(calls, [...], …)`."""
    for node in ast.walk(fn):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "assertEqual" and len(node.args) >= 2
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id == "calls"
                and isinstance(node.args[1], ast.List)):
            return node.args[1]
    return None


def has_strings(node: ast.AST, *words: str) -> bool:
    values = [n.value for n in ast.walk(node)
              if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    return all(w in values for w in words)


def comment_text(lines: list, fn: ast.FunctionDef) -> str:
    body = lines[fn.lineno - 1:fn.end_lineno]
    parts = [line.strip()[1:].strip() for line in body
             if line.strip().startswith("#")]
    return " ".join(" ".join(parts).split())


def test_ac15_review_package_test_changed_only_by_mandate():
    """`test_developer_step_has_no_package` правлен ровно по требованию 8.

    Сценарий: версии `tests/test_review_package.py` на базе диффа задачи и
    на HEAD. В ожидаемом списке вызовов git метода элементы
    `remote get-url origin` и `push -q origin <ref>:<ref>` перенесены в
    самый конец (после последнего `rev-parse --verify --quiet`), прочие
    элементы — те же и в том же порядке; остальной код метода
    (включая докстринг) не тронут; файл вне метода совпадает с базой
    побайтно; в комментарии метода фраза «…её отправка в `origin`, затем
    чтение головы…» заменена на отправку при выходе из команды, начало и
    конец комментария прежние. Сам тест зелёный.

    Ловит мутацию: элементы удалены, а не перенесены, или перенесены не в
    конец — список HEAD не равен ожидаемой перестановке базы.
    Ловит мутацию: заодно поправлен другой тест файла или ослаблено
    сравнение (`assertCountEqual`) — текст вне метода или код метода
    отличается от базы.
    Ловит мутацию: комментарий о порядке отправки не поправлен — прежняя
    фраза осталась.
    """
    assert DIFF_BASE, "база диффа задачи не определена"
    old_text, new_text = show(DIFF_BASE, TEST_FILE), show("HEAD", TEST_FILE)
    assert old_text and new_text, f"{TEST_FILE} не прочитан из git"
    old_fn = method_node(ast.parse(old_text))
    new_fn = method_node(ast.parse(new_text))
    assert old_fn is not None and new_fn is not None, f"{TEST_NAME} не найден"
    old_list, new_list = expected_calls(old_fn), expected_calls(new_fn)
    assert old_list is not None and new_list is not None, \
        "ожидаемый список вызовов git не найден"

    old_items = list(old_list.elts)
    moved = ([e for e in old_items if has_strings(e, "remote", "get-url", "origin")]
             + [e for e in old_items if has_strings(e, "push", "-q", "origin")])
    assert len(moved) == 2, "в базе нет двух переносимых элементов"
    rest = [e for e in old_items if not any(e is m for m in moved)]
    assert [ast.dump(e) for e in new_list.elts] == \
        [ast.dump(e) for e in rest + moved], "перенос элементов не по перечню"
    assert has_strings(rest[-1], "rev-parse", "--verify", "--quiet")

    old_list.elts, new_list.elts = [], []
    assert ast.dump(new_fn) == ast.dump(old_fn), "код метода вне списка изменён"

    old_lines, new_lines = old_text.splitlines(), new_text.splitlines()
    assert (old_lines[:old_fn.lineno - 1] + old_lines[old_fn.end_lineno:]
            == new_lines[:new_fn.lineno - 1] + new_lines[new_fn.end_lineno:]), \
        "файл вне метода отличается от базы"

    old_comment = comment_text(old_lines, old_fn)
    new_comment = comment_text(new_lines, new_fn)
    phrase = "её отправка в `origin`, затем чтение головы"
    assert phrase in old_comment, "в базе нет прежней фразы комментария"
    assert phrase not in new_comment, "прежняя фраза комментария осталась"
    assert "при выходе из команды" in new_comment, new_comment
    head, tail = old_comment.split("сверка PLAN.md с головой,", 1)[0], \
        old_comment.split("Последний —", 1)[1]
    assert new_comment.startswith(head) and new_comment.endswith(tail), \
        "комментарий правлен вне фразы о порядке отправки"

    run = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
         f"{TEST_FILE}::{TEST_CLASS}::{TEST_NAME}"],
        cwd=str(CODE_ROOT), capture_output=True, text=True, timeout=100)
    assert run.returncode == 0, run.stdout[-2000:] + run.stderr[-2000:]
