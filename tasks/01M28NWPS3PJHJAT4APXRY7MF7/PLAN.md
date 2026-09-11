---
task: 01M28NWPS3PJHJAT4APXRY7MF7
type: plan
author_role: developer
status: ready        # draft | ready | approved
schema_version: 5    # версия формата артефакта, см. scripts/guard.py
---

# PLAN: гонка гейта зон при одновременном старте — атомарный захват зоны

## Подход

Сегодня `runner._cmd_run` для роли `developer` проверяет
`zone_lock.blocking_conflict`, а признак занятости («agent run started»)
появляется в журнале только глубоко внутри `run_agent_once`, секундами
позже, после сборки промпта/брифа/скилов/окружения. Два параллельных
`cmd_run` на общей зоне успевают оба пройти проверку до того, как хоть
один записал занятость.

Фикс — новая функция `zone_lock.claim(conn, task_id, t)`: в одной
транзакции SQLite (`BEGIN IMMEDIATE`, тот же приём, что
`store.next_task_number`/CAS `store.set_state`) читает `blocking_conflict`
и, если конфликта нет, тут же журналирует `zone_lock.CLAIM_ACTION`
(«zone claimed», актор `developer`). `BEGIN IMMEDIATE` берёт
эксклюзивную запись-блокировку сразу при входе в транзакцию — вторая
параллельная `claim()` не может начать СВОЮ транзакцию, пока первая не
закоммитит (или не откатит) свою, поэтому вторая гарантированно увидит
уже записанный `CLAIM_ACTION` первой и получит именованный отказ.

`zone_lock._occupies` расширяется третьим маркером (`CLAIM_ACTION`,
актор `developer`) и симметричным ему снятием — литеральная строка
`"zone claim released"` (без имени константы: приёмочные тесты сверяют
её буквально, SPEC требование 2). Семантика — «последний по id маркер
после `_stay_since_id` решает» (латест-wins): однопроходный обсчёт
журнала по возрастанию id, эквивалентный старому `OR` для двух старых
маркеров (`"agent run started"`/`RELEASE_ACTION`, ни один тест которых
не подмешивает новые маркеры) и корректно моделирующий «взяли — отпустили
— взяли снова» для новых (AC-4).

`runner._cmd_run` вызывает `zone_lock.claim` вместо `zone_lock.refusal`
ДО сборки промпта/спавна (требование 1, AC-1). Остаток тела шага (пауза,
стоп-кран волны, workspace, pre-flight, фиксация, сборка промпта, цикл
попыток агента) вынесен без изменения текста и отступов в отдельную
функцию `_run_developer_step`, чтобы `_cmd_run` мог обернуть её вызов
`try/finally`: в `finally` — если захват записан ИМЕННО этим вызовом
(`claim_pending`) и разработчик фактически не стартовал в текущем
пребывании (`zone_lock.claimed_but_not_started`) — захват снимается
(`zone_lock.release_claim`, актор `fsm`, требование 2, AC-2/AC-3). Один
общий `finally` покрывает ЛЮБОЙ путь возврата после захвата (sys.exit
паузы/стоп-крана, `return` workspace/pre-flight/фиксации, `sys.exit`
несобранных скилов, «skipped»-исход `run_agent_once` до записи «agent run
started») — не нужно перечислять и чинить каждый путь отдельно.

`claim_pending=False`, когда `blocking_conflict` вернул `None` потому что
задача УЖЕ занимает зону сама (маркер уже стоит с более раннего старта в
этом же пребывании) — тогда новый `CLAIM_ACTION` не пишется вовсе (он
ничего не изменил бы в `_occupies`), и `finally` не имеет права снять
occupancy, реально установленную более ранним стартом.

`blocking_conflict`/`refusal`/`queue_order`/`queue_position`/
`cmd_zone_release`/`cmd_zone_reorder` — публичный контракт не меняется
(требование 3, AC-5): `catalog`/`doctor`/`auto._wait_for_zone` продолжают
звать `blocking_conflict` как раньше и корректно видят новую занятость,
потому что она отражается в том же `_occupies`.

