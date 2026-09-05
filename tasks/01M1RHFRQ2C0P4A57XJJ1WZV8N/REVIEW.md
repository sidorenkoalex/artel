---
task: 01M1RHFRQ2C0P4A57XJJ1WZV8N
type: review
author_role: reviewer
status: approved        # draft | approved | changes_requested | escalate
iteration: 1
schema_version: 4    # версия формата артефакта, см. scripts/guard.py
---

# REVIEW: регрессия №13 — после замечаний ревью `auto` запускает разработчика, а не переход

## Соответствие SPEC

Фаза A (гейт плана): требования SPEC 1-5 покрыты шагами 1-3 PLAN.md
таблицей покрытия полностью, шаги — проверяемые единицы размера MR
(журнальный рубеж в `auto.py`, git-based рубеж в `fsm_advance.py`,
инфраструктура тестов), подход не конфликтует с конвенциями
(`_capacity_gate_refuses`/`_zones_gate_refuses` — тот же паттерн
независимого гейта в `in_dev()`, `_pull_main_or_escalate` — тот же
паттерн деградации «git не ответил»). Замечаний к плану нет.

Фаза B (ревью MR), по критериям приёмки:

| Требование | Вердикт | Комментарий |
|---|---|---|
| AC-1 (пред-advance не пропускает `in_dev` с неотработанным `review→in_dev`/`acceptance→in_dev`/`merge_gate→in_dev`/`verifying→in_dev`) | OK | `_REWORK_GATE_STATES`/`_role_step_since_state_entry` (`auto.py:83,96-120`); тест `test_ac1_ac4_ac9_...py::PreAdvanceYieldsToDeveloperAfterReviewReworkTest` зелёный |
| AC-2 (то же для возврата из `escalated`, включая `spec_writing`/`tests_writing`) | OK | проверка не смотрит на источник перехода — только на факт `agent run finished` после последней `state -> X`, что закрывает и прямой reject, и возврат через `escalated` одним кодом; тест `test_ac2_ac8_...py::EscalatedReturnToInDevStillNeedsADeveloperStepTest` зелёный |
| AC-3 (гейт `in_dev -> review` не пропускает переход на неизменённом коде после `changes_requested`) | OK | `_review_rework_gate_refuses` (`fsm_advance.py:740-789`), сверка по времени коммитов (`%cI`), не по sha/тексту; тест `test_ac3_ac4_ac6_ac7_...py::GateRefusesUnchangedCodeAfterChangesRequestedTest` зелёный |
| AC-4 (отказ обоих рубежей именован с номером итерации) | OK | оба рубежа несут буквальную фразу «замечания ревью не отработаны: нет шага developer после итерации N» (`auto.py:123-137`, `fsm_advance.py:783-784`); тесты `NamedAndJournaledAutoRefusalTest`/`GateNamesTheIterationInTheJournalTest` зелёные |
| AC-5 (сценарий «замечания ревью → auto» запускает developer, не advance по готовому PLAN.md) | OK | тест воспроизводит переход `review -> in_dev` РЕАЛЬНЫМ `fsm.cmd_advance` внутри цикла — `test_ac5_review_remarks_runs_developer_step.py` зелёный |
| AC-6 (шаг developer после возврата снимает оба рубежа, следующий advance проходит штатно) | OK | `test_ac3...py::DeveloperCommitAfterTheVerdictUnblocksTheGateTest` — коммит после вердикта + журнал `agent run finished` → переход в `review` состоялся, developer повторно не звался |
| AC-7 (ручной `advance` Оператора на неизменённом коде — именованный отказ, не переход) | OK | рубеж встроен в САМ `fsm_advance.in_dev()` (`fsm_advance.py:912`), не только в обёртку `auto.py` — `test_ac3...py::ManualAdvanceOnUnchangedCodeIsNamedNotSilentTest` вызывает `fsm.cmd_advance` напрямую, минуя `auto`, и получает отказ |
| AC-8 (возврат из `escalated` по ANSWER — `auto` запускает роль, не повторяет эскалацию по старому артефакту) | OK | `test_ac2_ac8_...py::EscalatedReturnByAnswerRunsTheRoleNotTheOldEscalationTest` воспроизводит реальный второй инцидент 05.09 (QUESTIONS.md раунда 1 остаётся на диске) — analyst получает шаг, не повторная эскалация |
| AC-9 (регресс: `tests_writing` после отказа трассируемости даёт test_author шаг на каждой итерации) | OK | `review` и `tests_writing` намеренно вне `_REWORK_GATE_STATES`/стоп-крана требования 4 (уже так было, не тронуто); `TestsWritingTraceabilityRefusalRegressionTest` зелёный, 3 шага подряд |
| AC-10 (существующие regression-suite `test_auto_cycle.py`/`test_advance_guard.py` и планка 01M1R8B3ZKXQT0Z0G6QQQDV906 зелёные без ослабления) | manual (обоснованно) | половина (два файла tests/) прогнана мной лично — зелёные (см. «Проверено исполнением»), не ослаблены (diff — только добавления, 0 удалений); вторая половина (чужая уже смерженная планка) физически недоступна из этого дерева — `test_scope_markers.py` документирует это с проверкой `git log --all`/`git branch -a`, тот же класс, что уже разбирал Оператор в аудитах v6/v7 (ADR-0007) |

