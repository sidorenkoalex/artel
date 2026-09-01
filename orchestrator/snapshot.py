"""Снапшот артефактов задачи в `refs/artifacts/<id>` ЦЕЛЕВОГО при закрытии
(`done`/`killed`, не канарейка) — SPEC T094, требования 12-14; AC-13,
AC-14, AC-15.

Только внешний target (self/догфуд остаётся на однобраншевом флоу без
снапшота до A7, требование 16/AC-18) и только не-канареечная задача
(требование 12/AC-13) — вызывающий код (`orchestrator/cleanup.py`)
решает это ДО вызова `publish_and_cleanup`.

Правило требования 14 (AC-14): снапшот пишется ОДИНАКОВО для целевых
уровня `full` и `partial` — всегда в `refs/artifacts/<id>` РЕПОЗИТОРИЯ
ЦЕЛЕВОГО (его `origin`, тот же клон `config.PROJECTS/<target>/workspace`,
которым уже пользуется `runner.role_cwd`), никогда в
`.artel/projects/<target>/` пульта — здесь нет ни одной строки, которая
писала бы куда-то, кроме этого клона и его `origin`.
"""
import os
from pathlib import Path

from . import artifact_branch, config, fixation, gitcmd, retro, store

SNAPSHOT_REF_TMPL = "refs/artifacts/{task_id}"
RETRO_REL_TMPL = "tasks/{task_id}/RETRO.md"


def _target_workspace(target: str) -> Path:
    return config.PROJECTS / target / "workspace"


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
    body = (retro.build_killed(conn, task_id) if outcome == "killed"
           else retro.build_done(conn, task_id, gitcmd.head_sha()))
    header = (
        "---\n"
        f"operator: {_operator_identity()}\n"
        f"model: {_model_identifier()}\n"
        f"artel_sha: {gitcmd.head_sha()}\n"
        "---\n\n"
    )
    return header + body


def pending(task_id: str) -> bool:
    """True — снапшот этой задачи ещё не подтверждён в origin целевого:
    её артефактная ветка пульта всё ещё существует (AC-15). Задачи
    self/канарейки сюда не попадают — вызывающий код не заводит для них
    артефактную ветку вовсе, `snapshot_pending` для них всегда `False`."""
    return artifact_branch.snapshot_pending(task_id)


def publish_and_cleanup(conn, task_id: str, target: str, outcome: str) -> str:
    """Публикует снапшот (`tasks/<id>/` артефактной ветки + RETRO с
    frontmatter operator/model/artel_sha) в `refs/artifacts/<id>` origin
    целевого; ТОЛЬКО при подтверждённом push убирает артефактную ветку
    пульта (AC-13, AC-15). Строка — что вышло; идемпотентна — повторный
    вызов на уже опубликованном снапшоте безвреден (перезапишет тот же
    ref новым эквивалентным коммитом, ветка пульта к этому моменту уже
    убрана — `read_tree` вернёт пусто, но следующий вызов и не должен
    случаться: `cleanup`/`doctor` зовут эту функцию, только пока
    `pending(task_id)` истинно).
    """
    files = artifact_branch.read_tree(task_id)
    files[RETRO_REL_TMPL.format(task_id=task_id)] = _retro_with_frontmatter(
        conn, task_id, outcome)

    workspace = _target_workspace(target)
    workspace.mkdir(parents=True, exist_ok=True)
    if not (workspace / ".git").is_dir():
        init = gitcmd.in_repo(workspace, "init", "-q", "-b", config.MAIN_BRANCH)
        if init.returncode != 0:
            return f"снапшот {task_id} не опубликован: workspace {target} не git-репо"

    commit_sha = artifact_branch.write_commit(
        workspace, files, f"{task_id}: снапшот закрытия ({outcome})",
        fixation.FIXATION_AUTHOR_NAME, fixation.FIXATION_AUTHOR_EMAIL)
    if not commit_sha:
        return f"снапшот {task_id} не собран: git не ответил"

    ref = SNAPSHOT_REF_TMPL.format(task_id=task_id)
    push = gitcmd.in_repo(workspace, "push", "-q", "origin", f"{commit_sha}:{ref}")
    if push is None or push.returncode != 0:
        reason = push.stderr.strip()[:300] if push is not None and push.stderr else "git не ответил"
        store.journal(conn, task_id, "orchestrator",
                      "снапшот закрытия: push не удался", reason)
        return f"снапшот {task_id} не доставлен в origin {target}: {reason}"

    store.journal(conn, task_id, "orchestrator", "снапшот закрытия опубликован",
                  f"{ref} <- {commit_sha}")
    branch_note = artifact_branch.drop(task_id)
    return f"снапшот {task_id} опубликован в {ref} ({target}); {branch_note}"
