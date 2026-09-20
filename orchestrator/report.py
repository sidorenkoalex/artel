"""Команда `report`: статический HTML-срез `state.db` + метрики гейтовой
нагрузки (tasks/T092/SPEC.md) — read-only, без демона, HTTP и шага сборки,
тот же дух самодостаточности, что и утверждённый макет
`tasks/T080/mockup.html` (борд, карточка задачи, алерты, очередь гейтов).

Читает состояние и журнал ТОЛЬКО через уже существующие функции
`orchestrator/store.py` (SPEC требование 11): `all_tasks`/`task_steps` на
каждую задачу вместо одного SQL-запроса по всей таблице `steps` разом —
такой функции («весь журнал пульта одним запросом») store.py не несёт, а
заводить её эта задача не вправе («Не входит» SPEC — правки вне
report.py/artel.py). `steps.id` — сквозной autoincrement через все
задачи, так что склейка списков по задачам и сортировка по `id`
восстанавливает единую хронологию журнала без отдельного запроса.
"""
import html as html_lib
import json
import statistics
from datetime import datetime, timedelta, timezone

# `alerts` этот модуль сам больше не зовёт (алерт расхождения курса
# заводит `spend.check_rate_divergence`, SPEC 01M2ZNJX2N5SPZCAQE6EHD4EWH
# требование 6), но имя остаётся частью поверхности модуля: планка
# 01M1RGQV4DG2FX1B90W4EEETTR (AC-5) подменяет `report.alerts` шпионом и
# проверяет, что вывод отчёта не заводит алертов сам.
from . import agent_log, alerts, config, spend, store  # noqa: F401

# Гейты, где решение принимает только Оператор, независимо от политики
# `gates.yaml` (`orchestrator/gates.py` применяет её ТОЛЬКО к acceptance;
# spec_gate/merge_gate ручные безусловно) — тот же список состояний, что
# уже даёт флаг «ЖДЁТ ОПЕРАТОРА» `catalog.cmd_status`.
MANUAL_GATE_STATES = ("spec_gate", "acceptance", "merge_gate", "escalated")

# Порядок колонок борда для известных состояний FSM; состояние вне этого
# списка (опечатка фикстуры, будущий FSM) уходит в конец отсортированным,
# а не пропадает молча.
STATE_ORDER = (
    "spec_writing", "spec_gate", "tests_writing", "in_dev", "review",
    "verifying", "acceptance", "merge_gate", "escalated", "done", "killed",
)

# Действие и пара акторов журнала на переходе acceptance -> merge_gate:
# `autogate` — `fsm._maybe_autogate_acceptance`, `operator` — ручной путь
# `approve` (оба зовут `store.set_state`, которая журналирует именно этим
# действием).
GATE_TRANSITION_ACTION = "state -> merge_gate"
GATE_RATIO_ACTORS = ("autogate", "operator")
GATE_RATIO_WINDOW = 10
OPERATOR_WINDOW_DAYS = 14

# Число последних задач, для которых блок метрики «трение» (tasks/T095/
# SPEC.md, требование 3) показывает значения — «последние задачи», не
# весь корпус разом (борд и так уже показывает все задачи).
FRICTION_RECENT_TASKS = 10

# Наблюдатель роста карты кодовой базы (SPEC 01M1RGQV4DG2FX1B90W4EEETTR):
# действие журнала «карта: размер» и источник алертов `map.growth` пишет
# часть 1 (01M1RFVWV6WWTXRC5F40K61632, doctor.check_map_growth/
# fsm_postmerge) — эта задача только читает тот же формат (см. docstring
# tasks/01M1RGQV4DG2FX1B90W4EEETTR/acceptance_tests/_fixtures.py).
MAP_SIZE_ACTION = "карта: размер"
MAP_GROWTH_SOURCE = "map.growth"
# Последние N записей ряда в таблице `report` (AC-6) — тот же порядок
# величины, что и остальные окна «последние N» этого модуля выше.
MAP_SIZE_TABLE_LIMIT = 12
# Число последних задач ГЛОБАЛЬНО (не по target), по которым считается
# медиана вызовов инструментов `developer` (AC-2, требование 1) — курс
# роли в config.TOKEN_RATES один на все target, поэтому и выборка одна.
MAP_GROWTH_CALLS_TASK_WINDOW = 10
# Строка-заглушка target'а без единой записи «карта: размер» (AC-10) —
# буквальный текст SPEC, без изменений.
NO_MEASUREMENTS_TEXT = ("измерений нет: карта ни разу не регенерировалась "
                        "после мержа этой версией")


def _esc(value) -> str:
    return html_lib.escape(str(value))


def _usd(value) -> str:
    return f"${(value or 0.0):.2f}"


# Прочерк-заглушка «неизвестно» — колонка NULL, будь то задача старше
# появления `diff_bytes`/`split_assessment` или снимок, которому не
# ответил git (tasks/01M1KS8K9RXWHX2PW3ZKB0P903, требование 6, AC-12;
# ANSWER-1/ANSWER-2) — не путать с «сигналов нет» ниже, буквальным
# значением заполненной колонки, а не заглушкой отсутствия данных.
_DASH = "—"