Архитектурно не значимо — правка одного модуля по образцу уже принятого
в кодовой базе приёма (CAS `set_state`), ADR не заводится.

## Шаги

1. `orchestrator/zone_lock.py`: константа `CLAIM_ACTION`, приватная
   `_CLAIM_RELEASED_ACTION`; вынесение текста отказа в `_refusal_text`
   (общий для `refusal`/`claim`); переписанный `_occupies` (латест-wins,
   три маркера вместо двух через `_visit_has_action`, которая удаляется
   как более не используемая); новые `claim`, `claimed_but_not_started`,
   `release_claim`.
2. `orchestrator/runner.py`: `_cmd_run` — замена `zone_lock.refusal` на
   `zone_lock.claim`; вынесение остатка тела в `_run_developer_step`;
   `try/finally` со снятием захвата по `claimed_but_not_started`.
3. Юнит-тесты `tests/test_zone_lock.py` — функции `claim`/
   `claimed_but_not_started`/`release_claim` в изоляции (успех, конфликт,
   «уже занимает сама», актор снятия/захвата), не дублируя многопоточный
   сценарий гонки и полный проход `runner._cmd_run` — те уже покрыты
   приёмочными тестами `tasks/01M28NWPS3PJHJAT4APXRY7MF7/
   acceptance_tests/` (AC-1, AC-3, AC-6, AC-7 гоняют реальный `cmd_run`
   целиком; отдельный мок-дубль этого же пути в юнитах ничего нового не
   ловил бы).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 2 |
| 2 | 1, 2 |
| 3 | 1 |

## Влияние на систему

`zone_lock._occupies` — единственная точка правды занятости зоны,
читаемая `blocking_conflict`/`catalog._zone_wait_suffix`/
`doctor.hung_test_watchdog`/`auto._wait_for_zone` (SPEC AC-5) — они не
трогаются этой задачей вовсе и корректно видят новый маркер, потому что
зовут `blocking_conflict` целиком, не копируют проверку. Риск —
расхождение поведения `_occupies` для существующих сценариев (два старых
маркера); закрыт тем, что латест-wins на журнале БЕЗ новых маркеров
математически эквивалентен старому `OR` (ни `RELEASE_ACTION`, ни
`"agent run started"` никогда не сопровождаются `"zone claim released"` в
существующих тестах) — и подтверждается прогоном `tests/test_zone_lock.py`
и `tests/test_zones_gate.py` (AC-8, приёмочный тест уже гоняет оба файла
дочерним процессом).

Новая транзакция `BEGIN IMMEDIATE` в `claim()` — та же диалектная
конструкция, что уже используют `store.next_task_number`/`store.
set_state` (комментарий `store.py` про переносимость на Postgres —
`SELECT ... FOR UPDATE` — эту задачу не трогает, схему не меняем).
Откат изменения — правка `runner._cmd_run` обратно на `zone_lock.
refusal` и удаление новых имён `zone_lock.py`; ничего постороннего не
затронуто (зоны задачи — `orchestrator/runner.py`,
`orchestrator/zone_lock.py`, `orchestrator/store.py`, `tests/`;
`orchestrator/store.py` в итоге не тронут — существующего `journal`
хватило).

Гейты/лимиты/инварианты не ослабляются: `BLOCKING_STATES`, диапазон
пребывания, фильтр актора `developer` для `AGENT_STARTED_ACTION` —
все сохранены буквально.

## Риски

- `_occupies` теперь читает журнал за O(число записей задачи) на КАЖДЫЙ
  вызов `claim`/`claimed_but_not_started` (было — то же самое и раньше в
  `blocking_conflict`/`refusal`) — журнал одной задачи в пределах
  пребывания короткий (десятки записей), заметного замедления не
  ожидается.
- `claim()` держит эксклюзивную блокировку записи БД (`BEGIN IMMEDIATE`)
  на время своего маленького чтения+записи — не на весь `_cmd_run`:
  окно блокировки — миллисекунды, не секунды сборки промпта.

## Предложения системе
