---
task: 01M4JC5B3TYFCVY51RKZ1AM1VF
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Очередь зоны решает старт

## Подход
Правило старта живёт в `orchestrator/zone_lock.py` одним узлом
`_start_conflict(conn, id, t) -> (вид, путь, id, состояние) | None`, через
который проходят и `blocking_conflict` (возвращает прежнюю тройку — её
распаковывают `auto._wait_for_zone`/`catalog`/`doctor`), и `claim`/
`refusal` (текст отказа выбирается по виду). Так отказ доходит до `run` и
до цикла ожидания `auto` без правки `runner.py`/`auto.py` (требование 7).

Порядок проверки в `_start_conflict` (задача в `in_dev`, свои зоны есть,
сама зону ещё не занимает):
1. Держатель пересекающейся зоны (`_occupies`) — прежний отказ «занята
   <id>» (требование 5, последняя фраза).
2. Состав очереди `_queue_members` — ожидающие задачи `in_dev` того же
   проекта, не занимающие зону, чьи собственные зоны пересекаются с
   зонами задачи (`_shared_zone`/`_paths_overlap`, с вложенностью), плюс
   сама задача. Задача в эскалации — не `in_dev`, по определению SPEC
   («ожидающая задача — задача в `in_dev`») в состав не входит и очередь
   не держит.
3. Незавершённая зависимость `merge_after` в составе очереди — отказ «ждёт
   зону ради зависимости <id>» (требование 3); проверяется до порядка,
   поэтому `zone-reorder` его не обходит (AC-4).
4. Первая по `queue_order` задача, которая держит очередь
   (`_holds_queue`: живой цикл — правило `lease.foreign_live_lease`:
   heartbeat свежий И pid адресуем на своём host, не `paused`, без
   отказа п.3; `lease.is_live` смотрит только на heartbeat и мёртвый
   процесс держал бы очередь до 2 ч — REVIEW R1-F1); сама проверяемая задача считается держащей (её `run`/
   `auto` держат lease в момент вызова; пауза отказывает дальше своим
   штатным отказом и захват снимается `release_claim`). Первая — не сама
   задача → отказ «ждёт очереди зоны: впереди <id>» (требования 1, 4).

`queue_order`: явная позиция (`zone_queue_position`) — как сейчас, впереди
всех; остальные — топологически по `merge_after` (транзитивно через
задачи вне набора, цикл не зацикливает — оставшиеся берутся по прежнему
ключу), среди готовых — прежний ключ (approve, затем `updated_at`).

Показ: новый `zone_lock.queue_wait(conn, id, t) -> QueueWait | None`
(путь, причина, позиция, всего, держит ли очередь) — тот же состав и
порядок; `catalog._zone_wait_suffix` и `doctor.check_zone_waits` строят
строку из него, добавляя «не держит очередь» после «очередь N/M».
Задача, впереди которой никого нет, но которая сама очередь не держит,
показывается без причины («очередь 1/3, не держит очередь») — AC-6.
`queue_position(conn, id, path=None)` считает по тому же составу
(`path`, если передан, сужает его до пересекающих этот путь — прежняя
семантика существующих тестов).

`cmd_zone_reorder([])` — `sys.exit` с подсказкой `zone-reorder <id1>
<id2> ...` до цикла записи (требование 6).

Импорты `lease` и `merge_after` — внутри функций: `lease` -> `runner` ->
`zone_lock`, `merge_after` -> `scripts/guard` -> `zone_lock` — на уровне
модуля это циклы.

## Шаги
1. `orchestrator/zone_lock.py`: `_start_conflict`, `_queue_members`,
   `_waiting_dependency`, `_holds_queue`, `QueueWait`/`queue_wait`, новый
   `queue_order`, `queue_position` по составу очереди, отказы `claim`/
   `refusal` по виду, `cmd_zone_reorder` без аргументов — отказ.
2. `orchestrator/catalog.py::_zone_wait_suffix`,
   `orchestrator/doctor/hung_test_watchdog.py::check_zone_waits` — показ
   из `queue_wait` с пометкой «не держит очередь».