# --------------------------------------------------------------- чтение

def _all_steps(conn, tasks: list) -> list:
    """Журнал ВСЕХ задач одним списком, в сквозной хронологии `id`."""
    steps = []
    for row in tasks:
        steps.extend(store.task_steps(conn, row["id"]))
    steps.sort(key=lambda r: r["id"])
    return steps


# ------------------------------------ наблюдатель роста карты (AC-1..AC-12)
#
# Читает журнал и алерты ТОЛЬКО через уже существующие функции store.py
# (`all_tasks`/`task_steps`/`open_alerts`/`alerts_older_than`), тем же
# приёмом, что `_all_steps` выше — зона этой задачи не включает store.py
# (SPEC frontmatter `zones`), заводить в нём новую специализированную
# выборку эта задача не вправе.

def _map_size_entries(conn, target: str) -> list:
    """Записи ряда «карта: размер» этого target, хронологически (по
    возрастанию `id` — сквозной autoincrement `steps` через все задачи).

    Каждый элемент — уже разобранный JSON `detail` записи с добавленным
    ключом `ts` (момент записи, для окна калибровки AC-7)."""
    entries = []
    for row in store.all_tasks(conn):
        if row["target"] != target:
            continue
        for s in store.task_steps(conn, row["id"]):
            if s["action"] != MAP_SIZE_ACTION:
                continue
            try:
                detail = json.loads(s["detail"])
            except (TypeError, ValueError):
                continue
            entries.append((s["id"], {**detail, "ts": s["ts"]}))
    entries.sort(key=lambda pair: pair[0])
    return [detail for _, detail in entries]


def map_size_table_rows(conn, target: str) -> list:
    """AC-6/AC-10: последние `MAP_SIZE_TABLE_LIMIT` записей ряда этого
    target, хронологически (старые из выбранных — первыми); пустой ряд —
    пустой список, без ошибки."""
    return _map_size_entries(conn, target)[-MAP_SIZE_TABLE_LIMIT:]


def _map_growth_reference_ts(conn, target: str) -> str | None:
    """Момент последнего подтверждённого (`ack_ts` не `NULL`) алерта
    `map.growth` этого target — точка отсчёта окна калибровки (AC-7); нет
    такого алерта вовсе — `None` (точка отсчёта — начало ряда).

    `store.alerts_older_than` — единственная существующая функция store.py,
    отдающая алерты НЕЗАВИСИМО от `ack` (`open_alerts` намеренно фильтрует
    только неподтверждённые) — читаем ей ВСЕ алерты пульта (`ts` фиксированной
    ширины, лексикографически растёт, дальний конец диапазона гарантированно
    старше любого реального алерта) и фильтруем этот target/source здесь."""
    all_alerts = store.alerts_older_than(conn, "9999-12-31 23:59:59Z")
    acked = [a["ack_ts"] for a in all_alerts
            if a["target"] == target and a["source"] == MAP_GROWTH_SOURCE
            and a["ack_ts"] is not None]
    return max(acked) if acked else None


def map_growth_calibration_median(conn, target: str) -> float | None:
    """AC-7: медиана окна калибровки `map.growth` этого target — тот же
    алгоритм, что `doctor.check_map_growth` части 1 (01M1RFVWV6WWTXRC5F40K
    61632): окно — первые `config.MAP_GROWTH_CALIBRATION_MERGES` записей
    ряда ПОСЛЕ точки отсчёта (`_map_growth_reference_ts`); окно ещё не
    заполнено — `None` (не 0, не медиана частичного окна).

    Ряда нет вовсе (AC-10) — короткое замыкание ДО обращения к
    `config.MAP_GROWTH_CALIBRATION_MERGES`: до мержа части 1 этой
    константы в `config.py` ещё нет вовсе (см. docstring `_fixtures.py`),
    а target без данных не обязан на неё натыкаться."""
    entries = _map_size_entries(conn, target)
    if not entries:
        return None
    reference_ts = _map_growth_reference_ts(conn, target)
    after_ref = [e for e in entries
                if reference_ts is None or e["ts"] > reference_ts]
    window_size = config.MAP_GROWTH_CALIBRATION_MERGES
    if len(after_ref) < window_size:
        return None
    window = after_ref[:window_size]
    return statistics.median(e["bytes_total"] for e in window)


def map_growth_open_alerts(conn, target: str) -> list:
    """AC-8: открытые (`ack_ts IS NULL`) алерты `map.growth` ИМЕННО этого
    target — фильтр поверх `store.open_alerts` (без нового чтения БД)."""
    return [a for a in store.open_alerts(conn)
           if a["target"] == target and a["source"] == MAP_GROWTH_SOURCE]


