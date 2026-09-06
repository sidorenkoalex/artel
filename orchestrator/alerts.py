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
  сюда же — стоп-кран волны (01M1THKPNZ11DBZAQDMJ33EMJR, требование 3):
  `WAVE_BREAKER_TASKS` РАЗНЫХ задач target self отказали ОДНИМ классом
  (`failure_classification.TRANSIENT_SYSTEM_CLASSES` плюс «таймаут
  шага») в пределах `WAVE_BREAKER_WINDOW_SEC` — `target=config.
  DEFAULT_TARGET`, `source=WAVE_BREAKER_SOURCE`. Заводится
  `check_wave_breaker_failure`/`check_wave_breaker_timeout`, зовущимися
  из ДВУХ точек `orchestrator/runner.py`, уже журналирующих
  классифицированный отказ и таймаут шага в `steps` — счётчик читает
  ТОЛЬКО этот журнал (не открытые алерты: сторож зависших прогонов
  тестов, `doctor.check_hung_test_runs`, заводит `kind=incident` своим,
  не пересекающимся источником и в счётчик не входит, требование 4).
  Дедуп — по (target, kind, source, класс), не по буквальному тексту
  сообщения (число задач и минуты меняются от срабатывания к
  срабатыванию) — тем же приёмом, что `raise_token_rate_divergence_alert`
  ниже.
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
- `warning` — расхождение расчёта с фактом, не требующее остановки
  конвейера (SPEC 01M1PP0VYRT55WN8GGVG66X89Y, требование 5): курс роли
  (`config.TOKEN_RATES`) разошёлся с фактической ценой CLI сильнее
  порога `config.TOKEN_RATE_DIVERGENCE_ALERT_THRESHOLD`. `target` —
  `None`: расхождение считается по роли поперёк всех задач и target'ов,
  не про одну задачу. Заводится `report.token_rate_divergence` через
  `raise_token_rate_divergence_alert` — НЕ через `raise_alert` напрямую:
  сообщение несёт растущие суммы/счётчики, поэтому дедуп по точному
  тексту `message` (см. докстрок `raise_alert` выше) для этого алерта не
  работает — дедуп здесь по роли, не по тексту (REVIEW.md
  01M1PP0VYRT55WN8GGVG66X89Y итерации 1, R1-F2). Дедуп по точному
  `message` пригоден только для алертов «по шагу/задаче» (текст
  естественно идентичен при повторе того же отказа) — для алертов-
  АГРЕГАТОВ, чей текст меняется между прогонами, нужен отдельный ключ
  дедупа, как здесь.
- `warning` — сигнал деградации, не блокирующий переход (tasks/
  01M1P9RJVYHTAC087J4B2CAR44, требование 3): ревью-пакет итерации > 1 не
  собрал diff («diff не собран») — раньше тихая строка журнала, теперь
  видна Оператору без подъёма лога шага. `target` — id задачи. Заводится
  `runner.cmd_run` (`raise_diff_not_collected_alert`), закрывается сам,
  когда следующий сбор пакета той же задачи снова несёт diff
  (`close_diff_not_collected_alerts`) — тем же приёмом авто-ack, что
  `attention`, но без привязки к переходу FSM: подтверждение наступает
  уже на следующем СБОРЕ ПАКЕТА, не на смене состояния задачи.
