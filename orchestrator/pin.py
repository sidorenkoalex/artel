"""Команда `pin-update`: обновление пина запущенной версии (A7, Stage1,
требования 5-6).

Stage0 (`orchestrator/fsm_merge_gate.py`) удерживает рабочее дерево и
HEAD `config.ROOT` от изменения переходом `merge_gate -> done` —
единственный способ продвинуть его вперёд, к текущему main артели
(её `origin`), — эта операторская команда, вне цикла FSM любой задачи.
`doctor.check_root_pin` только СООБЩАЕТ о расхождении (AC-13); сам пин
обновляет только эта команда (AC-14).
"""
import sys

from . import config, gitcmd, store


def cmd_pin_update(sha: str) -> None:
    conn = store.db()
    old_sha = gitcmd.head_sha()

    fetch = gitcmd.git("fetch", "-q", "origin", config.MAIN_BRANCH)
    if fetch is None or fetch.returncode != 0:
        sys.exit(f"pin-update: git fetch origin {config.MAIN_BRANCH} не "
                 f"удался: {fetch.stderr.strip()[:300] if fetch is not None else 'git не ответил'}")

    merge = gitcmd.git("merge", "--ff-only", sha)
    if merge is None or merge.returncode != 0:
        sys.exit(f"pin-update: git merge --ff-only {sha} не удался: "
                 f"{merge.stderr.strip()[:300] if merge is not None else 'git не ответил'}")

    new_sha = gitcmd.head_sha()
    detail = f"pin обновлён: {old_sha} -> {new_sha}"
    store.journal(conn, config.PIN_UPDATE_JOURNAL_TASK_ID, "operator",
                  "pin обновлён", detail)
    print(f"[pin-update] {detail}")
