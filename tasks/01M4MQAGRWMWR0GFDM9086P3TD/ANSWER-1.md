---
task: 01M4MQAGRWMWR0GFDM9086P3TD
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

---
task: 01M4MQAGRWMWR0GFDM9086P3TD
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: состояние аудита в STATE_ROLE, аудит задач с ТЗ, зоны, модель Claude Opus 5.5, деление на две части

## Ответы

Расширение зон разрешено: orchestrator/runner.py, orchestrator/role_prompt.py, orchestrator/artel.py, orchestrator/zone_lock.py, orchestrator/merge_after.py, orchestrator/report.py, orchestrator/canary.py

1. **A — новое агентское состояние аудита в `config.STATE_ROLE`.** Состояние
   дописывается в `FSM_STATES` `tests/test_invariants.py` (~75) приложением
   PLAN и в `FSM_STATES` `tests/test_auto_cycle.py` (~63) — свипы
   инвариантов охватывают его (усиление). Обязательные условия (отдельные
   критерии с тестами, где сказано):
   - состояние вписано в `orchestrator/zone_lock.py` (~118), иначе задача
     выпадает из прогноза очереди зон — тест на прогноз;
     `orchestrator/merge_after.py` (~58), `orchestrator/report.py` (~41);
   - бюджет из SPEC (`budget.apply_spec_budget`) применяется на переходе
     `spec_writing → аудит`, до первого шага аудитора; повторное
     применение на `approve` сохраняется — тест «аудит идёт под потолком
     SPEC, а не по умолчанию»;
   - возврат из аудита в `spec_writing` — в `orchestrator/brief.py` (~62,
     триггеры возврата): бриф аналитика несёт аудит;
   - приложение `roles.yaml` (роль `spec_auditor`) — в том же мерже, что
     ключ `STATE_ROLE` (`tests/test_roles_map_fixture.py` ~50);
   - канарейка проходит аудит: состояние агентское, автогейт SPEC — после
     него; если `orchestrator/canary.py` перечисляет состояния — правка
     там (зона выдана).
   `orchestrator/runner.py` — только если без него роль не резолвится;
   особого случая роли вне `STATE_ROLE` не делать.

2. **A — аудит у задач с `TZ.md` (флоу аналитика).** SPEC, написанный
   Оператором без `TZ.md`, идёт на `spec_gate` как сегодня; аудит для
   него — командой Оператора (требование 7). Ослабления против
   сегодняшнего нет. Уточнение ADR-0022 п.3 вносит Оператор документом.

3. **A — зоны расширены** строкой мандата выше (миссия роли,
   флаг `approve` и команда повторного аудита, прогноз очереди зон,
   порядок мержа, отчёт, канарейка при необходимости). `orchestrator/fsm.py`,
   `orchestrator/brief.py`, `orchestrator/auto.py`, `scripts/guard.py`,
   `orchestrator/fsm_advance.py` уже в зонах ТЗ.

4. **Модель аудитора — Claude Opus 5.5 (`claude-opus-5-5`, провайдер
   claude), решение Оператора 11.10.** По умолчанию в любом наборе моделей,
   в том числе в `codex-all`, где аналитик на другой модели: роль без
   своей записи в наборе резолвится по ярусу `strong` (`roles.yaml`), а
   боевая модель яруса — `claude-opus-5-5`. Наследования модели
   аналитика не делать. Тест: под набором `codex-all` бриф/запуск
   аудитора — `claude-opus-5-5`, провайдер claude. Смена модели аудитора
   — только записью `spec_auditor` в набор (решение Оператора). Уточнение
   ADR-0022 п.6 вносит Оператор документом.

5. **B — две задачи.** Эта задача — механика: состояние, роль, бриф,
   guard `SPEC-AUDIT.md`, глубина по сигналам, возврат по `fail`, вердикт
   в `show`/`status`, флаг `approve`, команда повторного аудита;
   приложения `roles.yaml`, `templates/SPEC-AUDIT.md`,
   `skills/spec-audit.md`, `tests/test_invariants.py` (`FSM_STATES`).
   Требование 9 ТЗ (матрица последствий в `templates/QUESTIONS.md` и
   `skills/spec-authoring.md`) — в «Не входит», отдельной задачей сразу
   после этой. Бюджет этой задачи — рамка ТЗ $85.
