---
task: 01M1TKP08PKB87K8772H69GCXJ
type: plan
author_role: developer
status: ready
schema_version: 4
---

# PLAN: R3 — `fsm.py`: подтяжка в модуль `pull.py`, approve как таблица переходов

## Подход
Два независимых механических рефакторинга внутри `orchestrator/fsm.py`,
без изменения поведения (правило фазы R):

1. **`orchestrator/pull.py`** несёт исход подтяжки главной ветки как один
   из четырёх типов — `Fresh`, `Pulled(sha)`, `Conflict(files, note)`,
   `Refused(reason)` (обычные классы с `__eq__`/`__repr__`, не dataclass:
   AC-1 сверяет только `inspect.signature`, форма типа не важна) — и
   функцию `evaluate(conn, task_id, t, state, *, origin_main_source,
   origin_main_sha, read_branch_text_or_refuse)`, которая производит один
   из них. Логика прежней `_pull_main_or_escalate` (218 строк) разложена
   на `_conflicting_files`, `_auto_resolve_map_conflict`,
   `_merge_conflict_note`, `_clean_worktree_before_merge`, `_run_merge`,
   `_handle_merge_failure`, `_materialize_and_run_plank`, `evaluate` —
   каждая заметно короче потолка требования AC-1 (150 строк).

   `orchestrator.fsm._pull_main_or_escalate` остаётся точкой входа с
   прежней сигнатурой/контрактом возврата: вызывает `pull.evaluate` и
   переводит исход в строки `"fresh"`/`"pulled"`/`"escalated"`/`"refused"`.
   Записи журнала/эскалации (`store.journal`/`store.set_state(...,
   "escalated", ...)`) для каждого исхода несёт сам `pull.py` (не fsm.py
   отдельным шагом) — так порядок и текст побочных эффектов (в т.ч. пара
   `store.set_state` + `alerts.raise_alert` для инцидента «would be
   overwritten by merge») остаётся байт-в-байт таким же, как до переноса,
   без риска рассинхронизировать текст в двух местах.

   `_origin_main_source`/`_origin_main_sha` (сверка свежести против
   origin, общий узел с `fsm_merge_gate.py` — своя копия там же, обратный
   импорт `fsm_merge_gate -> fsm -> pull -> fsm` завёл бы цикл) и
   `_read_branch_text_or_refuse` (общий узел ещё нескольких функций
   `fsm.py`) остаются определены в `fsm.py` и передаются в `pull.evaluate`
   ПАРАМЕТРАМИ, а не импортом `pull.py` обратно в `fsm`: `pull.py` не
   зависит от `fsm.py` вовсе (чистый лист, `fsm.py` импортирует его как
   обычный модуль на уровне файла, без циклов). Это же решает AC-5:
   `mock.patch.object(fsm, "_origin_main_sha", ...)` (два существующих
   теста) продолжает долетать до реального `git merge`, потому что вызов
   этого имени остаётся текстуально внутри `fsm.py` (аргумент, вычисленный
   в момент вызова `_pull_main_or_escalate`, не bare-имя внутри `pull.py`).

   `_merge_conflict_note` — единственное перенесённое имя, которое
   существующий тест зовёт НАПРЯМУЮ через `fsm._merge_conflict_note(...)`
   (`tests/test_fsm_merge_conflict_note.py`, чистая функция, не мок) —
   `fsm.py` реэкспортирует его (`from .pull import _merge_conflict_note`).

2. **`_cmd_approve`** — цепочка `if state == ...` заменена словарём
   «состояние -> обработчик» внутри самой функции (тем же приёмом, что
   уже несёт `_cmd_advance`, SPEC T091): тело каждой ветки перенесено без
   изменений в отдельную функцию `_approve_spec_gate`/`_approve_acceptance`/
   `_approve_merge_gate`/`_approve_escalated` с единой сигнатурой
   `(conn, task_id, t, state, sid)`; ветка «иначе» — прежний текст отказа.

## Шаги
1. `orchestrator/pull.py` — типы исходов + декомпозиция логики подтяжки;
   `orchestrator/fsm.py::_pull_main_or_escalate` — тонкий переводчик
   исхода в прежний контракт возврата; реэкспорт `_merge_conflict_note`.
2. `orchestrator/fsm.py::_cmd_approve` — таблица «состояние -> обработчик»
   вместо цепочки `if`/`elif`.
3. Юнит-тесты: `tests/test_pull.py` (все четыре исхода `pull.evaluate` в
   лёгкой песочнице с фейковым git) и `tests/test_cmd_approve_dispatch.py`
   (каждое состояние таблицы ведёт к своему обработчику, состояние вне
   таблицы — к прежнему тексту отказа).
4. `python3 scripts/codebase_map.py` — карта регенерирована тем же
   коммитом (правка `*.py` в `orchestrator/`).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (pull.py: типы + декомпозиция) | 1 |
| 2 (`_pull_main_or_escalate`: сигнатура/контракт неизменны) | 1 |
| 3 (`_cmd_approve`: таблица) | 2 |
| 4 (поведение байт-в-байт) | 1, 2, 3 |
| 5 (юнит-тесты на pull.py и таблицу approve) | 3 |
| 6 (смоук трёх сценариев байт-в-байт) | 1, 3 |

## Влияние на систему
`orchestrator/pull.py` — новый модуль, не меняет ничьё чужое поведение:
единственный вызывающий — `orchestrator/fsm.py::_pull_main_or_escalate`,
три точки входа (`in_dev -> review`, `acceptance -> merge_gate`,
`merge_gate -> done`) сохраняют прежний контракт (AC-2), поэтому
`fsm_advance.py`/`fsm_merge_gate.py` не тронуты и не требуют правки.

`_cmd_approve` — форма диспетчеризации меняется, поведение (какое
состояние куда ведёт, какие тексты печатаются/журналируются) — нет;
`fsm_merge_gate._cmd_approve_merge_gate_cycle` зовётся с теми же
позиционными аргументами (`conn, task_id, sid, t, state`), что и раньше.

Гейты/инварианты/тесты, соседствующие с изменением (не ослаблены):
существующие тесты `tests/test_branch_freshness_gate.py`,
`tests/test_fsm_map_conflict_autoresolve.py`,
`tests/test_fsm_merge_conflict_note.py` (утверждения не правились) и
приёмочные тесты задачи `tasks/01M1TKP08PKB87K8772H69GCXJ/acceptance_tests/`
прогнаны зелёными после рефакторинга (AC-6, AC-9). Откат — вернуть тело
`_pull_main_or_escalate`/`_cmd_approve` из истории git, удалить
`orchestrator/pull.py` и его тесты.

## Риски
- `pull.py` объявляет исходы обычными классами (не `dataclass`/
  `NamedTuple`) ради простоты (`__eq__` только по значимым полям) — AC-1
  сверяет структуру через `inspect.signature`, форма типа для приёмки не
  важна; если система ожидает `dataclass` конкретно, это не проверяется
  ни одним критерием.

## Предложения системе
