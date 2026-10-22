---
task: 01M5JPEHY8HY70R5T5AQ0EDSH1
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Зависимость merge_after с общей зоной держит старт последователя в любом незавершённом состоянии

## Подход
Правило «своя незавершённая зависимость ждёт ту же зону» переносится из состава очереди
(`_queue_members`, только `in_dev`) на весь граф `merge_after`:
`zone_lock._waiting_dependency(conn, t, own)` берёт транзитивные зависимости задачи
(`_ancestors`), отбрасывает отсутствующие в БД, `done`/`killed` и задачи другого проекта и
возвращает `(путь пересечения, id, состояние)` первой незавершённой с общей зоной
(`_shared_zone` от `_own_paths(zones)` — то же правило пересечения, что у очереди).
`_start_conflict` и `_holds_queue` зовут её; `queue_wait` (а через него `status` и `doctor`)
получает то же решение без своих правок. Держатель (`_occupier`) проверяется раньше —
порядок в `_start_conflict` не меняется. `_reason` для вида «зависимость» добавляет
« (<состояние>)».

`_ancestors` перестаёт падать на id, которого нет в БД (`store.get_task` → `SystemExit`):
такой id не раскрывается дальше. Это нужно AC-2 — без этого `claim` C с несуществующей
зависимостью падает и в `queue_order`, и в новом обходе; правка — одна проверка
`store.task_exists`, поведение для существующих задач прежнее.

`doctor.check_zone_waits`: для ожидающей задачи A, у которой `blocking_conflict` называет
задачу X и A ∈ `_ancestors(X)` (X зависит от A прямо или транзитивно), к детали дописывается
«взаимная блокировка с X по merge_after» и выходы: `answer X <файл> со строкой «Зависимости
мержа: …»` — прямо, если X в `escalated`/`in_dev`/`review`/`merge_gate`, иначе с оговоркой
«после перехода держателя в merge_gate: …»; `zone-release A` — всегда. Уровень `warn`.
Вся логика — внутри `check_zone_waits` (ограничение зоны SPEC), транзитивность — через
`zone_lock._ancestors` (тот же обход, что у `queue_order`; доступ doctor к закрытым
помощникам модулей уже есть: `liveness._pid_alive`, `merge_lock._holder_is_dead`).

## Шаги
1. `orchestrator/zone_lock.py`: `_waiting_dependency` по транзитивному графу, вызовы в
   `_start_conflict`/`_holds_queue`, текст `_reason`, устойчивость `_ancestors` к
   отсутствующему id.
2. `orchestrator/doctor/hung_test_watchdog.py::check_zone_waits`: строка взаимной
   блокировки и выходы.
3. Прогон долгоживущего файла задачи, `tests/test_zone_lock.py`,
   `tests/test_01m4jc5b3tyfcvy51rkz1am1vf_zone_queue_start.py`, тестов doctor/status; планка
   `plank-run`; регенерация карты.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 2 |
| 4 | 1, 2, 3 |
| 5 | 3 (тесты — долгоживущий файл test_author) |

## Влияние на систему
Затронуто решение о старте первого шага разработчика (`claim`, `refusal`,
`blocking_conflict` → `auto._wait_for_zone`) и показ `status`/`doctor`. Держатель зоны
по-прежнему проверяется первым; захват `claim` (транзакция `BEGIN IMMEDIATE`),
`zone-release`, `queue_order`, `zone-reorder`, отказы `merge_gate` и мандаты `answer` не
меняются. Новое правило может только добавить ожидание (зависимость вне `in_dev` теперь
держит старт) — это и есть требование. Существующие тесты не правятся. Откат — revert
одного коммита.

## Риски
- Зависимость в поздних состояниях (`review`…`merge_gate`), зону не занимающая, теперь тоже
  держит старт — по требованию 1 («любое состояние, кроме done и killed»).
- Цикл `merge_after`: `_ancestors` обходит его через `seen`; задача может ждать зону ради
  зависимости, которая ждёт ради неё, — это видно в `doctor` как обычное ожидание.

## Предложения системе
- `_ancestors` в `zone_lock.py` падал `SystemExit` на id `merge_after`, которого нет в БД (через `store.get_task`), в том числе в `queue_order`: проверка `if dep_row is not None` была мёртвой, потому что `get_task` никогда не возвращает `None`. Класс: «проверка на None после функции, которая завершает процесс».
