"""Цикл `auto`: run+advance, пока в шаге работает агент."""
from . import agent_log, budget, config, fsm, lease, pause, runner, store

# Действие журнала, которым отказ `advance` узнаётся вне зависимости от
# конкретной причины (SPEC T038, требование 1): каждая точка `cmd_advance`
# (orchestrator/fsm.py), отказывающая переходу НЕ через guard структуры
# артефакта, журналирует actor "fsm" и action, начинающийся с этой фразы.
# Guard же возвращает `True` и уводит цикл на существующую немедленную
# остановку раньше, до этой проверки (требование 3) — пересечения нет.
REFUSAL_ACTION_PREFIX = "переход отклонён"


def _advance_refusal(conn, task_id: str, journaled_before: int) -> str | None:
    """Текст `action` записи `fsm` «переход отклонён…», добавленной ИМЕННО
    этим вызовом `cmd_advance`; `None` — отказ не журналировался (агент ещё
    работает — требование 4).

    `journaled_before` — число строк журнала задачи ДО вызова: отказ
    ищется среди добавленных после него, иначе отказ прошлого шага
    засчитался бы за отказ текущего.
    """
    for row in store.task_steps(conn, task_id)[journaled_before:]:
        if row["actor"] == "fsm" and row["action"].startswith(REFUSAL_ACTION_PREFIX):
            return row["action"]
    return None


def auto_stop_advice(conn, task_id: str, state: str) -> tuple[str, str]:
    """Причина остановки и следующая команда — по факту, а не по имени состояния.

    Имя состояния не всегда называет причину: в `escalated` задача оказывается
    и после падения агента, и после пробитого потолка, а команды у этих двух
    случаев разные. Потолок спрашиваем у того же `budget_block`, которым
    отказывается стартовать `run`, — так подсказка цикла не может разойтись с
    его отказом.
    """
    reason, hint = config.AUTO_STOP.get(
        state, (f"состояние {state} циклом не обслуживается", "artel.py show {id}"))
    if state == "escalated" and budget.budget_block(
            store.get_task(conn, task_id)) is not None:
        reason, hint = config.AUTO_STOP_BUDGET
    return reason, hint.format(id=task_id)


def auto_stop(conn, task_id: str, state: str, reason: str, hint: str) -> None:
    """Остановка цикла: запись в журнал и итог Оператору (требования 2, 5)."""
    store.journal(conn, task_id, "operator", "auto остановлен",
                  f"{state}: {reason}")
    print(f"[{task_id}] auto остановлен: {reason}")
    print(f"  состояние: {state}")
    print(f"  дальше: {hint}")


def cmd_auto(task_id: str, session_id: str | None = None) -> None:
    """Цикл run+advance, пока в шаге работает агент, — до места, где нужен человек.

    Механику шага команда не дублирует: внутри те же `cmd_run` и
    `cmd_advance`, которые Оператор зовёт руками, — бюджет, ретраи, журнал
    и вердикты FSM остаются целиком в них. Своё у цикла одно — условие
    выхода: работаем, пока у шага есть агентская роль, останавливаемся на
    первом же состоянии без неё. Так новое агентское состояние (MVP,
    plan_review) подхватится само, а новое ручное — само остановит.

    Роль шага резолвит `runner.step_role`, а не прямое чтение
    `config.STATE_ROLE`: `spec_writing` — агентское состояние только при
    заведённом `tasks/<id>/TZ.md` (SPEC T025, требование 1) — условность
    зависит от конкретной задачи, а не только от имени состояния, поэтому
    статический словарь эту проверку сам провести не может.

    Решений auto не принимает: approve и reject остаются за Оператором —
    ручные гейты обходить нечем (docs/design.md §4, docs/invariants.md 18).

    Держит lease задачи один раз на весь цикл (SPEC T044, требование 2) и
    передаёт свой `session_id` во внутренние `run`/`advance` — те видят
    уже существующий lease своей же сессии и на каждом шаге его продлевают
    (требование 7), сами не отпуская (см. `orchestrator/lease.py`).
    """
    conn = store.db()
    lease.run_locked(conn, task_id, session_id,
                     lambda sid: _cmd_auto(conn, task_id, sid),
                     on_refusal="print")


