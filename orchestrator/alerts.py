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
"""
from . import store

KINDS = ("incident", "threshold", "trigger")


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
