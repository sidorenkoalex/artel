"""Команда `report`: статический HTML-срез `state.db` + метрики гейтовой
нагрузки (tasks/T092/SPEC.md) — read-only, без демона, HTTP и шага сборки,
тот же дух самодостаточности, что и утверждённый макет
`tasks/T080/mockup.html` (борд, карточка задачи, алерты, очередь гейтов).

Читает состояние и журнал ТОЛЬКО через функции `orchestrator/store.py`
(SPEC требование 11). Журнал — ОДНОЙ выборкой `store.all_steps` (SPEC
01M3GKJFN90ATK2KECNDZXPPP6, требование 3): до неё отчёт звал
`store.task_steps` на каждую задачу, и число запросов к `steps` росло с
числом задач — на 268 задачах и 38 тысячах записей это и был основной
вклад в профиль чтения БД (находка ревизии CR-2026-09-26-2). `steps.id` —
сквозной autoincrement через все задачи, так что одна выборка `ORDER BY
id` и есть единая хронология журнала.
"""
import html as html_lib
import json
import re
import statistics
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

# `alerts` этот модуль сам больше не зовёт (алерт расхождения курса
# заводит `spend.check_rate_divergence`, SPEC 01M2ZNJX2N5SPZCAQE6EHD4EWH
# требование 6), но имя обязано остаться атрибутом модуля: планка
# 01M1RGQV4DG2FX1B90W4EEETTR (AC-5) наводит на `report.alerts` шпиона
# (`mock.patch.object`) вокруг вызова `map_growth_cost_estimate` и
# проверяет, что ОЦЕНКА РОСТА КАРТЫ алертов не заводит; без атрибута
# такая подмена падает с `AttributeError`. Про отчёт целиком планка
# этого не спрашивает — и не могла бы: `token_rate_divergence` ниже
# алерты на пути `cmd_report` как раз заводит (см. её докстроку).
from . import agent_log, alerts, config, explore_metric, retro, rounds, spend, store, targets  # noqa: F401
from . import fsm
from .advance_gates import test_integrity, two_sided
from .providers import base as provider_base
from .providers import claude as claude_provider

# Гейты, где решение принимает только Оператор, независимо от политики
# `gates.yaml` (`orchestrator/gates.py` применяет её ТОЛЬКО к acceptance;
# spec_gate/merge_gate ручные безусловно) — тот же список состояний, что
# уже даёт флаг «ЖДЁТ ОПЕРАТОРА» `catalog.cmd_status`.
MANUAL_GATE_STATES = ("spec_gate", "acceptance", "merge_gate", "escalated")

# Порядок колонок борда для известных состояний FSM; состояние вне этого
# списка (опечатка фикстуры, будущий FSM) уходит в конец отсортированным,
# а не пропадает молча. Сам список — `fsm.STATES` (SPEC
# 01M5TB6VDVV6AM8DWPGVQE8CDW, требование 11), имя остаётся для читателей.
STATE_ORDER = fsm.STATES

# Действие и пара акторов журнала на переходе acceptance -> merge_gate:
# `autogate` — `fsm._maybe_autogate_acceptance`, `operator` — ручной путь
# `approve` (оба зовут `store.set_state`, которая журналирует именно этим
# действием).
GATE_TRANSITION_ACTION = "state -> merge_gate"
GATE_RATIO_ACTORS = ("autogate", "operator")
GATE_RATIO_WINDOW = 10
OPERATOR_WINDOW_DAYS = 14
# Окно блока «Разведка ролей» — своё, равное окну команды `explore-stats`
# по умолчанию: на тех же данных блок и команда дают те же числа (SPEC
# 01M4RZAYH3SWJW4WFBW4QW15FP, требование 8).
EXPLORE_WINDOW_DAYS = explore_metric.DEFAULT_DAYS

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
# медиана вызовов инструментов `developer` (AC-2, требование 1) — тариф
# модели один на все target, поэтому и выборка одна.
MAP_GROWTH_CALLS_TASK_WINDOW = 10
# Строка-заглушка target'а без единой записи «карта: размер» (AC-10) —
# буквальный текст SPEC, без изменений.
NO_MEASUREMENTS_TEXT = ("измерений нет: карта ни разу не регенерировалась "
                        "после мержа этой версией")

# Замер расхода test_author (SPEC 01M4NZ5W9ZTKGTW7DGZQGMP2GP, требование
# 10) — только чтение журнала шага, лога шага и файлов на диске. Лог шага —
# рендер провайдера: строка вызова `· <Инструмент> <аргумент>`, аргумент
# обрезан до `TOOL_ARGUMENT_LIMIT`; видимый аргумент такой длины мог быть
# обрезан — его полного пути нет, файлы и строки по нему «н/д».
TEST_AUTHOR_ROLE = "test_author"
STEP_STARTED_ACTION = "agent run started"
NOT_AVAILABLE = "н/д"
_LOG_PATH_RE = re.compile(r"лог: (.+?), промпт: ")
_PROVIDER_RE = re.compile(r"provider=([\w-]+)")
_PYTEST_SECONDS_RE = re.compile(r" in (\d+(?:\.\d+)?)s\b")
# Группы Write по видимому префиксу пути: `acceptance_tests/` может быть
# виден лишь как `…/acceptance` (обрезка), `tests/` — отдельным сегментом,
# иначе `acceptance_tests/` попал бы и сюда. Порядок — проверки. Слева от
# сегмента допустимо и «:» — короткая форма пути `wt:tests/…`,
# `docs:acceptance_tests/…` (`base.short_log_path`, задача
# 01M4RZB9287PXZ4Y7ZJG7HDR6Y).
WRITE_GROUPS = (("acceptance_tests/", re.compile(r"(?:^|[/:])acceptance")),
                ("tests/", re.compile(r"(?:^|[/:])tests/")))