def _cmd_auto(conn, task_id: str, session_id: str) -> None:
    t = store.get_task(conn, task_id)
    state = t["state"]
    store.journal(conn, task_id, "operator", "auto старт",
                  f"состояние {state}, лимит {config.AUTO_MAX_STEPS} шагов")
    print(f"[{task_id}] auto: старт из {state}, "
          f"лимит {config.AUTO_MAX_STEPS} шагов за вызов")

    steps = 0
    role = runner.step_role(t)
    # Текст отказа `advance` предыдущего шага без смены состояния; `None` —
    # предыдущий шаг не был таким отказом, или это первый шаг цикла
    # (SPEC T038, требование 1).
    prev_refusal = None
    while role is not None:
        if steps >= config.AUTO_MAX_STEPS:
            auto_stop(conn, task_id, state,
                      f"лимит {config.AUTO_MAX_STEPS} шагов за вызов исчерпан",
                      f"artel.py log {task_id} (что происходит), "
                      f"затем artel.py auto {task_id} — продолжит отсюда")
            return
        steps += 1
        before = state

        try:
            runner.cmd_run(task_id, session_id=session_id)
        except SystemExit as exc:
            # Отказ стартовать `cmd_run` сообщает единственным способом —
            # sys.exit с текстом (исчерпанный бюджет, лимит параллельных
            # задач, штатная пауза). В цикле текст печатаем сами: пойманный
            # SystemExit нигде не покажется.
            print(str(exc))
            # Пауза (SPEC T070, требование 2) — не «эскалация по бюджету»:
            # причина должна быть видна Оператору в итоговом сообщении, а
            # не потеряться среди прочих отказов `run`, иначе цикл
            # останавливается верно, но молча про настоящую причину (тот
            # же приём различения, что и `auto_stop_advice` для бюджета
            # внутри `escalated`).
            if pause.is_paused(store.get_task(conn, task_id)):
                reason, hint = config.AUTO_STOP_PAUSE
                auto_stop(conn, task_id, state, reason, hint.format(id=task_id))
                return
            auto_stop(conn, task_id, state, "run отказался стартовать",
                      f"artel.py budget {task_id} <usd> или artel.py kill {task_id}")
            return

        # Состояние перечитываем до advance: упавший агент и исчерпанный
        # потолок уводят задачу в escalated изнутри run, и advance оттуда
        # только напечатал бы, что двигать нечего.
        t = store.get_task(conn, task_id)
        state = t["state"]
        refusal = None
        if runner.step_role(t) is not None:
            journaled_before = len(store.task_steps(conn, task_id))
            if fsm.cmd_advance(task_id, session_id=session_id):
                # guard отклонил артефакт-условие (требование 2): тот же
                # по характеру стоп, что и штатный отказ guard'а вне
                # цикла — цикл не зовёт cmd_run заново для того же
                # состояния, а останавливается на нём. Подсказка входит
                # и в reason (значит, и в журнал), не только в hint
                # (только на экран) — та же по смыслу подсказка, что и у
                # отказа guard'а вне цикла, должна быть видна и в журнале.
                hint = f"почини артефакт и повтори artel.py advance {task_id}"
                auto_stop(conn, task_id, state,
                          f"advance отклонён guard'ом артефакта-условия — "
                          f"{hint}", hint)
                return
            refusal = _advance_refusal(conn, task_id, journaled_before)
            t = store.get_task(conn, task_id)
            state = t["state"]
        # Живой вывод агента уже был на экране и в логе — здесь только
        # сводка шага и ссылка на лог прогона (требование 6).
        print(f"[{task_id}] auto шаг {steps}/{config.AUTO_MAX_STEPS}: {role} "
              f"{before} -> {state}, "
              f"лог: {agent_log.last_agent_log(task_id, role)}")
        if state == before and refusal is not None and refusal == prev_refusal:
            # Требование 1 (инцидент T035): два подряд шага без смены
            # состояния, и на обоих advance отказал тем же текстом —
            # причина отказа вне зоны агента, прогон агента её не лечит.
            hint = f"почини причину и повтори artel.py advance {task_id}"
            auto_stop(conn, task_id, state, f"{refusal} — {hint}", hint)
            return
        # Шаг без журналируемого отказа (агент ещё работает, требование 4)
        # рвёт серию — не даёт двум ОДИНАКОВЫМ, но не идущим подряд отказам
        # склеиться через него в ложную остановку.
        prev_refusal = refusal if state == before else None
        role = runner.step_role(t)

    reason, hint = auto_stop_advice(conn, task_id, state)
    auto_stop(conn, task_id, state, reason, hint)