## Замечания

Пусто — 0 blocker/major/minor.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Пусто — замечаний в этой итерации не заведено.

## Вердикт

approved

## Проверено исполнением

- `python3 -m unittest discover -s tasks/01M1RHFRQ2C0P4A57XJJ1WZV8N/acceptance_tests -p 'test_*.py' -v` — 10 тестов (AC-1, AC-2, AC-4×2, AC-5, AC-6, AC-7, AC-8, AC-9), все `ok`.
- `python3 -m unittest tests.test_auto_cycle tests.test_advance_guard -v` — 47 тестов (AC-10, часть а), все зелёные, ноль ослабленных ассертов (diff файла — только добавления).
- `python3 -m unittest tests.test_zones_gate tests.test_capacity_gate tests.test_branch_freshness_gate tests.test_review_freshness tests.test_review_registry_gate tests.test_answer_gate tests.test_answer tests.test_invariants tests.test_fsm_branch_correct_status_reads tests.test_fsm_draft_mr_reentry tests.test_step_refixation tests.test_fsm_autogate tests.test_advance_refusal_history` — 150 тестов, все зелёные (соседние гейты `in_dev`/`review`, которым PLAN.md заявляет незатронутость, — подтверждено прогоном, не пересказом).
- `python3 scripts/codebase_map.py --check` — без вывода (карта содержательно свежа; `built_at_sha` — единственная строка диффа `docs/codebase-map.md`, что и ожидается по конвенции).
- Прочитан код `orchestrator/auto.py` (60-200, 280-556) и `orchestrator/fsm_advance.py` (120-352, 682-918) целиком, сверен с diff построчно — рефакторинг предварительного advance в `if gated_role and not role_ran: ... else: ...` не меняет логику для состояний вне `_REWORK_GATE_STATES` и не теряет `steps`/`idle_steps`/`prev_refusal` учёт.
- Отдельно прослежен путь исключения коммитов «подтяжка main» (`_PULL_MAIN_COMMIT_INFIX`) — префикс `f"{task_id}: подтяжка "` совпадает буквально с обоими местами, что пишут такие коммиты (`orchestrator/fsm.py:125,305`).
- Отдельно проверено, что реальный `orchestrator/runner.py::_cmd_run` (строка 757) журналирует `agent run finished` безусловно при rc=0 без ошибки пайпа — правка `FakeRun` в `tests/test_auto_cycle.py` (журналирование на каждый холостой вызов) корректно моделирует это поведение, не подгоняет тест под код.

## Предложения системе

Пусто.
