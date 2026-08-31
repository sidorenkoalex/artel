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
