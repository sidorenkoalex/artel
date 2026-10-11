---
task: 01M4MQAGRWMWR0GFDM9086P3TD
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Аудит SPEC — шаг spec_auditor между сдачей SPEC и spec_gate (ADR-0022)

## Фаза A — план

- Таблица покрытия PLAN.md полная: требования 1–21 привязаны к шагам 1–6.
- Шаги размером с MR: ядро, роль и бриф, перечни, guard, тесты, приложения.
- Подход не расходится с архитектурой. Вся логика визита собрана в
  `orchestrator/advance_gates/spec_audit.py` в пределах зоны. Роль
  резолвится через `STATE_ROLE` без особого случая (ANSWER-1 п.1).
  Защищённые пути (`roles.yaml`, `templates/SPEC-AUDIT.md`,
  `skills/spec-audit.md`, `tests/test_invariants.py`) идут только
  приложениями. `git apply --check` каждого из четырёх даёт код 0
  (проверено, см. ниже).
- «Влияние на систему» сходится с diff: изменены только файлы зон SPEC,
  `checkpoint.py`/`store.py`/`schema.py` не тронуты, путь отката описан.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `config.py` `STATE_ROLE["spec_audit"]="spec_auditor"`; `runner.step_role` не менялся |
| 2 | OK | `fsm_advance.spec_writing`: `step_role(t)=="analyst"` (есть TZ.md) → `spec_audit`, иначе `spec_gate`; других `set_state(...,"spec_gate")` из `spec_writing` нет (grep) |
| 3 | OK | Порядок: вопросы → грязная копия → guard → бюджет — не тронут |
| 4 | OK | `apply_spec_budget` стоит до `set_state`; в `_cmd_spec_audit` тоже; на approve сохранён |
| 5 | OK | Приложение `roles.yaml`: agent/strong/spec-audit; модель резолвится по ярусу (AC-6 зелёный) |
| 6 | OK | `brief.spec_auditor_brief`: TZ, SPEC целиком, каждый ANSWER, проекция карты; QUESTIONS и логи не берутся. Миссия несёт sha входа и сигналы |
| 7 | OK | `spec_audit.signals` а–д; `config.SPEC_AUDIT_SIGNAL_PATHS` — четыре непустые категории, «гейты» включают `advance_gates/` и `gates.yaml`; порог 45, сравнение `>=` |
| 8 | OK | `guard.RULES["spec_audit"]` — семь разделов, статусы draft/ready/escalate; `spec_audit_field_errors` проверяет наличие и значения полей |
| 9 | OK | `TASK_ROOT_ALLOWED_MD` расширен точным именем |
| 10 | OK | Добавлена ветка `runner._missing_required_artifact` |
| 11 | OK | `fsm_advance.spec_audit`: свежесть → статус → грязная копия → guard → escalate → привязка → `leave`; лимит 2 возврата, счётчик ведётся по журналу |
| 12 | OK | `freshness_refusal`: префикс автокоммита роли и sha коммита в журнале после последнего `state -> spec_audit`; отказ класса «роль ещё не закончила» |
| 13 | OK | `content_sha` — `rev-parse <ref>:<путь>`; оба отказа называют оба sha |
| 14 | OK | `VERDICT_ACTION`/`RETURN_ACTION`; `last_verdict` читается только из журнала |
| 15 | OK | В `_RETURN_TRIGGER_STATES_BY_TARGET["spec_writing"]` добавлен `spec_audit`; detail перехода несёт раздел «Вердикт» |
| 16 | OK | show/status/auto; без флага approve при `fail` отказывает и называет флаг; разбор позиционного sha флаг пропускает; вне `spec_gate` — `sys.exit` |
| 17 | OK | `fsm.cmd_spec_audit` с lease, только из `spec_gate` |
| 18 | OK | `zone_lock`, `merge_after`, `report`, `docs/stack.md` (оба места) |
| 19 | OK | `canary._pass_spec_gate`: `fail` → `_kill_inconclusive`, текст с вердиктом; планка AC-23 зелёная |
| 20 | OK | `test_auto_cycle.FSM_STATES` изменён правкой, `test_invariants` — приложением |
| 21 | OK | Изменено только объявленное ожидание (`call_count` 1→2), оно покрыто мандатом ANSWER-3 |

## Замечания