def _map_growth_tool_call_count(log_path) -> int:
    """Число вызовов инструментов в файле лога шага — сырой поток
    `--output-format stream-json`, одна строка потока — одно событие (тот
    же формат, что уже разбирает `agent_log._parse_stream_event`/
    `_tool_use_calls`, независимая копия здесь — зона этой задачи не
    включает `agent_log.py`, а те функции модуля приватные)."""
    count = 0
    for raw_line in log_path.read_text(encoding="utf-8",
                                       errors="replace").splitlines():
        stripped = raw_line.lstrip()
        if not stripped.startswith("{"):
            continue
        try:
            event = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict) or event.get("type") != "assistant":
            continue
        content = event.get("message", {}).get("content")
        if not isinstance(content, list):
            continue
        count += sum(1 for block in content
                    if isinstance(block, dict) and block.get("type") == "tool_use")
    return count


def _map_growth_calls_estimate(conn) -> tuple:
    """(calls, is_estimate) — AC-2/AC-3: медиана числа вызовов инструментов
    `developer` по логам последних `MAP_GROWTH_CALLS_TASK_WINDOW` задач
    ГЛОБАЛЬНО (не по target — курс роли один на все target, требование 1);
    выборка пуста (ни одной задачи с логом `developer` в окне) — фолбэк
    `config.MAP_GROWTH_CALLS_ESTIMATE`, помеченный как «оценка»."""
    tasks = store.all_tasks(conn)[-MAP_GROWTH_CALLS_TASK_WINDOW:]
    counts = []
    for row in tasks:
        if not config.LOGS.exists():
            continue
        task_calls = [_map_growth_tool_call_count(p)
                     for p in config.LOGS.glob(f"{row['id']}-developer-*.log")]
        if task_calls:
            counts.append(sum(task_calls))
    if not counts:
        return config.MAP_GROWTH_CALLS_ESTIMATE, True
    return statistics.median(counts), False


def map_growth_cost_estimate(conn, target: str) -> dict | None:
    """AC-1..AC-5: оценка «стоимость карты за шаг developer» этого target —
    только число-ориентир для вывода `report`, не читается ни FSM, ни
    алертами (AC-5: ни один вызов `alerts.*` внутри). Ряда «карта: размер»
    у target нет вовсе — `None` (AC-10, нечего оценивать)."""
    entries = _map_size_entries(conn, target)
    if not entries:
        return None
    latest = entries[-1]
    bytes_value = (latest["bytes_projection"] if "bytes_projection" in latest
                  else latest["bytes_total"])
    tokens = bytes_value // 3

    calls, is_estimate = _map_growth_calls_estimate(conn)

    rates = config.TOKEN_RATES["developer"]
    cost_usd = (tokens * calls * rates["cache_read_usd_per_token"]
               + tokens * rates["cache_creation_usd_per_token"])
    return {"tokens": tokens, "calls": calls, "cost_usd": cost_usd,
           "is_estimate": is_estimate}


# -------------------------------------------------------------- метрики

def _ratio(entries: list) -> dict | None:
    total = len(entries)
    if not total:
        return None
    autogate = sum(1 for e in entries if e["actor"] == "autogate")
    operator = total - autogate
    return {
        "total": total,
        "autogate": autogate,
        "operator": operator,
        "autogate_pct": round(autogate * 100 / total),
        "operator_pct": round(operator * 100 / total),
    }


def _gate_ratio(steps: list) -> dict:
    """Доля acceptance автогейтом/руками — вся история и последние
    `GATE_RATIO_WINDOW` записей перехода (SPEC требование 8а)."""
    entries = [s for s in steps if s["action"] == GATE_TRANSITION_ACTION
              and s["actor"] in GATE_RATIO_ACTORS]
    return {
        "history": _ratio(entries),
        "last_window": _ratio(entries[-GATE_RATIO_WINDOW:]),
    }


def _operator_journal_by_day(steps: list) -> list:
    """Число записей actor=operator по дням за последние
    `OPERATOR_WINDOW_DAYS` дней (SPEC требование 8б); возрастает по дате."""
    cutoff = (datetime.now(timezone.utc)
             - timedelta(days=OPERATOR_WINDOW_DAYS)).date()
    counts: dict = {}
    for s in steps:
        if s["actor"] != "operator":
            continue
        raw_date = (s["ts"] or "")[:10]
        try:
            day = datetime.strptime(raw_date, "%Y-%m-%d").date()
        except ValueError:
            continue
        if day < cutoff:
            continue
        counts[raw_date] = counts.get(raw_date, 0) + 1
    return sorted(counts.items())


def _cost_per_done_task(tasks: list) -> float | None:
    """$/задачу по done-задачам (SPEC требование 8в); `None` — done нет."""
    done_spend = [row["spent_usd"] or 0.0 for row in tasks
                 if row["state"] == "done"]
    if not done_spend:
        return None
    return sum(done_spend) / len(done_spend)


# --------------------------------------- калибровка курса токенов (AC-6/AC-7)
#
# `spend.charge_step` журналирует действие "agent cost KNOWN" (SPEC
# 01M1PP0VYRT55WN8GGVG66X89Y, требование 6, AC-8) с фактической ценой
# запуска ($, полная точность — `actual_usd=<repr>`, не округлённое
# отображение `cost_note`) и разбивкой usage по видам
# (`spend._tokens_by_type_text`). Разбор этого формата и математика
# сверки живут в `orchestrator/spend.py` — у писателя формата: с SPEC
# 01M2ZNJX2N5SPZCAQE6EHD4EWH (требование 6) читателей у строки KNOWN
# двое, сверка при записи шага и отчёт, и две копии расчёта разошлись бы.


