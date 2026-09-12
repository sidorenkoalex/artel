---
task: 01M291EPQ2VFGCHZTXXC81616V
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Очередь мержа FIFO вместо отказа, мёртвые записи очереди, doctor

## Подход

Второй `approve` на занятый мьютекс merge-окна (`orchestrator/merge_lock.py`,
SPEC T053) сейчас сразу `sys.exit`'ит именованным отказом
(`orchestrator/fsm_merge_gate.py::_cmd_approve_merge_gate_cycle`, вызов
`merge_lock.acquire`). Вместо этого он должен встать в FIFO-очередь и
опрашивать освобождение окна, забирая его сам — без нового ручного
`approve`.

Новый модуль `orchestrator/merge_queue.py` (по образцу `zone_lock.py` для
механики ожидания/очереди и `merge_lock.py` для CRUD-приёма) несёт всю
логику: регистрация ожидающего в таблице `merge_queue` (новая, `schema.py`,
тем же приёмом, что `merge_locks`), пруна мёртвых записей (тот же признак,
что `merge_lock._holder_is_dead` — требование 5), определение головы
очереди (FIFO по `enqueued_ts`), цикл опроса с интервалом
`MERGE_GATE_CI_WAIT_POLL_SEC` и потолком `MERGE_QUEUE_WAIT_CEILING_SEC`
(новая константа, `config.py`, дефолт 7200 сек), добавка `status`
(`catalog.cmd_status`, по образцу `_zone_wait_suffix`) и журналирование
входа в очередь.

`_cmd_approve_merge_gate_cycle` меняется минимально: там, где раньше был
`sys.exit(refusal)` при занятом мьютексе, теперь вызывается
`merge_queue.wait_for_window(conn, task_id, sid)` — она либо возвращается с
уже взятым этой сессией мьютексом (после освобождения и получения головой
очереди), либо сама завершает процесс `sys.exit`'ом по истечении потолка
очереди. Дальше цикл продолжает работать буквально как раньше (тело гейта,
ожидание CI вне мьютекса) — часть 1 (SPEC T087, держание мьютекса на весь
цикл `approve`, включая ожидание CI) не трогается ни строкой.

`doctor` получает новую проверку `check_merge_queue`
(`orchestrator/doctor/leases.py`, рядом с `check_merge_lock`): видимость
живых записей очереди + отдельный fail-`Check` на мёртвые (тот же признак
мёртвости, что и пруна очереди в `merge_queue.py` — не отдельная копия
логики). Без auto-ack/incident-алерта (в отличие от `check_merge_lock`):
AC-9 требует только видимость в `doctor.all_checks`, добавление алертной
обвязки было бы расширением объёма задачи сверх критерия приёмки.

## Шаги

1. `config.py`: константа `MERGE_QUEUE_WAIT_CEILING_SEC = 7200`.
2. `schema.py`: таблица `merge_queue` (SCHEMA + `migrate()`, тем же
   приёмом, что `merge_locks`).
3. `store.py`: CRUD `merge_queue` — `merge_queue_rows`,
   `enqueue_merge_wait`, `touch_merge_queue_heartbeat`, `dequeue_merge_wait`,
   `delete_merge_queue_row`.
4. Новый модуль `orchestrator/merge_queue.py`: `_prune_dead_entries`,
   `_head_task_id`, `_current_holder_id`, `queue_wait_minutes`,
   `wait_suffix`, `wait_for_window` (требования 1-5).
5. `fsm_merge_gate.py`: `_cmd_approve_merge_gate_cycle` — отказ мьютекса
   ведёт в `merge_queue.wait_for_window`, не в `sys.exit` (требования 1-4).
6. `catalog.py`: `cmd_status` несёт добавку `merge_queue.wait_suffix`
   (требования 1-2, AC-2).
7. `orchestrator/doctor/leases.py` + `doctor/__init__.py` (импорт
   `merge_lock`, экспорт `check_merge_queue`) + `doctor/cli.py::all_checks`
   — новая проверка `check_merge_queue` (требование 6, AC-9).
8. Регенерация `docs/codebase-map.md` (новый модуль).
9. Юнит-тесты на `merge_queue.py` (`tests/test_merge_queue.py`) +
   прогон приёмочной планки задачи и существующих
   `tests/test_merge_lock.py`/`tests/test_merge_gate_ci_wait.py` (AC-10).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 4, 5 |
| 2 | 3, 4 |
| 3 | 1, 4 |
| 4 | 5 (не тронуто — существующий расчёт `start`/`deadline`) |
| 5 | 3, 4 |
| 6 | 7 |
| 7 | 5, 9 (AC-10) |

## Влияние на систему

Новая таблица `merge_queue` — аддитивная миграция (`add_column`-эквивалент
`CREATE TABLE IF NOT EXISTS`), не трогает существующие таблицы/колонки.
Единственная точка входа механики очереди — `merge_queue.wait_for_window`,
вызываемая ТОЛЬКО там, где раньше был безусловный `sys.exit(refusal)`:
поведение при СВОБОДНОМ мьютексе (`refusal is None`) не меняется ни на
строку — `merge_lock.acquire`/`release`/`run_window` (SPEC T053) и цикл
ожидания CI (SPEC T087) остаются нетронутыми, что и проверяет AC-10 —
существующие планки `test_merge_lock.py`/`test_merge_gate_ci_wait.py`
мокают `merge_lock.acquire` напрямую (всегда возвращая `None`) или мокают
`_cmd_approve_merge_gate` целиком, так что новую ветку (очередь) они не
задевают вовсе.

Потолок ожидания очереди (`MERGE_QUEUE_WAIT_CEILING_SEC`, до 2 часов) —
блокирующий цикл `time.sleep` внутри вызова `approve`: тот же класс
устройства, что уже несёт `_wait_for_branch_ci_green` (потолок CI) — не
новый класс риска для системы, только новая точка того же механизма.
Откат — ревert коммита; таблица `merge_queue` остаётся пустой (никто её не
пишет) и безвредна.

## Риски

- Пруна мёртвых записей вызывается на каждом опросе КАЖДОГО участника
  очереди (не только головы) — при большой очереди это O(N) SELECT на
  каждый опрос каждого участника, то есть O(N²) в худшем случае. При
  ожидаемом размере очереди (единицы задач одновременно на `merge_gate`)
  это не проблема; при росте параллельности стоит вынести саму пруну на
  голову очереди отдельным шагом, если станет заметно.

## Предложения системе

- Ветка задачи была заведена от пина main (699fa124), в котором ещё не
  было ни части 1 (01M291EJMA, зависимость этой задачи), ни поделённого
  родителя (01M29284PT) — оба смержены в main уже ПОСЛЕ отвода зоны этой
  задаче, что дало неизбежный конфликт подтяжки в `fsm_merge_gate.py`/
  `catalog.py`/`docs/codebase-map.md` на шаге `merge_gate` (закрыт этим
  же шагом, слияние см. коммит "слияние main — очередь merge_queue
  встроена перед мьютексом части 1"). Явная зависимость («часть 2 из 2,
  зависит от уже смерженной части 1») была в самом SPEC — возможно,
  `cmd_new`/зона могли бы предупреждать при заведении задачи, если
  указанная задача-зависимость (или родитель деления) на момент старта
  ещё не смержена в main, чтобы конфликт был виден раньше отдельного
  цикла ревью/эскалации.
