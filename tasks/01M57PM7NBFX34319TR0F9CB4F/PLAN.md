---
task: 01M57PM7NBFX34319TR0F9CB4F
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Несколько проектов: мьютекс и очередь мержа по проекту

## Подход
Схема не меняется (SPEC «Не входит»): проект строки `merge_locks`/`merge_queue`
вычисляется `LEFT JOIN tasks` по `task_id` с нормализацией
`COALESCE(NULLIF(t.target, ''), DEFAULT_TARGET)` — ровно правило
`store.task_target` (требование 13: пустой, `NULL`, нет строки задачи — артель).

- `orchestrator/store.py`: новые `merge_lock_rows` (все строки с `rowid` и
  `target`, по порядку вставки), `project_merge_lock_row(conn, target)`,
  `touch_merge_lock_heartbeat(conn, rowids, ts)` (UPDATE только heartbeat по
  `rowid`), `project_merge_queue_rows(conn, target)` (FIFO очереди проекта).
  `set_merge_lock` сносит только строку проекта задачи `task_id`, не всю
  таблицу. `merge_lock_row` — прежняя сигнатура, детерминированно первая
  строка по `rowid`. Снятие по проекту — прежний `release_merge_lock(conn,
  session_id, pid)`: строка процесса принадлежит ровно одному проекту, и
  снятие по процессу строки других проектов не трогает (AC-5, AC-11) —
  отдельная функция с фильтром проекта ничего не добавила бы.
- `orchestrator/merge_lock.py`: `acquire` читает строку проекта задачи;
  тексты отказа и перехвата прежние. `touch_heartbeat(conn, task_id=None,
  session_id=None)`: с `task_id` — продлевает только строку того же проекта,
  той же задачи и сессии (по умолчанию `session.resolve_session_id`); без
  `task_id` — одна строка продлевается как прежде (AC-17), при нескольких
  строках — только строки текущей сессии (ANSWER-2, ответ 2). Чтение и запись
  под тем же `BEGIN IMMEDIATE`.
- `orchestrator/merge_queue.py`: `_head_task_id`/`_current_holder_id`/
  `_current_holder_label` получают необязательный `target` (без него —
  прежний исход, решение О-2); `wait_for_window` и `wait_suffix` передают
  проект ждущей задачи. Пруна мёртвых записей прежняя (по всей очереди).
- `orchestrator/fsm_merge_gate.py`: `:355` и `:631` →
  `touch_heartbeat(conn, task_id, session.resolve_session_id())`
  (сигнатуры `_wait_for_branch_ci_green`/`_await_main_ci` не меняются),
  `:1474` → `touch_heartbeat(conn, task_id, sid)`.
- `orchestrator/notes.py`: `_silence_window_reason` перебирает все строки
  мьютекса; первая живая строка артели (или неопределённого проекта)
  открывает окно.
- `orchestrator/doctor/leases.py`: `check_merge_lock` — проверка на каждую
  строку (`_merge_lock_row_check`); `orchestrator/doctor/lease_alerts.py`:
  `_merge_lock_alert_live(message, rows)` — условие живо, пока есть строка с
  теми же `task_id`/`session_id` и мёртвым pid, по всем строкам.

Причина возврата (инцидент целостности) — ответ Оператора ANSWER-2: его
пункты закрыты здесь (раздел «Не входит», строка матрицы, свои тесты
`tests/test_merge_lock_by_project.py`).

## Шаги
1. store + merge_lock + merge_queue + fsm_merge_gate + notes + doctor (один
   MR), карта `docs/codebase-map.md` регенерирована.