def _known_cost_breakdown(detail: str) -> tuple:
    """(фактическая_цена, разбивка_по_видам) из детали «agent cost
    KNOWN» — `spend.known_cost_breakdown`, разбор переехал к писателю
    формата (SPEC 01M2ZNJX2N5SPZCAQE6EHD4EWH, требование 6). Имя
    сохранено: это адрес разбора строки KNOWN для читателя отчёта, на
    него же ссылается SPEC (требование 2)."""
    return spend.known_cost_breakdown(detail)


def token_rate_divergence(conn) -> dict:
    """{роль: {"coefficient", "steps", "since"}} — расхождение курса
    роли с фактом CLI (SPEC 01M1PP0VYRT55WN8GGVG66X89Y, требования 4-5;
    SPEC 01M2ZNJX2N5SPZCAQE6EHD4EWH, требования 6-7).

    Источник — журнал: каждая запись `spend.KNOWN_COST_JOURNAL_ACTION`
    (`spend.charge_step`) несёт фактическую цену завершённого шага (из
    `total_cost_usd` финального события потока) и разбивку usage по
    видам. Чтение журнала (`spend.known_cost_pairs`) и сам расчёт с
    алертом (`spend.check_rate_divergence`) — те же функции, которыми
    считает сверку `charge_step` в момент записи шага: одна математика
    на обе точки, не две (требование 6, AC-8).

    Считается с даты `calibrated_at` курса роли (требование 7): строки
    KNOWN старше неё записаны шагами ДРУГОЙ модели, их складывание со
    свежими и дало бы то самое расхождение, которое контур обязан
    ловить. Роль без подходящих строк — отсутствует в результате вовсе,
    не 0.0 (AC-6 прежней SPEC: «не считается расхождением по
    умолчанию»).

    Не read-only (отсюда алерт в `cmd_report`) — осознанное исключение,
    описанное в докстроке `cmd_report`.
    """
    result = {}
    for role, pairs in spend.known_cost_pairs(conn).items():
        divergence = spend.check_rate_divergence(conn, role, pairs)
        if divergence is not None:
            result[role] = divergence
    return result


def _task_step_logs(task_id: str) -> list:
    """Файлы логов шагов задачи, доступные на диске прямо сейчас.

    Роль/номер прогона в имени файла (`<id>-<role>-N.log`) здесь не
    важны — трение считается по ЗАДАЧЕ (AC-2), не по конкретной роли."""
    if not config.LOGS.exists():
        return []
    return sorted(config.LOGS.glob(f"{task_id}-*-*.log"))


def _task_journal_friction(task_id: str, steps: list) -> list:
    """Значения трения этой задачи, уже посчитанные ВЖИВУЮ и записанные
    `orchestrator/runner.py` в журнал (`agent_log.FRICTION_JOURNAL_ACTION`,
    вариант 4б SPEC требования 4-5, обоснование — tasks/T095/PLAN.md)."""
    values = []
    for row in steps:
        if (row["task_id"] != task_id
                or row["action"] != agent_log.FRICTION_JOURNAL_ACTION):
            continue
        try:
            values.append(float(row["detail"]))
        except (TypeError, ValueError):
            continue
    return values


def _task_friction(task_id: str, steps: list) -> tuple:
    """(среднее трение задачи, число учтённых шагов); `None` — нечего
    усреднять.

    Журнал — приоритетный источник (вариант 4б, `_task_journal_friction`):
    если хоть один шаг задачи успел записать своё трение туда, в дело
    идут ТОЛЬКО эти значения — персистентный `.artel/logs/*.log` того же
    шага несёт рендер-транскрипт, не сырой поток (`agent_log.
    step_friction`, докстринг; ответ Оператора 01.09, ANSWER-1.md), и
    повторный разбор файла дал бы ложный 0.0, разбавляющий честное число
    журнала. Файлы `.artel/logs/` — запасной путь ТОЛЬКО когда журнал по
    задаче пуст: у фикстур приёмочных тестов (без настоящего прогона
    шага через `runner.py`) журнальной записи нет вовсе, а лог доступен
    и несёт сырой `stream-json` напрямую — тот же наблюдаемый случай,
    что и лог, вычищенный `prune`, до которого журнал не успел появиться
    (AC-5: честный пропуск, не ошибка)."""
    journal_values = _task_journal_friction(task_id, steps)
    if journal_values:
        return sum(journal_values) / len(journal_values), len(journal_values)

    values = []
    for log_path in _task_step_logs(task_id):
        try:
            values.append(agent_log.step_friction(log_path))
        except OSError:
            continue
    if not values:
        return None, 0
    return sum(values) / len(values), len(values)


