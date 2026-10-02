"""Коммит закрытия задачи (`done`/`killed`) — последний коммит RETRO в
ссылку документов `refs/artifacts/<id>` пульта (ADR-0021 п.3). Снимка
закрытия (коммита без родителя с деревом ветки, отдельного push в
`origin` клона target и удаления ветки) больше нет: история документов
задачи остаётся достижимой из головы ссылки, включая коммит лока планки.

Имя модуля историческое: до ADR-0021 здесь собирался снимок закрытия
(ADR-0018 п.1); исторические снимки — коммиты без родителя под тем же
именем ссылки — читаются как раньше, этот модуль их не трогает.

Коммит закрытия записывается в журнал (`CLOSING_ACTION`) — с ним `doctor`
сверяет неизменность закрытой ссылки (`closing_sha`).
"""
import os

from . import artifact_branch, gitcmd, retro, store

SNAPSHOT_REF_TMPL = "refs/artifacts/{task_id}"
RETRO_REL_TMPL = "tasks/{task_id}/RETRO.md"


def _operator_identity() -> str:
    """Идентичность закрывающего Оператора для поля `operator` RETRO
    (значение AC-13 не диктует — берётся то же, что уже читает `runner.
    git_identity` для авторства шага роли: `git config user.name`,
    иначе — системный пользователь)."""
    res = gitcmd.git("config", "--get", "user.name")
    name = res.stdout.strip() if res is not None and res.returncode == 0 else ""
    return name or os.environ.get("USER") or os.environ.get("LOGNAME") or "unknown"


def _model_identifier() -> str:
    """Идентификатор модели для поля `model` RETRO — источник вне объёма
    этой задачи (SPEC «Не входит»: пошаговые метаданные RETRO); значение
    берётся из окружения, если задано Оператором/раннером, иначе
    `"unknown"` — поле обязано СУЩЕСТВОВАТЬ (AC-13), не гадать значение."""
    return os.environ.get("ARTEL_MODEL") or os.environ.get("ANTHROPIC_MODEL") or "unknown"


def _retro_with_frontmatter(conn, task_id: str, outcome: str) -> str:
    """Ретроспектива снимка: `outcome` — ФАКТИЧЕСКИЙ исход задачи, не
    литерал (SPEC 01M3KE80RNBCY9G48E75Z14TA7, требования 1-4). У
    смерженной задачи это «Итог: done, sha …» и вечный адрес
    `refs/artifacts/<id>` (ADR-0005 п.4, ADR-0018 п.1) вместо
    контент-адресной строки `docs/retro/<id>.md`: снимок сам и есть тот
    адрес, а на `<sha>:tasks/<id>/` его читателю опираться незачем. У
    ликвидированной — прежние «Итог: killed — причина: …» и прежняя
    строка адреса, путь не меняется (требование 4).

    sha в строке «Итог: done» — `gitcmd.head_sha()` пульта на момент
    публикации, то же значение, что несёт `artel_sha` ниже: sha самого
    коммита мержа известен только внутри
    `orchestrator/fsm_merge_gate.py::_publish_merge_artifacts` (локальная
    `merge_sha`) и ни одним носителем наружу не выставлен — точный sha
    мержа смерженной задачи остаётся в `docs/retro/<id>.md` main."""
    body = (retro.build_killed(conn, task_id) if outcome == "killed"
           else retro.build_done(
               conn, task_id, gitcmd.head_sha(),
               address=SNAPSHOT_REF_TMPL.format(task_id=task_id)))
    header = (
        "---\n"
        f"operator: {_operator_identity()}\n"
        f"model: {_model_identifier()}\n"
        f"artel_sha: {gitcmd.head_sha()}\n"
        "---\n\n"
    )
    return header + body


# Действие журнала коммита закрытия: `doctor` ищет по нему sha, с которым
# сверяет голову закрытой ссылки.
CLOSING_ACTION = "коммит закрытия"


def commit_closing(conn, task_id: str, outcome: str) -> str:
    """Коммит `tasks/<id>/RETRO.md` поверх головы ссылки документов;
    строка — что вышло. `outcome` — фактическое состояние закрытой задачи
    из БД (`done`/`killed`): его называют и ретроспектива, и сообщение
    коммита.

    Ссылки локально нет (задача заведена до ADR-0021 и на новое
    устройство не переносилась, п.13) — коммит не пишется: первый коммит
    без родителя с одним RETRO.md выдал бы себя за историю документов.
    Записанный коммит фиксируется (`store.record_fixation`) — фиксация
    закрытой задачи указывает на коммит закрытия."""
    ref = artifact_branch.branch_name(task_id)
    if not artifact_branch.ref_head(task_id):
        note = f"коммит закрытия {task_id} не записан: {ref} нет локально"
        store.journal(conn, task_id, "orchestrator",
                      "коммит закрытия не записан", note)
        return note
    text = _retro_with_frontmatter(conn, task_id, outcome)
    sha = artifact_branch.commit_files(
        task_id, {RETRO_REL_TMPL.format(task_id=task_id): text},
        f"{task_id}: закрытие ({outcome}) — RETRO")
    if not sha:
        note = f"коммит закрытия {task_id} не записан: git не ответил"
        store.journal(conn, task_id, "orchestrator",
                      "коммит закрытия не записан", note)
        return note
    store.journal(conn, task_id, "orchestrator", CLOSING_ACTION,
                  f"{ref} <- {sha} ({outcome})")
    store.record_fixation(conn, task_id)
    return f"коммит закрытия {task_id}: {ref} <- {sha}"


def closing_sha(conn, task_id: str) -> str:
    """sha последнего записанного коммита закрытия задачи; пустая строка —
    записи нет (задача не закрыта или закрыта до ADR-0021: исторический
    снимок записи о коммите закрытия не несёт)."""
    for row in reversed(store.task_steps(conn, task_id)):
        if row["action"] == CLOSING_ACTION:
            _, _, rest = (row["detail"] or "").partition(" <- ")
            return rest.split(" ", 1)[0]
    return ""
