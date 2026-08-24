"""Переходы автомата: advance по артефактам, approve/reject Оператора."""
import subprocess
import sys
from pathlib import Path

from scripts import guard

from . import artifacts, budget, ci, config, fixation, store


def guard_refuses(conn, task_id: str, path: Path) -> bool:
    """Прогон guard по артефакту-условию перехода; True — переход отменён.

    Структуру артефакта проверяет код на самом переходе, а не роль по
    договорённости и не CI задним числом (SPEC T017, требование 5): задачу
    двигают статусы артефактов, значит артефакт со сломанной структурой
    двигать её не должен. Отказ — журнал, названный файл и все причины
    списком: разбирать его будет Оператор, и трейсбека ему тут не надо.
    """
    errors = guard.check(path)
    if not errors:
        return False
    store.journal(conn, task_id, "fsm", "переход отклонён guard'ом",
                  "; ".join(errors))
    print(f"[{task_id}] переход отклонён: {path.name} не проходит guard")
    for error in errors:
        print(f"  - {error}")
    print(f"  дальше: почини артефакт и повтори artel.py advance {task_id}")
    return True


def cmd_advance(task_id: str) -> None:
    """Единственная точка движения FSM: читает статусы артефактов."""
    conn = store.db()
    t = store.get_task(conn, task_id)
    state = t["state"]
    tdir = config.TASKS / task_id

    if state == "spec_writing":
        meta = artifacts.frontmatter(tdir / "SPEC.md")
        if meta.get("status") == "ready":
            if guard_refuses(conn, task_id, tdir / "SPEC.md"):
                return
            # До смены состояния: потолок задачи должен стоять уже к тому
            # моменту, когда Оператор смотрит на неё на гейте SPEC.
            budget.apply_spec_budget(conn, t, meta)
            store.set_state(conn, task_id, "spec_gate", "fsm",
                            "SPEC готов — ждёт approve")
        else:
            print(f"[{task_id}] SPEC.md ещё не ready — нечего продвигать")

    elif state == "review":
        meta = artifacts.frontmatter(tdir / "REVIEW.md")
        status = meta.get("status")
        if status not in config.REVIEW_VERDICTS:
            print(f"[{task_id}] REVIEW.md status={status} — жду вердикта")
            return
        if guard_refuses(conn, task_id, tdir / "REVIEW.md"):
            return

        iteration = artifacts.fresh_verdict_iteration(meta, t["reviewed_iter"])
        if iteration is None:
            detail = (
                f"вердикт REVIEW.md (status={status}, "
                f"iteration={meta.get('iteration', '—')}) уже учтён — "
                f"жду новый прогон ревьювера с iteration: {t['reviewed_iter'] + 1}"
            )
            store.journal(conn, task_id, "fsm", "переход отклонён", detail)
            print(f"[{task_id}] {detail}")
            print(f"  дальше: artel.py run {task_id}  (прогон ревьювера)")
            return
        store.update_task(conn, task_id, reviewed_iter=iteration)

        if status == "approved":
            store.set_state(conn, task_id, "acceptance", "fsm",
                            "ревью пройдено — приёмка Оператором "
                            "(по критериям SPEC)")
        elif status == "changes_requested":
            iters = t["review_iters"] + 1
            if iters >= config.LIMIT_REVIEW_ITERS:
                store.set_state(conn, task_id, "escalated", "fsm",
                                f"лимит ревью "
                                f"{config.LIMIT_REVIEW_ITERS} исчерпан")
            else:
                store.update_task(conn, task_id, review_iters=iters)
                store.set_state(conn, task_id, "in_dev", "fsm",
                                f"замечания ревью, итерация {iters}")
        elif status == "escalate":
            store.set_state(conn, task_id, "escalated", "fsm",
                            "эскалация от ревьювера")

    elif state == "in_dev":
        # разработчик закончил: PLAN ready и ветка запушена -> в ревью
        if artifacts.frontmatter(
                tdir / "PLAN.md").get("status") in ("ready", "approved"):
            if guard_refuses(conn, task_id, tdir / "PLAN.md"):
                return
            store.set_state(conn, task_id, "review", "fsm",
                            "MR готов — прогон ревьювера")
        else:
            print(f"[{task_id}] PLAN.md не ready — разработчик ещё работает")

    else:
        print(f"[{task_id}] состояние {state} двигается через approve/reject/run")


# Состояния, на входе в approve которых требуется подтверждённый sha
# (SPEC T021, требование 4): именно те 4 ветки, которые ниже что-то
# подтверждают, а не просто отвечают «нечего подтверждать».
APPROVE_NEEDS_SHA = ("spec_gate", "acceptance", "merge_gate", "escalated")


