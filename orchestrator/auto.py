"""Цикл `auto`: run+advance, пока в шаге работает агент."""
from . import agent_log, budget, config, fsm, runner, store


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


def cmd_auto(task_id: str) -> None:
    """Цикл run+advance, пока в шаге работает агент, — до места, где нужен человек.

    Механику шага команда не дублирует: внутри те же `cmd_run` и
    `cmd_advance`, которые Оператор зовёт руками, — бюджет, ретраи, журнал
    и вердикты FSM остаются целиком в них. Своё у цикла одно — условие
    выхода: работаем, пока состояние есть в STATE_ROLE, останавливаемся на
    первом же состоянии вне его. Так новое агентское состояние (MVP,
    plan_review) подхватится само, а новое ручное — само остановит.

    Решений auto не принимает: approve и reject остаются за Оператором —
    ручные гейты обходить нечем (docs/design.md §4, docs/invariants.md 18).
    """
    conn = store.db()
    state = store.get_task(conn, task_id)["state"]
    store.journal(conn, task_id, "operator", "auto старт",
                  f"состояние {state}, лимит {config.AUTO_MAX_STEPS} шагов")
    print(f"[{task_id}] auto: старт из {state}, "
          f"лимит {config.AUTO_MAX_STEPS} шагов за вызов")

    steps = 0
    while state in config.STATE_ROLE:
        if steps >= config.AUTO_MAX_STEPS:
            auto_stop(conn, task_id, state,
                      f"лимит {config.AUTO_MAX_STEPS} шагов за вызов исчерпан",
                      f"artel.py log {task_id} (что происходит), "
                      f"затем artel.py auto {task_id} — продолжит отсюда")
            return
        steps += 1
        role, before = config.STATE_ROLE[state], state

        try:
            runner.cmd_run(task_id)
        except SystemExit as exc:
            # Отказ стартовать `cmd_run` сообщает единственным способом —
            # sys.exit с текстом (исчерпанный бюджет, budget_block). В цикле
            # текст печатаем сами: пойманный SystemExit нигде не покажется.
            print(str(exc))
            auto_stop(conn, task_id, state, "run отказался стартовать",
                      f"artel.py budget {task_id} <usd> или artel.py kill {task_id}")
            return

        # Состояние перечитываем до advance: упавший агент и исчерпанный
        # потолок уводят задачу в escalated изнутри run, и advance оттуда
        # только напечатал бы, что двигать нечего.
        state = store.get_task(conn, task_id)["state"]
        if state in config.STATE_ROLE:
            fsm.cmd_advance(task_id)
            state = store.get_task(conn, task_id)["state"]
        # Живой вывод агента уже был на экране и в логе — здесь только
        # сводка шага и ссылка на лог прогона (требование 6).
        print(f"[{task_id}] auto шаг {steps}/{config.AUTO_MAX_STEPS}: {role} "
              f"{before} -> {state}, "
              f"лог: {agent_log.last_agent_log(task_id, role)}")

    reason, hint = auto_stop_advice(conn, task_id, state)
    auto_stop(conn, task_id, state, reason, hint)
