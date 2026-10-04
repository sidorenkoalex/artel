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

Строки мандатов файла ответа разбирает и проверяет общий узел
`advance_gates/mandate.py` (SPEC 01M3GKJBXEBHB6ZA48J7VG8Z8W, требования
1-2) — тот же, что зовут гейт зон и гейт неослабления тестов: элемент, не
являющийся путём репозитория, отказывает ЗДЕСЬ, до коммита ANSWER, а не
молча не засчитывается гейтом через шаг роли (прецедент 26.09).

Отправку ссылки документов `refs/artifacts/<id>` в origin после коммита
ANSWER делает сам узел записи (`artifact_branch.commit_files`, ADR-0021
п.3). Коммит ANSWER перефиксирует документы задачи (`store.
record_fixation`): это запись пульта по команде Оператора, а не правка
мимо гейтов, и следующая сверка фиксации не должна видеть её
расхождением.
"""
import sys
from pathlib import Path

from . import (artifact_branch, artifact_source, cycle_hint, fixation,
               fsm_advance, gitcmd, lease, runner, store, workspace)
from .advance_gates import mandate


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
    определяет ТОЛЬКО этот путь `answer`, без него — прежний отказ).

    Саму строку разбирает общий узел `mandate.elements` (SPEC
    01M3GKJBXEBHB6ZA48J7VG8Z8W, требование 1) — тот же, что зовут оба
    гейта; здесь остаётся только выбор первой строки маркера в тексте."""
    for line in raw.splitlines():
        found = mandate.elements(line, fsm_advance._ZONES_MANDATE_MARKER)
        if found is not None:
            return found
    return []


def _test_mandate_marker_elements(raw: str) -> list[str]:
    """Элементы ВСЕХ строк маркера `mandate.TEST_WEAKENING_MANDATE_MARKER`
    («Ослабление тестов разрешено: …») в тексте файла ответа, в порядке
    появления, без повторов; пустой список — маркера нет (SPEC
    01M42NB9GKXNP74HAYEJ7C7CA8, требование 3).

    Все строки, а не первая, как у мандата зон выше: гейт неослабления
    (`test_integrity._answer_mandate`) засчитывает элементы каждой строки
    файла, и журнал приёма обязан назвать ровно то, что гейт засчитает."""
    found: list[str] = []
    for line in raw.splitlines():
        for element in mandate.elements(
                line, mandate.TEST_WEAKENING_MANDATE_MARKER) or ():
            if element not in found:
                found.append(element)
    return found


