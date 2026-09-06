"""Команда `pin-update`: обновление пина запущенной версии (A7, Stage1,
требования 5-6); `pin --to` — откат пина (tasks/
01M1NGFK3N6MRMYGCC09H975V3/SPEC.md, требования 3-4, ADR-0013 ч.3).

Stage0 (`orchestrator/fsm_merge_gate.py`) удерживает рабочее дерево и
HEAD `config.ROOT` от изменения переходом `merge_gate -> done` —
единственный способ продвинуть его вперёд, к текущему main артели
(её `origin`), — эта операторская команда, вне цикла FSM любой задачи.
`doctor.check_root_pin` только СООБЩАЕТ о расхождении (AC-13); сам пин
обновляет только эта команда (AC-14).

`cmd_pin_update` (AC-1/AC-2, ANSWER-1 п.3-4): отказывает, если на
целевом sha нет зелёного прогона канарейки не старше
`config.CANARY_MAX_MERGES_SINCE_GREEN` мержей main
(`canary.merges_since_last_green_run`) — ADR-0013 требует зелёного
прогона канарейки v2 до обновления пина; проверка — ПОСЛЕ `fetch`, но
ДО `merge` (REVIEW.md итерации 1, R1-F1): `merge-base`/`rev-list`,
которыми считается возраст, нуждаются в том, чтобы целевой `sha` уже
был объектом ЛОКАЛЬНОЙ базы `config.ROOT` — обычно это как раз объект,
который ещё только принесёт `fetch` (`pin-update <sha>` продвигает пин
на sha main, ушедшего вперёд origin'а). `fetch` сам по себе HEAD не
двигает — только обновляет remote-tracking ref'ы, так что «отказ не
трогает HEAD» (ANSWER-1 п.4) верно и с гейтом после него.

`cmd_pin_to` (AC-5/AC-6/AC-7, ANSWER-1 п.5): откатывает HEAD `config.
ROOT` на явный `<sha>` (обязан быть предком текущего HEAD) либо, без
аргумента, на `main_sha` самого свежего зелёного прогона канарейки —
`git reset --hard`, БЕЗ fetch/push (main пульта на origin не трогается,
ADR-0013 ч.3). Каждый вызов — ровно одна запись журнала
(`config.PIN_UPDATE_JOURNAL_TASK_ID`), успешная или отказ.
"""
import sys

from . import canary, config, gitcmd, store


def cmd_pin_update(sha: str) -> None:
    conn = store.db()
    old_sha = gitcmd.head_sha()

    fetch = gitcmd.git("fetch", "-q", "origin", config.MAIN_BRANCH)
    if fetch is None or fetch.returncode != 0:
        sys.exit(f"pin-update: git fetch origin {config.MAIN_BRANCH} не "
                 f"удался: {fetch.stderr.strip()[:300] if fetch is not None else 'git не ответил'}")

    age = canary.merges_since_last_green_run(conn, sha)
    if age is None or age >= config.CANARY_MAX_MERGES_SINCE_GREEN:
        sys.exit(
            "pin-update: нет зелёного прогона канарейки не старше "
            f"{config.CANARY_MAX_MERGES_SINCE_GREEN} мержей main на sha "
            f"{sha[:7]} (ADR-0013) — прогони канарейку: "
            "python3 orchestrator/artel.py canary --k 1")

    merge = gitcmd.git("merge", "--ff-only", sha)
    if merge is None or merge.returncode != 0:
        sys.exit(f"pin-update: git merge --ff-only {sha} не удался: "
                 f"{merge.stderr.strip()[:300] if merge is not None else 'git не ответил'}")

    new_sha = gitcmd.head_sha()
    detail = f"pin обновлён: {old_sha} -> {new_sha}"
    store.journal(conn, config.PIN_UPDATE_JOURNAL_TASK_ID, "operator",
                  "pin обновлён", detail)
    print(f"[pin-update] {detail}")


def _refuse_rollback(conn, detail: str) -> None:
    """Отказ `pin --to` — журналируется НА КАЖДЫЙ вызов, не только успех
    (AC-7): Оператор не должен терять след неудачной попытки отката."""
    store.journal(conn, config.PIN_UPDATE_JOURNAL_TASK_ID, "operator",
                 "pin откат отклонён", detail)
    sys.exit(detail)


def cmd_pin_to(sha: str | None) -> None:
    conn = store.db()
    old_sha = gitcmd.head_sha()

    if sha is not None:
        if not gitcmd.is_ancestor(sha, old_sha):
            _refuse_rollback(
                conn, f"pin --to {sha}: sha не существует или не предок "
                f"текущего HEAD {old_sha} — main продвигается только "
                "вперёд, откат — назад по уже известной истории")
        target = sha
        reason = f"явный sha Оператора {sha}"
    else:
        latest_green = store.latest_green_canary_run(conn)
        if latest_green is None:
            _refuse_rollback(
                conn, "pin --to: в журнале нет зелёного прогона канарейки")
        target = latest_green["main_sha"]
        if target == old_sha:
            _refuse_rollback(
                conn, "pin --to: пин уже на sha последнего зелёного прогона")
        reason = ("последний зелёный прогон канарейки "
                  f"{latest_green['run_stamp']}")

    reset = gitcmd.git("reset", "--hard", target)
    if reset is None or reset.returncode != 0:
        _refuse_rollback(
            conn, f"pin --to {target}: git reset --hard не удался: "
            f"{reset.stderr.strip()[:300] if reset is not None else 'git не ответил'}")

    new_sha = gitcmd.head_sha()
    detail = f"pin откатан: {old_sha} -> {new_sha}; причина: {reason}"
    store.journal(conn, config.PIN_UPDATE_JOURNAL_TASK_ID, "operator",
                 "pin откатан", detail)
    print(f"[pin] {detail}")
