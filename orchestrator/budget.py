"""Потолок задачи: значение из SPEC, блокировка `run`, реакция после шага."""
import sqlite3
import sys

from . import config, spend, store


def spec_budget(meta: dict) -> tuple[float | None, str]:
    """Потолок из frontmatter SPEC: (сумма, причина отказа).

    Исходов три, а не два. Поля нет — (None, ""), и это не событие: задача
    работает по дефолту, как работала (требование 2). Поле есть, но взять
    его нельзя — (None, причина): аналитик что-то имел в виду, и молчать об
    этом нельзя. Иначе (сумма, "").

    Число разбирается тем же `cli_number`, что и аргумент команды `budget`:
    одно правило на оба входа в потолок, включая отсев nan/inf.

    Причин отказа две, и они разные по смыслу: «не сумма» — значение
    непонятно, «выше дефолта» — значение понятно, но применить его значило
    бы поднять потолок задачи без Оператора (инвариант 10). Сравнение —
    строгое и именно с DEFAULT_BUDGET_USD, а не с текущим потолком задачи:
    у задач из старых БД потолок $5–$10 от прежних дефолтов, и сравнение с
    ним отвергло бы у них разрешённые SPEC суммы.
    """
    if "budget_usd" not in meta:
        return None, ""
    raw = str(meta["budget_usd"]).strip()
    # YAML-кавычки вокруг числа — форма записи, а не отказ: `budget_usd: "25"`
    # аналитик пишет по привычке, и сумма от этого суммой быть не перестаёт.
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        raw = raw[1:-1].strip()
    value = spend.cli_number(raw)
    if value is None or value <= 0:
        return None, f"'{raw}' — не сумма в долларах"
    if value > config.DEFAULT_BUDGET_USD:
        return None, (f"${value:.2f} выше дефолта "
                      f"${config.DEFAULT_BUDGET_USD:.2f} — "
                      f"поднятие потолка только командой budget")
    return value, ""


def apply_spec_budget(conn, t: sqlite3.Row, meta: dict) -> None:
    """Ставит задаче потолок из SPEC — один раз и никогда поверх ручного.

    Вызывается на переходе spec_writing -> spec_gate: SPEC к этому моменту
    прочитан и признан готовым, а денег задача ещё не потратила (агент
    запускается только из in_dev и review).

    Кто задал потолок, помнит `budget_source`: с ним значение из SPEC не
    применяется ни повторно, ни поверх поднятия Оператора — в какую бы
    сторону ни шёл порядок (требование 4).

    Функция ничего не бросает и состояние не двигает: и непонятное значение,
    и значение выше дефолта — это предупреждение Оператору, а не остановка
    задачи (требование 3). Отказ и «не применён» — разные действия журнала:
    Оператор читает журнал по действию, и обе строки означают, что потолок
    остался прежним.
    """
    task_id = t["id"]
    old = t["budget_usd"] or 0.0
    value, refused = spec_budget(meta)

    if refused:
        detail = f"{refused}, остаётся потолок ${old:.2f}"
        store.journal(conn, task_id, "fsm", "бюджет из SPEC отклонён", detail)
        print(f"[{task_id}] ВНИМАНИЕ: бюджет из SPEC отклонён: {detail}")
        return
    if value is None:
        return

    source = t["budget_source"]
    if source is not None:
        why = ("уже применён" if source == config.BUDGET_SOURCE_SPEC
               else "потолок задан Оператором")
        detail = f"${value:.2f} — {why}, остаётся ${old:.2f}"
        store.journal(conn, task_id, "fsm",
                      "бюджет из SPEC не применён", detail)
        print(f"[{task_id}] бюджет из SPEC не применён: {detail}")
        return

    conn.execute(
        "UPDATE tasks SET budget_usd=?, budget_source=?, updated_at=? WHERE id=?",
        (value, config.BUDGET_SOURCE_SPEC, store.now(), task_id))
    conn.commit()
    detail = (f"${value:.2f} (прежний потолок ${old:.2f}, "
              f"дефолт ${config.DEFAULT_BUDGET_USD:.2f})")
    store.journal(conn, task_id, "fsm", "бюджет из SPEC", detail)
    print(f"[{task_id}] бюджет из SPEC: {detail}")