# Короткая форма пути не называет корня, от которого её читать: число
# строк по ней — «н/д», а не файл относительно рабочего каталога отчёта.
SHORT_PATH_PREFIXES = (provider_base.WORKTREE_LOG_PREFIX,
                       provider_base.DOCS_LOG_PREFIX)

# Сводка наблюдения неослабления (требование 11): класс текстового
# вердикта — по первому совпавшему маркеру; «покрыто мандатом» первым —
# старше любых других маркеров того же текста (решение Оператора, В3).
OBSERVATION_CLASSES = (
    ("покрыто мандатом", test_integrity.ASSERTIONS_COVERED),
    ("смена ожидания по SPEC",
     test_integrity.OUTCOME_EXPECTATION.split(" (", 1)[0]),
    ("находка вне раздела", test_integrity.REASON_OUTSIDE),
    ("ослабление", f"{test_integrity.OUTCOME_FINDING}: "
                   f"{test_integrity.REASON_WEAKENING}"),
    ("несовпадение с объявленным", test_integrity.REASON_MISMATCH),
)
OBSERVATION_OTHER_CLASS = "прочее"
OBSERVATION_OTHER_OUTCOME = "иная причина"


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
    """Журнал ВСЕХ задач одним списком, в сквозной хронологии `id`.

    Одна выборка (`store.all_steps`) вместо выборки на каждую задачу
    (требование 3) — и без сортировки в Python: `ORDER BY id` самой
    выборки уже даёт хронологию, которую прежняя склейка списков по
    задачам восстанавливала сортировкой.

    Отбор «только задачи из `tasks`» остаётся: журнал несёт записи
    псевдозадач пульта (`config.PIN_UPDATE_JOURNAL_TASK_ID`,
    `config.PROGRAM_SPEND_RESEED_TASK_ID`) — строки `tasks` у них нет, и
    прежняя склейка по задачам их не включала. Без этого фильтра они
    попали бы, например, в журнал Оператора по дням (`_operator_window`
    отбирает записи actor'а `operator` не глядя на `task_id`), то есть
    вывод отчёта изменился бы (требование 5 запрещает).
    """
    known = {row["id"] for row in tasks}
    return [row for row in store.all_steps(conn) if row["task_id"] in known]


# ------------------------------------ наблюдатель роста карты (AC-1..AC-12)
#
# Читает журнал и алерты через функции store.py (`all_tasks`/
# `steps_of_action`/`open_alerts`/`alerts_older_than`), тем же приёмом, что
# `_all_steps` выше.

