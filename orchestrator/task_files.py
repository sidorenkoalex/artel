"""Команда `task-rm <id> <путь>…`: удаление файлов в пределах своей задачи
(SPEC 01M6JJ4J4NBV2Y1Q4XHE3C3FVT, требование 4).

У роли нет `rm`, а `git clean` в рабочей копии и в каталогах пульта
отклоняет обёртка git роли (`orchestrator/role_git.py`): эта команда —
штатный способ убрать свой временный файл. Удаляются только файлы рабочей
копии задачи и файлы каталога её документов, которых нет в ссылке
документов (созданные после последнего автокоммита). Набор проверяется
целиком до первого удаления: один недопустимый путь — отказ всей команды,
ни один файл не удалён.

`.git` любого уровня и всё внутри него — отказ: после удаления файла `.git`
рабочей копии git пульта из неё нашёл бы репозиторий пульта — условие
инцидента 04.11.
"""
import os
import sys
from pathlib import Path

from . import artifact_branch, config, gitcmd, repo_context, runner, store, workspace

USAGE = "task-rm <id> <путь>…"


def cmd_task_rm(rest: list) -> None:
    if len(rest) < 2:
        sys.exit(f"Использование: {USAGE}")
    task_id, paths = rest[0], rest[1:]
    if runner.in_role_environment():
        own = os.environ.get(config.ARTEL_TASK_ENV)
        if not own:
            sys.exit(f"task-rm: процесс роли без {config.ARTEL_TASK_ENV} — "
                     f"задача шага не определена, файлы не удалены")
        if task_id != own:
            sys.exit(f"task-rm: процессу роли задачи {own} доступны только "
                     f"её файлы, не задачи {task_id}; файлы не удалены")
    task_id, target = _task(task_id)
    roots = [Path(os.path.realpath(workspace.path(task_id, target))),
             Path(os.path.realpath(artifact_branch.docs_dir(task_id, target)))]
    in_branch = _artifact_files(task_id, target)
    planned, refusals = [], []
    for raw in paths:
        item, reason = _check(raw, roots, task_id, in_branch)
        if reason is not None:
            refusals.append(f"{raw}: {reason}")
        else:
            planned.append(item)
    if refusals:
        sys.exit("task-rm: отказ всей команды, ни один файл не удалён —\n  "
                 + "\n  ".join(refusals))
    for item in planned:
        os.unlink(item)
        print(f"удалён {item}")


def _task(task_id: str) -> tuple[str, str]:
    """(полный id, проект) задачи по БД; задачи нет — отказ."""
    if not store.db_usable():
        sys.exit(f"task-rm: БД пульта недоступна — задача {task_id} не найдена")
    conn = store.db_readonly()
    try:
        full = store.resolve_task_id(conn, task_id)
        if not store.task_exists(conn, full):
            sys.exit(f"task-rm: задача {task_id} не найдена")
        return full, store.task_target(conn, full)
    finally:
        conn.close()


def _artifact_files(task_id: str, target: str) -> set[str]:
    """Пути `tasks/<id>/…` в голове ссылки документов задачи; ссылки нет —
    пусто. git не ответил при живой ссылке — отказ: иначе файл ветки
    сошёл бы за новый."""
    repo = repo_context.clone_path(target)
    ref = artifact_branch.branch_name(task_id)
    if not gitcmd.branch_head_sha(ref, repo=repo):
        return set()
    files = gitcmd.ls_tree_files(ref, f"tasks/{task_id}", repo=repo)
    if files is None:
        sys.exit(f"task-rm: ссылка документов {ref} не прочитана — файлы не удалены")
    return set(files)


def _within(path: Path, roots: list) -> Path | None:
    for root in roots:
        if path == root or root in path.parents:
            return root
    return None


def _check(raw: str, roots: list, task_id: str,
           in_branch: set) -> tuple[Path | None, str | None]:
    """(путь к удалению, None) либо (None, причина отказа). Родительский
    каталог разрешается до конца, сам путь — нет: удаляется ссылка, а не
    её цель."""
    absolute = os.path.abspath(raw)
    name = os.path.basename(absolute)
    if name in ("", ".", ".."):
        return None, "каталог, не файл"
    item = Path(os.path.realpath(os.path.dirname(absolute))) / name
    root = _within(item, roots)
    if root is None or item == root:
        return None, "вне рабочей копии задачи и каталога её документов"
    rel = item.relative_to(root)
    if any(part.lower() == ".git" for part in rel.parts):
        return None, "`.git` и его содержимое не удаляются"
    if not os.path.lexists(item):
        return None, "файла нет"
    if item.is_symlink():
        if _within(Path(os.path.realpath(item)), roots) is None:
            return None, "символическая ссылка ведёт за пределы задачи"
    elif item.is_dir():
        return None, "каталог, не файл"
    if root == roots[1] and f"tasks/{task_id}/{rel.as_posix()}" in in_branch:
        return None, "файл лежит в ссылке документов задачи"
    return item, None