def confirm_fixation(conn, task_id: str, sha: str | None) -> bool:
    """True — approve может продолжить; False — сообщил и ждёт sha (не отказ).

    Живьём пересчитывает `fixation.fix()`, а не читает `tasks.fixed_sha`:
    approve обязан сверяться с ТЕКУЩИМ состоянием (ADR-0003 п.15, «сверка
    на каждом следующем гейте... = сравнение sha + чистота рабочей
    копии»), а не с тем, что было на момент прошлого перехода.

    Фиксации нет (`sha == ""` — git не ответил, песочница без
    репозитория) — сверять не с чем: approve ведёт себя как до T021
    (требование 3, критерий 3). Расхождение sha или грязная копия —
    `sys.exit`, тем же стилем, что и отказ merge по красному CI ниже.
    """
    target = store.task_target(conn, task_id)
    current, clean = fixation.fix(task_id, target)
    if not current:
        return True
    if sha is None:
        print(f"[{task_id}] approve требует sha — зафиксирован {current}")
        print(f"  повтори: artel.py approve {task_id} {current}")
        return False
    if sha != current or not clean:
        reason = (f"sha {sha} не совпадает с зафиксированным {current}"
                  if sha != current else
                  f"грязная копия артефактов при sha {current}")
        store.journal(conn, task_id, "operator", "approve отклонён", reason)
        sys.exit(f"[{task_id}] approve отклонён: {reason}")
    return True


def cmd_approve(task_id: str, sha: str | None = None) -> None:
    conn = store.db()
    t = store.get_task(conn, task_id)
    state = t["state"]
    if state in APPROVE_NEEDS_SHA and not confirm_fixation(conn, task_id, sha):
        return
    if state == "spec_gate":
        store.set_state(conn, task_id, "in_dev", "operator",
                        "гейт SPEC пройден")
        print(f"  дальше: artel.py run {task_id}  (запуск разработчика)")
    elif state == "acceptance":
        store.set_state(conn, task_id, "merge_gate", "operator",
                        "приёмка пройдена")
        print(f"  дальше: artel.py approve {task_id}  (выполнит merge)")
    elif state == "merge_gate":
        branch = t["branch"]
        # Зелёный CI — условие мержа, проверяемое кодом, а не глазами
        # Оператора (SPEC T017, требование 6). Неизвестный статус — это
        # «нельзя»: иначе сломанный или неавторизованный `gh` бесшумно
        # возвращал бы систему к «смержим, посмотрим потом».
        green, note = ci.branch_status(branch)
        store.journal(conn, task_id, "orchestrator", "статус CI ветки", note)
        if not green:
            sys.exit(f"[{task_id}] merge отклонён: {note}\n"
                     f"  задача осталась на гейте merge; почини CI ветки "
                     f"{branch} и повтори: artel.py approve {task_id}")
        print(f"[{task_id}] {note}")
        for cmd in (["git", "checkout", config.MAIN_BRANCH],
                    ["git", "pull", "--ff-only"],
                    ["git", "merge", "--no-ff", branch, "-m",
                     f"{task_id}: merge {branch}"], ["git", "push"]):
            res = subprocess.run(cmd, cwd=config.ROOT,
                                 capture_output=True, text=True)
            if res.returncode != 0:
                store.journal(conn, task_id, "orchestrator", "merge FAILED",
                              res.stderr.strip()[:500])
                sys.exit(f"merge упал на {' '.join(cmd)}:\n{res.stderr}")
        store.set_state(conn, task_id, "done", "orchestrator",
                        f"смержено: {branch}")
    elif state == "escalated":
        # Куда возвращать — знает только тот, кто эскалировал: провал агента
        # (cmd_run) пишет в escalated_from состояние своего шага, потому что
        # чинить надо этот шаг, а не начинать разработку заново. Эскалации по
        # вердикту ревьювера и по исчерпанным лимитам его не пишут и, как
        # раньше, уходят в in_dev: там работа и продолжается.
        back = t["escalated_from"] or "in_dev"
        store.update_task(conn, task_id, escalated_from=None)
        store.set_state(conn, task_id, back, "operator",
                        "эскалация разрешена, продолжаем")
        print(f"  дальше: artel.py run {task_id}")
    else:
        print(f"[{task_id}] в состоянии {state} нечего подтверждать")


def cmd_reject(task_id: str, reason: str) -> None:
    conn = store.db()
    t = store.get_task(conn, task_id)
    if t["state"] != "acceptance":
        sys.exit(f"[{task_id}] reject применим только в acceptance "
                 f"(сейчас {t['state']})")
    rejects = t["accept_rejects"] + 1
    if rejects > config.LIMIT_ACCEPT_REJECTS:
        store.set_state(conn, task_id, "escalated", "fsm",
                        f"лимит отказов приёмки исчерпан: {reason}")
    else:
        store.update_task(conn, task_id, accept_rejects=rejects)
        store.set_state(conn, task_id, "in_dev", "operator",
                        f"приёмка отклонена: {reason}")