def _read_answer_file(task_id: str, file_path: str) -> str:
    try:
        return Path(file_path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        sys.exit(f"[{task_id}] файл ответа не прочитан из {file_path}: {exc}")


def _read_checked_answer_file(task_id: str, file_path: str,
                              code_branch: str | None) -> str:
    """Текст файла ответа, прошедший проверку строк мандатов (SPEC
    01M3GKJBXEBHB6ZA48J7VG8Z8W, требование 2).

    Отказ здесь — ДО коммита ANSWER и до записи в журнал: элемент, который
    не является путём репозитория, гейтом молча не засчитывается, и
    26.09 мандат «Расширение зон разрешено: orchestrator/artel.py — только
    разбор аргументов…» стоил задаче лишнего круга ролью. Проверяются все
    строки обоих маркеров, правила — `mandate.refusals`."""
    raw = _read_answer_file(task_id, file_path)
    problems = mandate.refusals(raw, code_branch,
                                repo=workspace.task_repo(task_id))
    if problems:
        sys.exit(f"[{task_id}] answer отказана — строка мандата не прошла "
                 f"проверку:\n" + "\n".join(f"  {p}" for p in problems))
    return raw


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


INSTRUCTION_ACTION = "ANSWER создан: указание Оператора"
INSTRUCTION_STATES = ("in_dev", "review")
_ROLE_ENV_REFUSAL = ("answer отказана — вызов из окружения роли (role_env), "
                     "REVIEW 01M287TPG0HAVXS8CHBCY679WN итерация 1, "
                     "замечание R1-F1")


def _has_mandate_lines(raw: str) -> bool:
    """Есть ли в тексте хоть одна строка маркера мандата зон или тестов —
    даже с пустым или негодным списком элементов: такой файл идёт
    прежним путём мандата (SPEC 01M443BPQEA9ZMJ3R50THNB1MF, требование 1),
    где его элементы проверяет и отказывает `mandate.refusals`."""
    return any(mandate.elements(line, marker) is not None
               for line in raw.splitlines()
               for marker in (fsm_advance._ZONES_MANDATE_MARKER,
                              mandate.TEST_WEAKENING_MANDATE_MARKER))


def _instruction_text(conn, task_id: str, file_path: str) -> str | None:
    """Текст указания Оператора (SPEC 01M443BPQEA9ZMJ3R50THNB1MF,
    требования 1-3) — файл без строк мандатов в `in_dev`/`review`;
    `None` — не указание, команда идёт прежним путём под lease.

    Рубеж окружения роли — до чтения файла, как у мандатов: роль не
    выдаёт указание сама себе. Пустой файл — именованный отказ до
    коммита ANSWER."""
    state = store.get_task(conn, task_id)["state"]
    if state not in INSTRUCTION_STATES:
        return None
    if runner.in_role_environment():
        sys.exit(f"[{task_id}] {_ROLE_ENV_REFUSAL}")
    raw = _read_answer_file(task_id, file_path)
    if _has_mandate_lines(raw):
        return None
    if not raw.strip():
        sys.exit(f"[{task_id}] answer отказана — пустой файл указания "
                 f"{file_path}: ANSWER не создан")
    return raw


def cmd_answer(task_id: str, file_path: str,
              session_id: str | None = None) -> None:
    """Берёт lease задачи перед работой (SPEC T044, требование 2) — тем же
    приёмом, что и остальные мутирующие команды задачи (approve/reject/
    run/kill/workspace).

    Исключение — указание Оператора в `in_dev`/`review` (SPEC
    01M443BPQEA9ZMJ3R50THNB1MF, требование 5): lease не берётся, потому
    что его держит идущий шаг роли, а указание адресовано её СЛЕДУЮЩЕМУ
    шагу — ни состояние, ни шаг, ни lease оно не трогает, только
    добавляет ANSWER в ссылку документов.

    Префикс -> полный id (SPEC T094, требование 3, AC-3) резолвится ЗДЕСЬ,
    до lease (REVIEW T094 итерация 1, замечание 1)."""
    conn = store.db()
    task_id = store.resolve_task_id(conn, task_id)
    raw = _instruction_text(conn, task_id, file_path)
    if raw is not None:
        _commit_instruction(conn, task_id, raw)
        return
    lease.run_locked(conn, task_id, session_id,
                     lambda sid: _cmd_answer(conn, task_id, file_path))


def _commit_answer(conn, task_id: str, raw: str) -> tuple[str, str]:
    """Коммит следующего `ANSWER-n.md` с текстом `raw` в ссылку документов
    и перефиксация; (путь ANSWER, ветка-источник)."""
    fixation.stop_on_ref_drift(conn, task_id, "operator", "answer")
    branch, _foreign = artifact_source.resolve(conn, task_id)
    existing = artifact_branch.ls_tree(task_id, branch, f"tasks/{task_id}") or []
    n = _next_answer_number(existing)
    rel_answer = f"tasks/{task_id}/ANSWER-{n}.md"
    text = _answer_document(task_id, n, raw)
    commit_message = f"{task_id}: ANSWER-{n} — ответ Оператора"
    commit_sha = artifact_branch.commit_files(task_id, {rel_answer: text},
                                              commit_message)
    if not commit_sha:
        sys.exit(f"[{task_id}] {rel_answer} не закоммичен в артефактную "
                 f"ветку {branch}")
    store.record_fixation(conn, task_id)
    return rel_answer, branch


def _commit_instruction(conn, task_id: str, raw: str) -> None:
    rel_answer, branch = _commit_answer(conn, task_id, raw)
    store.journal(conn, task_id, "operator", INSTRUCTION_ACTION, rel_answer)
    print(f"[{task_id}] {rel_answer} создан и закоммичен в артефактную "
          f"ветку {branch}")
    print("  указание дойдёт до роли на её следующем шаге; идущий шаг не "
          "прерывается")


def _cmd_answer(conn, task_id: str, file_path: str) -> None:
    """Гейт состояния (SPEC 01M287TPG0HAVXS8CHBCY679WN, требование 1):
    `escalated` — прежний путь без изменений. `in_dev`/`review` —
    принимается ТОЛЬКО если текст файла несёт строку маркера
    `fsm_advance._ZONES_MANDATE_MARKER` («Расширение зон разрешено:
    ...») — состояние задачи не меняется, журнал получает отдельную
    запись с путями мандата (AC-1) — либо строку мандата тестов
    («Ослабление тестов разрешено: ...», SPEC 01M42NB9GKXNP74HAYEJ7C7CA8,
    требование 3), тогда запись называет его элементы. Файл без маркеров
    в этих состояниях сюда не доходит — это указание Оператора, его
    принимает `cmd_answer` без lease (SPEC 01M443BPQEA9ZMJ3R50THNB1MF);
    отказ ниже остаётся только гонке «состояние сменилось между
    чтением и lease». Любое другое состояние вне `escalated` — прежний
    отказ, прежнее сообщение (AC-2).

    Ветка `in_dev`/`review` отказывает ещё до чтения файла, если ТЕКУЩИЙ
    процесс сам исполняется в окружении роли (`runner.in_role_environment`)
    — рубеж, симметричный `canary._authorized_pool_payload`
    (`orchestrator/canary.py:317`): без него developer/reviewer, ведущий
    свой же активный шаг `in_dev`/`review` (где `role_cmd()` даёт процессу
    безусловный `Bash(python3:*)`), мог бы вызвать эту же команду CLI за
    «Оператора» и сам себе выдать мандат на расширение зон (REVIEW
    01M287TPG0HAVXS8CHBCY679WN итерация 1, замечание R1-F1). `escalated`
    рубеж не несёт: в этом состоянии шаг роли уже завершён, действующего
    процесса роли для задачи нет.

    Проверка строк мандатов (`_read_checked_answer_file`, SPEC
    01M3GKJBXEBHB6ZA48J7VG8Z8W, требование 2) стоит в ОБЕИХ принимающих
    ветвях состояния, сразу за чтением файла: отказать надо до коммита
    ANSWER, и в `escalated` тоже — маркер мандата законен в любом
    принимаемом состоянии, а прежде содержимое файла там не разбиралось
    вовсе."""
    t = store.get_task(conn, task_id)
    state = t["state"]
    mandate_paths: list[str] = []
    test_elements: list[str] = []
    if state == "escalated":
        raw = _read_checked_answer_file(task_id, file_path, t["branch"])
    elif state in INSTRUCTION_STATES:
        if runner.in_role_environment():
            sys.exit(f"[{task_id}] {_ROLE_ENV_REFUSAL}")
        raw = _read_checked_answer_file(task_id, file_path, t["branch"])
        mandate_paths = _zones_mandate_marker_paths(raw)
        # Мандат тестов принимается здесь тем же рубежом и той же
        # проверкой строк, что мандат зон (SPEC 01M42NB9GKXNP74HAYEJ7C7CA8,
        # требование 3): иначе уточнить его в `in_dev` можно было только
        # новой эскалацией developer — полным шагом роли.
        test_elements = _test_mandate_marker_elements(raw)
        if not mandate_paths and not test_elements:
            sys.exit(f"[{task_id}] answer доступна только для задачи в "
                     f"состоянии escalated (сейчас: {state})")
    else:
        sys.exit(f"[{task_id}] answer доступна только для задачи в "
                 f"состоянии escalated (сейчас: {state})")

    rel_answer, branch = _commit_answer(conn, task_id, raw)

    if mandate_paths or test_elements:
        kinds = []
        if mandate_paths:
            kinds.append(f"мандат на расширение зон: "
                         f"{', '.join(mandate_paths)}")
        if test_elements:
            kinds.append(f"мандат на ослабление тестов: "
                         f"{', '.join(test_elements)}")
        action = f"ANSWER создан ({'; '.join(kinds)})"
    elif state == "escalated":
        # Требование 3: ответ эскалацию НЕ снимает — её снимает `approve`,
        # и до 26.09 журнал об этом ожидании не говорил, а цикл `auto`
        # останавливался сразу после ответа.
        action = "ANSWER создан, ждёт approve"
    else:
        action = "ANSWER создан"
    store.journal(conn, task_id, "operator", action, rel_answer)
    print(f"[{task_id}] {rel_answer} создан и закоммичен в артефактную "
          f"ветку {branch}")
    if state == "escalated":
        print(f"  дальше: artel.py approve {task_id} (снятие эскалации)")


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
    """Тот же рубеж `runner.in_role_environment()`, что и ветка
    `in_dev`/`review` `_cmd_answer` выше, и по той же причине (REVIEW
    01M287TPG0HAVXS8CHBCY679WN итерация 1, замечание R1-F1) — эта команда
    несёт ту же чувствительность (мандат Оператора на расширение зоны
    задачи), доступна из тех же активных состояний роли, и должна
    отказывать симметрично."""
    if runner.in_role_environment():
        sys.exit(f"[{task_id}] zones-extend отказана — вызов из окружения "
                 f"роли (role_env), REVIEW 01M287TPG0HAVXS8CHBCY679WN "
                 f"итерация 1, замечание R1-F1")
    paths = fsm_advance._split_zone_paths(paths_arg)
    if not paths:
        sys.exit(f"[{task_id}] zones-extend: отказ — пустой список путей")

    fixation.stop_on_ref_drift(conn, task_id, "operator", "zones-extend")
    branch, _foreign = artifact_source.resolve(conn, task_id)
    existing = artifact_branch.ls_tree(task_id, branch, f"tasks/{task_id}") or []
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
    store.record_fixation(conn, task_id)
    store.journal(conn, task_id, "operator",
                  f"ANSWER создан (мандат на расширение зон: {paths_str})",
                  rel_answer)

    # AC-5/AC-6: обновление `zones_extension` — ТОЛЬКО если PLAN.md ГОЛОВЫ
    # (не worktree) уже несёт раздел «## Расширение зон» с РОВНО тем же
    # множеством путей, что переданы команде; иначе БД не трогается вовсе
    # (`_plan_zones_extension_paths` даёт `None`, когда раздела/строки
    # «Пути:» нет — тот же разбор, что уже применяет гейт зон).
    plan_text, _reason = artifact_branch.show(task_id, branch,
                                              f"tasks/{task_id}/PLAN.md")
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
        # Команда продолжения (SPEC 01M2XFSNVGWA2VX5XFEYR93Y4Z, требование
        # 6): гейт зон на этом мандате отказывает действием класса «роль
        # ещё не закончила», и `auto` сам запускает developer оформить
        # раздел — Оператору не нужен ручной `run` (инцидент 13.09).
        print("  дальше: " + cycle_hint.launch_text(
            conn, task_id, "auto", "— цикл сам запустит developer, тот "
            "оформит раздел «## Расширение зон» PLAN.md"))