3. Юнит-тесты в `tests/test_zone_lock.py` на свойства, не покрытые
   долгоживущим файлом задачи (транзитивная зависимость через задачу вне
   очереди, цикл `merge_after`, не-вложенные зоны под общим каталогом —
   разные очереди, запуск без зависимости в очереди); карта
   `scripts/codebase_map.py`.
4. Итерация 2 (REVIEW R1-F1, R1-F2): `_holds_queue` — живость цикла с
   проверкой pid (`lease.foreign_live_lease(conn, id, None)`); сторожа в
   `tests/test_zone_lock.py`:
   `test_lease_with_dead_pid_does_not_hold_queue`,
   `test_blocking_conflict_names_queue_head_and_waiting_dependency`
   (тройка `blocking_conflict` для отказа очереди и отказа зависимости).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1, 4 |
| 5 | 1, 2 |
| 6 | 1 |
| 7 | 1, 4 |
| 8 | 3 (существующие ожидания не меняются) |

## Влияние на систему
Меняется решение замка зон на свободной зоне: раньше проходила любая
ожидающая задача, теперь — только первая держащая очередь. При занятой
зоне поведение прежнее (тот же отказ и тот же держатель). `runner.py`/
`auto.py` не трогаются: тройка `blocking_conflict` сохраняет форму.
Существующие тесты `tests/test_zone_lock.py`, долгоживущий
`tests/test_01m484rnv3qbdy3b0m16j916zp_zone_lock_projects.py`,
`tests/test_auto_cycle.py::WaitForZoneTest` не меняются. Инварианты замка
(атомарность `claim` в `BEGIN IMMEDIATE`, `_occupies`) не ослабляются —
новая проверка лишь добавляет отказы. Откат — revert merge-коммита.

Проверено в шаге: долгоживущий файл задачи, `tests/test_zone_lock.py`,
`tests/test_01m484rnv3qbdy3b0m16j916zp_zone_lock_projects.py`,
`tests/test_auto_cycle.py`, тесты catalog/doctor/runner — зелёные;
планка (`plank-run`) — 1 passed. Новые юнит-тесты краснеют на заявленных
мутациях: временная подмена `_ancestors`, `_holds_queue` и
`_queue_members` через `mock`. `suite-run` №1: новых падений на ветке
0, одно падение есть и на базе 9738666a.

Итерация 2: те же четыре файла `tests/` (задачи, `test_zone_lock`,
`…zone_lock_projects`, `test_auto_cycle`) — 113 passed, 49 subtests;
`plank-run` — 1 passed, код 0. Мутации через `mock` (код на диске не
менялся): `lease.foreign_live_lease` подменён правилом «только
heartbeat» — `test_lease_with_dead_pid_does_not_hold_queue` красный;
`blocking_conflict`, отдающий только `_OCCUPIED`, —
`test_blocking_conflict_names_queue_head_and_waiting_dependency` красный;
без мутаций оба зелёные.

## Риски
- Запись входа в ожидание `auto` (`wait_enter_action`, текст в `auto.py`,
  только чтение) для отказа очереди звучит «держит <id> (in_dev)» —
  <id> там задача впереди, а не держатель. Текст меняется только правкой
  `auto.py` вне зоны.
- Стоимость: `status`/`doctor` для каждой ожидающей задачи читают журнал
  конкурентов (`_occupies`, lease) — квадратично по числу ожидающих
  `in_dev`; на десятках задач незаметно.

- Взаимная зависимость `merge_after` двух ожидающих одну зону задач дала
  бы обеим отказ «ждёт зону ради зависимости»; цикл отсекает проверка
  `merge_after.check` при заявлении значения, `queue_order` на цикле не
  зацикливается (юнит-тест).

## Предложения системе
- Нет команды «дождаться конца чужого `suite-run`»: при занятом замке
  полного прогона роль сама пишет цикл опроса pid
  (`orchestrator/suite_run.py`, отказ «повтори после его конца»).
- Итог `suite-run --wait` полного набора печатает «прошло: 1» при
  тысячах выполненных тестов (по логу ~4700), а лог прогона
  (`.artel/logs/`) роли недоступен на чтение — разобрать, какой тест падает
  и на базе, роль не может (`orchestrator/suite_run.py::render`).
