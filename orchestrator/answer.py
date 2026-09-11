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

from . import artifact_branch, artifact_source, fsm_advance, gitcmd, lease, store


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


def _zones_mandate_marker_paths(raw: str) -> list[str]:
    """Пути строки маркера `fsm_advance._ZONES_MANDATE_MARKER` в тексте
    файла ответа Оператора («Расширение зон разрешено: <пути>») —
    пустой список, если маркера в тексте нет (SPEC, требование 1: маркер
    определяет ТОЛЬКО этот путь `answer`, без него — прежний отказ)."""
    for line in raw.splitlines():
        line = line.strip()
        if line.startswith(fsm_advance._ZONES_MANDATE_MARKER):
            return fsm_advance._split_zone_paths(
                line[len(fsm_advance._ZONES_MANDATE_MARKER):])
    return []


def _read_answer_file(task_id: str, file_path: str) -> str:
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        sys.exit(f"[{task_id}] файл ответа не прочитан из {file_path}: {exc}")


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
    """Гейт состояния (SPEC 01M287TPG0HAVXS8CHBCY679WN, требование 1):
    `escalated` — прежний путь без изменений. `in_dev`/`review` —
    принимается ТОЛЬКО если текст файла несёт строку маркера
    `fsm_advance._ZONES_MANDATE_MARKER` («Расширение зон разрешено:
    ...») — состояние задачи не меняется, журнал получает отдельную
    запись с путями мандата (AC-1). Файл без маркера в этих состояниях,
    как и любое другое состояние вне `escalated`, — прежний отказ,
    прежнее сообщение (AC-2)."""
    t = store.get_task(conn, task_id)
    state = t["state"]
    mandate_paths: list[str] = []
    if state == "escalated":
        raw = _read_answer_file(task_id, file_path)
    elif state in ("in_dev", "review"):
        raw = _read_answer_file(task_id, file_path)
        mandate_paths = _zones_mandate_marker_paths(raw)
        if not mandate_paths:
            sys.exit(f"[{task_id}] answer доступна только для задачи в "
                     f"состоянии escalated (сейчас: {state})")
    else:
        sys.exit(f"[{task_id}] answer доступна только для задачи в "
                 f"состоянии escalated (сейчас: {state})")

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

    if mandate_paths:
        action = ("ANSWER создан (мандат на расширение зон: "
                 f"{', '.join(mandate_paths)})")
    else:
        action = "ANSWER создан"
    store.journal(conn, task_id, "operator", action, rel_answer)
    print(f"[{task_id}] {rel_answer} создан и закоммичен в артефактную "
          f"ветку {branch}")


def cmd_zones_extend(task_id: str, paths_arg: str,
                     session_id: str | None = None) -> None:
    """`zones-extend <id> <путь1>[, <путь2>]` (SPEC
    01M287TPG0HAVXS8CHBCY679WN, требование 2): та же lease-дисциплина
    и резолв префикса, что у `cmd_answer`."""
    conn = store.db()
    task_id = store.resolve_task_id(conn, task_id)
    lease.run_locked(conn, task_id, session_id,
                     lambda sid: _cmd_zones_extend(conn, task_id, paths_arg))


def _cmd_zones_extend(conn, task_id: str, paths_arg: str) -> None:
    paths = fsm_advance._split_zone_paths(paths_arg)
    if not paths:
        sys.exit(f"[{task_id}] zones-extend: отказ — пустой список путей")

    branch, _foreign = artifact_source.resolve(conn, task_id)
    existing = gitcmd.ls_tree_files(branch, f"tasks/{task_id}") or []
    n = _next_answer_number(existing)
    rel_answer = f"tasks/{task_id}/ANSWER-{n}.md"
    paths_str = ", ".join(paths)
    raw = (f"{fsm_advance._ZONES_MANDATE_MARKER} {paths_str}\n\n"
          f"мандат Оператора: {paths_str}\n")
    text = _answer_document(task_id, n, raw)
    commit_message = f"{task_id}: ANSWER-{n} — ответ Оператора"
    commit_sha = artifact_branch.commit_files(task_id, {rel_answer: text},
                                              commit_message)
    if not commit_sha:
        sys.exit(f"[{task_id}] {rel_answer} не закоммичен в артефактную "
                 f"ветку {branch}")
    artifact_branch.push(task_id)
    store.journal(conn, task_id, "operator",
                  f"ANSWER создан (мандат на расширение зон: {paths_str})",
                  rel_answer)

    # AC-5/AC-6: обновление `zones_extension` — ТОЛЬКО если PLAN.md ГОЛОВЫ
    # (не worktree) уже несёт раздел «## Расширение зон» с РОВНО тем же
    # множеством путей, что переданы команде; иначе БД не трогается вовсе
    # (`_plan_zones_extension_paths` даёт `None`, когда раздела/строки
    # «Пути:» нет — тот же разбор, что уже применяет гейт зон).
    plan_text, _reason = gitcmd.show(branch, f"tasks/{task_id}/PLAN.md")
    plan_paths = (fsm_advance._plan_zones_extension_paths(plan_text)
                 if plan_text is not None else None)
    if plan_paths is not None and set(plan_paths) == set(paths):
        t = store.get_task(conn, task_id)
        merged = sorted(set(fsm_advance._split_zone_paths(t["zones_extension"]))
                        | set(paths))
        store.update_task(conn, task_id, zones_extension=",".join(merged))
        print(f"[{task_id}] {rel_answer} создан, zones_extension обновлён: "
             f"{','.join(merged)}")
    else:
        store.journal(conn, task_id, "operator",
                      "раздел PLAN отсутствует — разработчик добавит на "
                      "следующем шаге", "")
        print(f"[{task_id}] {rel_answer} создан, раздел «Расширение зон» "
             f"PLAN.md не совпадает с переданными путями — zones_extension "
             f"не изменён")
