"""Команда `pause`/`resume`: штатная приостановка задачи (SPEC T070).

Пауза не заводит нового состояния FSM (требование 4, AC-6) — пометка
живёт колонкой `tasks.paused`, не файлом в рабочем каталоге задачи
(требование 4, AC-7): рабочих копий несколько, БД — единственный
источник правды, той же логикой, что уже несут lease
(`orchestrator/lease.py`) и merge-lock.

Пометку проверяет только `runner._cmd_run` перед стартом агентного шага
(требование 2) — `kill` (`orchestrator/cleanup.py`), `approve`/`reject`
и `advance` (`orchestrator/fsm.py`) её не читают вовсе (требования 6-8):
они не заходят в эту точку, поэтому исполняются на приостановленной
задаче как обычно без единой правки в их модулях.

`cmd_pause`/`cmd_resume` не берут lease задачи и не проходят лимитер
параллельных задач — по тому же доводу, что и `orchestrator/
release.py::cmd_release`: они не мутируют шаг задачи, только пометку.
"""
from . import store


def is_paused(task_row) -> bool:
    """Пометка паузы задачи — из строки `tasks` БД, не из файла (AC-7)."""
    return bool(task_row["paused"])


def cmd_pause(task_id: str) -> None:
    """Ставит пометку паузы: следующий агентный шаг `run`/`auto` не
    начнётся (AC-1), уже идущий шаг не прерывается (AC-3).

    Задача, уже приостановленная, — не ошибка (требование 9, AC-12):
    понятное сообщение вместо повторной записи в БД и журнал — молчаливый
    no-op, а не вторая запись о том же факте.
    """
    conn = store.db()
    t = store.get_task(conn, task_id)
    if is_paused(t):
        print(f"[{task_id}] уже на паузе — pause ничего не делает")
        return
    store.update_task(conn, task_id, paused=1)
    store.journal(conn, task_id, "operator", "pause",
                  "задача приостановлена: следующий агентный шаг не начнётся")
    print(f"[{task_id}] приостановлена: следующий run/auto не начнёт "
          f"агентный шаг, пока не выполнишь `artel.py resume {task_id}`")


def cmd_resume(task_id: str) -> None:
    """Снимает пометку паузы (AC-4); сама шаг не запускает и `advance` не
    зовёт (AC-5).

    Задача, не бывшая на паузе, — не ошибка (требование 9, AC-13):
    понятное сообщение, без записи в журнал (нечего снимать — не новый
    факт).
    """
    conn = store.db()
    t = store.get_task(conn, task_id)
    if not is_paused(t):
        print(f"[{task_id}] не была на паузе — resume ничего не делает")
        return
    store.update_task(conn, task_id, paused=0)
    store.journal(conn, task_id, "operator", "resume", "пауза снята")
    print(f"[{task_id}] пауза снята: run/auto снова начинают агентные шаги")
