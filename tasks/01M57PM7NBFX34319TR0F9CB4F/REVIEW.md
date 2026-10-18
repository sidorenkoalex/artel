---
task: 01M57PM7NBFX34319TR0F9CB4F
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Несколько проектов: мьютекс и очередь мержа по проекту

## Фаза A — план
- Таблица покрытия PLAN закрывает требования 1–13, у каждого есть шаг.
- Шагов два, размер — один MR (код всех семи модулей зоны и свои тесты по ANSWER-2). Это соответствует обоснованию монолита в SPEC.
- Подход «проект строки через `LEFT JOIN tasks` + `COALESCE(NULLIF(t.target,''), DEFAULT_TARGET)`» не трогает схему (SPEC «Не входит») и повторяет `store.task_target` (`orchestrator/store.py:701-707`: нет строки → DEFAULT, `row["target"] or DEFAULT`).
- Пункты ANSWER-2 есть в PLAN: п.1 (`suite_lock` общий) — «Не входит» и строка матрицы; пп.2–4 — свои тесты в `tests/test_merge_lock_by_project.py`.
- Секция «Влияние на систему» совпадает с diff. Изменены только файлы зоны: 7 модулей, `tests/` (только добавления) и регенерированная карта. Путь отката описан.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `acquire` читает `store.project_merge_lock_row(conn, task_target(task_id))` (`merge_lock.py:71`). `set_merge_lock` удаляет только строки своего проекта (`store.py`, цикл по `merge_lock_rows`). |
| 2 | OK | Ветки отказа и перехвата, их тексты не изменены. `release` по-прежнему снимает строку по (session_id, pid). |
| 3 | OK | `_own_rows` сверяет проект, задачу и сессию. Все три вызова в `fsm_merge_gate` (`:355`, `:632`, `:1476`) передают `task_id` и сессию. Сигнатуры `_wait_for_branch_ci_green` и `_await_main_ci` не изменены. Прежняя форма без аргументов при одной строке ведёт себя как раньше, при нескольких строках продлевает только строки своей сессии (ANSWER-2 п.2). |
| 4 | OK | `wait_for_window` вызывает `_head_task_id(conn, target)`, а `project_merge_queue_rows` сохраняет прежний FIFO (`enqueued_ts, rowid`). Потолок ожидания и текст отказа по потолку не изменены. |
| 5 | OK | Мёртвые записи по-прежнему убираются по всей очереди до определения головы. |
| 6 | OK | Журнал входа в очередь и `wait_suffix` называют держателя через `_current_holder_label(conn, target)`; отказ `acquire` — держателя строки своего проекта. Минуты считаются по записи самой задачи (`queue_wait_minutes`). |
| 7 | OK | Добавлены `merge_lock_rows`, `project_merge_lock_row`, `touch_merge_lock_heartbeat` и `project_merge_queue_rows`. Прежние функции сохранены с прежними сигнатурами. `merge_lock_row` теперь детерминирован (`ORDER BY rowid`). |
| 8 | OK | `target=None` по умолчанию даёт прежнюю ветку (`merge_queue_rows` / `merge_lock_row`). |
| 9 | OK | `notes._silence_window_reason` перебирает все живые строки. Строка внешнего проекта пропускается без `return`, следующая строка артели открывает окно. |
| 10 | OK | `check_merge_lock` проверяет каждую строку через `_merge_lock_row_check`. `_merge_lock_alert_live` использует `any(...)` по всем строкам, поэтому живая строка другого проекта инцидент не снимает. |
| 11 | OK | `git diff --stat 14525c02...HEAD -- tests/` показывает только три новых файла, перечисленные в требовании файлы не тронуты. Все они зелёные (см. ниже). |
| 12 | OK | Долгоживущие тесты задачи и свои тесты детерминированы: подменённые часы и сон, без сети. |
| 13 | OK | Нормализация в SQL совпадает с `store.task_target`. AC-16 зелёный. |

## Замечания
Замечаний уровня blocker, major или minor нет.

Наблюдение без влияния на вердикт. В `fsm_merge_gate.py:355` и `:632` heartbeat продлевается по `session.resolve_session_id()`, а не по `sid`, с которым брали мьютекс. Расхождение возможно, только если `fsm.cmd_approve` вызвать с явным `session_id`, отличным от сессии окружения. Тогда `_own_rows` не найдёт строку, и долгое ожидание CI её не продлит. Почему это не дефект: CLI вызывает approve без `session_id` (`artel.py:2037`), и `lease.run_locked` разрешает его тем же `resolve_session_id(None)`, так что в рабочем пути значения совпадают. Форму сигнатуры прямо задаёт SPEC (требование 3: сигнатуры функций ожидания не меняются).

Проверка повторов (ADR-0020 п.4). `WaitTextsAnyOrderTest` и `WaitForWindowOtherProjectQueueTest` частично пересекаются с AC-10 и AC-8/AC-2 долгоживущего файла. Но каждый добавляет своё: три проекта во всех шести порядках; живой держатель другого проекта вместе с его более ранней записью в очереди. Кроме того, эти тесты прямо требует ANSWER-2 пп.3–4. Повтором не считаю.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: в итерации 1 замечаний нет.

## Вердикт
approved

## Проверено исполнением
- `python3 …/artel.py plank-run 01M57PM7NBFX34319TR0F9CB4F`: 2 passed, код выхода pytest 0.
- `python3 -m pytest -q tests/test_merge_lock_by_project.py tests/test_01m57pm7nbfx34319tr0f9cb4f_merge_mutex_by_project.py tests/test_01m57pm7nbfx34319tr0f9cb4f_mutex_readers_all_rows.py tests/test_merge_lock.py tests/test_merge_queue.py tests/test_notes.py tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py tests/test_doctor.py tests/test_merge_gate_ci_wait.py tests/test_main_ci_line.py`: 256 passed, 108 subtests passed.
- Временная мутация (код потом возвращён `git checkout`, `git status` чистый). Мутировано три места: `_own_rows` без `task_id` продлевает все строки; `wait_for_window` использует голову всей очереди (`_head_task_id(conn)`); журнал входа берёт держателя первой строкой (`_current_holder_label(conn)`). Итог прогона `tests/test_merge_lock_by_project.py`: 16 failed. Красными стали все три теста — `LegacyTouchHeartbeatTest` (оба порядка), `WaitForWindowOtherProjectQueueTest` (обе пары) и `WaitTextsAnyOrderTest` (12 подслучаев). Каждый тест ловит свою заявленную мутацию.
- `git diff --stat 14525c02...HEAD -- tests/`: только добавления трёх файлов. Файлы из требования 11 и AC-15 не тронуты.
- `python3 scripts/codebase_map.py`, затем `git diff -- docs/codebase-map.md` без строки `built_at_sha`: 0 строк, карта свежая (регенерация откачена).
- CI коммита 65eb9542 зелёный (16 проверок, по пакету).

## Предложения системе
- Ключ мьютекса — сессия, но `fsm_merge_gate` передаёт её функциям ожидания CI неявно, через `resolve_session_id()`. Явный `sid` в сигнатуре (`_wait_for_branch_ci_green`/`_await_main_ci`) убрал бы расхождение на тестовом шве `cmd_approve(session_id=…)`. Это повод для отдельной задачи, а не для этой: SPEC здесь сигнатуры зафиксировал.
