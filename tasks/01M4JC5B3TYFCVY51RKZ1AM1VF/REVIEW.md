---
task: 01M4JC5B3TYFCVY51RKZ1AM1VF
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: Очередь зоны решает старт

## Фаза A — план
- Таблица покрытия полна: требования 1–8 сопоставлены шагам 1–3.
- Шаги размером с MR: правило старта и показ в `zone_lock.py`, показ в
  `catalog`/`doctor`, юнит-тесты и карта.
- Подход соответствует архитектуре: один узел `_start_conflict` для
  `blocking_conflict`/`claim`/`refusal`, форма тройки
  `blocking_conflict` не меняется, `auto.py`/`runner.py` не тронуты
  (требование 7). Отложенные импорты `lease`/`merge_after` обоснованы
  циклами импорта.
- «Влияние на систему» сходится с diff: изменены только
  `zone_lock.py`, `catalog.py`, `doctor/hung_test_watchdog.py`, в
  `tests/test_zone_lock.py` только добавления, карта свежая. Откат —
  revert. Риск с текстом `wait_enter_action` («держит <id>» для отказа
  очереди) назван честно, его правка вне зоны.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `_start_conflict` → `_queue_members` (`_shared_zone`, с вложенностью) → первая по `queue_order` держащая; отказ «ждёт очереди зоны: впереди <id>». |
| 2 | OK | `queue_order`: позиции Оператора — первыми, остальные топологически по `_ancestors` (транзитивно), внутри — прежний ключ; цикл не зависает. |
| 3 | OK | `_waiting_dependency` проверяется до порядка — `zone-reorder` его не обходит (AC-4). |
| 4 | Не так | Живость цикла проверяется `lease.is_live`, а он смотрит только на возраст heartbeat (≤ 7200 с) и не проверяет pid. Если процесс цикла умер, задача ещё до 2 ч держит очередь — R1-F1. Пауза и эскалация — OK. |
| 5 | OK | `queue_wait`/`queue_position` берут тот же состав и порядок, пометка «не держит очередь» стоит после «очередь N/M»; при занятой зоне — «занята <id>». |
| 6 | OK | `cmd_zone_reorder([])` — `sys.exit` с подсказкой до цикла записи. |
| 7 | OK по коду, нет сторожа | Отказ доходит до `auto._wait_for_zone` через тройку `blocking_conflict`. Но в `tests/` это свойство ничем не защищено — R1-F2. |
| 8 | OK | Существующие методы `tests/` не изменены, в diff `tests/test_zone_lock.py` только добавления. |

## Замечания

- major — orchestrator/zone_lock.py:517 (`_holds_queue`, вызов
  `lease.is_live`) — в требовании 4 «цикл `run`/`auto` по задаче не
  идёт» проверяется по одному возрасту heartbeat. `lease.is_live`
  (orchestrator/lease.py:363–378) не проверяет pid. После kill -9,
  закрытого терминала или перезагрузки строка lease остаётся «живой»
  ещё `LEASE_STALE_AFTER_SEC` = 7200 с. Всё это время мёртвая задача
  стоит впереди очереди: `claim`/`run`/`auto` всех задач за ней получают
  «ждёт очереди зоны: впереди <мёртвая>» на свободной зоне, а `status`
  не ставит ей пометку «не держит очередь». Это как раз простой
  свободной зоны, который задача должна была убрать. Воспроизведено
  исполнением (см. «Проверено исполнением»): A и B живы, pid lease A
  подменён на мёртвый 999999, `liveness._pid_alive` → False,
  `lease.is_live(A)` → True, `claim B` → «зона … свободна, ждёт очереди
  зоны: впереди A». Предложение: считать держащей очередь только задачу,
  у которой lease жив тем же правилом, что в
  `lease.foreign_live_lease` (lease.py:258–282: heartbeat свежий И pid
  адресуем на своём host; pid чужого host считается живым). Например,
  вынести это правило в общую функцию `lease` или вызвать его из
  `_holds_queue`. Добавить в `tests/` тест на lease с мёртвым pid.
