"""Команда `plank-run <id> [файл]`: штатный локальный прогон планки задачи в
шаге роли (SPEC 01M41R4YAM4NGEQXW1FWH7T22M, требования 1-2).

С ADR-0021 (этап 1) документы задачи живут в каталоге документов, а планку
в рабочую копию кода кладёт только пульт на время своего прогона. Команды
для такого же прогона у роли не было — она копировала планку руками и
убирала за собой; 03.10.2026 пять раз уборкой стал `shutil.rmtree("tasks")`
— весь отслеживаемый каталог задач рабочей копии. Здесь выкладка и уборка —
узлом пульта (`acceptance.plank_in_code_copy`): убирается только
`tasks/<id>/` рабочей копии кода, на любом исходе прогона.

Источник планки: в `tests_writing` — черновик `acceptance_tests/` каталога
документов задачи (его пишет test_author, в ссылку он попадёт только после
шага); в остальных состояниях — зафиксированная планка ссылки документов,
а не диск каталога документов.

Только чтение для пульта: строка задачи, журнал, ссылки и ветка задачи не
меняются, lease не берётся — поэтому команда в перечне команд роли
(`artel._ROLE_ALLOWED_COMMANDS`).
"""
import sys
from pathlib import Path

from . import acceptance, artifact_branch, config, store, workspace

NO_PLANK = "планки нет"


def _code_dir(task_id: str, target: str) -> Path:
    """Рабочая копия кода задачи — тот же выбор, что у прогона пульта
    (`advance_gates/acceptance._acceptance_run_body`)."""
    if target == config.DEFAULT_TARGET:
        return workspace.path(task_id)
    return config.PROJECTS / target / "workspace"


def _is_plank_file(rel: str) -> bool:
    """Кеш байткода черновика (прогон test_author из каталога документов)
    — не часть планки."""
    return "__pycache__" not in rel.split("/") and not rel.endswith(".pyc")


def _draft_files(docs_plank: Path) -> dict[str, bytes]:
    if not docs_plank.is_dir():
        return {}
    files = {}
    for path in sorted(docs_plank.rglob("*")):
        rel = path.relative_to(docs_plank).as_posix()
        if path.is_file() and _is_plank_file(rel):
            files[rel] = path.read_bytes()
    return files


def _has_tests(names) -> bool:
    return any(Path(n).name.startswith("test_") and n.endswith(".py")
               for n in names)


def _selected(arg: str, task_id: str, names: list[str]) -> str | None:
    """Путь от каталога планки для аргумента `[файл]` (с `::узлом` pytest,
    если он назван) либо `None`, если такого файла в планке нет. Принимает
    имя файла и его путь с префиксом `tasks/<id>/acceptance_tests/`."""
    path, sep, node = arg.partition("::")
    for prefix in (f"tasks/{task_id}/acceptance_tests/", "acceptance_tests/"):
        if path.startswith(prefix):
            path = path[len(prefix):]
    path = path.rstrip("/")
    if path in names or any(n.startswith(path + "/") for n in names):
        return path + sep + node
    return None


def _docs_in_code_copy(own_dir: Path) -> list[str]:
    """Файлы `tasks/<id>/` рабочей копии кода вне `acceptance_tests/` —
    документы, записанные туда по ошибке: уборка выкладки снесла бы их до
    того, как пульт после шага перенесёт их в ссылку документов."""
    if not own_dir.is_dir():
        return []
    return sorted(p.relative_to(own_dir).as_posix()
                  for p in own_dir.rglob("*")
                  if p.is_file() and not p.relative_to(own_dir).as_posix()
                  .startswith("acceptance_tests/"))


def cmd_plank_run(task_id: str, file_arg: str | None = None) -> None:
    conn = store.db()
    task_id = store.resolve_task_id(conn, task_id)
    t = store.get_task(conn, task_id)
    target = store.task_target(conn, task_id)
    head = f"[{task_id}] plank-run"

    code_dir = _code_dir(task_id, target)
    if not code_dir.is_dir() or code_dir.resolve() == config.ROOT.resolve():
        sys.exit(f"{head}: отказ — рабочей копии кода задачи нет ({code_dir}); "
                 f"планку выложить некуда")

    draft = None
    if t["state"] == "tests_writing":
        docs_plank = (artifact_branch.docs_dir(task_id, target)
                      / "acceptance_tests")
        draft = _draft_files(docs_plank)
        names = sorted(draft)
        source = f"черновик {docs_plank}"
    else:
        ref = artifact_branch.branch_name(task_id)
        prefix = f"tasks/{task_id}/acceptance_tests/"
        paths = artifact_branch.ls_tree(task_id, ref, prefix.rstrip("/"))
        if paths is None and not artifact_branch.rev_sha(task_id, ref):
            paths = []  # ссылки нет — нет и зафиксированной планки
        if paths is None:
            sys.exit(f"{head}: отказ — ссылка документов {ref} не прочитана "
                     f"(git не ответил); планка не выложена")
        names = sorted(p[len(prefix):] for p in paths if p.startswith(prefix))
        source = f"зафиксированная планка {ref}"
    if not _has_tests(names):
        sys.exit(f"{head}: отказ — {NO_PLANK}: в источнике ({source}) нет "
                 f"файлов test_*.py; pytest не запускался")

    selected = None
    if file_arg:
        selected = _selected(file_arg, task_id, names)
        if selected is None:
            sys.exit(f"{head}: отказ — файла {file_arg} нет в планке "
                     f"({source}); в ней: {', '.join(names)}")

    own_dir = code_dir / "tasks" / task_id
    stray_docs = _docs_in_code_copy(own_dir)
    if stray_docs:
        sys.exit(f"{head}: отказ — в рабочей копии кода лежат файлы "
                 f"{own_dir}: {', '.join(stray_docs)}; документы задачи "
                 f"пишутся в каталог документов "
                 f"{artifact_branch.docs_dir(task_id, target)}, а plank-run "
                 f"убирает {own_dir} целиком")

    print(f"{head}: {source}, cwd {code_dir}", flush=True)
    with acceptance.plank_in_code_copy(
            task_id, artifact_branch.branch_name(task_id), code_dir,
            files=draft) as tdir:
        tests_dir = tdir / "acceptance_tests"
        target_arg = str(tests_dir / selected) if selected else str(tests_dir)
        code, output = acceptance.run_plank([target_arg], code_dir)
    print(output)
    summary = acceptance.run_summary_line(output) or "итоговой строки нет"
    if code is None:
        sys.exit(f"{head}: итог pytest: {summary}; прогон превысил "
                 f"{config.ACCEPTANCE_TIMEOUT_SEC}с и оборван")
    print(f"{head}: итог pytest: {summary}; код выхода pytest: {code}")
    if code != 0:
        sys.exit(code)
