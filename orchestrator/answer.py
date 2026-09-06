"""Команда `answer`: канал ответа Оператора на эскалацию (SPEC T075,
SPEC 01M1KT0792125J9ZNJNZJ86E9Q требование 2).

`artel.py answer <id> <файл-с-ответом>` читает текст ответа из файла
Оператора и коммитит `tasks/<id>/ANSWER-n.md` (`n` — порядковый номер,
следующий за уже существующими файлами того же префикса) в артефактную
ветку пульта (`artifact_branch.commit_files`) — плотницки, без чекаута
(ADR-0012/A7): туда же, откуда его читает возврат из эскалации
(`fsm._answer_file_count` через `artifact_source.resolve`), а не в
worktree кодовой ветки задачи, которую эта команда до A7 создавала как
побочный эффект. Кодовая ветка и рабочее дерево `answer` не трогает
вовсе (ANSWER-1.md Оператора этой задачи, вариант A вопроса 1: у любой
задачи после A7 артефактная ветка есть всегда, отдельного пути «прежнего
флоу» для `answer` не существует).

Идентичность коммита — служебная (`fixation.FIXATION_AUTHOR_*`, дефолт
`artifact_branch.commit_files`), тем же приёмом, что и автокоммит шага
(`checkpoint._commit_external_step_artifacts`, «образец» из SPEC
«Материалы»): плотницкая запись не завязана ни на чей git-конфиг, читать
identity вызывающей сессии здесь уже нечего.

Push артефактной ветки после коммита ANSWER (SPEC
01M1TQ0X14Y5B3C87WC0Q31PK2, требование 1, AC-1) — тем же
`artifact_branch.push`, что уже зовут автокоммит шага и `cmd_new`:
классификация причины отказа и журналирование — внутри самой `push`,
здесь только вызов.
"""
import sys
from pathlib import Path

from . import artifact_branch, artifact_source, gitcmd, lease, store


def _next_answer_number(names) -> int:
    """Следующий свободный номер `ANSWER-n.md` по списку путей
    АРТЕФАКТНОЙ ветки задачи (`gitcmd.ls_tree_files`) — максимум
    существующих + 1, не счёт файлов: второй раунд эскалации после
    первого ответа обязан получить `ANSWER-2.md`, даже если бы
    `ANSWER-1.md` когда-то убрали."""
    existing = []
    for name in names:
        stem = Path(name).stem
        if not stem.startswith("ANSWER-"):
            continue
        suffix = stem[len("ANSWER-"):]
        if suffix.isdigit():
            existing.append(int(suffix))
    return max(existing, default=0) + 1


def _answer_document(task_id: str, n: int, raw: str) -> str:
    return (
        f"---\n"
        f"task: {task_id}\n"
        f"type: answer\n"
        f"author_role: operator\n"
        f"status: ready\n"
        f"schema_version: 2\n"
        f"---\n\n"
        f"# ANSWER-{n}: ответ Оператора\n\n"
        f"## Ответы\n\n"
        f"{raw}"
    )


def cmd_answer(task_id: str, file_path: str,
              session_id: str | None = None) -> None:
    """Берёт lease задачи перед работой (SPEC T044, требование 2) — тем же
    приёмом, что и остальные мутирующие команды задачи (approve/reject/
    run/kill/workspace).

    Префикс -> полный id (SPEC T094, требование 3, AC-3) резолвится ЗДЕСЬ,
    до lease (REVIEW T094 итерация 1, замечание 1)."""
    conn = store.db()
    task_id = store.resolve_task_id(conn, task_id)
    lease.run_locked(conn, task_id, session_id,
                     lambda sid: _cmd_answer(conn, task_id, file_path))


def _cmd_answer(conn, task_id: str, file_path: str) -> None:
    t = store.get_task(conn, task_id)
    if t["state"] != "escalated":
        sys.exit(f"[{task_id}] answer доступна только для задачи в "
                 f"состоянии escalated (сейчас: {t['state']})")
    try:
        raw = Path(file_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        sys.exit(f"[{task_id}] файл ответа не прочитан из {file_path}: {exc}")

    branch, _foreign = artifact_source.resolve(conn, task_id)
    existing = gitcmd.ls_tree_files(branch, f"tasks/{task_id}") or []
    n = _next_answer_number(existing)
    rel_answer = f"tasks/{task_id}/ANSWER-{n}.md"
    text = _answer_document(task_id, n, raw)
    commit_message = f"{task_id}: ANSWER-{n} — ответ Оператора"
    commit_sha = artifact_branch.commit_files(task_id, {rel_answer: text},
                                              commit_message)
    if not commit_sha:
        sys.exit(f"[{task_id}] {rel_answer} не закоммичен в артефактную "
                 f"ветку {branch}")
    artifact_branch.push(task_id)

    store.journal(conn, task_id, "operator", "ANSWER создан", rel_answer)
    print(f"[{task_id}] {rel_answer} создан и закоммичен в артефактную "
          f"ветку {branch}")
