"""Общие хелперы планки 01M3H3T8RKTVKTJJYEAGW19BPS (вынос команды
`ci-rerun` в `orchestrator/ci_rerun.py`).

Задача — рефакторинг «перенести дословно», поэтому почти каждый критерий
сверяет СЕГОДНЯШНИЙ файл с его ДОРЕФАКТОРИНГОВОЙ версией. Версия «до» —
не копия текста в планке (она протухла бы от любой подтяжки main), а
`git show <merge-base(origin/main, HEAD)>:<путь>`: точка расхождения
ветки задачи с базой интеграции, тот же приём, что у
`tasks/01M2CN465WEDCF6D77V37FJ82E/acceptance_tests/_util.py`.

Сверка — по AST, не по тексту: перенос функции в другой модуль
НЕИЗБЕЖНО меняет квалификацию имён (`_origin_main_sha` ->
`fsm._origin_main_sha`, `VERIFYING_STATUS_ACTION` ->
`fsm.VERIFYING_STATUS_ACTION`), и побайтная сверка исходника отказывала
бы корректному переносу. Сверяются те величины, которые критерии
называют буквально: строковые литералы (тексты отказов, тексты записей
журнала) и порядок вызовов по имени последнего сегмента (обращения к
`gh` через `ci.*`, `store.journal`, `sys.exit`).
"""
import ast
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

TASK_ID = "01M3H3T8RKTVKTJJYEAGW19BPS"

#: Шесть функций команды, которые требование 1 и AC-1 называют поимённо.
MOVED_FUNCTIONS = ("cmd_ci_rerun", "_ci_rerun_refuse", "_last_red_status_sha",
                   "_last_ci_rerun_reason", "_ci_rerun_outcome",
                   "_cmd_ci_rerun")

#: Пять закрытых имён команды, которых AC-3 требует в `fsm.py` не видеть.
PRIVATE_NAMES = tuple(n for n in MOVED_FUNCTIONS if n != "cmd_ci_rerun")

FSM_REL = "orchestrator/fsm.py"
CI_RERUN_REL = "orchestrator/ci_rerun.py"
ARTEL_REL = "orchestrator/artel.py"
UNIT_TESTS_REL = "tests/test_ci_rerun_command.py"

# Квалификаторы, которые перенос имеет право добавить или снять: команда
# переезжает ровно между этими двумя модулями. Всё остальное (`ci.`,
# `store.`, `config.`, `mock.`) сверяется как есть.
_MODULE_PREFIX_RE = re.compile(r"\b(?:fsm|ci_rerun)\.")


def merge_base(ref: str = "origin/main") -> str:
    """sha точки расхождения ветки задачи с базой интеграции."""
    res = subprocess.run(["git", "merge-base", ref, "HEAD"], cwd=REPO_ROOT,
                         capture_output=True, text=True, check=True)
    return res.stdout.strip()


def base_source(rel_path: str) -> str:
    """Текст файла в версии «до рефакторинга» (точка расхождения с
    `origin/main`) — через git, без обращения к диску рабочей копии."""
    res = subprocess.run(["git", "show", f"{merge_base()}:{rel_path}"],
                         cwd=REPO_ROOT, capture_output=True, text=True,
                         check=True)
    return res.stdout


def current_source(rel_path: str) -> str:
    """Текст файла в сегодняшнем рабочем дереве ветки задачи."""
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def changed_paths_since_base() -> list:
    """Пути, изменённые веткой задачи относительно точки расхождения,
    включая незакоммиченное рабочее дерево."""
    res = subprocess.run(["git", "diff", "--name-only", merge_base()],
                         cwd=REPO_ROOT, capture_output=True, text=True,
                         check=True)
    return [line for line in res.stdout.splitlines() if line]


def functions(source: str) -> dict:
    """{имя -> узел} для функций ВЕРХНЕГО уровня модуля."""
    tree = ast.parse(source)
    return {node.name: node for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def qualified_functions(source: str) -> dict:
    """{'Класс.метод' | 'функция' -> узел} для всех функций модуля:
    верхний уровень и методы классов (вложенность глубже не нужна —
    в сверяемых файлах её нет)."""
    tree = ast.parse(source)
    out = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out[node.name] = node
        elif isinstance(node, ast.ClassDef):
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out[f"{node.name}.{sub.name}"] = sub
    return out


def module_assignments(source: str) -> dict:
    """{имя -> нормализованный исходник} для присваиваний верхнего уровня
    (фикстуры-константы модуля тестов)."""
    tree = ast.parse(source)
    out = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                out[target.id] = normalize_module_prefix(
                    ast.get_source_segment(source, node) or "")
    return out


def _body_without_docstring(node) -> list:
    """Тело функции без докстринга: AC-1 перечисляет, что обязано остаться
    дословным (тексты отказов, тексты записей журнала, обращения к `gh`),
    и докстринга в этом перечне нет — ссылку на новый модуль в нём
    поправить можно."""
    body = list(node.body)
    if body and isinstance(body[0], ast.Expr) and \
            isinstance(body[0].value, ast.Constant) and \
            isinstance(body[0].value.value, str):
        return body[1:]
    return body


def string_literals(node) -> list:
    """Строковые литералы тела функции в порядке обхода AST — включая
    части f-строк; докстринг исключён."""
    out = []

    def walk(current):
        for child in ast.iter_child_nodes(current):
            if isinstance(child, ast.Constant) and isinstance(child.value, str):
                out.append(child.value)
            walk(child)

    for stmt in _body_without_docstring(node):
        if isinstance(stmt, ast.Constant) and isinstance(stmt.value, str):
            out.append(stmt.value)
        walk(stmt)
    return out


def call_names(node) -> list:
    """Имена вызываемых в теле функции объектов в порядке обхода AST —
    ПОСЛЕДНИЙ сегмент точечного имени (`ci.trigger_rerun` ->
    `trigger_rerun`, `fsm._origin_main_sha` -> `_origin_main_sha`): смена
    модуля-хозяина при переносе имя не меняет, а вот исчезнувший или
    переставленный вызов видно сразу."""
    out = []

    def walk(current):
        for child in ast.iter_child_nodes(current):
            if isinstance(child, ast.Call):
                func = child.func
                if isinstance(func, ast.Attribute):
                    out.append(func.attr)
                elif isinstance(func, ast.Name):
                    out.append(func.id)
                else:
                    out.append("<выражение>")
            walk(child)

    for stmt in _body_without_docstring(node):
        walk(stmt)
    return out


def normalize_module_prefix(text: str) -> str:
    """Текст без квалификаторов `fsm.`/`ci_rerun.` — единственного, что
    перенос команды в другой модуль вправе поменять в подменах и вызовах
    существующих юнит-тестов (AC-4: «изменены только импорты и пути
    подмен»)."""
    return _MODULE_PREFIX_RE.sub("", text)


def normalized_function_source(source: str, node) -> str:
    """Исходник функции без квалификаторов модуля и без докстринга —
    единица сверки «прежняя проверка не изменена» (AC-4)."""
    segments = [ast.get_source_segment(source, stmt) or ""
                for stmt in _body_without_docstring(node)]
    return normalize_module_prefix("\n".join(segments))
