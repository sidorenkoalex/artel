---
task: 01M1SCQ6WZHMQVK1AHP9F392JZ
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 4
---

# REVIEW: регрессия №15 — рубеж «замечания ревью не отработаны» сверяется с коммитом ревьювера, а не с последним коммитом REVIEW.md

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (опорное время = автокоммит шага reviewer, либо запись журнала) | OK | `_reviewer_verdict_baseline` (fsm_advance.py:748) — фильтр по `_REVIEWER_STEP_AUTOCOMMIT_PREFIX`, точно совпадающему с `checkpoint.py:535` (`own_commit_marker`, роль `reviewer`); fallback на `store.task_steps` при отсутствии совпадающего коммита. Покрыто AC-1/AC-2 и в приёмочных (`IncidentScenarioTest`, `BaselineFallsBackToJournalTest`), и в юнитах (`tests/test_fsm_review_rework_gate.py`). |
| 2 (OR: коммит developer в коде ИЛИ запись журнала после `state -> in_dev`, через общую функцию) | OK | fsm_advance.py:842 зовёт `auto._role_step_since_state_entry(conn, task_id, "in_dev", "developer")` — ту же функцию, что уже использует журнальный гейт `auto.py` (не независимая копия). AC-3/AC-4 подтверждены `DeveloperStepAfterBaselinePassesTest`, `SharedRoleStepCriterionTest` (легитимный первый вход, ANSWER-3). |
| 3 (отказ называет оба момента и источник) | OK | fsm_advance.py:846-850 формирует `detail` с `review_ts.isoformat()`, источником и `code_ts_text`. Прогон `RefusalNamesBothMomentsAndSourceTest` подтверждает обе даты и слово `reviewer` в тексте отказа. |
| 4 (правка леджера developer'ом не сдвигает опорное время) | OK | Фильтр по префиксу сообщения берёт РОЛЬ из сообщения автокоммита (`checkpoint.py` пишет `role` дословно) — автокоммит шага `developer` не проходит фильтр `reviewer`, даже будучи самым свежим коммитом REVIEW.md. `test_ac2_developer_ledger_edit_does_not_move_the_baseline` — зелёный. |
| AC-8 (регрессия №13 не ослаблена) | OK | `tests/test_auto_cycle.py` не тронут диффом; полный прогон — 33/33 теста зелёные (см. «Проверено исполнением»). |

Импорт `auto` в `fsm_advance.py` на уровне модуля не создаёт цикла — `auto.py` импортирует `fsm` (не `fsm_advance`), сам `fsm_advance` из `auto` не импортируется обратно; проверено прогоном (см. ниже).

## Замечания

- minor — `orchestrator/fsm_advance.py:839-845` — новая ветка поведения не покрыта тестом: когда `_latest_developer_commit_iso_date` не находит ни одного коммита developer (`code_ts is None` — кодовая ветка ещё не существует либо git не ответил, а не «developer никогда не запускался» — это отдельный, покрытый AC-7 случай с реальным коммитом ДО вердикта), рубеж больше не выходит сразу в «не отказывать» (как было в регрессии №13 — `if code_ts is None: return False`), а проваливается в проверку журнала: если она тоже не находит сигнала, рубеж ОТКАЗЫВАЕТ. Докстринг (fsm_advance.py:819-826) описывает это осознанно («журнальное условие OR при этом всё равно проверяется отдельно») — это не противоречит требованию 2 буквально (OR из двух сигналов, ни один не сработал → отказ обоснован), но ни один тест (ни `tests/test_fsm_review_rework_gate.py`, ни приёмочная планка) не создаёт сценарий с отсутствующей/несуществующей кодовой веткой, чтобы зафиксировать этот выбор — при следующей правке рубежа риск тихо откатить его к старому «нечем сверить -> не отказывать» и не заметить регресс тестами. Предложение: добавить юнит-тест на `_review_rework_gate_refuses` (не только на `_reviewer_verdict_baseline`) со случаем «код-ветка не существует, журнал тоже пуст» → рубеж отказывает.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | orchestrator/fsm_advance.py:839-845 | ветка `code_ts is None` → журнальная проверка не покрыта тестом | будущая правка рубежа может тихо вернуть старое «нечем сверить — не отказывать» без красного теста | добавить юнит-тест на `_review_rework_gate_refuses` для случая «нет коммитов developer в коде И нет записи журнала» |

## Вердикт

approved

Единственное замечание — minor (пробел в тест-покрытии сознательно задокументированного вырожденного случая, не дефект поведения). Обоснование по SPEC — полное, все AC-1..AC-8 подтверждены прогоном приёмочных и юнит-тестов, регрессия №13 не ослаблена, `docs/codebase-map.md` актуален по содержимому, импортного цикла нет.

## Проверено исполнением

- `python3 -m unittest tests.test_fsm_review_rework_gate tests.test_auto_cycle tests.test_advance_guard -v` — 54 теста, все зелёные (включая `AutoLeaseTest`, `AutoNeverPassesAGateTest`, `AutoStepLimitTest`, `AutoStopsOnRepeatedAdvanceRefusalTest` и весь `test_auto_cycle.py` — AC-8).
- `python3 -m unittest discover -s tasks/01M1SCQ6WZHMQVK1AHP9F392JZ/acceptance_tests -p "test_review_rework_gate.py" -v` — 9 приёмочных тестов задачи, все зелёные (AC-1..AC-7 целиком, настоящий git с управляемой `GIT_COMMITTER_DATE`).
- `python3 scripts/codebase_map.py` — перегенерировал карту и сверил с закоммиченной версией построчно без строки `built_at_sha`: содержимое совпадает целиком (единственная разница в диффе MR — сама строка `built_at_sha`), после сверки восстановил файл `git checkout -- docs/codebase-map.md`.
- `python3 -c "import orchestrator.fsm_advance"` и `python3 -c "import orchestrator.auto"` — оба модуля импортируются без ошибок, цикла импорта нет (подтверждает довод PLAN «Влияние на систему»).
- Прочитал `orchestrator/auto.py::_role_step_since_state_entry`/`_is_legit_first_entry_detail`/`_LEGIT_FIRST_ENTRY_DETAILS` и `orchestrator/checkpoint.py:535` (`own_commit_marker`) — сверил сигнатуру вызова и текст префикса автокоммита с реализацией.

## Предложения системе
