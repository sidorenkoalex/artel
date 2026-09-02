"""GitHub-адаптер целевого `forge: github`: Draft-MR-флоу задачи (SPEC
T079, требования 1-2). Первый прогон — на самой артели (target `artel`,
targets.yaml).

Операция merge (требование 3) намеренно не несёт отдельного вызова:
ANSWER-1 (вопрос 1) прямо допускает «расчёт на автоопределение GitHub по
коммиту в истории main» как валидный способ реализации — `git merge
--no-ff` (fsm.py) делает head ветки задачи предком коммита main, и
GitHub сам закрывает Draft MR с пометкой merged, обнаружив это после
push; отдельный вызов адаптера здесь добавлял бы вторую точку отказа
ровно там, где GitHub уже даёт наблюдаемый результат бесплатно.

Любой сбой этого модуля — инцидент (журнал + `alerts.raise_alert`), не
отказ перехода FSM: Draft-MR-флоу — побочный эффект входа в `in_dev`/
`merge_gate`, а не условие перехода (тот же приём, что `fsm.py::
_regenerate_and_commit_map`/`_generate_and_commit_retro`, SPEC T042/T043).
"""
from . import alerts, ci, config, gitcmd, store, targets


def _is_github_target(target_name: str) -> bool:
    try:
        return targets.target(target_name).get("forge") == "github"
    except targets.TargetsError:
        return False


def _incident(conn, task_id: str, action: str, message: str) -> None:
    store.journal(conn, task_id, "orchestrator", action, message)
    alerts.raise_alert(conn, store.task_target(conn, task_id), "incident",
                       "github_adapter", message)


def _touched_protected_paths(branch: str, base: str) -> list[str]:
    """Пути `config.PROTECTED_PATHS`, затронутые диффом `base...branch`
    (A7, требование 7, AC-16) — независимо от предупреждения, которое
    уже печатает CI-job protected-paths (не заменяет его, дополняет).

    Git не ответил на diff — пустой список (не отказ и не эскалация:
    подсветка в MR — необязательное дополнение, отсутствие ответа не
    имеет права держать заведение Draft MR)."""
    res = gitcmd.git("diff", "--name-only", f"{base}...{branch}")
    if res is None or res.returncode != 0:
        return []
    paths = [p for p in res.stdout.splitlines() if p]
    return [p for p in paths if any(p == pp or p.startswith(pp)
                                    for pp in config.PROTECTED_PATHS)]


def ensure_draft_mr(conn, task_id: str, t) -> None:
    """Draft MR ветки задачи — ровно один раз за жизненный цикл (SPEC
    T079, требование 1, AC-1): идемпотентность несёт колонка
    `tasks.draft_mr_created`, не повторный запрос к GitHub на каждый
    повторный вход в `in_dev` (после замечаний ревью или reject из
    `verifying`) — дешевле и не зависит от сети на этих визитах.

    Канареечные задачи (`tasks/T065/SPEC.md`) пропускаются: синтетический
    прогон не должен заводить настоящие MR на настоящем GitHub на каждый
    запуск `canary` — заведение вне объёма ТЗ T079 (границы SPEC,
    «Не входит», песочница/креды — вне объёма).
    """
    if t["draft_mr_created"] or t["is_canary"]:
        return
    target_name = t["target"] or config.DEFAULT_TARGET
    if not _is_github_target(target_name):
        return
    try:
        base = targets.target(target_name)["base"]
    except targets.TargetsError as exc:
        _incident(conn, task_id, "Draft MR FAILED", f"targets.yaml: {exc}")
        return

    branch = t["branch"]
    push = gitcmd.git("push", "-u", "origin", branch)
    if push is None or push.returncode != 0:
        _incident(conn, task_id, "Draft MR FAILED",
                  f"git push -u origin {branch} не удался: "
                  f"{push.stderr.strip()[:300] if push is not None else 'git не ответил'}")
        return

    title = f"{task_id}: {t['title'] or task_id}"
    create = ci.gh("pr", "create", "--draft", "--title", title,
                   "--head", branch, "--base", base, "--body",
                   f"Draft MR задачи {task_id} (заведён автоматически "
                   f"GitHub-адаптером, SPEC T079).")
    if create is None or create.returncode != 0:
        detail = ((create.stderr or create.stdout).strip()[:300]
                  if create is not None else "gh не ответил")
        _incident(conn, task_id, "Draft MR FAILED", detail)
        return

    store.update_task(conn, task_id, draft_mr_created=1)
    store.journal(conn, task_id, "orchestrator", "Draft MR заведён",
                 create.stdout.strip()[:300])

    # Подсветка защищённых путей (A7, требование 7, AC-16): комментарий
    # на MR — в дополнение к предупреждению CI-job protected-paths, не
    # взамен него. Отказ комментария — не отказ Draft MR (та уже
    # заведена): incident тем же приёмом, что и остальные сбои модуля.
    protected = _touched_protected_paths(branch, base)
    if protected:
        comment = ci.gh(
            "pr", "comment", branch, "--body",
            f"⚠️ Диф задачи {task_id} затрагивает защищённые пути: "
            f"{', '.join(protected)} (config.PROTECTED_PATHS).")
        if comment is None or comment.returncode != 0:
            detail = ((comment.stderr or comment.stdout).strip()[:300]
                      if comment is not None else "gh не ответил")
            _incident(conn, task_id, "MR protected-paths comment FAILED",
                      detail)


