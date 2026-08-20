"""Переходы автомата: advance по артефактам, approve/reject Оператора."""
import subprocess
import sys

from . import artifacts, budget, config, store


def cmd_advance(task_id: str) -> None:
    """Единственная точка движения FSM: читает статусы артефактов."""
    conn = store.db()
    t = store.get_task(conn, task_id)
    state = t["state"]
    tdir = config.TASKS / task_id

    if state == "spec_writing":
        meta = artifacts.frontmatter(tdir / "SPEC.md")
        if meta.get("status") == "ready":
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
        conn.execute("UPDATE tasks SET reviewed_iter=? WHERE id=?",
                     (iteration, task_id))
        conn.commit()

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
                conn.execute("UPDATE tasks SET review_iters=? WHERE id=?",
                             (iters, task_id))
                store.set_state(conn, task_id, "in_dev", "fsm",
                                f"замечания ревью, итерация {iters}")
        elif status == "escalate":
            store.set_state(conn, task_id, "escalated", "fsm",
                            "эскалация от ревьювера")

    elif state == "in_dev":
        # разработчик закончил: PLAN ready и ветка запушена -> в ревью
        if artifacts.frontmatter(
                tdir / "PLAN.md").get("status") in ("ready", "approved"):
            store.set_state(conn, task_id, "review", "fsm",
                            "MR готов — прогон ревьювера")
        else:
            print(f"[{task_id}] PLAN.md не ready — разработчик ещё работает")

    else:
        print(f"[{task_id}] состояние {state} двигается через approve/reject/run")


def cmd_approve(task_id: str) -> None:
    conn = store.db()
    t = store.get_task(conn, task_id)
    state = t["state"]
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
        for cmd in (["git", "checkout", "main"], ["git", "pull", "--ff-only"],
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
        conn.execute("UPDATE tasks SET escalated_from=NULL WHERE id=?", (task_id,))
        conn.commit()
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
        conn.execute("UPDATE tasks SET accept_rejects=? WHERE id=?",
                     (rejects, task_id))
        store.set_state(conn, task_id, "in_dev", "operator",
                        f"приёмка отклонена: {reason}")
