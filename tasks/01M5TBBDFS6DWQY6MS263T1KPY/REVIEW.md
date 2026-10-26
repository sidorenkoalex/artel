---
task: 01M5TBBDFS6DWQY6MS263T1KPY
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Эпики Э1 — эпик как сущность пульта, команды эпика и модель доски для `status` и `epic show`

## Фаза A: план
- Таблица покрытия PLAN полна: требования 1–14 разнесены по шагам 1–6, шаг 7 — юнит-тесты и карта.
- Шаги размером в MR (схема/store, board, epics+CLI, new, approve, status) — проверяемые, не микрооперации.
- Подход соответствует конвенциям: SQL только в `store.py` (`SqlOnlyInStoreTest`), lease по id эпика не вводится, `lease.py`/`watch.py` только читаются. «Влияние на систему» совпадает с diff: 9 модулей зоны SPEC, `tests/test_epics_board_units.py` (новый), одна строка `tests/test_multitarget.py` по ANSWER-1. Путь отката описан (revert; таблица/колонка безвредны).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `schema._migrate_epics` (schema.py:232): быстрая проверка колонки вне транзакции, повтор под `BEGIN IMMEDIATE`, DDL+ALTER+индекс, журнал `config.EPICS_MIGRATION_JOURNAL_TASK_ID` последним; без `steps` — явный `commit`. Вызов в конце `migrate` — после догона колонок `steps` (проверено юнит-тестом). `PROJECT_DIRS` + `epics`. |
| 2 | OK | `epics.new_epic_id` = `E` + `idgen.new_task_id()`; особого случая нет — `--after E…` отказывает причиной формы `check`, `show E…` — текстом `get_task` (AC-9 зелёный). |
| 3, 6 | OK | `epics.binding_refusal` — общий узел для `epic add`, `new --epic` (предварительно и в транзакции `_new_task_row`), частей деления. |
| 4 | OK | `new/edit/close` — `_transaction` (BEGIN IMMEDIATE, журнал последним); `add/remove` — `lease.run_locked` задачи, транзакция внутри; `_existing` до lease. `run_locked` снимает lease в `finally` (lease.py:377) — отказ внутри транзакции lease не оставляет. |
| 5 | OK | Предварительная проверка эпика в `cmd_new` до ТЗ/клона/ссылки; `merge_after.declared_for_new` — объединение ТЗ + `--after` с дедупликацией по полному id до `check`, повтор внутри строки ТЗ по-прежнему отказ. Путь `--after` без `--tz` — `elif`, запись — общий `record_declared` (catalog.py:697). |
| 7 | OK | `_as_epic_goal` до `lease.run_locked`, SPEC читается `artifact_branch.show` без журнала; эпик заводится в `_spawn_division_subtasks` перед частями — мягкие отказы гейта до него не доходят; повтор проверки под lease; `_approve_sha_arg` пропускает `--as-epic`. |
| 8 | OK | `board._ordered` — Кан с кучей по id, хвост цикла по id. |
| 9 | OK | Проверка терминальности и закрытие в одной транзакции; `ready_to_close` требует непустого эпика. |
| 10 | OK | Ключи верхнего уровня ровно по SPEC; `pin` — `watch._pin_head()`; модель только читает. Элементы несут надмножество ключей (`parent`, `state`, `divisions`, `ready_to_close`) — SPEC требует наличия, не точного состава. |
| 11 | OK | operator → ci → dependency (`zone_lock.queue_wait`) → role; терминальные — `None`. |
| 12 | OK | `epics.show_lines` из модели, столбцы по SPEC, «эпик готов к закрытию». |
| 13 | OK | `_status_line` вынесена дословно из старого цикла; блоки проектов по имени, группы эпиков из модели, затем задачи без эпика; без эпиков — прежний вывод (AC-29 планки зелёная). |
| 14 | OK | Журнал последним во всех транзакциях; SQL в `store.py`; дедупликация до `check`. |

## Замечания
- minor — orchestrator/catalog.py:1121 (`_print_status_blocks`) — при наличии эпиков `status` зовёт `board.build_model` по каждому проекту, а та снова зовёт `zone_lock.queue_wait` на каждую карточку, хотя `_status_line` уже считает ожидание зоны (`_zone_wait_suffix`): удвоение запросов на строку. На корректность не влияет; при росте числа задач — лишняя задержка `status`. Можно оставить до Э4 (модель станет единственным источником).
- minor — orchestrator/board.py:48 — карточка несёт ключ `parent`, которого нет в перечне требования 10; для `epic show` он нужен. Предложение: при Э4 (контракт `board --json`) явно закрепить расширенный набор ключей в SPEC, чтобы внешние потребители не опирались на недокументированное поле.

Blocker/major не найдено.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

(Minor-наблюдения выше в реестр не заведены: они не требуют исправления в этой задаче.)

## Вердикт
approved

## Проверено исполнением
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M5TBBDFS6DWQY6MS263T1KPY` — `test_ac29_status_without_epics.py`: 1 passed, код выхода pytest 0.
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m5tbbdfs6dwqy6ms263t1kpy_*.py tests/test_epics_board_units.py tests/test_multitarget.py tests/test_merge_after_module.py` — 162 passed, 14 subtests passed (8.1 с).
- Сверка `tests/` с базой: изменено только утверждение `tests/test_multitarget.py:288-289` (литерал + `epics`, вид `assertEqual` прежний) — в точности мандат ANSWER-1; прочие изменения `tests/` — новый файл `tests/test_epics_board_units.py`, оба метода с заявками «Ловит мутацию», не повторяют долгоживущие файлы задачи (миграция на `steps` без `target`/`session_id`; цикл `merge_after` в порядке).
- Чтение `orchestrator/lease.py:334-379` — `release` в `finally` у `run_locked` (проверка, что отказ `epic add/remove` внутри транзакции не оставляет lease).

## Предложения системе
- Шаг ревью: составные bash-команды (`;`, `sed`) требуют подтверждения, которого в шаге никто не даёт — стоит упомянуть в миссии шага, что команды лучше дробить.
