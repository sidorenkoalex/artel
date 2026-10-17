---
task: 01M52EEHSRD93WMPHWB5VJYRKD
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/advance_gates/acceptance.py, orchestrator/fsm_merge_gate.py, orchestrator/suite_run.py, orchestrator/plank_run.py, orchestrator/pull.py, orchestrator/amend.py, orchestrator/notes.py, orchestrator/fsm.py, orchestrator/fsm_autogate.py, orchestrator/fsm_advance.py, orchestrator/advance_gates/tests_writing.py, orchestrator/advance_gates/test_integrity.py, tests/
merge_after: 01M52EEFNA1WH31962HVNT0YZ9
budget_usd: 40
---

# SPEC: D0-3: один источник профиля у вызывающих прогон

## Контекст
Часть 3 из 3 задачи D0 (родитель 01M52CQB468758M2NAA15C15ZE; основание —
ADR-0023, вторая поправка 16.10.2026). Часть 2 (01M52EEFNA1WH31962HVNT0YZ9)
научила места запуска в `orchestrator/acceptance.py` (`run`, `run_repeat`,
`run_plank`, `run_full_suite`, `full_suite`) и `two_sided.run` принимать
профиль `pytest-own` (`project_profile.Profile`) каналом `command` и
запускать pytest с argv, `cwd` и окружением по профилю; `acceptance_suite`
уже сам берёт профиль проекта задачи (`acceptance._task_own_profile`).
Остальные вызывающие по-прежнему передают либо список `command`
(гейт мержа: `fsm_merge_gate._full_suite_command` отдаёт
`list(decision.profile.command)`), либо ничего — и для внешнего проекта с
`runner: pytest-own` запускаются не по профилю. Задача — довести профиль
проекта задачи до этих вызывающих тем же каналом.

## Требования
1. Вызывающие прогона вне `orchestrator/acceptance.py` передают профиль
   проекта задачи (`command`, `runner`, `workdir`, `env`) тем же каналом,
   которым сегодня передаётся `command` (`Profile` вместо списка):
   - гейт мержа — `orchestrator/fsm_merge_gate.py:962-967` (вызовы
     `acceptance.full_suite`);
   - `suite-run` — `orchestrator/suite_run.py`, в том числе ключ итога
     (`:511`, `:533`);
   - `plank-run` — `orchestrator/plank_run.py:187` (`acceptance.run_plank`);
   - `amend-tests` — `orchestrator/amend.py:545-549`, `:715-718`;
   - прогоны `pull` — `orchestrator/pull.py:664-666`;
   - сухой сбор `tests_writing` — `orchestrator/fsm_advance.py:594-596`,
     `orchestrator/advance_gates/tests_writing.py:557-563`;
   - вызывающие двустороннего прогона —
     `orchestrator/advance_gates/test_integrity.py:1429`, `:1527`
     (`two_sided.run`).
2. Автогейт приёмки и `approve` на acceptance получают профиль через
   `acceptance.acceptance_suite` (механика части 2).
3. Задача — только передача профиля: логика гейтов и логика
   `orchestrator/suite_run.py` не меняются.
4. Прогоны без задачи (в том числе `orchestrator/notes.py:1040`) и прогоны
   задач артели сохраняют сегодняшнее поведение.
5. `preflight` и `acceptance-dry-run` pytest не запускают и не правятся.

## Критерии приёмки
AC-1. Автогейт приёмки для задачи учебного проекта с профилем
`runner: pytest-own` запускает полный набор с argv, `cwd` и окружением по
профилю `pytest-own`.

AC-2. `approve` на acceptance для задачи учебного проекта с профилем
`pytest-own` запускает полный набор с argv, `cwd` и окружением по профилю.

AC-3. Гейт мержа для задачи учебного проекта с профилем `pytest-own`
запускает полный набор с argv, `cwd` и окружением по профилю.

AC-4. `suite-run` для задачи учебного проекта с профилем `pytest-own`
запускает полный набор с argv, `cwd` и окружением по профилю.

AC-5. `plank-run` для задачи учебного проекта с профилем `pytest-own`
запускает pytest с argv, `cwd` и окружением по профилю.

AC-6. `amend-tests` для задачи учебного проекта с профилем `pytest-own`
запускает pytest с argv, `cwd` и окружением по профилю.

AC-7. Прогоны `pull` для задачи учебного проекта с профилем `pytest-own`
запускают pytest с argv, `cwd` и окружением по профилю.

AC-8. Двусторонний прогон для задачи учебного проекта с профилем
`pytest-own` запускает pytest с argv, `cwd` и окружением по профилю.

AC-9. Сухой сбор `tests_writing` для задачи учебного проекта с профилем
`pytest-own` запускает pytest с argv, `cwd` и окружением по профилю.

AC-10. Для задачи артели argv, `cwd` и окружение каждого из мест запуска
AC-1 — AC-9 не изменились относительно main.

AC-11. Прогон без задачи (`orchestrator/notes.py:1040`,
`acceptance.run_full_suite`) запускается с теми же argv, `cwd` и
окружением, что на main.

## Оценка объёма и деление
Сработавшие сигналы: файлов зоны ≥ 5 (12 файлов `orchestrator/` и
`tests/`); критериев приёмки ≥ 10 (11); `budget_usd` ≥ $30 ($40 — рамка
Оператора из ТЗ).

Обоснование монолита (материал для решения Оператора): задача уже
является третьей частью деления D0, и её зоны заданы Оператором в ТЗ
целиком. Изменение однородно — одна и та же замена «список `command` →
`Profile`» на стороне вызывающих по механике, уже вмёрженной частью 2; в
каждом файле зоны это одна-две точки вызова (адреса в требовании 1).
Технически вызывающих можно разнести по подзадачам — каждая была бы
мержима отдельно, промежуточное состояние не нерабочее, лишь неполное, —
но AC-10 (у артели ничего не изменилось) общий для всех мест, а
фиксированная цена каждой подзадачи (analyst, test_author, developer,
reviewer — ~$14 на задачу) кратно превысит объём правки в одном файле.
Оператор задал рамку $40 на часть целиком.

## Обоснование зависимостей мержа
- `01M52EEFNA1WH31962HVNT0YZ9` — часть 2 того же деления (D0-2, раннер
  `pytest-own` в местах запуска): строка ТЗ «Порядок: после части 2»;
  задача опирается на приём профиля местами запуска, который вносит
  часть 2. На момент SPEC часть 2 уже в `done`.

## Не входит
- Правка `orchestrator/acceptance.py` и `orchestrator/advance_gates/two_sided.py`.
- Запись sled в `targets.yaml`.
- Правка `preflight` (`orchestrator/preflight.py`) и `acceptance-dry-run`
  (`orchestrator/dry_run.py`) — они pytest не запускают.
- Изменение логики гейтов и логики `orchestrator/suite_run.py` сверх
  передачи профиля.

## Материалы
- ADR-0023, вторая поправка 16.10.2026.
- Родитель: 01M52CQB468758M2NAA15C15ZE; часть 1: 01M52EEDEYV14658X8VFNHCW8K;
  часть 2: 01M52EEFNA1WH31962HVNT0YZ9.
- Места запуска части 2: `orchestrator/acceptance.py` (`_own`,
  `_task_own_profile`, `full_suite`, `run_plank`, `run_full_suite`).