def _friction_by_task(tasks: list, steps: list) -> list:
    """[(id, среднее|None, число шагов), ...] для последних
    `FRICTION_RECENT_TASKS` задач (SPEC требование 3, AC-2)."""
    recent = tasks[-FRICTION_RECENT_TASKS:]
    return [(row["id"], *_task_friction(row["id"], steps)) for row in recent]


def _friction_trend(by_task: list) -> str:
    """Направление трения по известным (не «нет данных») значениям
    списка: сравнение среднего первой и второй половины — простейшая
    детерминированная мера направления без статистики (`median` и
    подобное — сигнатура регресс-флага, docs/roadmap.md, запрещённого
    этой задаче, «Не входит» SPEC)."""
    known = [v for _, v, _ in by_task if v is not None]
    if len(known) < 2:
        return "недостаточно данных"
    mid = len(known) // 2
    earlier = sum(known[:mid]) / mid
    later = sum(known[mid:]) / (len(known) - mid)
    if later > earlier:
        return "рост"
    if later < earlier:
        return "снижение"
    return "стабильно"


# --------------------------------------------------------------- рендер

def _tile_html(row) -> str:
    escalated = bool(row["escalated_from"]) or row["state"] == "escalated"
    escalation_line = ""
    if escalated:
        source = row["escalated_from"] or "—"
        escalation_line = (
            f'<div class="tile-field tile-escalation">'
            f'Эскалация (из {_esc(source)})</div>')
    return (
        f'<div class="tile">'
        f'<span class="tile-id">{_esc(row["id"])}</span>'
        f'<span class="tile-title">{_esc(row["title"])}</span>'
        f'<div class="tile-field">Статус: {_esc(row["state"])}</div>'
        f'<div class="tile-field">Бюджет: {_usd(row["budget_usd"])}'
        f' · Расход: {_usd(row["spent_usd"])}</div>'
        f'<div class="tile-field">Итерации ревью: {row["review_iters"]}'
        f'/{config.LIMIT_REVIEW_ITERS}</div>'
        f'{escalation_line}'
        f'</div>'
    )


def _board_html(tasks: list) -> str:
    by_state: dict = {}
    for row in tasks:
        by_state.setdefault(row["state"], []).append(row)

    ordered_states = [s for s in STATE_ORDER if s in by_state]
    ordered_states += sorted(s for s in by_state if s not in STATE_ORDER)

    columns = []
    for state in ordered_states:
        tiles_html = "".join(_tile_html(row) for row in by_state[state])
        columns.append(
            f'<div class="col">'
            f'<div class="col-head"><span class="state-tag">'
            f'{_esc(state)}</span></div>'
            f'{tiles_html}'
            f'</div>'
        )
    if not columns:
        return '<p class="empty">Задач нет.</p>'
    return '<div class="board">' + "".join(columns) + '</div>'


def _gate_queue_html(tasks: list) -> str:
    gated = [row for row in tasks if row["state"] in MANUAL_GATE_STATES]
    if not gated:
        return '<p class="empty">Очередь пуста — ни одна задача не ждёт Оператора.</p>'
    rows = "".join(
        f'<div class="gate-row">'
        f'<span class="gate-name">{_esc(row["state"])}</span>'
        f'<span class="gate-task">{_esc(row["id"])} — '
        f'«{_esc(row["title"])}»</span>'
        f'</div>'
        for row in gated
    )
    return rows


def _closed_tasks_html(tasks: list, steps: list) -> str:
    """Закрытые задачи: диф/шаги/стоимость рядом с секцией «Оценка объёма
    и деление» (tasks/01M1KS8K9RXWHX2PW3ZKB0P903, требование 6, AC-12) —
    материал для пересмотра порогов Оператором по факту, без какой-либо
    автоматической корректировки. `diff_bytes`/`split_assessment` — уже
    прочитанные полем `all_tasks`, число шагов — из уже собранного
    `steps` (`_all_steps`), ни одного нового обращения к БД."""
    done = [row for row in tasks if row["state"] == "done"]
    if not done:
        return '<p class="empty">Закрытых задач нет.</p>'
    step_counts: dict = {}
    for s in steps:
        step_counts[s["task_id"]] = step_counts.get(s["task_id"], 0) + 1
    rows = "".join(
        f'<div class="closed-row">'
        f'<span class="closed-id">{_esc(row["id"])}</span>'
        f'<span class="closed-field">Диф: '
        f'{_esc(row["diff_bytes"]) if row["diff_bytes"] is not None else _DASH}'
        f' байт</span>'
        f'<span class="closed-field">Шагов: {step_counts.get(row["id"], 0)}</span>'
        f'<span class="closed-field">Стоимость: {_usd(row["spent_usd"])}</span>'
        f'<span class="closed-field">Оценка объёма: '
        f'{_esc(row["split_assessment"]) if row["split_assessment"] is not None else _DASH}'
        f'</span>'
        f'</div>'
        for row in done
    )
    return f'<div class="closed-list">{rows}</div>'