def ensure_head_in_origin(conn, task_id: str, branch: str) -> tuple[bool, str]:
    """Голова `branch` видна в origin — предусловие входа в `verifying`
    (`fsm_advance.py::review`) и КАЖДОГО approve `merge_gate`
    (`fsm_merge_gate.py::_cmd_approve_merge_gate`) (SPEC
    01M1GS5HZ1JXFGKVR95HEW0AEZ, требования 1-3, 7): опрос CI по sha,
    которого origin не видел, висит до потолка ожидания вместо
    содержательного ответа (тот же класс инцидента, что решает эта
    задача).

    Сверяет ТОЧНЫЙ sha (`gitcmd.remote_branch_sha` vs
    `gitcmd.branch_head_sha`), не факт присутствия имени ветки в origin
    (AC-2) — устаревший коммит там не читается как «уже опубликован».
    Совпадают — no-op, без единой записи в журнал (AC-1/AC-8: «попытки
    push нет»). Расходятся — публикует голову тем же вызовом, которым
    ветка публикуется впервые (`ensure_draft_mr` выше, `git push -u
    origin <branch>`): успех журналируется и возвращает `(True, "")`
    (AC-3/AC-8); провал журналируется и возвращает `(False, <причина>)`
    с ИМЕНОВАННЫМ текстом причины, который SPEC требует байт-в-байт
    (AC-4/AC-9) — решение о смене состояния/эскалации на этом отказе
    остаётся за вызывающим кодом, сам хелпер состояние задачи не трогает.
    """
    local = gitcmd.branch_head_sha(branch)
    remote = gitcmd.remote_branch_sha(branch)
    if local and remote == local:
        return True, ""
    push = gitcmd.git("push", "-u", "origin", branch)
    if push is None or push.returncode != 0:
        err = ((push.stderr or push.stdout).strip()[:300]
              if push is not None else "git не ответил")
        detail = f"голова ветки не в origin, push не удался: {err}"
        store.journal(conn, task_id, "orchestrator",
                      "push FAILED (голова не в origin)", detail)
        return False, detail
    store.journal(conn, task_id, "orchestrator", "push (голова не в origin)",
                 f"git push -u origin {branch}: "
                 f"{push.stdout.strip()[:300] or 'ok'}")
    return True, ""


def undraft_mr(conn, task_id: str, t) -> None:
    """Снимает Draft (SPEC T079, требование 2, AC-2) на входе в
    `merge_gate`; молчит, если Draft MR этой задачи не заводился
    (`ensure_draft_mr` не отработал, canary, forge не github)."""
    if not t["draft_mr_created"] or t["is_canary"]:
        return
    target_name = t["target"] or config.DEFAULT_TARGET
    if not _is_github_target(target_name):
        return
    branch = t["branch"]
    ready = ci.gh("pr", "ready", branch)
    if ready is None or ready.returncode != 0:
        detail = ((ready.stderr or ready.stdout).strip()[:300]
                  if ready is not None else "gh не ответил")
        _incident(conn, task_id, "MR undraft FAILED", detail)
        return
    store.journal(conn, task_id, "orchestrator", "MR снят с Draft",
                 ready.stdout.strip()[:300] or "ok")