2. Свои тесты `tests/test_merge_lock_by_project.py` по ANSWER-2 пп. 2-4:
   - `LegacyTouchHeartbeatTest` — `touch_heartbeat(conn)` при строках двух
     проектов продлевает только строку текущей сессии, оба порядка вставки;
   - `WaitForWindowOtherProjectQueueTest` — более ранняя запись очереди
     другого проекта и живой держатель другого проекта не задерживают
     `wait_for_window` (глобальный FIFO даёт паузу → красный);
   - `WaitTextsAnyOrderTest` — строки трёх проектов во всех 6 порядках
     вставки: отказ `acquire`, запись журнала входа в очередь и добавка
     `status` называют держателя проекта ждущей задачи.
   Каждый проверен временной мутацией (продление всех строк; голова по всей
   очереди; держатель — первая строка таблицы) — красный, код возвращён.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 (`acquire` по `project_merge_lock_row`, `set_merge_lock` по проекту) |
| 2 | 1 (тексты/перехват/`release` прежние) |
| 3 | 1 (`touch_heartbeat`, три вызова в `fsm_merge_gate`), 2 |
| 4 | 1 (`wait_for_window`, `_head_task_id(conn, target)`), 2 |
| 5 | 1 (пруна прежняя, голова — по проекту) |
| 6 | 1 (`_current_holder_label(conn, target)`), 2 |
| 7 | 1 (store) |
| 8 | 1 (необязательный `target`) |
| 9 | 1 (notes) |
| 10 | 1 (doctor) |
| 11 | 1 — файлы не тронуты, прогнаны зелёными |
| 12 | долгоживущие тесты задачи + шаг 2 |
| 13 | 1 (нормализация в SQL = `store.task_target`) |

## Матрица неослабления

| Что меняется | Свойство | Остаётся | Чем покрыто |
|---|---|---|---|
| мьютекс и очередь мержа по проекту | взаимное исключение и FIFO внутри проекта | да | `tests/test_merge_lock.py`, `tests/test_merge_queue.py` без изменений; долгоживущие тесты задачи |
| `suite_lock` (замок полных прогонов) | не больше N полных прогонов на машину | да — не меняется, общий для всех проектов (ресурс машины, не проекта; ANSWER-2, ответ 1) | прежние тесты `suite_lock` без изменений |
| `notes`/`doctor` по всем строкам | окно тишины по держателю артели; инцидент мёртвого держателя | да, при любом числе и порядке строк | `tests/test_notes.py`, `tests/test_doctor.py`, `tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py` без изменений; долгоживущие тесты задачи |

## Не входит
- Замок полных прогонов `suite_lock` (`orchestrator/suite_lock.py`) остаётся
  общим для всех проектов — ресурс машины, не проекта (ANSWER-2, ответ 1);
  не меняется.
- Колонка `target` в `merge_locks`/`merge_queue`, правка `schema.py`.

## Влияние на систему
- Внутри проекта поведение прежнее: `set_merge_lock` сносит строку своего
  проекта, `acquire` читает её под `BEGIN IMMEDIATE` — гонка двух задач
  одного проекта закрыта тем же замком SQLite (на всю БД).
- Между проектами исключение снимается намеренно (ТЗ). Общие ресурсы
  (главная копия, журнал, пин, `suite_lock`) не затрагиваются — сверка SPEC.
- Читатели строки мьютекса вне зон (`tests/…`, `merge_lock_row`) получают
  прежнюю сигнатуру; при одном проекте исход тот же.
- Тесты, гейты, лимиты не ослаблены; `tests/test_merge_lock.py`,
  `test_merge_queue.py`, `test_notes.py`, `test_doctor.py`,
  `test_merge_gate_ci_wait.py`, `test_main_ci_line.py`, окно тишины — не
  тронуты и зелёные.
- Откат — revert merge-коммита задачи; схема БД не менялась.

## Риски
- Строка мьютекса, чья задача сменила `target` во время окна, сменит и
  проект — сценарий вне штатного (target задаётся при `new`).
- Без `task_id` и при нескольких строках `touch_heartbeat(conn)` продлит
  строки текущей сессии во всех проектах — прежняя форма вызова больше не
  используется кодом пульта, только как совместимость.

## Предложения системе
- Шаг роли: `pytest -n 8` в рабочем каталоге падает «node down» — сторожу
  `conftest.py` стоит назвать причину явнее (сейчас — пустой «no tests ran»).
