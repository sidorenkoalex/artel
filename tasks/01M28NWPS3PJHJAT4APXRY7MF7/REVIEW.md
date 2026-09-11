---
task: 01M28NWPS3PJHJAT4APXRY7MF7
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: гонка гейта зон при одновременном старте — проверка конфликта и захват зоны одной транзакцией

## Фаза A: проверка плана

1. Покрытие требований — полное: требования 1-2 закрыты шагами 1-2
   (`zone_lock.claim`/`_occupies`/`runner._cmd_run` + `try/finally`),
   требование 3 — шагом 1 (`_occupies`/`blocking_conflict` остаются
   единственной точкой правды для `catalog`/`doctor`/`auto`). Таблица
   покрытия PLAN.md соответствует фактическому diff.
2. Размер шагов — три шага, ~275 строк суммарно (diff --stat), каждый —
   проверяемая единица (модуль zone_lock, модуль runner, тесты), не
   микрооперации и не «сделать всё».
3. Подход не конфликтует с конвенциями: `BEGIN IMMEDIATE` — тот же
   диалектный приём, что уже применяет `store.next_task_number`
   (сверено построчно, orchestrator/store.py:199-218) — не новая
   техника для кодовой базы, риск синтаксиса/семантики SQLite минимален.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1. Атомарный захват (BEGIN IMMEDIATE, CLAIM_ACTION до промпта/спавна) | OK | `zone_lock.claim` (zone_lock.py:382-419): `conn.commit()` + `BEGIN IMMEDIATE`, `_occupies`/`blocking_conflict` внутри транзакции, `CLAIM_ACTION` пишется актором `developer` до возврата в `_cmd_run`, который вызывает `claim` строго до `_run_developer_step` (runner.py:201-207) |
| 2. Снятие захвата при не стартовавшем шаге | OK | `try/_run_developer_step/finally` (runner.py:209-222) покрывает все пути возврата (`sys.exit` паузы/стоп-крана/скилов, `return` workspace/pre-flight/фиксации, «skipped»-исход до записи «agent run started»); `claimed_but_not_started` (zone_lock.py:422-433) корректно фильтрует актора `developer`, `release_claim` пишет литеральную строку `"zone claim released"` актором `fsm` |
| 3. Семантика `_occupies`/`blocking_conflict` для остальных вызывающих не меняется | OK | `catalog`/`doctor`/`auto._wait_for_zone` не тронуты вовсе (diff --stat), видят новый маркер через тот же `blocking_conflict`; подтверждено приёмочным тестом AC-5 (`catalog._zone_wait_suffix`) |

## Замечания

_(пусто)_

## Реестр замечаний

_(пусто — новых замечаний в этой итерации не заведено)_

## Вердикт

approved

Обоснование: логика атомарности проверена не только по чтению кода, но
и прогоном — реальный многопоточный прогон `runner.cmd_run` (AC-1/AC-6)
стабильно (5 запусков подряд) даёт ровно один старт и один именованный
отказ, что и есть цель задачи (закрытие гонки SPEC «Контекст»). Латест-
wins в `_occupies` (zone_lock.py:274-320) проверен на всех переходах
маркеров (claim→released→reclaim, AC-4) и на фильтре актора `developer`
для `CLAIM_ACTION`/`"agent run started"` — тот же класс регрессии
01M1REVJ8AJ, закрытый и для нового маркера. `_run_developer_step`
вызывается для ЛЮБОЙ роли (не только developer) — то же поведение, что
и до рефакторинга (тело шага у `_cmd_run` и раньше не ветвилось по
роли после зонного гейта), имя функции — унаследованный нейминг, не
новый дефект; не блокирует, minor, не заведено отдельным замечанием.

## Проверено исполнением

- `python3 -m unittest tests.test_zone_lock -v` — 33 теста, все зелёные
  (включая 5 новых юнитов `claim`/`claimed_but_not_started`/
  `release_claim`).
- `python3 -m unittest tests.test_zones_gate -v` — 20 тестов, все
  зелёные (AC-8: соседний гейт зон не задет).
- Приёмочные тесты задачи (`tasks/01M28NWPS3PJHJAT4APXRY7MF7/
  acceptance_tests/`), прогнаны напрямую интерпретатором:
  `python3 -m unittest test_ac1_ac6_concurrent_zone_claim_race
  test_ac2_ac4_occupies_claim_and_release
  test_ac3_ac7_claim_released_on_failed_start
  test_ac5_other_callers_see_claim_occupancy
  test_ac8_existing_zone_tests_stay_green` — 13 тестов, все зелёные
  (AC-8 внутри этого прогона сама поднимает `tests.test_zone_lock`/
  `tests.test_zones_gate` дочерним процессом — второе независимое
  подтверждение).
- `test_ac1_ac6_concurrent_zone_claim_race` (реальные потоки ОС,
  барьер перед `cmd_run`) прогнан ОТДЕЛЬНО ещё 4 раза подряд — ни
  одной флуктуации, ровно один "ok"/один "exit" в каждом запуске.
- `python3 scripts/codebase_map.py` — сверка содержимого
  `docs/codebase-map.md` против HEAD: отличается только строка
  `built_at_sha` (легальное расхождение, не дефект — генерация
  локально отменена `git checkout --` после сверки, рабочее дерево не
  тронуто).
- Прочитаны исходники `orchestrator/zone_lock.py`,
  `orchestrator/runner.py` (полностью, не только diff-хунки) и
  `orchestrator/store.py:183-267,385-424,566-601` для проверки паттерна
  `BEGIN IMMEDIATE`/`conn.commit()` внутри `journal()`/
  `next_task_number` — подтверждено отсутствие незакоммиченной
  транзакции после успешного `claim()` (коммит происходит неявно
  внутри `store.journal`).
- Полный набор `tests/` не запускался (решение Оператора 05.09) — CI
  коммита 2480cc82 зелёный (7 проверок), это условие гейтов
  verifying/merge, не этого шага.

## Предложения системе

_(пусто)_
