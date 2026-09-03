"""Таблица alerts: несущий носитель порогов/инцидентов/триггеров (A3,
tasks/T022/SPEC.md требование 7).

Раньше пороги программы (`budget.check_program_spend`) и recovery-сигналы
жили только в журнале шагов задачи — искать их можно было лишь через
конкретную задачу. `alerts` — их отдельная, задаче не привязанная таблица
(поле `target`, не `task_id`: несущая часть инцидентов вроде расхождения
sha репозитория target'а вообще не про одну задачу).

SQL самих операций — в store.py (ADR-0003 3ж: «единственный модуль, который
пишет SQL»); этот модуль зовёт его функции по имени.

`kind`:
- `incident` — целостность/гигиена (recovery-сверка, сироты, гряз. репо);
- `threshold` — вычислимый порог программы (roadmap §5), переведён
  с журнальных событий сюда;
- `trigger` — реестр docs/triggers.md; ack обязан нести решение
  («внедряем — задача N» либо «отложено до <граница>»), поэтому только
  для него `ack()` требует непустой `resolution`.
- `attention` — остановка `auto` не на ручном гейте и не по паузе (SPEC
  01M1KCSTBYF1CRJBSY4P6VYQEA, требование 3): цикл буксует или встал там,
  где раньше был виден только по запросу статуса Оператором. `target` —
  id задачи. Заводится `auto.auto_stop` (`raise_attention_alert`),
  закрывается автоматически на следующем успешном переходе состояния
  этой задачи, кем бы он ни был вызван (требование 4) —
  `close_attention_alerts`, зовётся из `store.set_state`, единственной
  точки любого перехода FSM.
"""
from . import store

KINDS = ("incident", "threshold", "trigger", "attention")


def raise_alert(conn, target: str | None, kind: str, source: str,
                message: str) -> bool:
    """Заводит алерт; True — заведён, False — такой же уже открыт (не дублируем).

    Дедуп — среди НЕПОДТВЕРЖДЁННЫХ алертов с тем же (target, kind, source,
    message): повторный прогон doctor/порога, пока Оператор не подтвердил
    сигнал, не плодит копию (SPEC T022, критерий 5). После `ack` то же
    условие, наступившее заново, заводит новую строку — подтверждение не
    навсегда глушит сигнал.
    """
    if kind not in KINDS:
        raise ValueError(f"alerts: kind '{kind}' — не {KINDS}")
    if store.open_alert_exists(conn, target, kind, source, message):
        return False
    store.insert_alert(conn, target, kind, source, message)
    return True


def open_alerts(conn, kind: str | None = None) -> list:
    """Неподтверждённые алерты, свежие сверху; kind — фильтр по типу."""
    return store.open_alerts(conn, kind)


def raise_attention_alert(conn, task_id: str, message: str) -> bool:
    """Заводит алерт `kind=attention` остановки `auto` (требование 3) —
    тонкая обёртка над `raise_alert`: дедуп по (target, kind, source,
    message) и решение «заведён/уже открыт» остаются его же."""
    return raise_alert(conn, task_id, "attention", "auto", message)


def close_attention_alerts(conn, task_id: str) -> None:
    """Закрывает открытые алерты `kind=attention` этой задачи (требование
    4): любой успешный переход состояния задачи закрывает буксование,
    которое он сам и разрешил. Не `auto_ack`/`ack` — оба решают ЧУЖУЮ
    задачу (doctor/Оператор соответственно, SPEC «Не входит»); здесь
    закрытие не требует решения человека, сама смена состояния и есть
    ответ на вопрос «буксует ли».
    """
    for row in open_alerts(conn, "attention"):
        if row["target"] == task_id:
            store.ack_alert(conn, row["id"], "auto",
                            "закрыт следующим переходом состояния задачи")


def auto_ack(conn, alert_id: int) -> None:
    """Ack от имени `doctor`: условие, представленное алертом, при текущем
    прогоне фактически исчезло (tasks/T035/SPEC.md, требование 6).

    Не переиспользует `ack()`: тот — ручной путь Оператора (CLI
    `alert-ack`), с его собственными правилами (`trigger` требует текст
    решения). Авто-ack — только для incident-алертов трёх сирот и
    `backup_age` (doctor.py решает, когда звать), решение всегда одно и
    то же и по построению не требует текста от человека.
    """
    resolution = f"условие ушло, прогон doctor {store.now()}"
    store.ack_alert(conn, alert_id, "doctor", resolution)


def ack(conn, alert_id: int, actor: str, resolution: str = "") -> str | None:
    """Подтверждает алерт; None — ок, иначе причина отказа (не подтверждён).

    `kind=trigger` без текста решения — отказ (docs/triggers.md: «ack
    триггера обязан нести решение»; SPEC T022, критерий 6). Для
    incident/threshold решение необязательно — это не решения программы,
    достаточно факта «Оператор видел».
    """
    row = store.get_alert(conn, alert_id)
    if row is None:
        return f"alert {alert_id} не найден"
    if row["ack_ts"] is not None:
        return f"alert {alert_id} уже подтверждён {row['ack_ts']} ({row['ack_by']})"
    if row["kind"] == "trigger" and not resolution.strip():
        return ("ack триггера обязан нести решение (docs/triggers.md: "
                "«внедряем — задача N» либо «отложено до <граница>»)")
    store.ack_alert(conn, alert_id, actor, resolution)
    return None
