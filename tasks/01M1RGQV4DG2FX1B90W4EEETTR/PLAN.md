---
task: 01M1RGQV4DG2FX1B90W4EEETTR
type: plan
author_role: developer
status: ready
schema_version: 4
---

# PLAN: Наблюдатель роста карты, часть 2 — блок report и оценка в деньгах

## Подход
Читаем журнал «карта: размер» (действие, которое пишет часть 1) и алерты
`map.growth` ТОЛЬКО через уже существующие функции `store.py`
(`all_tasks`/`task_steps`/`open_alerts`/`alerts_older_than`) — зона этой
задачи не включает `store.py`, заводить в нём новую специализированную
выборку нельзя. `store.alerts_older_than(conn, "9999-12-31 23:59:59Z")`
даёт единственный существующий способ прочитать алерты НЕЗАВИСИМО от
`ack` (`open_alerts` фильтрует только неподтверждённые) — используется
для поиска точки отсчёта окна калибровки (AC-7).

Все новые функции — чистые читатели `orchestrator/report.py`:
- `_map_size_entries(conn, target)` — внутренний помощник: записи ряда
  «карта: размер» этого target, хронологически (сквозной `steps.id`).
- `map_size_table_rows` (AC-6/AC-10) — последние 12 записей.
- `map_growth_calibration_median` (AC-7) — тот же алгоритм окна, что
  `doctor.check_map_growth` части 1: короткое замыкание на пустом ряде
  ДО обращения к `config.MAP_GROWTH_CALIBRATION_MERGES` — этой константы
  ещё нет в `config.py` до мержа части 1 (родительская 01M1RFVWV6WWTXRC
  5F40K61632), а target без данных не обязан на неё натыкаться.
- `map_growth_open_alerts` (AC-8) — фильтр `store.open_alerts` по
  target+source.
- `map_growth_cost_estimate` (AC-1..AC-5) — `tokens` от `bytes_projection`/
  `bytes_total` последней записи; `calls` — медиана числа вызовов
  инструментов `developer` по логам последних 10 задач ГЛОБАЛЬНО
  (`config.MAP_GROWTH_CALLS_TASK_WINDOW` — модульная константа
  `report.py`, не `config.py` — окно не именовано SPEC как конфиг), с
  фолбэком на новую `config.MAP_GROWTH_CALLS_ESTIMATE`; `cost_usd` по
  курсу `config.TOKEN_RATES["developer"]`. Ни одного обращения к
  `alerts.*`.
- Подсчёт вызовов инструментов в файле лога — независимая копия парсинга
  формата `--output-format stream-json` внутри `report.py`
  (`_map_growth_tool_call_count`), а не импорт приватных
  `agent_log._parse_stream_event`/`_tool_use_calls`: зона задачи не
  включает `agent_log.py`, а те имена — приватный API модуля.

Блок `artel report`: `_map_growth_html(conn, tasks)` — по каждому target
из `store.all_tasks` (тот же источник, что уже использует остальной
`report.py`, без `targets.yaml`); target без записей — фиксированная
строка AC-10 без обращения к калибровке/оценке. Встроено в `_render`
новым параметром `map_growth_html`, вычисляется в `cmd_report` рядом с
`token_rate_divergence` — секция вставлена последней панелью, без
влияния на прежние.

`config.py`: одна новая константа `MAP_GROWTH_CALLS_ESTIMATE = 40`
(AC-3) — единственное изменение зоны в этом файле; пороги роста самой
карты (`MAP_GROWTH_CALIBRATION_MERGES` и т.п.) — не входит, заводит их
часть 1.

## Шаги
1. `config.py`: константа `MAP_GROWTH_CALLS_ESTIMATE`.
2. `report.py`: чтение ряда/калибровки/алертов/оценки (AC-1..AC-10) +
   рендер блока в `artel report`, подключение в `_render`/`cmd_report`.
3. Юнит-тесты нового кода (см. также залоченные `acceptance_tests/`).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 2 |
| 2 | 2 |
| 3 | 2 |
| 4 | 2 |
| 5 | 2, 3 |

## Влияние на систему
Изменения строго внутри `orchestrator/report.py` и `orchestrator/
config.py` (зона SPEC). Ничего не пишет в `state.db` кроме уже
существующего побочного эффекта `token_rate_divergence` (не тронут).
Ни один переход FSM не импортирует `report` (проверено тестом AC-5,
зелёный и до, и после правки) — оценка не влияет на гейты/автогейт.
Существующие `tests/test_report.py` зелёные без правки ассертов (AC-11,
43/43). Откат — `git revert` этого коммита, обе функции читающие,
следов в БД не остаётся.

## Риски
До мержа родительской задачи 01M1RFVWV6WWTXRC5F40K61632 (часть 1) в
журнале нет ни одной записи «карта: размер» — блок `report` для каждого
target будет показывать «измерений нет» (AC-10), это ожидаемое
поведение (SPEC, «Порядок выполнения»), не дефект этой задачи.

## Предложения системе
(пусто)