def _alerts_html(alerts: list) -> str:
    if not alerts:
        return '<p class="empty">Незакрытых алертов нет.</p>'
    items = "".join(
        f'<li class="alert-item">'
        f'<span class="alert-kind">{_esc(a["kind"])}</span>'
        f'<span class="alert-text">{_esc(a["message"])}</span>'
        f'<span class="alert-source">source: {_esc(a["source"])}</span>'
        f'</li>'
        for a in alerts
    )
    return f'<ul class="alert-list">{items}</ul>'


def _ratio_line(label: str, ratio: dict | None) -> str:
    if ratio is None:
        return f'<div class="metric-row">{_esc(label)}: записей нет</div>'
    return (
        f'<div class="metric-row">{_esc(label)}: '
        f'autogate {ratio["autogate"]} ({ratio["autogate_pct"]}%) / '
        f'operator {ratio["operator"]} ({ratio["operator_pct"]}%) '
        f'из {ratio["total"]}</div>'
    )


def _divergence_html(divergence: dict) -> str:
    """Коэффициент расхождения курса токенов по роли (SPEC
    01M1PP0VYRT55WN8GGVG66X89Y, требование 4, AC-6) — часть панели
    метрик `report`, не отдельная команда (выбор разработчика, требование
    4 явно оставляет его на усмотрение).

    Дата калибровки и число вошедших шагов — в той же строке (SPEC
    01M2ZNJX2N5SPZCAQE6EHD4EWH, требование 7, AC-8): без них читатель не
    может сказать, по какому периоду и по скольким шагам посчитана
    цифра, а в сверку входят не все строки KNOWN роли."""
    if not divergence:
        return ('<div class="metric-row">нет завершённых шагов с известной '
                'стоимостью — коэффициент расхождения не считается</div>')
    return "".join(
        f'<div class="metric-row">{_esc(role)}: коэффициент расхождения '
        f'{value["coefficient"]:.2f} по {value["steps"]} шагам '
        f'с {_esc(value["since"])}</div>'
        for role, value in sorted(divergence.items())
    )


def _metrics_html(steps: list, tasks: list, total_spent: float,
                  total_estimate: float, divergence: dict | None = None) -> str:
    gate_ratio = _gate_ratio(steps)
    per_day = _operator_journal_by_day(steps)
    cost_per_task = _cost_per_done_task(tasks)

    per_day_html = "".join(
        f'<div class="metric-row">{_esc(day)}: operator {count}</div>'
        for day, count in per_day
    ) or '<div class="metric-row">записей actor=operator за 14 дней нет</div>'

    cost_line = (_usd(cost_per_task) if cost_per_task is not None
                else "нет done-задач")

    # Верхняя оценка (SPEC 01M1NWCM3TDY0YABEKE8DYQA1C, требование 6) —
    # отдельная строка от точного расхода, не сложена с ним в одно число
    # (иначе оценка перестала бы быть отличимой от факта, требование 6).
    return (
        '<div class="metrics">'
        '<h3>Доля acceptance: автогейт vs Оператор</h3>'
        f'{_ratio_line("за всю историю", gate_ratio["history"])}'
        f'{_ratio_line("за последние 10 задач", gate_ratio["last_window"])}'
        '<h3>Записи actor=operator по дням (последние 14 дней)</h3>'
        f'{per_day_html}'
        '<h3>Экономика</h3>'
        f'<div class="metric-row">$/задачу (done): {cost_line}</div>'
        f'<div class="metric-row">Суммарный расход программы: '
        f'{_usd(total_spent)}</div>'
        f'<div class="metric-row">Суммарная верхняя оценка (курс роли не '
        f'задан): {_usd(total_estimate)}</div>'
        '<h3>Калибровка курса токенов</h3>'
        f'{_divergence_html(divergence or {})}'
        '</div>'
    )


def _friction_html(tasks: list, steps: list) -> str:
    """Блок метрики «трение» (tasks/T095/SPEC.md, требование 3): значения
    по последним задачам и тренд. Источник — журнал `steps` (шаги,
    посчитавшие трение вживую при завершении, вариант 4б) с запасным
    путём на файлы `.artel/logs/`, доступные на диске в момент генерации
    (AC-4/AC-5, `_task_friction`) — ни то, ни другое не новая запись в
    `state.db`: только уже существующие `store.task_steps`/чтение файлов."""
    by_task = _friction_by_task(tasks, steps)
    rows_html = "".join(
        f'<div class="metric-row">{_esc(task_id)}: '
        + (f'{round(avg * 100)}% (шагов: {n})' if avg is not None
           else "трение не посчитано")
        + '</div>'
        for task_id, avg, n in by_task
    ) or '<p class="empty">Задач нет.</p>'

    return (
        '<h3>Значения по последним задачам</h3>'
        f'{rows_html}'
        '<h3>Тренд</h3>'
        f'<div class="metric-row">{_esc(_friction_trend(by_task))}</div>'
    )


