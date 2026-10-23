"""Команда `pull-main`: подтяжка main в ветку задачи на `verifying` без
возврата к роли (SPEC 01M4PMR5EVFK4KQDPWB1KEGM7V).

До команды отставшую от main ветку задачи в `verifying` подтягивали
только `reject` в `in_dev` и шагом разработчика «код не менять» (повтор
11.10). Команда зовёт тот же узел подтяжки, что переходы автомата
(`fsm._pull_main_or_escalate` → `pull.evaluate`), отправляет новую голову
в origin и оставляет задачу ждать CI этой головы: состояние не двигает,
гейт не проходит.

`fsm` импортируется ОТЛОЖЕННО, внутри функции, — тем же приёмом и по той
же причине, что в `orchestrator/ci_rerun.py`: модульный импорт замкнул бы
цикл, а имя `fsm._pull_main_or_escalate` должно читаться в момент вызова
(его подменяют тесты).
"""
import sys

from . import github_adapter, lease, pull, store

# Действие записи журнала об исходе «подтянуто» (требование 7): её читают
# тесты и Оператор — «событие подтяжки» команды есть ровно эта запись.
PULL_MAIN_ACTION = "main подтянут в ветку (pull-main)"

# Отказ журналируется ДРУГИМ действием — тот же приём, что
# `ci_rerun.CI_RERUN_REFUSED_ACTION`: отказ не должен читаться как
# состоявшаяся подтяжка.
PULL_MAIN_REFUSED_ACTION = "pull-main отклонён"

# Подстроки ответа Оператору (требования 9, 10).
PULL_MAIN_ALREADY_FRESH = "main уже в ветке"
PULL_MAIN_PUSH_FAILED = "отправка головы в origin не удалась"
PULL_MAIN_PUSH_RETRY = "опрос verifying отправит голову сам"


def cmd_pull_main(task_id: str, session_id: str | None = None) -> None:
    """`pull-main <id>` — подтяжка main в ветку задачи, стоящей в
    `verifying`.

    Префикс -> полный id резолвится до lease, как у `ci_rerun.cmd_ci_rerun`.
    Lease — без `same_host_ok` (требование 3): подтяжку меняет ветка и
    журнал, и параллельный держатель — в том числе отвязанный `auto` своей
    сессии под другим pid — не должен делать то же одновременно.
    """
    lease.run_task_command(task_id, session_id, _cmd_pull_main)


def _refuse(conn, task_id: str, text: str) -> None:
    """Именованный отказ: запись журнала + `sys.exit`, без подтяжки,
    отправки головы и сброса потолка. Не возвращается никогда."""
    store.journal(conn, task_id, "operator", PULL_MAIN_REFUSED_ACTION, text)
    sys.exit(f"[{task_id}] pull-main: отказ — {text}")


def _cmd_pull_main(conn, task_id: str) -> None:
    from . import fsm  # отложенный импорт — см. докстринг модуля

    # Требование 2: состояние — по свежему чтению ПОД lease; строка,
    # прочитанная до захвата, могла устареть за время ожидания.
    t = store.get_task(conn, task_id)
    branch = t["branch"]
    if t["state"] != "verifying":
        _refuse(conn, task_id,
                f"задача в состоянии {t['state']}, а подтяжка командой "
                f"допустима только в verifying")

    outcome = fsm._pull_main_or_escalate(conn, task_id, t, "verifying",
                                         run_plank=True, operator_pull=True)
    if outcome == "fresh":
        print(f"[{task_id}] {PULL_MAIN_ALREADY_FRESH} {branch} — подтягивать "
              f"нечего, задача ждёт CI текущей головы")
        return
    if outcome == "unavailable":
        _refuse(conn, task_id,
                f"сверка ветки {branch} с origin не состоялась (причина — "
                f"строкой выше и записью журнала «{pull.UNAVAILABLE_ACTION}»): "
                f"подтяжки не было, повтори команду, когда git ответит")
    if outcome == "refused":
        # Требование 13 (а): отказ до слияния — `git merge` не начинался,
        # причину уже записал и напечатал узел подтяжки.
        _refuse(conn, task_id,
                f"подтяжка в ветку {branch} не начата — причина отказа узла "
                f"подтяжки строкой выше и в журнале задачи")
    if outcome == "escalated":
        sys.exit(f"[{task_id}] pull-main: задача эскалирована узлом подтяжки "
                 f"— причина в журнале задачи (artel.py log {task_id})")

    # Исход «подтянуто» (требования 7-9). Канарейку origin не трогает, как
    # опрос `verifying` в `fsm_advance`.
    if t["is_canary"]:
        pushed, why = True, ""
        push_note = "канарейка — голова в origin не отправляется"
    else:
        pushed, why = github_adapter.ensure_head_in_origin(conn, task_id, branch)
        push_note = ("голова отправлена в origin" if pushed
                     else f"{PULL_MAIN_PUSH_FAILED}: {why}")
    store.journal(conn, task_id, "operator", PULL_MAIN_ACTION,
                  f"ветка {branch}; {push_note}")
    if not pushed:
        # Требование 9: CI по голове, которой нет в origin, не придёт —
        # сброс потолка дал бы задаче лишнее время ждать впустую.
        sys.exit(f"[{task_id}] pull-main: main подтянут в ветку {branch}, но "
                 f"{PULL_MAIN_PUSH_FAILED} ({why}); {PULL_MAIN_PUSH_RETRY}; "
                 f"отсчёт потолка verifying не сброшен")
    # Требование 8: отсчёт потолка `verifying` — от новой головы.
    store.update_task(conn, task_id, updated_at=store.now())
    print(f"[{task_id}] {PULL_MAIN_ACTION}: {branch}; {push_note}; отсчёт "
          f"потолка verifying начат заново — задача ждёт CI новой головы")
