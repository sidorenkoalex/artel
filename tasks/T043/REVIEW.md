---
task: T043
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 2
---

# REVIEW: RETRO: дайджест задачи в main на переходе в done/killed

## Гейт плана (Фаза A)

PLAN.md, «Подход», решение 3 переписано: снята неверная фраза
«единственный способ гарантировать лимит 30 строк для done без
исключения» (замечание к Фазе A итерации 1), теперь явно описывает
разведение `full=False` (done, первая строка) / `full=True` (killed,
целиком) с указанием источника риска (`runner.py:239-241`,
`agent_log.log_tail`, `config.LOG_TAIL_LINES`) и ссылкой на конкретный
тест-регресс. Решение 6 дополнено разбором привязки инцидента
killed-долга к `debt_id` с указанием строк и тестов. Обоснование теперь
соответствует коду (было главным замечанием Фазы A итерации 1 — снято).
Покрытие таблицы требований не изменилось (полное), шаги остались теми
же проверяемыми единицами, подход по-прежнему следует T042. Новых
конфликтов с конвенциями/архитектурой нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Без изменений с итерации 1 — `Ac1DoneRetroTest` зелёный. |
| 2 | OK | Без изменений — `cleanup.py` не тронут, `Ac2KillDoesNotTouchMainTest` зелёный. |
| 3 | OK | Без изменений — `AC-4` зелёный. |
| 4 | OK | Замечание-1 итерации 1 закрыто: `_escalations_block(steps, *, full)` (`orchestrator/retro.py:120-136`) для done (`full=False`) отдаёт ровно одну строку (первая строка `detail` + «…» при многострочности) — лимит 30 строк гарантирован статически, не зависит от содержимого `detail`. Проверено: `tests/test_retro.py::test_build_done_truncates_multiline_escalation_to_first_line` (15-строчный `detail`, имитирующий `log_tail`) — зелёный, файл ≤30 строк, «строка лога» в текст не попадает. |
| 5 | OK | Поля на месте, дефект многострочной эскалации устранён (см. требование 4). |
| 6 | OK | Без изменений — `build_killed` не тронут дефектом Замечания-1 (killed и так под исключением требования 4). |
| 7 | OK | `full=True` для killed сохраняет дословную цитату целиком — `test_build_killed_quotes_multiline_escalation_verbatim` зелёный. |
| 8 | OK | Без изменений с итерации 1. |
| 9 | OK | Замечание-2 итерации 1 закрыто: `_retro_incident`/`_commit_retro` в цикле подбора killed-долгов (`orchestrator/fsm.py:161`, `165`) теперь получают `debt_id` вместо `task_id` — привязка журнала и `alerts.raise_alert`/`target` внутри блока стала последовательной с `_write_and_stage_retro` (строка 164). Проверено: `tests/test_fsm_retro.py::GenerateAndCommitRetroTest::test_killed_debt_generation_failure_attributes_incident_to_debt_not_task` и `::test_killed_debt_commit_failure_attributes_incident_to_debt_not_task` (второй — с разными `target` у долга и мержащейся задачи) — оба зелёные, журнал уходит в `debt_id`, алерт — в `target` долга. |
| 10 | OK | Без изменений. |
| 11 | OK | Без изменений — см. AC-7. |
| 12 | OK | Без изменений. |
| 13 | OK | Без изменений. |
| AC-1 | OK | См. требование 4. |
| AC-2 | OK | Без изменений. |
| AC-3 | OK | См. требование 9. |
| AC-4 | OK | `Ac4DeterministicGenerationTest` зелёный. |
| AC-5 | OK | `NewGitCallsGoThroughGitcmdTest` зелёный. |
| AC-6 | OK | Прогнан самостоятельно: `python3 -m unittest discover -s tests` — 656 тестов (652 + 4 новых теста этой итерации), 3 провала, все три в `tests/test_multitarget.py::RoleEnvTest` (сверка GIT_AUTHOR/COMMITTER identity со стендом машины) — воспроизводится независимо от правок T043, вне зоны задачи. |
| AC-7 | OK | `git diff --stat main...task/t043-retro-daydzhest-zadachi-v-main` — только `docs/codebase-map.md`, `orchestrator/`, `tasks/T043/`, `tests/`; `.github/`, `skills/`, `templates/` не затронуты. `ProtectedPathsUntouchedTest` зелёный. |
| AC-8 | OK | Без изменений. |
| AC-9 | OK | Без изменений. |

## Замечания

Замечания итерации 1 (blocker — многострочная эскалация ломала лимит
30 строк для done; major — инцидент/журнал killed-долга уходили под
чужой task_id/target) проверены на исправление точечным чтением
`orchestrator/retro.py` и `orchestrator/fsm.py`, самостоятельным
прогоном изменённых тестов (`tests.test_retro`, `tests.test_fsm_retro`
— 20/20 зелёных), полного набора приёмочных тестов задачи
(`tasks/T043/acceptance_tests/` — 11/11 зелёных, включая
`ProtectedPathsUntouchedTest`) и полного `tests/` (656 тестов, 3
предсуществующих провала вне зоны задачи, воспроизводимых на HEAD без
правок T043). `scripts/guard.py tasks/T043/SPEC.md tasks/T043/PLAN.md`
— ок. Оба замечания устранены по существу, регресс-тесты
соответствуют сценариям поломки из итерации 1 и падали бы на старом
коде (проверено чтением: с `task_id` вместо `debt_id` записи ушли бы в
чужой журнал/target; с недифференцированной full-цитатой
`build_done` вернул бы «строка лога» в тексте). Новых дефектов класса
«многострочный текст ломает лимит строк» или «неверная привязка
task_id/debt_id» в дифф этой итерации не найдено — единственные
источники многострочного текста в файле (`context_line`, `reason`
kill) остаются гарантированно однострочными по конструкции
(`_first_context_line` берёт первую непустую строку; `reason` kill —
литерал `"kill switch"`, `orchestrator/cleanup.py:113`, без
пользовательского ввода).

## Вердикт

approved — оба замечания итерации 1 устранены, подтверждено тестами и
самостоятельным прогоном; новых дефектов не найдено.