def _map_size_entries(conn, target: str) -> list:
    """Записи ряда «карта: размер» этого target, хронологически (по
    возрастанию `id` — сквозной autoincrement `steps` через все задачи).

    Каждый элемент — уже разобранный JSON `detail` записи с добавленным
    ключом `ts` (момент записи, для окна калибровки AC-7).

    Одна выборка журнала (требование 3 SPEC 01M3GKJFN90ATK2KECNDZXPPP6)
    вместо выборки на каждую задачу target'а, и выборка эта — только
    записи ЭТОГО действия (`store.steps_of_action`), а не весь журнал
    пульта: ряд роста карты собирается тремя вызовами на каждый target
    (`map_size_table_rows`, `map_growth_calibration_median`,
    `map_growth_cost_estimate`), так что весь журнал на вызов означал бы
    `3 × T` полных проходов на отчёт — REVIEW.md итерации 1, R1-F2.

    Принадлежность target'у по-прежнему берётся у КАТАЛОГА ЗАДАЧ
    (`all_tasks`), не у колонки `steps.target`: ряд роста карты одного
    target не должен уметь показать запись другого, даже если колонка
    журнала разошлась с каталогом."""
    task_ids = {row["id"] for row in store.all_tasks(conn)
               if row["target"] == target}
    entries = []
    for s in store.steps_of_action(conn, MAP_SIZE_ACTION):
        if s["task_id"] not in task_ids:
            continue
        try:
            detail = json.loads(s["detail"])
        except (TypeError, ValueError):
            continue
        entries.append({**detail, "ts": s["ts"]})
    return entries


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
    ГЛОБАЛЬНО (не по target — тариф модели один на все target,
    требование 1); выборка пуста (ни одной задачи с логом `developer` в
    окне) — фолбэк
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
    у target нет вовсе — `None` (AC-10, нечего оценивать).

    Цена — действующий тариф МОДЕЛИ роли `developer` (SPEC
    01M300A14KRHCFB0DQXVCBJEKF, требование 1), и считается он тем же
    `spend.partial_cost_usd`, что и стоимость шага: карта прочитывается
    из кэша на каждый вызов инструмента и один раз пишется в кэш — это и
    есть разбивка usage, вторая копия арифметики здесь не нужна. Тариф не
    разрешился — `cost_usd` равен `None` (оценку не по чему считать), а
    не нулю: ноль читался бы как «карта бесплатна»."""
    entries = _map_size_entries(conn, target)
    if not entries:
        return None
    latest = entries[-1]
    bytes_value = (latest["bytes_projection"] if "bytes_projection" in latest
                  else latest["bytes_total"])
    tokens = bytes_value // 3

    calls, is_estimate = _map_growth_calls_estimate(conn)

    cost_usd = spend.partial_cost_usd("developer", {
        "cache_read_input_tokens": tokens * calls,
        "cache_creation_input_tokens": tokens})
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
    """{модель: коэффициент} — расхождение тарифа модели с фактом CLI
    (SPEC 01M1PP0VYRT55WN8GGVG66X89Y, требования 4-5; SPEC
    01M2ZNJX2N5SPZCAQE6EHD4EWH, требования 6-7; ключ-МОДЕЛЬ — SPEC
    01M300A14KRHCFB0DQXVCBJEKF, требование 4, AC-6). Коэффициент —
    `spend.RateDivergence`, то есть число (контракт `dict[str, float]`
    цел), несущее вдобавок число вошедших шагов и дату сверки
    атрибутами `steps`/`since`.

    Источник — журнал: каждая запись `spend.KNOWN_COST_JOURNAL_ACTION`
    (`spend.charge_step`) несёт фактическую цену завершённого шага (из
    `total_cost_usd` финального события потока), модель того шага и
    разбивку usage по видам. Чтение журнала (`spend.known_cost_pairs`) и
    сам расчёт с алертом (`spend.check_rate_divergence`) — те же
    функции, которыми считает сверку `charge_step` в момент записи шага:
    одна математика на обе точки, не две (требование 6, AC-8).

    Пары (роль, модель) одной модели складываются в ОДИН коэффициент:
    предмет отчётной цифры — цена, а она у модели одна на все роли
    яруса; разрез по ролям внутри модели читателю отчёта ничего не
    добавил бы, а разрез по моделям — ровно то, чего не было видно в
    инциденте 13.09-20.09.

    Считается с даты действующего тарифа модели: строки KNOWN старше неё
    посчитаны по другой цене, их складывание со свежими и дало бы то
    самое расхождение, которое контур обязан ловить. Модель без
    подходящих строк — отсутствует в результате вовсе, не 0.0 (AC-6
    прежней SPEC: «не считается расхождением по умолчанию»).

    Не read-only (отсюда алерт в `cmd_report`) — осознанное исключение,
    описанное в докстроке `cmd_report`.
    """
    by_model: dict = {}
    for (_, model_id), pairs in spend.known_cost_pairs(conn).items():
        by_model.setdefault(model_id, []).extend(pairs)
    result = {}
    for model_id, pairs in by_model.items():
        divergence = spend.check_rate_divergence(conn, model_id, pairs)
        if divergence is not None:
            result[model_id] = divergence
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

def _project(row) -> str:
    """Проект задачи; строка без ключа `target` (фикстуры, старые срезы)
    и NULL — задача артели, как в `status`."""
    return (row["target"] if "target" in row.keys() else None) or config.DEFAULT_TARGET


def _project_suffix(row) -> str:
    """Метка ` [<проект>]` сразу за id строки задачи — только у задачи
    внешнего проекта, как в `status` (SPEC 01M57PMBHWK5EGQ8HPA5TQX72H,
    требование 1); строка артели прежняя. Не экранирована."""
    project = _project(row)
    return f" [{project}]" if project != config.DEFAULT_TARGET else ""


def _project_label(row) -> str:
    return _esc(_project_suffix(row))


def _project_labels(tasks: list) -> dict:
    """{id задачи: метка} — для строк, которые несут только id задачи."""
    return {row["id"]: _project_label(row) for row in tasks}


def _tile_html(row) -> str:
    escalated = bool(row["escalated_from"]) or row["state"] == "escalated"
    escalation_line = ""
    if escalated:
        source = row["escalated_from"] or "—"
        escalation_line = (
            f'<div class="tile-field tile-escalation">'
            f'Эскалация (из {_esc(source)})</div>')
    # Проект — только у задачи внешнего проекта (SPEC
    # 01M563E1SH9SB63S2MW4A9B82N, требование 7). Скобки — снаружи
    # элемента проекта (SPEC 01M57PMBHWK5EGQ8HPA5TQX72H, требование 1):
    # его собственный текст остаётся ровно именем проекта.
    project = _project(row)
    project_line = ""
    if project != config.DEFAULT_TARGET:
        project_line = f' [<span class="tile-project">{_esc(project)}</span>]'
    return (
        f'<div class="tile">'
        f'<span class="tile-id">{_esc(row["id"])}</span>'
        f'{project_line}'
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
        f'<span class="gate-task">{_esc(row["id"])}{_project_label(row)} — '
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
        f'<span class="closed-id">{_esc(row["id"])}{_project_label(row)}</span>'
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


def _alert_label(alert, projects: set, task_ids: set) -> str:
    """Метка ` [<проект>]` алерта внешнего проекта (SPEC
    01M57PMBHWK5EGQ8HPA5TQX72H, требование 2; ANSWER-2, п.2): `target` —
    имя проекта (`targets.yaml` или проект задачи выборки), не артели.
    Алерт артели, NULL и алерт с id задачи — без метки; значение, не
    названное ни проектом, ни id задачи, печатается в скобках как есть."""
    target = alert["target"]
    if not target or target == config.DEFAULT_TARGET:
        return ""
    if target not in projects and target in task_ids:
        return ""
    return f'<span class="alert-project">[{_esc(target)}]</span>'


def _declared_projects() -> set:
    """Имена проектов `targets.yaml`; негодный или отсутствующий файл —
    пустой набор: отчёт строится и без декларации проектов."""
    try:
        return set(targets.load())
    except targets.TargetsError:
        return set()


def _alerts_html(alerts: list, projects: set = frozenset(),
                 task_ids: set = frozenset()) -> str:
    if not alerts:
        return '<p class="empty">Незакрытых алертов нет.</p>'
    items = "".join(
        f'<li class="alert-item">'
        f'{_alert_label(a, projects, task_ids)}'
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
    """Коэффициент расхождения тарифа токенов по МОДЕЛИ (SPEC
    01M1PP0VYRT55WN8GGVG66X89Y, требование 4, AC-6; ключ-модель — SPEC
    01M300A14KRHCFB0DQXVCBJEKF, требование 4) — часть панели метрик
    `report`, не отдельная команда (выбор разработчика, требование 4
    явно оставляет его на усмотрение). Строка на модель: моделей у
    пульта несколько, и склеенная цифра снова скрыла бы, чья цена
    разошлась.

    Дата калибровки и число вошедших шагов — в той же строке (SPEC
    01M2ZNJX2N5SPZCAQE6EHD4EWH, требование 7, AC-8): без них читатель не
    может сказать, по какому периоду и по скольким шагам посчитана
    цифра, а в сверку входят не все строки KNOWN роли. Значение —
    `spend.RateDivergence`: сам коэффициент числом, период — его
    атрибутами."""
    if not divergence:
        return ('<div class="metric-row">нет завершённых шагов с известной '
                'стоимостью — коэффициент расхождения не считается</div>')
    return "".join(
        f'<div class="metric-row">{_esc(model_id)}: коэффициент расхождения '
        f'{value:.2f} по {value.steps} шагам '
        f'с {_esc(value.since)}</div>'
        for model_id, value in sorted(divergence.items())
    )


def _gate_ratio_rows(steps: list, prefix: str = "") -> str:
    gate_ratio = _gate_ratio(steps)
    return (
        f'{_ratio_line(prefix + "за всю историю", gate_ratio["history"])}'
        f'{_ratio_line(prefix + "за последние 10 задач", gate_ratio["last_window"])}'
    )


def _economy_rows(tasks: list, total_spent: float, total_estimate: float,
                  prefix: str = "") -> str:
    cost_per_task = _cost_per_done_task(tasks)
    cost_line = (_usd(cost_per_task) if cost_per_task is not None
                else "нет done-задач")
    # Верхняя оценка (SPEC 01M1NWCM3TDY0YABEKE8DYQA1C, требование 6) —
    # отдельная строка от точного расхода, не сложена с ним в одно число
    # (иначе оценка перестала бы быть отличимой от факта, требование 6).
    return (
        f'<div class="metric-row">{_esc(prefix)}$/задачу (done): {cost_line}</div>'
        f'<div class="metric-row">{_esc(prefix)}Суммарный расход программы: '
        f'{_usd(total_spent)}</div>'
        f'<div class="metric-row">{_esc(prefix)}Суммарная верхняя оценка '
        f'(тариф модели не разрешён): {_usd(total_estimate)}</div>'
    )


def _by_project(tasks: list) -> list:
    """[(проект, его задачи)] — артель первой, остальные по имени; задача
    с `target` NULL — задача артели (SPEC 01M57PMBHWK5EGQ8HPA5TQX72H,
    требование 3)."""
    groups: dict = {}
    for row in tasks:
        groups.setdefault(_project(row), []).append(row)
    return sorted(groups.items(),
                  key=lambda item: (item[0] != config.DEFAULT_TARGET, item[0]))


def _split_metrics_html(steps: list, tasks: list) -> tuple:
    """(доля acceptance, экономика) по строке на проект: значения проекта
    считаются только по его задачам и их записям журнала, окно доли —
    последние записи этого проекта, а не его доля в окне пульта (SPEC
    01M57PMBHWK5EGQ8HPA5TQX72H, требование 3, AC-3)."""
    gate_rows, economy_rows = [], []
    for project, project_tasks in _by_project(tasks):
        ids = {row["id"] for row in project_tasks}
        project_steps = [s for s in steps if s["task_id"] in ids]
        prefix = f"{project}: "
        gate_rows.append(_gate_ratio_rows(project_steps, prefix))
        economy_rows.append(_economy_rows(
            project_tasks,
            sum(row["spent_usd"] or 0.0 for row in project_tasks),
            sum(row["spent_estimate_usd"] or 0.0 for row in project_tasks),
            prefix))
    return "".join(gate_rows), "".join(economy_rows)


def _metrics_html(steps: list, tasks: list, total_spent: float,
                  total_estimate: float, divergence: dict | None = None) -> str:
    per_day = _operator_journal_by_day(steps)

    per_day_html = "".join(
        f'<div class="metric-row">{_esc(day)}: operator {count}</div>'
        for day, count in per_day
    ) or '<div class="metric-row">записей actor=operator за 14 дней нет</div>'

    # Разбивка по проекту — только при задачах больше одного проекта
    # (ANSWER-1, п.2): у одного проекта, в том числе единственного
    # внешнего, блоки прежние.
    if len({_project(row) for row in tasks}) > 1:
        gate_html, economy_html = _split_metrics_html(steps, tasks)
    else:
        gate_html = _gate_ratio_rows(steps)
        economy_html = _economy_rows(tasks, total_spent, total_estimate)

    return (
        '<div class="metrics">'
        '<h3>Доля acceptance: автогейт vs Оператор</h3>'
        f'{gate_html}'
        '<h3>Записи actor=operator по дням (последние 14 дней)</h3>'
        f'{per_day_html}'
        '<h3>Экономика</h3>'
        f'{economy_html}'
        '<h3>Калибровка курса токенов</h3>'
        f'{_divergence_html(divergence or {})}'
        '</div>'
    )


# ------------------------------------- токены рядом с долларами (AC-7..AC-9)
#
# Разбор записей токенов журнала живёт в `orchestrator/retro.py` — один
# читатель на три места показа (`status`, RETRO, `report`), см. его
# докстринг. Здесь только вёрстка двух разрезов.

def _token_cost_row_html(marker: str, usd: str, total: int | None,
                         by_kind: dict) -> str:
    """Строка разреза: адрес (задача или роль), доллары и токены по видам
    РЯДОМ, в одном элементе (требования 4-5).

    Записей токенов нет — прочерк вместо суммы и вместо разбивки, не
    нули: `input=0 … cache_read=0` читалось бы как «шаг прошёл
    бесплатно». Сумма и разбивка показываются независимо: у строки,
    чьи шаги записаны прежним видом записи, сумма известна, а разбивки
    нет (REVIEW.md итерации 1, R1-F1).

    Формулировку обеих частей даёт `retro.tokens_detail_text` — там же,
    где и в RETRO: разрез ролей отчёта суммирует ВЕСЬ журнал пульта, и
    исторические записи без разбивки из него не исчезнут, так что
    неполная разбивка обязана называть свою сумму явно (REVIEW.md
    итерации 2, R2-F1)."""
    tokens_part = _esc(retro.tokens_detail_text(total, by_kind))
    return (f'<div class="metric-row">{_esc(marker)}: {usd} · '
            f'{tokens_part}</div>')


def _tokens_by_task(tasks: list, steps: list) -> str:
    """Разрез задач (AC-7/AC-9): каждая задача пульта — своей строкой, с
    её деньгами и суммой её записей токенов по видам.

    Все задачи, а не только закрытые: разрез отвечает на вопрос «во что
    обошлась задача», и живая задача ровно так же его задаёт."""
    if not tasks:
        return '<p class="empty">Задач нет.</p>'
    by_task: dict = {}
    for s in steps:
        by_task.setdefault(s["task_id"], []).append(s)
    rows = []
    for row in tasks:
        task_steps = by_task.get(row["id"], [])
        # `_token_cost_row_html` экранирует адрес сам — метка сырая.
        rows.append(_token_cost_row_html(
            f'{row["id"]}{_project_suffix(row)}', _usd(row["spent_usd"]),
            retro.task_token_total(task_steps),
            retro.task_token_breakdown(task_steps)))
    return "".join(rows)


def _tokens_by_role(steps: list) -> str:
    """Разрез ролей (AC-8): роль — своей строкой, деньги и токены
    просуммированы поперёк ВСЕХ задач пульта.

    Источник тот же, что у блока стоимости RETRO (`retro.actor_costs`):
    деньги по `agent run finished`, токены по обоим носителям суммы, —
    две копии этой агрегации разошлись бы между RETRO и отчётом.
    Оттуда же и прочерк вместо денег у роли, чью стоимость журнал не
    записал (REVIEW.md итерации 1, R1-F2)."""
    rows = retro.actor_costs(steps)
    if not rows:
        return ('<p class="empty">Шагов с учтённой стоимостью нет.</p>')
    return "".join(_token_cost_row_html(row.actor, retro.usd_text(row.usd),
                                        row.total, row.tokens)
                   for row in rows)


def _token_cost_html(tasks: list, steps: list) -> str:
    return (
        '<div class="metrics">'
        '<h3>В разрезе задач</h3>'
        f'{_tokens_by_task(tasks, steps)}'
        '<h3>В разрезе ролей</h3>'
        f'{_tokens_by_role(steps)}'
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
    labels = _project_labels(tasks)
    rows_html = "".join(
        f'<div class="metric-row">{_esc(task_id)}{labels.get(task_id, "")}: '
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


# ------------------------- расход test_author и сводка наблюдения неослабления
#
# SPEC 01M4NZ5W9ZTKGTW7DGZQGMP2GP, требования 10-11: только чтение уже
# записанного — журнала, лога шага и файлов на диске; git не вызывается.

def _in_window(ts) -> bool:
    """Запись не старше `OPERATOR_WINDOW_DAYS` — то же окно и то же
    сравнение дат, что у `_operator_journal_by_day`."""
    cutoff = (datetime.now(timezone.utc)
              - timedelta(days=OPERATOR_WINDOW_DAYS)).date()
    try:
        return datetime.strptime((ts or "")[:10], "%Y-%m-%d").date() >= cutoff
    except ValueError:
        return False


def _test_author_steps(steps: list) -> list:
    """Запуски test_author за окно: запись «agent run started» открывает
    запуск задачи, следующие записи test_author той же задачи (прогоны
    pytest и vitest, стоимость, провайдер) относятся к нему."""
    current: dict = {}
    found = []
    for row in steps:
        if row["actor"] != TEST_AUTHOR_ROLE:
            continue
        detail = row["detail"] or ""
        if row["action"] == STEP_STARTED_ACTION:
            match = _LOG_PATH_RE.search(detail)
            step = {"task": row["task_id"], "ts": row["ts"] or "",
                    "log": match.group(1) if match else None, "cost": None,
                    "tokens": None, "provider": None, "pytest": []}
            current[row["task_id"]] = step
            if _in_window(row["ts"]):
                found.append(step)
            continue
        step = current.get(row["task_id"])
        if step is None:
            continue
        if row["action"] in (agent_log.PYTEST_RUN_ACTION,
                             agent_log.VITEST_RUN_ACTION):
            match = _PYTEST_SECONDS_RE.search(detail)
            step["pytest"].append(float(match.group(1)) if match else 0.0)
            continue
        provider = _PROVIDER_RE.search(detail)
        if provider is not None:
            step["provider"] = provider.group(1)
        if row["action"] == retro.FINISHED_JOURNAL_ACTION:
            cost = retro.COST_RE.search(detail)
            tokens = retro.TOKENS_RE.search(detail)
            step["cost"] = float(cost.group(1)) if cost else None
            step["tokens"] = int(tokens.group(1)) if tokens else None
    return found


def _tool_calls(log) -> list | None:
    """[(инструмент, видимый аргумент)] строк вызова лога шага; `None` —
    лога нет на диске."""
    if not log:
        return None
    try:
        text = Path(log).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    prefix = claude_provider.TOOL_CALL_LINE_PREFIX
    calls = []
    for line in text.splitlines():
        if line.startswith(prefix):
            name, _, arg = line[len(prefix):].partition(" ")
            if name:
                calls.append((name, arg))
    return calls


def _file_lines(path: str) -> int | None:
    try:
        return len(Path(path).read_text(encoding="utf-8",
                                        errors="replace").splitlines())
    except OSError:
        return None


def _write_groups(calls: list) -> dict:
    """{группа: (вызовов Write, файлов, строк, строк Write «н/д»)} —
    файлы по различным полным путям; путь, видимый целиком до предела
    обрезки, путь в короткой форме `wt:`/`docs:` или файл, которого нет на
    диске, — «н/д» (ANSWER-1, п.2)."""
    groups = {}
    def group_of(arg: str):
        return next((g for g, p in WRITE_GROUPS if p.search(arg)), None)

    for group, _pattern in WRITE_GROUPS:
        writes = [arg for name, arg in calls
                  if name == "Write" and group_of(arg) == group]
        lines, unknown = {}, 0
        for arg in writes:
            count = None
            if (len(arg) < claude_provider.TOOL_ARGUMENT_LIMIT
                    and not arg.startswith(SHORT_PATH_PREFIXES)):
                count = lines[arg] if arg in lines else _file_lines(arg)
            if count is None:
                unknown += 1
            else:
                lines[arg] = count
        groups[group] = (len(writes), len(lines), sum(lines.values()), unknown)
    return groups


def _test_author_row_html(step: dict, label: str = "") -> str:
    calls = _tool_calls(step["log"])
    # Запуск без записи провайдера — старше поля `provider=`, когда
    # исполнитель был один: Claude.
    claude = (step["provider"] or claude_provider.ClaudeProvider.name) \
        == claude_provider.ClaudeProvider.name
    cost = _usd(step["cost"]) if step["cost"] is not None else _DASH
    tokens = step["tokens"] if step["tokens"] is not None else _DASH
    parts = [f"стоимость {cost}", f"токенов {tokens}"]
    if calls is None:
        parts.append(f"вызовы инструментов: {NOT_AVAILABLE} (лога нет)")
    else:
        kinds = Counter(name for name, _arg in calls)
        if not claude:
            kinds.pop("Write", None)
        shown = ", ".join(f"{name} {count}" for name, count in sorted(kinds.items()))
        parts.append(f"вызовы инструментов: {shown or 'нет'}")
    runs = step["pytest"]
    parts.append(f"прогоны pytest: {len(runs)}, {sum(runs):.2f} с")
    for group, _pattern in WRITE_GROUPS:
        if calls is None or not claude:
            parts.append(f"{group} Write {NOT_AVAILABLE}, файлов "
                         f"{NOT_AVAILABLE}, строк {NOT_AVAILABLE}")
            continue
        writes, files, lines, unknown = _write_groups(calls)[group]
        text = f"{group} Write {writes}, файлов {files}, строк {lines}"
        if unknown:
            text += (f", {NOT_AVAILABLE} по {unknown} вызовам Write (путь "
                     f"обрезан или файла нет)")
        parts.append(text)
    return (f'<div class="metric-row">{_esc(step["task"])}{label} '
            f'{_esc(step["ts"][:10])}: {_esc(" · ".join(parts))}</div>')


def _test_author_html(steps: list, tasks: list = ()) -> str:
    labels = _project_labels(tasks)
    rows = [_test_author_row_html(step, labels.get(step["task"], ""))
            for step in _test_author_steps(steps)]
    return "".join(rows) or (f'<p class="empty">Шагов test_author за '
                             f'{OPERATOR_WINDOW_DAYS} дней нет.</p>')


def _explore_html(steps: list, now: datetime) -> str:
    """Блок «Разведка ролей» из уже прочитанного журнала — без своего
    запроса к БД; те же строки, что печатает `explore-stats`."""
    roles = explore_metric.DEFAULT_ROLES
    summary = explore_metric.summarize(steps, now, EXPLORE_WINDOW_DAYS, roles)
    return "".join(
        f'<div class="metric-row">{_esc(line)}</div>'
        for line in explore_metric.render_lines(summary, roles,
                                                EXPLORE_WINDOW_DAYS))


def _observation_class(verdict: str) -> str:
    for label, marker in OBSERVATION_CLASSES:
        if marker in verdict:
            return label
    return OBSERVATION_OTHER_CLASS


def _observation_key(detail: str) -> tuple:
    """(класс вердикта, исход и признак стороны «новая на базе», исход и
    признак стороны «старая на ветке») записи наблюдения."""
    verdict = re.search(rf"{re.escape(test_integrity.OBSERVATION_VERDICT)}"
                        rf"(.*?){re.escape(test_integrity.OBSERVATION_KIND)}",
                        detail, re.S)
    key = [_observation_class(verdict.group(1)) if verdict
           else OBSERVATION_OTHER_CLASS]
    known = (two_sided.SIDE_ASSERTION, two_sided.SIDE_GREEN,
             two_sided.SIDE_LIMIT)
    for label in (two_sided.NEW_ON_BASE, two_sided.OLD_ON_BRANCH):
        side = re.search(
            rf"{re.escape(label)}: (.*?); "
            rf"{re.escape(test_integrity.OBSERVATION_CHANGED)}(\w+)",
            detail, re.S)
        if side is None:
            key += [OBSERVATION_OTHER_OUTCOME, _DASH]
            continue
        outcome = side.group(1)
        key += [outcome if outcome in known else OBSERVATION_OTHER_OUTCOME,
                side.group(2)]
    return tuple(key)


def _observation_html(steps: list) -> str:
    """Таблица «класс текстового вердикта × исход и признак «в изменённых
    строках» по каждой стороне → число записей» (требование 11)."""
    counts = Counter(_observation_key(row["detail"] or "") for row in steps
                     if row["action"] == test_integrity.OBSERVATION_ACTION)
    if not counts:
        return '<p class="empty">Записей наблюдения нет.</p>'
    order = [label for label, _marker in OBSERVATION_CLASSES] + \
        [OBSERVATION_OTHER_CLASS]
    body = "".join(
        "<tr>" + "".join(f"<td>{_esc(cell)}</td>" for cell in key)
        + f"<td>{count}</td></tr>"
        for key, count in sorted(counts.items(),
                                 key=lambda item: (order.index(item[0][0]),
                                                   item[0])))
    new, old = two_sided.NEW_ON_BASE, two_sided.OLD_ON_BRANCH
    return ('<table class="map-size-table">'
            f'<thead><tr><th>текстовый вердикт</th><th>{_esc(new)}</th>'
            '<th>в изменённых</th>'
            f'<th>{_esc(old)}</th><th>в изменённых</th>'
            '<th>записей</th></tr></thead>'
            f'<tbody>{body}</tbody></table>')


# ---------------------------- круги до кода (SPEC 01M59DP2GV3SAN54M562CQY42R)
#
# Подсчёт — `orchestrator/rounds.py` по уже выбранному журналу отчёта
# (`_all_steps`): блок не добавляет ни одного запроса к `steps`.

def _rounds_number(value: float) -> str:
    return f"{round(value, 2):g}"


def _rounds_summary(values: list, fmt=_rounds_number) -> tuple:
    return fmt(statistics.median(values)), fmt(statistics.mean(values))


def _rounds_table_html(entries: list) -> str:
    """Таблица одного проекта: строка на задачу и строка итога — медиана и
    среднее каждого числа; составные столбцы — «X / Y» в обеих формах."""
    rows = []
    for row, counted in entries:
        hot = ' class="rounds-hot"' if rounds.over_threshold(counted) else ""
        rows.append(
            f'<tr{hot}><td>{_esc(row["id"])}</td><td>{_esc(_project(row))}</td>'
            f'<td>{counted.audits}</td>'
            f'<td>{counted.audit_returns} / {counted.gate_returns}</td>'
            f'<td>{counted.escalations}</td><td>{counted.review_iters}</td>'
            f'<td>{_usd(counted.cost_before_plank)} / '
            f'{_usd(counted.cost_total)}</td></tr>')
    counts = [counted for _row, counted in entries]

    def summary(field: str, fmt=_rounds_number) -> tuple:
        return _rounds_summary([getattr(c, field) for c in counts], fmt)

    def cell(*fields: str, fmt=_rounds_number) -> str:
        parts = [summary(field, fmt) for field in fields]
        median = " / ".join(p[0] for p in parts)
        mean = " / ".join(p[1] for p in parts)
        return f'<td>медиана {median}<br>среднее {mean}</td>'

    rows.append(
        '<tr class="rounds-total"><td colspan="2">Итог: медиана и среднее</td>'
        f'{cell("audits")}{cell("audit_returns", "gate_returns")}'
        f'{cell("escalations")}{cell("review_iters")}'
        f'{cell("cost_before_plank", "cost_total", fmt=_usd)}</tr>')
    return (
        '<table class="rounds-table">'
        '<tr><th>Задача</th><th>Проект</th><th>Аудиты SPEC</th>'
        '<th>Возвраты аудита / с гейта SPEC</th><th>Эскалации</th>'
        '<th>Итерации ревью</th><th>Расход до планки / всего</th></tr>'
        + "".join(rows) + '</table>')


def _rounds_html(tasks: list, steps: list) -> str:
    """Блок «Круги до кода» (требования 2-5): задачи, созданные за
    `OPERATOR_WINDOW_DAYS` дней; при задачах больше одного проекта —
    таблица на проект, как прочие блоки отчёта."""
    window = [row for row in tasks if _in_window(row["created_at"])]
    if not window:
        return (f'<p class="empty">Задач, созданных за последние '
                f'{OPERATOR_WINDOW_DAYS} дней, нет.</p>')
    by_task: dict = {}
    for s in steps:
        by_task.setdefault(s["task_id"], []).append(s)

    def entries(rows: list) -> list:
        return [(row, rounds.count(by_task.get(row["id"], []), row["review_iters"]))
                for row in rows]

    # Разбивка — по тому же признаку, что у `_metrics_html`: задачи больше
    # одного проекта у пульта, не только в окне.
    if len({_project(row) for row in tasks}) == 1:
        return _rounds_table_html(entries(window))
    return "".join(f'<h3>{_esc(project)}</h3>{_rounds_table_html(entries(rows))}'
                   for project, rows in _by_project(window))


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
    # Нерезолвимый тариф модели `developer` печатается словами, а не
    # `_usd(None)` = «$0.00»: цена, которую не по чему посчитать, и цена,
    # равная нулю, — разные состояния, а читатель панели различает их
    # только здесь.
    cost = (f"{_usd(estimate['cost_usd'])}{suffix}"
            if estimate["cost_usd"] is not None
            else "тариф модели роли developer не разрешён")
    return (
        '<div class="metric-row">Стоимость карты за шаг developer: '
        f'{cost} '
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
  .tile .tile-project { margin-left: 6px; color: var(--muted); font-size: 11px; }
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
  table.rounds-table { border-collapse: collapse; font-size: 12px; margin: 6px 0; }
  table.rounds-table th, table.rounds-table td {
    border: 1px solid var(--border); padding: 4px 8px; text-align: left;
  }
  table.rounds-table tr.rounds-hot td { background: #fdecec; font-weight: 600; }
  table.rounds-table tr.rounds-total td { color: var(--muted); }
  footer { padding: 0 24px 30px; font-size: 11px; color: var(--muted); }
"""