def _map_size_table_html(rows: list) -> str:
    body_rows = "".join(
        '<tr>'
        f'<td>{_esc(r.get("ts", ""))}</td>'
        f'<td>{_esc(r["bytes_total"])}</td>'
        f'<td>{_esc(r["bytes_projection"]) if "bytes_projection" in r else _DASH}</td>'
        f'<td>{_esc(r["sections_total"])}</td>'
        f'<td>{_esc(r["bytes_by_dir"])}</td>'
        '</tr>'
        for r in rows
    )
    return (
        '<table class="map-size-table">'
        '<thead><tr><th>дата</th><th>bytes_total</th>'
        '<th>bytes_projection</th><th>sections_total</th>'
        '<th>bytes_by_dir</th></tr></thead>'
        f'<tbody>{body_rows}</tbody>'
        '</table>'
    )


def _map_growth_estimate_html(estimate: dict | None) -> str:
    if estimate is None:
        return ""
    suffix = " (оценка)" if estimate["is_estimate"] else ""
    return (
        '<div class="metric-row">Стоимость карты за шаг developer: '
        f'{_usd(estimate["cost_usd"])}{suffix} '
        f'(tokens={estimate["tokens"]}, calls={estimate["calls"]})</div>'
    )


def _map_growth_target_html(conn, target: str) -> str:
    """Блок одного target (AC-6..AC-10): таблица ряда, медиана калибровки,
    открытые алерты `map.growth`, денежная оценка — target без единой
    записи «карта: размер» показывает фиксированную строку вместо всего
    этого (AC-10), не обращаясь к `config.MAP_GROWTH_CALIBRATION_MERGES`
    части 1 (которой до её мержа может ещё не быть в `config.py`)."""
    rows = map_size_table_rows(conn, target)
    if not rows:
        return (
            f'<div class="map-growth-target"><h3>{_esc(target)}</h3>'
            f'<p class="empty">{_esc(NO_MEASUREMENTS_TEXT)}</p></div>'
        )
    median = map_growth_calibration_median(conn, target)
    median_line = (f'<div class="metric-row">Медиана окна калибровки: '
                  f'{_esc(median)}</div>' if median is not None else "")
    open_ = map_growth_open_alerts(conn, target)
    alerts_html = (_alerts_html(open_) if open_
                  else '<p class="empty">Открытых алертов map.growth нет.</p>')
    estimate = map_growth_cost_estimate(conn, target)
    return (
        f'<div class="map-growth-target"><h3>{_esc(target)}</h3>'
        f'{_map_size_table_html(rows)}'
        f'{median_line}'
        f'{alerts_html}'
        f'{_map_growth_estimate_html(estimate)}'
        '</div>'
    )


def _map_growth_html(conn, tasks: list) -> str:
    """Блок «Рост карты кодовой базы» — по каждому target, известному
    пульту через `store.all_tasks` (тот же источник, что и остальной
    `report.py` — борд/закрытые задачи, без `targets.yaml`)."""
    targets = sorted({row["target"] for row in tasks if row["target"]})
    if not targets:
        return '<p class="empty">Задач нет.</p>'
    return "".join(_map_growth_target_html(conn, target) for target in targets)


_STYLE = """
  :root {
    --bg: #f4f5f7; --panel: #ffffff; --border: #dde1e6; --text: #1c2530;
    --muted: #667085; --accent: #2f5fd6; --accent-soft: #e8edfc;
    font-family: -apple-system, "Segoe UI", "Helvetica Neue", Arial, sans-serif;
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--text); line-height: 1.4; }
  header.topbar { padding: 14px 24px; background: #16213e; color: #f4f5f7; }
  header.topbar h1 { font-size: 18px; margin: 0; font-weight: 600; }
  main { padding: 20px 24px 40px; display: flex; flex-direction: column; gap: 20px; }
  section.panel {
    background: var(--panel); border: 1px solid var(--border);
    border-radius: 10px; padding: 16px 18px;
  }
  section.panel > h2 { margin: 0 0 12px; font-size: 15px; font-weight: 600; }
  h3 { font-size: 13px; margin: 14px 0 6px; }
  .empty { font-size: 13px; color: var(--muted); font-style: italic; }
  ul.alert-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
  .alert-item {
    display: flex; gap: 10px; padding: 8px 10px; border-radius: 6px;
    border-left: 3px solid #b7791f; background: #fdf6ea; font-size: 13px;
  }
  .gate-row {
    display: flex; align-items: center; gap: 16px; padding: 10px 12px;
    border: 1px solid var(--border); border-radius: 8px; margin-bottom: 8px;
  }
  .gate-name {
    font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 11px;
    font-weight: 700; color: var(--accent); background: var(--accent-soft);
    border-radius: 4px; padding: 1px 6px;
  }
  .board { display: flex; gap: 12px; overflow-x: auto; padding-bottom: 6px; }
  .col {
    background: #fafbfc; border: 1px solid var(--border); border-radius: 8px;
    min-width: 168px; flex: 0 0 168px; padding: 8px;
    display: flex; flex-direction: column; gap: 8px;
  }
  .col-head { margin-bottom: 2px; }
  .state-tag {
    font-family: ui-monospace, Menlo, Consolas, monospace; font-size: 11px;
    font-weight: 700; color: #16213e;
  }
  .tile {
    background: var(--panel); border: 1px solid var(--border);
    border-radius: 6px; padding: 7px 8px; font-size: 12px;
  }
  .tile .tile-id { font-family: ui-monospace, Menlo, Consolas, monospace; font-weight: 700; }
  .tile .tile-title { display: block; margin: 2px 0 4px; color: var(--text); }
  .tile-field { color: var(--muted); font-size: 11px; }
  .tile-escalation { color: #c22b2b; font-weight: 600; }
  .metrics { font-size: 13px; }
  .metric-row { padding: 2px 0; }
  .closed-list { display: flex; flex-direction: column; gap: 6px; }
  .closed-row {
    display: flex; flex-wrap: wrap; gap: 14px; align-items: baseline;
    padding: 6px 8px; border: 1px solid var(--border); border-radius: 6px;
    font-size: 12px;
  }
  .closed-id { font-family: ui-monospace, Menlo, Consolas, monospace; font-weight: 700; }
  .closed-field { color: var(--muted); }
  .map-growth-target { margin-bottom: 16px; }
  table.map-size-table {
    border-collapse: collapse; font-size: 12px; margin: 6px 0;
  }
  table.map-size-table th, table.map-size-table td {
    border: 1px solid var(--border); padding: 4px 8px; text-align: left;
  }
  footer { padding: 0 24px 30px; font-size: 11px; color: var(--muted); }
"""


