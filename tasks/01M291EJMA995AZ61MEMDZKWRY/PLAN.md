---
task: 01M291EJMA995AZ61MEMDZKWRY
type: plan
author_role: developer
status: ready        # draft | ready | approved
schema_version: 5    # версия формата артефакта, см. scripts/guard.py
---

# PLAN: Мьютекс merge-окна держится на весь цикл approve merge_gate

## Подход

Сегодня `_cmd_approve_merge_gate_cycle` (orchestrator/fsm_merge_gate.py)
берёт/отпускает мьютекс `merge_locks` (`merge_lock.acquire`/`release`)
ВНУТРИ `while True`, вокруг каждого отдельного захода в тело гейта
(`_cmd_approve_merge_gate`), и отпускает его сразу после каждого
захода — включая исход `("wait", branch)`, после которого цикл уходит
в `_wait_for_branch_ci_green` (опрос CI вне мьютекса, SPEC T087). Это и
есть дыра: на время ожидания CI окно свободно, параллельный `approve`
другой задачи может войти и утянуть main вперёд.

Изменение — чисто структурное, без новых состояний FSM и без изменения
`orchestrator/merge_lock.py` по существу (требование 7):

1. `_cmd_approve_merge_gate_cycle`: `merge_lock.acquire` выносится ДО
   `while True`, `merge_lock.release` — в `finally` ВОКРУГ всего цикла
   (не вокруг каждого захода). Тело цикла продолжает чередовать
   `_cmd_approve_merge_gate`/`_wait_for_branch_ci_green` как сегодня,
   просто уже не трогая мьютекс само.
2. `orchestrator/merge_lock.py`: новая маленькая функция
   `touch_heartbeat(conn)` — продлевает `heartbeat_ts` ТЕКУЩЕГО
   держателя (если строка есть), сохраняя `task_id`/`session_id`/`pid`/
   `hostname` — тем же путём, что и `acquire` уже делает при
   повторном входе своей сессии (`store.merge_lock_row` +
   `store.set_merge_lock`, обе уже существуют, `store.py` вне зон этой
   задачи и не трогается). Не требует `session_id` аргументом: строка
   в таблице ровно одна на весь пульт (требование 2 SPEC T053), поэтому
   «текущий держатель» однозначен без сверки.
3. `_wait_for_branch_ci_green`: на каждой итерации опроса CI (до
   решения «зелёный/красный/потолок») зовёт `merge_lock.touch_heartbeat`
   — heartbeat продлевается на каждом опросе, а не только на входе/
   выходе из тела (требование 3, AC-2). Сигнатура функции не меняется —
   держатель мьютекса не идентифицируется по параметру, только по
   единственной строке таблицы.

Перехват мёртвого держателя (`merge_lock.acquire`, `_holder_is_dead`)
не трогается вовсе — он уже смотрит на `heartbeat_ts`/`pid` строки,
работает одинаково независимо от того, сколько времени строка живёт
между вызовами `acquire`.

## Шаги

1. `orchestrator/merge_lock.py`: добавить `touch_heartbeat(conn)`.
2. `orchestrator/fsm_merge_gate.py`: перенести `acquire`/`release`
   вокруг `_cmd_approve_merge_gate_cycle` целиком; добавить вызов
   `merge_lock.touch_heartbeat(conn)` в `_wait_for_branch_ci_green` на
   каждой итерации опроса.
3. `tests/test_merge_gate_ci_wait.py`: переписать
   `OuterCycleDeadlineTest.test_mutex_acquired_and_released_around_each_body_call`
   под новое поведение (мьютекс берётся один раз, остаётся взятым между
   двумя заходами в тело, отпускается один раз) — требование 7/AC-7 из
   SPEC. Соседний `test_ceiling_not_reset_by_a_second_wait_outcome` не
   трогается.
4. Прогнать приёмочные тесты задачи
   (`tasks/01M291EJMA995AZ61MEMDZKWRY/acceptance_tests/`),
   `tests/test_merge_gate_ci_wait.py`, `tests/test_merge_lock.py`,
   `tests/test_fsm_merge_gate_scratch_worktree_cleanup.py` (соседний
   модуль, чтобы не задеть плотницкий merge) — все в переднем плане с
   таймаутом.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 2 |
| 2 | 2 |
| 3 | 1, 2 |
| 4 | 2 |
| 5 | 1, 2 (не трогается) |
| 6 | 2 (не трогается) |
| 7 | 1, 2 (не трогается по существу) |

## Покрытие критериев приёмки

| AC | Шаг |
|---|---|
| AC-1 | 2 |
| AC-2 | 1, 2 |
| AC-3 | 2 |
| AC-4 | 2 (не трогается) |
| AC-5 | 2 |
| AC-6 | 1, 2 (не трогается) |
| AC-7 | 2, 3 |

## Влияние на систему

Зона изменения — `orchestrator/fsm_merge_gate.py` (внешний цикл гейта)
и `orchestrator/merge_lock.py` (новая функция продления heartbeat, без
изменения существующих `acquire`/`release`/`run_window`). Порядок
состояний FSM, тело гейта (`_cmd_approve_merge_gate`) и его внутренние
шаги (подтяжка, push, плотницкий merge, снимок артефактов) не
затронуты — меняются только точки вызова `acquire`/`release` вокруг
них.

Единственный побочный эффект для системы — окно, в течение которого
второй `approve` другой задачи получает отказ «занято сессией …»,
удлиняется с «время одного захода в тело» до «время всего цикла,
включая ожидание CI» (до `MERGE_GATE_CI_WAIT_CEILING_SEC` = 3600 сек).
Это ровно цель SPEC (устранение гонки 11.09), не побочный ущерб;
именованный отказ и текст не меняются (требование 6, не ослабляется).
Перехват мёртвого держателя (`_holder_is_dead`) продолжает работать
без изменений — решающим фактором остаётся продлённый `heartbeat_ts`,
а не специальная логика.

Откат — тривиальный: вернуть `acquire`/`release` внутрь `while True`
(git revert одного коммита), `touch_heartbeat` — мёртвый код без
вызовов, теста `test_ac2_...` в этом случае снова станет красным (что
и было до этой задачи).

Тесты `tests/test_merge_lock.py` (AC-6) не трогаются и не ослабляются —
новая функция `touch_heartbeat` не меняет поведение `acquire`/
`release`/`run_window`; приёмочный тест
`test_merge_lock_regression.py` прогоняет этот файл как регресс-планку.

## Риски

- `_wait_for_branch_ci_green` вызывается и напрямую в существующих
  юнит-тестах без предварительного `merge_lock.acquire` (например,
  `tests/test_merge_gate_ci_wait.py::WaitLoopContinuesOnNonFinalStatusTest`)
  — `touch_heartbeat` в этом случае просто не находит строку
  (`store.merge_lock_row` вернёт `None`) и молча ничего не делает,
  тесты не задеты.

## Предложения системе
