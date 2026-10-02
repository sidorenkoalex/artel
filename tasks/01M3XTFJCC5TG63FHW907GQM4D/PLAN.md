---
task: 01M3XTFJCC5TG63FHW907GQM4D
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Подсказки пульта называют полный порядок запуска цикла после наблюдения фоновых задач

## Подход
Одна точка сборки подсказки — `orchestrator/cycle_hint.py`:
- `launch_hint(conn, task_id, cmd, note="") -> list[str]` — `[строка запуска,
  "сначала:", "1. …", "2. …"]`. Случай выбирается по первой строке новой
  функции чтения `store.session_observations(conn, task_id, target, session_id)`
  (активные наблюдения сессии `session.resolve_session_id(None)` и проекта
  `store.task_target`, `LEFT JOIN` строки задачи → признак `task_enabled`,
  порядок `task_enabled DESC, last_seen_at DESC, rowid DESC` — «а» приоритетнее
  «б», внутри — как `matching_observation`). Строк нет — случай «в» с
  заполнителями `codex|claude` / `<ID чата>`. SQL в `cycle_hint.py` нет, в БД
  ничего не пишется.
- `launch_text(conn, task_id, cmd, note="")` — тот же результат одним текстом:
  первая строка продолжает префикс места вызова («дальше: …»), шаги — ниже с
  отступом. Нужен потому, что `Stop.hint` — строка, а `auto_stop` печатает
  `  дальше: {hint}`; так все 13 мест печатают одинаково и строка
  `дальше: artel.py auto <id>` остаётся цельной (на неё опираются
  `tests/test_answer.py:393`, `tests/test_step_cost.py:1053`,
  `tests/test_auto_cycle.py:982`).
- Места вызова: `fsm.py` (4), `auto.py` (4 — `_stop_command_stop` и
  `_step_limit_stop` получили параметр `conn`, их зовут только внутри
  `auto.py`), `answer.py`, `catalog.py`, `budget.py`, `ci_rerun.py`,
  `advance_gates/tests_writing.py`. Префиксы («дальше:», «затем:», текст до
  «затем» в `auto.py`) и пояснения сохранены, пояснение ушло в `note`.

## Шаги
1. `store.session_observations` + `orchestrator/cycle_hint.py`; замена 13 мест
   вызова; `tests/test_cycle_hint.py`; регенерация `docs/codebase-map.md`.
   Один коммит в ветку задачи.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (модуль `cycle_hint.py`, `launch_hint`) | 1 |
| 2 (13 мест через `launch_hint`) | 1 |
| 3 (форма результата) | 1 |
| 4 (случаи а/б/в) | 1 |
| 5 (фильтр сессии/проекта/active, выбор свежего, а > б) | 1 |
| 6 (чтение в `store.py`, без SQL в `cycle_hint.py`, только чтение) | 1 |
| 7 (строка «а»/«б» проходит `_cycle_args`) | 1 |
| 8 (тесты в `tests/test_cycle_hint.py`) | 1 |

Проверка: `tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py` (AC-1…AC-9) —
10 passed; `tests/test_cycle_hint.py` — 3 passed, каждый сторож краснел на
своей временной мутации (сортировка без `task_enabled`; `JOIN` вместо `LEFT
JOIN`; `launch_text` с ведущим переводом строки). Модули мест вызова:
`test_answer`, `test_step_cost`, `test_ci_rerun_command`,
`test_fsm_spec_gate_reject`, `test_zones_approve` — 125 passed;
`test_auto_cycle`, `test_catalog_status_log`, `test_catalog_new_race`,
`test_acceptance_tests_flow`, `test_detached_cycle`, `test_observation_edges`,
`test_analyst_role` — 213 passed; `test_spec_budget`, `test_git_fixation`,
`test_fsm_advance_gate_smoke`, `test_budget_live_lease_and_escalation`,
`test_invariants`, `test_auto_escalated_return_rework_gate` — 182 passed.
Полный набор — за CI.

## Влияние на систему
- Меняется только текст подсказок Оператору; поведение `run`/`auto`/`observe`/
  `watch`, гейты, лимиты, схема БД не трогаются. Новая функция `store` — только
  `SELECT`.
- Подсказка теперь читает БД (наблюдения) и резолвит сессию; `resolve_session_id`
  при отсутствии `ARTEL_SESSION_ID` может завести `.artel/session-id` — тот же
  путь, что у любой команды через lease, новой записи в БД нет.
- Откат — revert коммита задачи.

## Риски
- Подсказка многострочная: вывод команд стал длиннее; проверки существующих
  тестов — по вхождению подстроки, поэтому остаются верными.

## Предложения системе
- Окружение шага роли: `Bash` без `PATH` к `/bin` (команды `ls`/`cat` не
  находятся) и составные команды требуют подтверждения — разведка шла только
  через `git grep`/Read; стоит поправить `PATH` курируемого HOME роли.