Blocker и major нет. Ниже minor-наблюдения: в реестр они не заведены и
итерации не требуют, при желании их можно закрыть попутно.

- minor — tests/test_spec_audit_gate.py:76 (`test_return_count_counts_only_return_records`) — проверяет то же, что долгоживущий `ReturnCounterTest` (AC-17: `reject`/`spec-audit` счётчик не сбрасывают), только на уровне журнала. Близко к повтору по ADR-0020 п.4; остальные три метода файла проверяют новые свойства.
- minor — orchestrator/advance_gates/spec_audit.py:52 — используется приватное `mandate._ZONES_MANDATE_MARKER`. Если его переименуют, сломается импорт модуля аудита, а через него — `catalog`/`auto`/`fsm_advance`. Лучше дать публичное имя рядом с `TEST_WEAKENING_MANDATE_MARKER`.
- minor — orchestrator/advance_gates/spec_audit.py:89 `_answer_texts` и orchestrator/brief.py:735 `_answer_rel_names` — два независимых разбора имён `ANSWER-n.md`.

Проверенные сомнения, которые не подтвердились:
- `answer.py` состояние не меняет: возврат из эскалации идёт только через `_approve_escalated`, а там добавлен `record_entry`.
- Отсутствие `SPEC-AUDIT.md` в ссылке даёт `TREE_NOT_ON_BRANCH`, это подкласс «роль ещё не закончила». `auto` не встаёт, а запускает аудитора.
- В `tests/test_analyst_role.py` помимо ожидания добавлены фейк второго шага и подмена `freshness_refusal`. Ни одно прежнее утверждение не удалено и не ослаблено; свежесть держит `…_flow.py::FreshnessTest` на настоящем git.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт

approved. Все требования SPEC реализованы, blocker и major нет. При
мерже приложения `roles.yaml` и `skills/spec-audit.md` нужно наложить
вместе с кодом: без них
`tests/test_roles_map_fixture.py::LiveRolesMapConsistencyTest` красный
(«spec_auditor … в карте не описана»). С наложенными приложениями —
зелёный, см. ниже.

## Проверено исполнением

- `artel.py plank-run 01M4MQAGRWMWR0GFDM9086P3TD` — 4 passed (test_ac23_canary ×2, test_plan_appendices ×2), код 0.
- `pytest -p no:xdist tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_flow.py` — 23 passed, 14 subtests, 140 с.
- `pytest -p no:xdist` по `…_spec_audit_units.py`, `test_spec_audit_gate.py`, `test_analyst_role.py`, `test_auto_cycle.py`, `test_refusal_classes.py`, `test_stack_zones_pull_section.py`, `test_catalog_zone_overlap.py`, `test_roles_map_fixture.py` — 133 passed. Один fail: `test_roles_map_fixture::…describes_every_role…` без наложенного `roles.yaml`, ожидаемо.
- Все четыре приложения PLAN: `git apply --check -` — код 0 каждое.
- Наложены `roles.yaml` и `tests/test_invariants.py`, затем `roles.yaml` и `skills/spec-audit.md`. `test_invariants.py` с `spec_audit` в `FSM_STATES` — зелёный (86 passed). `test_roles_map_fixture.py` с тремя приложениями — 8 passed. После этого откат (`git checkout`/`git clean`), дерево чистое.
- Временная мутация: в `last_verdict` убран сброс вердикта на `state -> spec_audit`, в `_approve_escalated` убран `record_entry`. Красными стали `LastVerdictTest::test_new_entry_into_audit_clears_the_last_verdict` и `EscalationReturnEntryTest::test_return_from_escalation_into_audit_records_a_new_entry`. Код возвращён через `git checkout`.
- `python3 scripts/codebase_map.py` — расхождение с закоммиченной картой только в `built_at_sha`, карта свежая. Изменение откачено.
- grep `"spec_gate"`/`"spec_writing"` по `orchestrator/` — пропущенных перечней состояний не нашлось.

## Предложения системе

- Ревью-пакет: `pytest -n` в worktree падает «node down» (30 воркеров xdist); для локальных прогонов ревьювера стоит назвать в скиле `-p no:xdist`.
- Отказ `SPEC_AUDIT_SPEC_CHANGED` (класс «чинит Оператор») оставляет задачу в `spec_audit` без команды выхода: вернуть её можно только откатом SPEC в ссылке. Стоит описать путь Оператора в `docs/operator-gates.md`.