def budget_block(t: sqlite3.Row) -> str | None:
    """Сообщение, почему `run` не стартует по бюджету, или None.

    Потолок ≤ 0 (или NULL в БД прошлых версий) — потолка нет: иначе задача
    без бюджета эскалировалась бы на первом же шаге при нулевом расходе.
    """
    budget, spent = t["budget_usd"] or 0.0, t["spent_usd"] or 0.0
    if budget <= 0 or spent < budget:
        return None
    return (f"[{t['id']}] бюджет исчерпан: ${spent:.2f} из ${budget:.2f} — "
            f"агент не запускается.\n"
            f"  подними потолок: artel.py budget {t['id']} <usd>\n"
            f"  или закрой задачу: artel.py kill {t['id']}")


def enforce_budget(conn, task_id: str, state: str) -> bool:
    """Реакция на потолок после шага: True — задача ушла в escalated.

    Считает по свежим значениям из БД — стоимость шага туда уже прибавлена.
    """
    t = store.get_task(conn, task_id)
    budget, spent = t["budget_usd"] or 0.0, t["spent_usd"] or 0.0
    if budget <= 0:
        return False

    if spent >= budget:
        # Точка возврата (T006): шаг мог отработать успешно, и возвращать
        # задачу из escalated надо туда, где она стояла, а не в разработку.
        conn.execute("UPDATE tasks SET escalated_from=? WHERE id=?",
                     (state, task_id))
        conn.commit()
        store.set_state(conn, task_id, "escalated", "fsm",
                        f"бюджет исчерпан: ${spent:.2f} из ${budget:.2f}")
        print(f"  дальше: artel.py budget {task_id} <usd>  (или kill)")
        return True

    if spent >= budget * config.BUDGET_ALERT_RATIO:
        detail = (f"израсходовано ${spent:.2f} из ${budget:.2f} — "
                  f"больше {int(config.BUDGET_ALERT_RATIO * 100)}% бюджета")
        store.journal(conn, task_id, "fsm", "бюджет: предупреждение", detail)
        print(f"[{task_id}] ВНИМАНИЕ: {detail}")
    return False


def cmd_budget(task_id: str, raw_usd: str) -> None:
    """Меняет потолок задачи — единственный способ снять блокировку по бюджету."""
    conn = store.db()
    t = store.get_task(conn, task_id)
    new_budget = spend.cli_number(raw_usd)
    if new_budget is None or new_budget <= 0:
        sys.exit(f"budget: '{raw_usd}' — не сумма в долларах "
                 f"(пример: artel.py budget {task_id} 10)")

    old, spent = t["budget_usd"] or 0.0, t["spent_usd"] or 0.0
    # Источник «operator» ставится и здесь, и при поднятии уже поднятого:
    # решение Оператора о деньгах не перебивается значением из SPEC ни
    # после него, ни до (apply_spec_budget).
    conn.execute("UPDATE tasks SET budget_usd=?, budget_source=?, updated_at=? "
                 "WHERE id=?",
                 (new_budget, config.BUDGET_SOURCE_OPERATOR,
                  store.now(), task_id))
    conn.commit()
    store.journal(conn, task_id, "operator", "бюджет изменён",
                  f"${old:.2f} -> ${new_budget:.2f}, израсходовано ${spent:.2f}")
    print(f"[{task_id}] бюджет: ${old:.2f} -> ${new_budget:.2f} "
          f"(израсходовано ${spent:.2f})")

    if new_budget <= spent:
        print(f"  этого мало: израсходовано ${spent:.2f} — run остаётся "
              f"заблокирован")
        return
    # Задача с spent_usd >= прежнего потолка стояла заблокированной по бюджету
    # (после пересечения потолка `run` не стартует, другой эскалации взяться
    # неоткуда), и поднятие потолка эту блокировку снимает целиком: возвращаем
    # задачу в шаг, на котором её застал потолок, как это делает approve.
    if t["state"] == "escalated" and old > 0 and spent >= old:
        back = t["escalated_from"] or "in_dev"
        conn.execute("UPDATE tasks SET escalated_from=NULL WHERE id=?", (task_id,))
        conn.commit()
        store.set_state(conn, task_id, back, "operator",
                        "бюджет поднят, продолжаем")
        print(f"  дальше: artel.py run {task_id}")