def _render(tasks: list, steps: list, alerts: list, total_spent: float,
           total_estimate: float, divergence: dict | None = None,
           map_growth_html: str = "", *, now: datetime) -> str:
    projects = _declared_projects() | {_project(row) for row in tasks}
    task_ids = {row["id"] for row in tasks}
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
        f"{_alerts_html(alerts, projects, task_ids)}</section>\n"
        '<section class="panel"><h2>Очередь ожиданий Оператора</h2>'
        f"{_gate_queue_html(tasks)}</section>\n"
        '<section class="panel"><h2>Борд задач — состояния FSM</h2>'
        f"{_board_html(tasks)}</section>\n"
        '<section class="panel"><h2>Закрытые задачи</h2>'
        f"{_closed_tasks_html(tasks, steps)}</section>\n"
        '<section class="panel"><h2>Метрики гейтовой нагрузки</h2>'
        f"{_metrics_html(steps, tasks, total_spent, total_estimate, divergence)}</section>\n"
        '<section class="panel"><h2>Токены и стоимость</h2>'
        f"{_token_cost_html(tasks, steps)}</section>\n"
        '<section class="panel"><h2>Метрика «трение»</h2>'
        f"{_friction_html(tasks, steps)}</section>\n"
        f'<section class="panel"><h2>Шаги test_author (последние '
        f'{OPERATOR_WINDOW_DAYS} дней)</h2>'
        f'<div class="metrics">{_test_author_html(steps, tasks)}</div></section>\n'
        f'<section class="panel"><h2>Разведка ролей (последние '
        f'{EXPLORE_WINDOW_DAYS} дней)</h2>'
        f'<div class="metrics">{_explore_html(steps, now)}</div></section>\n'
        '<section class="panel"><h2>Двусторонний прогон (наблюдение '
        'неослабления)</h2>'
        f"{_observation_html(steps)}</section>\n"
        '<section class="panel"><h2>Рост карты кодовой базы</h2>'
        f"{map_growth_html}</section>\n"
        f'<section class="panel"><h2>Круги до кода (задачи последних '
        f'{OPERATOR_WINDOW_DAYS} дней)</h2>'
        f'<div class="metrics">{_rounds_html(tasks, steps)}</div></section>\n'
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
                 divergence, map_growth_html, now=datetime.now(timezone.utc))

    path = config.ROOT / ".artel" / "report.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(doc, encoding="utf-8")
    print(f"Отчёт сгенерирован: {path}")