"""
from datetime import datetime, timedelta, timezone

from . import config, store

KINDS = ("incident", "threshold", "trigger", "attention", "warning")

DIFF_NOT_COLLECTED_SOURCE = "review-diff"

TOKEN_RATE_DIVERGENCE_SOURCE = "report.token_rate_divergence"

# Стоп-кран волны, часть 1 (01M1THKPNZ11DBZAQDMJ33EMJR, требования 2-3).
WAVE_BREAKER_SOURCE = "wave_breaker"
# Действия журнала `steps`, ровно те же строки, что журналируют две точки
# вызова требования 3 (`failure_classification._record_failure_
# classification` и `orchestrator/runner.py:855`) — счётчик не изобретает
# собственный формат события, а читает уже существующий.
WAVE_BREAKER_FAILURE_ACTION = "agent failure classified"
WAVE_BREAKER_TIMEOUT_ACTION = "agent run TIMEOUT"
# Метка класса «таймаут шага» в тексте алерта (требование 2): у него нет
# записи в `failure_classification.CLASS_LABELS` — это не отказ попытки
# агента, а обрыв самого шага по времени, отдельная точка журнала.
WAVE_BREAKER_TIMEOUT_LABEL = "класс «таймаут шага»"


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


def raise_diff_not_collected_alert(conn, task_id: str, reason: str) -> bool:
    """Заводит `kind=warning` на «diff не собран» ревью-пакета итерации > 1
    (tasks/01M1P9RJVYHTAC087J4B2CAR44, требование 3) — тонкая обёртка над
    `raise_alert`: дедуп (target, kind, source, message) и решение
    «заведён/уже открыт» остаются его же."""
    message = f"{task_id}: ревью-пакет — diff не собран: {reason}"
    return raise_alert(conn, task_id, "warning", DIFF_NOT_COLLECTED_SOURCE, message)


def close_diff_not_collected_alerts(conn, task_id: str) -> None:
    """Авто-подтверждает открытые `kind=warning` «diff не собран» этой
    задачи (требование 3): следующий сбор ревью-пакета снова несёт diff —
    условие, которое алерт представлял, ушло. Тот же приём, что
    `close_attention_alerts`, но зовётся не переходом FSM, а самим
    `runner.cmd_run` на успешном сборе пакета."""
    for row in open_alerts(conn, "warning"):
        if row["target"] == task_id and row["source"] == DIFF_NOT_COLLECTED_SOURCE:
            store.ack_alert(conn, row["id"], "auto",
                            "diff следующего сбора пакета собран")


def raise_token_rate_divergence_alert(conn, role: str, message: str) -> bool:
    """Заводит `kind=warning` расхождения курса токенов роли `role`; True —
    заведён, False — по этой роли уже открыт такой алерт.

    Не тонкая обёртка над `raise_alert` (в отличие от
    `raise_diff_not_collected_alert`): дедуп там — по точному совпадению
    `message`, а `message` здесь несёт коэффициент/суммы, которые растут
    с каждым новым «agent cost KNOWN» шагом этой роли — почти НИКОГДА не
    совпадают между двумя прогонами `report.token_rate_divergence`
    (REVIEW.md итерации 1, R1-F2: два последовательных прогона заводили
    два разных открытых алерта вместо одного устойчивого сигнала).
    Дедуп здесь — по (`target=None`, `kind=warning`, `source`, роль),
    роль читается из префикса `message` (`_role_prefix`) без изменения
    его текста, назначенного вызывающим для чтения Оператором."""
    prefix = _role_prefix(role)
    for row in open_alerts(conn, "warning"):
        if (row["target"] is None and row["source"] == TOKEN_RATE_DIVERGENCE_SOURCE
                and row["message"].startswith(prefix)):
            return False
    return raise_alert(conn, None, "warning", TOKEN_RATE_DIVERGENCE_SOURCE, message)


def _role_prefix(role: str) -> str:
    return f"{role}: "


def _wave_breaker_task_count(conn, action: str, detail_contains: str | None) -> int:
    """Число РАЗНЫХ задач target self с записью журнала `steps.action=
    action` (и, если задан, `detail_contains` подстрокой `detail`) не
    старше `config.WAVE_BREAKER_WINDOW_SEC` (01M1THKPNZ11DBZAQDMJ33EMJR,
    требования 2, 5): `set` схлопывает несколько отказов ОДНОЙ и той же
    задачи в одну запись (требование/AC-5) — считаются задачи, не строки
    журнала.

    Читает `store.all_tasks`/`store.task_steps` (обе уже возвращают
    готовые строки) вместо нового SQL-запроса здесь: SQL живёт только в
    `store.py` (ADR-0003 3ж), а `store.py` вне зон этой задачи."""
    cutoff = datetime.now(timezone.utc) - timedelta(
        seconds=config.WAVE_BREAKER_WINDOW_SEC)
    task_ids = set()
    for t in store.all_tasks(conn):
        if (t["target"] or config.DEFAULT_TARGET) != config.DEFAULT_TARGET:
            continue
        for row in store.task_steps(conn, t["id"]):
            if row["action"] != action:
                continue
            if (detail_contains is not None
                    and detail_contains not in (row["detail"] or "")):
                continue
            ts = _parse_step_ts(row["ts"])
            if ts is not None and ts >= cutoff:
                task_ids.add(t["id"])
                break
    return len(task_ids)


def _parse_step_ts(ts: str) -> datetime | None:
    try:
        return datetime.strptime(ts, "%Y-%m-%d %H:%M:%SZ").replace(
            tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _raise_wave_breaker_alert(conn, class_label: str, task_count: int) -> bool:
    """Заводит `kind=incident` стоп-крана волны для `class_label`, если
    для него ещё нет открытого (требование 3, AC-8): дедуп по префиксу
    сообщения (target+kind+source+класс), не по буквальному тексту — число
    задач и минуты меняются от срабатывания к срабатыванию, тот же приём,
    что `raise_token_rate_divergence_alert` выше."""
    window_min = config.WAVE_BREAKER_WINDOW_SEC // 60
    prefix = f"стоп-кран волны: {class_label} у "
    message = f"{prefix}{task_count} задач за {window_min} минут"
    for row in open_alerts(conn, "incident"):
        if (row["target"] == config.DEFAULT_TARGET
                and row["source"] == WAVE_BREAKER_SOURCE
                and row["message"].startswith(prefix)):
            return False
    return raise_alert(conn, config.DEFAULT_TARGET, "incident",
                       WAVE_BREAKER_SOURCE, message)


def check_wave_breaker_failure(conn, failure_class: str | None) -> bool:
    """Стоп-кран волны для попытки, классифицированной
    `failure_classification._record_failure_classification` (требования
    2-3): считает только классы `TRANSIENT_SYSTEM_CLASSES` (1а/1б/
    системный кандидат) — «обрыв потока»/session_limit уже несут
    собственные алерты (`_record_failure_classification`) и волной не
    считаются. `failure_class=None` (текст попытки не распознан) —
    не в счётчике, `False` сразу.

    Отложенный импорт (тот же приём, что `store._close_attention_alert`):
    `failure_classification` сама читает `alerts` — прямой импорт на
    уровне модуля дал бы цикл."""
    from . import failure_classification
    if failure_class not in failure_classification.TRANSIENT_SYSTEM_CLASSES:
        return False
    class_label = failure_classification.CLASS_LABELS[failure_class]
    count = _wave_breaker_task_count(conn, WAVE_BREAKER_FAILURE_ACTION, class_label)
    if count < config.WAVE_BREAKER_TASKS:
        return False
    return _raise_wave_breaker_alert(conn, class_label, count)


def check_wave_breaker_timeout(conn) -> bool:
    """Стоп-кран волны для класса «таймаут шага» (требования 2, 6):
    действует наравне с `TRANSIENT_SYSTEM_CLASSES`, но читает журнал
    `WAVE_BREAKER_TIMEOUT_ACTION` — таймаут шага журналируется до
    классификации (нет текста попытки, которым занимался бы
    `failure_classification`)."""
    count = _wave_breaker_task_count(conn, WAVE_BREAKER_TIMEOUT_ACTION, None)
    if count < config.WAVE_BREAKER_TASKS:
        return False
    return _raise_wave_breaker_alert(conn, WAVE_BREAKER_TIMEOUT_LABEL, count)


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