- major — tests/ (свойство требования 7 / AC-8 об `auto`) — отказ
  очереди держит `auto._wait_for_zone` в ожидании, но проверяет это
  только планка `acceptance_tests/test_ac8_auto_wait_for_queue.py`
  («Группа: разовый»). После мержа её не гоняет ни CI, ни автогейт
  (ADR-0018 п. 3). Проверено временной мутацией
  `blocking_conflict`: `if conflict is None or conflict[0] != _OCCUPIED:
  return None` (отказы очереди и зависимости не доходят до
  `blocking_conflict`, а `claim` по-прежнему отказывает). Набор
  `tests/test_01m4jc5b3tyfcvy51rkz1am1vf_zone_queue_start.py`,
  `tests/test_zone_lock.py`,
  `tests/test_01m484rnv3qbdy3b0m16j916zp_zone_lock_projects.py`,
  `tests/test_auto_cycle.py` остался зелёным: 111 passed. Покраснела
  только планка (1 failed). Если позже `blocking_conflict` по ошибке
  вернётся к одной занятости, `auto` молча выйдет из ожидания и упрётся
  в отказ `claim`, а сторожа нет. Предложение: добавить в `tests/`
  тест (например, в `tests/test_zone_lock.py` на публичный
  `blocking_conflict`, или в `tests/test_auto_cycle.py::WaitForZoneTest`,
  где закрытое `_wait_for_zone` уже используется) с заявкой «Ловит
  мутацию: `blocking_conflict` возвращает только конфликт занятости».
  Тест должен проверять, что для задачи не впереди очереди на свободной
  зоне `blocking_conflict` возвращает тройку с id задачи впереди, а для
  зависимости — с id зависимости.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | fixed | orchestrator/zone_lock.py:517 | `_holds_queue` считает цикл живым по `lease.is_live` (только возраст heartbeat, без проверки pid) | После падения процесса цикла задача до 2 ч держит очередь при свободной зоне, задачи за ней не стартуют, показ без пометки «не держит очередь» | fixed: `_holds_queue` проверяет `lease.foreign_live_lease(conn, id, None)` (heartbeat И pid на своём host); тест `tests/test_zone_lock.py::ZoneLockTest::test_lease_with_dead_pid_does_not_hold_queue` (claim и `queue_wait` при мёртвом pid), красный на мутации «только heartbeat» |
| R1-F2 | fixed | tests/ (нет файла; свойство `zone_lock.blocking_conflict` → `auto._wait_for_zone`) | Отказ очереди и зависимости через `blocking_conflict` (требование 7, AC-8 об auto) проверяет только разовая планка | После мержа регресс `blocking_conflict` к одной занятости ничего в CI не покраснит (подтверждено временной мутацией: 111 passed) | fixed: `tests/test_zone_lock.py::ZoneLockTest::test_blocking_conflict_names_queue_head_and_waiting_dependency` — тройка с задачей впереди и с ждущей зависимостью; красный на мутации «`blocking_conflict` только `_OCCUPIED`» |

## Вердикт
changes_requested — исправить R1-F1 (проверять живость цикла с учётом
pid) и R1-F2 (сторож в `tests/` на отказы очереди и зависимости через
`blocking_conflict`). Остальные требования реализованы верно.

## Проверено исполнением
- `python3 -m pytest -q tests/test_01m4jc5b3tyfcvy51rkz1am1vf_zone_queue_start.py tests/test_zone_lock.py tests/test_01m484rnv3qbdy3b0m16j916zp_zone_lock_projects.py tests/test_auto_cycle.py`
  — 111 passed, 49 subtests passed.
- `artel.py plank-run 01M4JC5B3TYFCVY51RKZ1AM1VF` — 1 passed, код 0.
- R1-F1: временный тест в песочнице `ZoneQueueSandbox` (файл удалён
  после прогона). A и B живы, у lease A pid=999999 →
  `_pid_alive` False, `is_live(A)` True, `claim B` отказал «ждёт
  очереди зоны: впереди A» на свободной зоне.
- R1-F2: временная мутация `blocking_conflict` (только `_OCCUPIED`) — те же
  четыре файла `tests/` 111 passed, `plank-run` — 1 failed. Код
  возвращён `git checkout`, `git status` чистый.
- `python3 scripts/codebase_map.py` — diff только в `built_at_sha`, карта
  свежая (изменение откатено).

## Предложения системе
- `lease.is_live` (heartbeat без pid) и `lease.foreign_live_lease`
  (heartbeat + pid) — два разных понятия «живой lease» в одном модуле.
  Новые потребители берут первое по имени и получают 2-часовое окно
  «живого мертвеца». Стоит переименовать `is_live` (например, в
  `heartbeat_fresh`) или дать общий `is_running` с проверкой pid.
