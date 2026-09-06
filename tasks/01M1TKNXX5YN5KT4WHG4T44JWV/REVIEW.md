---
task: 01M1TKNXX5YN5KT4WHG4T44JWV
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: R2 — `fsm_advance.py`: гейты `in_dev` и `review` как предикаты с единым исходом

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (единый тип исхода `GateRefusal`) | OK | `GateRefusal(NamedTuple)` (`orchestrator/fsm_advance.py:30-38`), поля `action/detail/hint`, `None` — гейт пройден. |
| 2 (гейт — чистый предикат) | OK | `_capacity_gate`, `_zones_gate`, `_review_rework_gate`, `_origin_push_gate`, `_registry_gate` не вызывают `store.journal`/`print` — проверено AC-2 тестом и точечным чтением тел. |
| 3 (общий каркас `_run_gates`) | OK | `fsm_advance.py:41-59` — один цикл, один `store.journal`, одна печать, `return True`/`False`. |
| 4 (короткие тела ≤40 строк, без новых уровней вложенности) | OK | `in_dev` (39 строк тела) и `review` (41 строка с def, тело в пределах теста AC-6) декомпозированы на `_review_approved`/`_review_changes_requested`/`_review_escalate`/`_in_dev_plan_escalate`/`_acceptance_lock_refuses`; сигнатуры точек входа и имена, подменяемые тестами (`_capacity_gate_refuses`, `_zones_gate_refuses`, `_review_rework_gate_refuses`), сохранены как тонкие обёртки. |
| 5 (юнит-тесты каркаса) | OK | `tests/test_fsm_advance_gate_framework.py` — порядок, остановка на первом отказе, ровно один `journal`, пустой список без записи/печати. |
| 6 (смоук трёх сценариев байт-в-байт) | OK | `tests/test_fsm_advance_gate_smoke.py` — три сценария (ёмкость/зоны/рубеж), фикстура обновлена под объединённое поведение после подтяжки main (ANSWER-1/ANSWER-2), запущено — совпадает. |
| 7 (поведение не меняется) | OK | Порядок гейтов, тексты action/detail/hint — байт-в-байт прежние (сверено построчно с diff и таблицей PLAN «гейт → прежнее место → текст»); прогон полного списка тестов планки — зелёный. |

## Замечания

(пусто — blocker/major/minor не найдено)

## Реестр замечаний

(пусто — замечаний в этой итерации не заведено)

## Вердикт

approved

## Проверено исполнением

- `python3 scripts/codebase_map.py` — перегенерировал карту в рабочей копии, diff с закоммиченной версией — только строка `built_at_sha` (`grep -v '^built_at_sha:'` до/после идентичны); откатил командой `git checkout -- docs/codebase-map.md`. Карта в diff актуальна.
- `python3 -m unittest tasks.01M1TKNXX5YN5KT4WHG4T44JWV.acceptance_tests.test_ac1_ac2_gate_outcome_type tasks.01M1TKNXX5YN5KT4WHG4T44JWV.acceptance_tests.test_ac3_ac4_ac5_ac8_gate_chain tasks.01M1TKNXX5YN5KT4WHG4T44JWV.acceptance_tests.test_ac6_entry_point_shape tasks.01M1TKNXX5YN5KT4WHG4T44JWV.acceptance_tests.test_ac7_existing_gate_tests_still_pass tasks.01M1TKNXX5YN5KT4WHG4T44JWV.acceptance_tests.test_ac9_smoke_fixture_byte_identical` — 16/16 OK (все AC-1..AC-9 планки задачи).
- `python3 -m unittest tests.test_capacity_gate tests.test_zones_gate tests.test_fsm_review_rework_gate tests.test_review_registry_gate tests.test_advance_guard tests.test_branch_freshness_gate tests.test_github_adapter tests.test_fsm_draft_mr_reentry tests.test_invariants tests.test_multitarget tests.test_multitarget_invariants tests.test_zone_lock tests.test_fsm_map_conflict_autoresolve` — 223 теста, OK.
- `python3 -m unittest tests.test_fsm_merge_conflict_note tests.test_review_freshness tests.test_step_refixation tests.test_advance_refusal_history tests.test_review_package tests.test_split_assessment_merge_gate tests.test_canary tests.test_acceptance_tests_flow tests.test_acceptance tests.test_fsm_advance_gate_framework tests.test_fsm_advance_gate_smoke` — все зелёные, OK (без FAILED/ERROR).
- Прочитан весь diff `orchestrator/fsm_advance.py` целиком с диска ветки (698 строк изменений) — построчно сверены: порядок вызовов гейтов в `in_dev()` (лок → `_pull_main_or_escalate` → ёмкость → зоны → рубеж) и в `review()` (freshness → голова в origin → `store.update_task(reviewed_iter=...)` → approved/changes_requested/escalate) с текстом ДО правки из самого diff — совпадает; тексты `action`/`detail`/`hint` каждого гейта сверены буква-в-букву со старыми f-строками в удалённых участках diff.
- Полный набор `tests/` не запускал (в шаге ревью не требуется — гоняет CI на каждый пуш); сверка «набор не ослаблен» — по diff `tests/` (два новых файла, ни один существующий тест не тронут — AC-7 в PLAN подтверждён этим же).

## Предложения системе

(пусто)
