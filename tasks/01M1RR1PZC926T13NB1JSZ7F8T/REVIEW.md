---
task: 01M1RR1PZC926T13NB1JSZ7F8T
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 4
---

# REVIEW: занятость зоны — только по старту developer (регрессия 01M1REVJ8AJ)

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (`_occupies` считает занятостью `"agent run started"` только актора `developer`, `RELEASE_ACTION` — любым актором) | OK | `orchestrator/zone_lock.py:182-216`: `_visit_has_action` получил параметр `actor`, `_occupies` зовёт его с `actor="developer"` для `_AGENT_STARTED_ACTION` и без фильтра для `RELEASE_ACTION` — ровно та асимметрия, что требует требование 1. |
| 2 (семантика границы пребывания/очереди не меняется) | OK | `_stay_since_id`, `blocking_conflict`, `refusal`, очередь (`queue_order`/`queue_position`/`cmd_zone_reorder`) в diff не тронуты — сужен только один булев признак внутри `_occupies`, как заявлено в PLAN «Влияние на систему». |
| 3 (копилка/скил, необязательно) | OK (не делалось) | PLAN честно фиксирует «не делаю: не нашёл материала сверх уже описанного в SPEC» — требование помечено необязательным, отказ обоснован. |
| AC-1..AC-2, AC-7 (регрессия не воспроизводится, кандидат не блокирует соседа) | OK | Стаб-планка `tasks/01M1RR1PZC926T13NB1JSZ7F8T/acceptance_tests/test_zone_actor_filter_regression.py` — все 3 теста зелёные против кода задачи. |
| AC-3..AC-5 (реальный владелец/`RELEASE_ACTION`/форма `refusal` не меняются) | OK | `test_zone_actor_filter_preserved.py` — 3/3 зелёные. |
| AC-6 (существующие планки `test_zone_lock.py`/`test_zones_gate.py` зелёные без правки ассертов) | OK | Прогнал оба модуля напрямую (47 тестов, 0 упавших) и через `test_ac6_zone_lock_suites_stay_green.py` (2/2). Diff `tests/test_zone_lock.py` — только добавление нового класса/метода, ни один существующий ассерт не тронут. |

## Замечания

- ...

## Реестр замечаний

Пусто — итерация 1, замечаний нет.

## Вердикт

approved

## Проверено исполнением

- `python3 -m unittest tests.test_zone_lock tests.test_zones_gate -v` — 47 тестов, 0 ошибок/падений (AC-6, проверка «набор не ослаблен» — новый тест `test_non_developer_agent_start_in_same_stay_does_not_occupy` в diff добавлен, ни один существующий ассерт не удалён и не смягчён).
- `python3 -m unittest tasks.01M1RR1PZC926T13NB1JSZ7F8T.acceptance_tests.test_zone_actor_filter_regression tasks.01M1RR1PZC926T13NB1JSZ7F8T.acceptance_tests.test_zone_actor_filter_preserved -v` — 6 тестов (AC-1, AC-2, AC-7, AC-3, AC-4, AC-5), все зелёные.
- `python3 -m unittest tasks.01M1RR1PZC926T13NB1JSZ7F8T.acceptance_tests.test_ac6_zone_lock_suites_stay_green -v` — 2/2 (AC-6, независимая проверка через subprocess против реального дерева).
- Ручное чтение `orchestrator/zone_lock.py:140-260` (текущее дерево) — код соответствует diff буквально, `blocking_conflict`/`refusal`/`_stay_since_id`/очередь не тронуты.
- Сверка `docs/codebase-map.md`: `git show main:docs/codebase-map.md` vs `git show <ветка задачи>:docs/codebase-map.md` без строки `built_at_sha` (python-скрипт, построчное сравнение) — содержимое идентично, регенерация карты корректна, дрейфа нет.
- `git log main..task/01m1rr1pzc926t13nb1jsz7f8t-zanyatost-zony-tolko-po-startu --oneline` и `git ls-tree` артефактной ветки — файлов вне зон (`orchestrator/zone_lock.py`, `tests/`) и `docs/codebase-map.md` (ожидаемая регенерация карты) не найдено; ANSWER-файлов у задачи нет (эскалаций не было).

## Предложения системе

Нет.