def _render(tasks: list, steps: list, alerts: list, total_spent: float,
           total_estimate: float, divergence: dict | None = None,
           map_growth_html: str = "") -> str:
    return (
        "<!DOCTYPE html>\n"
        '<html lang="ru">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        "<title>Артель — отчёт пульта</title>\n"
        f"<style>{_STYLE}</style>\n"
        "</head>\n"
        "<body>\n"
        '<header class="topbar"><h1>Артель — отчёт пульта</h1></header>\n'
        "<main>\n"
        '<section class="panel"><h2>Алерты</h2>'
        f"{_alerts_html(alerts)}</section>\n"
        '<section class="panel"><h2>Очередь ожиданий Оператора</h2>'
        f"{_gate_queue_html(tasks)}</section>\n"
        '<section class="panel"><h2>Борд задач — состояния FSM</h2>'
        f"{_board_html(tasks)}</section>\n"
        '<section class="panel"><h2>Закрытые задачи</h2>'
        f"{_closed_tasks_html(tasks, steps)}</section>\n"
        '<section class="panel"><h2>Метрики гейтовой нагрузки</h2>'
        f"{_metrics_html(steps, tasks, total_spent, total_estimate, divergence)}</section>\n"
        '<section class="panel"><h2>Метрика «трение»</h2>'
        f"{_friction_html(tasks, steps)}</section>\n"
        '<section class="panel"><h2>Рост карты кодовой базы</h2>'
        f"{map_growth_html}</section>\n"
        "</main>\n"
        "<footer>Сгенерировано командой `report` из state.db — "
        "срез на момент запуска, история прежних отчётов не хранится."
        "</footer>\n"
        "</body>\n"
        "</html>\n"
    )


def cmd_report() -> None:
    """Генерирует `.artel/report.html` из текущего состояния `state.db` и
    печатает путь к файлу (SPEC требования 1-4, AC-1). Ни одного вызова
    git (требование 9, AC-10). Перезаписывает прежний файл по тому же
    пути — без истории версий (требование 10, AC-11).

    Не полностью read-only с 01M1PP0VYRT55WN8GGVG66X89Y (требование 5):
    `token_rate_divergence` попутно поднимает алерт `kind=warning` при
    большом расхождении курса — осознанное, локализованное исключение
    из read-only дизайна tasks/T092/SPEC.md, не общее правило для
    остальной части этой команды."""
    conn = store.db()
    tasks = store.all_tasks(conn)
    steps = _all_steps(conn, tasks)
    open_alerts_ = store.open_alerts(conn)
    total_spent = store.total_spent(conn)
    total_estimate = store.total_estimate(conn)
    # Калибровка курса токенов (требование 4, AC-6) — единственное место
    # в этой команде, которое пишет в `state.db` (алерт `kind=warning` при
    # большом расхождении, `token_rate_divergence`), а не только читает:
    # исключение из read-only дизайна `report` (tasks/T092/SPEC.md,
    # требование 9) обосновано и локализовано этой же SPEC (требование 5).
    divergence = token_rate_divergence(conn)
    # Наблюдатель роста карты (SPEC 01M1RGQV4DG2FX1B90W4EEETTR, требования
    # 2-3): read-only, ни одного вызова alerts.*/store-записи внутри —
    # единственный потребитель оценки этого блока, не FSM (AC-5).
    map_growth_html = _map_growth_html(conn, tasks)

    doc = _render(tasks, steps, open_alerts_, total_spent, total_estimate,
                 divergence, map_growth_html)

    path = config.ROOT / ".artel" / "report.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(doc, encoding="utf-8")
    print(f"Отчёт сгенерирован: {path}")
