---
task: T050
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 2
---

# REVIEW: CAS-переходы состояния задачи в БД

## Соответствие SPEC

Фаза A (гейт плана): каждое требование SPEC покрыто шагом PLAN (таблица
«Покрытие требований» полна), шаги — проверяемые единицы (правка
store.py, правка вызывателей по модулям, retry в kill, юнит-тесты,
прогон). Подход (CAS-UPDATE + исключение `CasConflict`, keyword-only
`expected_state`) не конфликтует с конвенциями: `store.py` остаётся
листом графа импортов (ADR-0003 3ж), схема не тронута.

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `set_state` требует keyword-only `expected_state` (store.py:388-389); `TypeError` без него подтверждён тестом (tests/test_cas_set_state.py, tasks/T050/acceptance_tests/test_ac4_*.py). |
| 2 | OK | Атомарный `UPDATE tasks SET state=?, updated_at=? WHERE id=? AND state=?` (store.py:420-422). |
| 3 | OK | `rowcount == 0` → `CasConflict(task_id, expected_state, actual)` до journal/фиксации (store.py:424-429); сообщение содержит оба состояния (AC-3 тест проходит). |
| 4 | OK | Ни один вызыватель (fsm.py, budget.py, runner.py) не перехватывает `CasConflict`, кроме `cleanup._cmd_kill` — единственное разрешённое исключение (grep по `store.set_state(` подтверждает: все вызовы за пределами allowed-модулей отсутствуют). |
| 5 | OK | Все вызовы в fsm.py используют `state`, прочитанный один раз на входе `_cmd_advance`/`_cmd_approve`/`_cmd_reject` (`t = store.get_task(...); state = t["state"]`), без повторного чтения перед `set_state`. Проверено чтением полного файла и приёмочными тестами AC-5 (гонка через `_race.single_shot_state_race`, все 5 веток зелёные). |
| 6 | OK | `cleanup._cmd_kill`: retry-цикл `while not won and state not in TERMINAL_STATES: try/except CasConflict: state = exc.actual` (cleanup.py:176-183) — не завершается ошибкой, использует `exc.actual` как следующий `expected_state`. |
| 7 | OK | Терминальность (`done`/`killed`) проверяется до входа в цикл и как условие его выхода; печатает сообщение, не мутирует, не бросает (AC-7 тесты зелёные). |
| 8 | OK | Приёмочный AC-8 гоняет kill под гонкой из ВСЕХ нетерминальных состояний FSM (`NON_TERMINAL_STATES` из `test_invariants.FSM_STATES`) — все проходят, `killed` достигается в каждом случае. |
| 9 | OK | Схема не менялась (диф store.py не трогает `SCHEMA`); AC-10 сверяет полный набор таблиц/колонок с БД, поднятой заново, тест зелёный. |
| 10 | OK | `charge`, `next_task_number`, leases, `update_task` не изменены (диф этих функций не касается — подтверждено чтением store.py целиком). |

## Замечания

<пусто — 0 blocker/major/minor>

Дополнительно проверено сверх диффа (для полноты, не в списке замечаний):
- Полный набор `tests/` (743 теста) — зелёный без изменений в песочнице.
- `tasks/T050/acceptance_tests/` (16 тестов, AC-1..AC-10) — зелёные.
- `tests/test_cas_set_state.py` (7 юнит-тестов) — зелёные.
- Конкурентный AC-1/AC-2 прогнан 20 раз подряд — без единого сбоя (не
  флаки).
- `python3 scripts/codebase_map.py` — карта свежая, диф только в строке
  `built_at_sha` (не содержательный, восстановлен обратно после проверки).
- `grep` по `store.set_state(` во всём `orchestrator/` и `tests/`/
  `tasks/*/acceptance_tests/` — вызовов вне store.py/fsm.py/budget.py/
  runner.py/cleanup.py и артефактов самой T050 не найдено; старые
  приёмочные тесты прежних задач `store.set_state` напрямую не зовут
  (только упоминание в докстринге T045), регрессии от смены сигнатуры
  нет.
- `budget.py`/`runner.py`: `t = store.get_task(...)` читается один раз
  на входе `_cmd_run`/`_cmd_budget`, `t["state"]` используется как
  `expected_state` во всех точках, включая после долгих операций (прогон
  агента, git push) — согласуется с духом требования 5, хотя оно
  формально касается только fsm.py (PLAN это явно объясняет).
- `git status`/`git diff --stat` вне `tasks/T050/` — изменены ровно
  store.py, fsm.py, budget.py, runner.py, cleanup.py, docs/codebase-map.md,
  tests/test_cas_set_state.py, tests/test_git_fixation.py — точно
  заявленная в PLAN «Влияние на систему» зона, side effects нет.

## Вердикт

approved

## Проверено исполнением
Ретроактивная пометка при миграции корпуса под evidence-контракт (T072, 2026-08-30): это ревью прошло до появления обязательной секции «Проверено исполнением» (SPEC T072, guard.py:review_evidence_errors). Факт исполнения проверок этим ревью, если они проводились, восстановить задним числом нельзя — что реально оценивалось, отражено выше, в разделах «Соответствие SPEC»/«Замечания» этого файла. Секция добавлена постфактум одним коммитом по всему корпусу только для соответствия новому структурному правилу guard.py, содержательно не переписывает исходное ревью.

## Предложения системе

<пусто>
