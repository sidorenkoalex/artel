# Инварианты системы

Реестр системных инвариантов Артели: что именно не должно сломаться ни в
одной фазе, каким тестом это ловится механически и откуда инвариант взят.

Инварианты — защиты в смысле ADR-0002 (принцип целостности). Ослабить,
отключить, заскипать или удалить кодирующий их тест может **только
Оператор отдельным ADR**; для роли конвейера такая правка — blocker
в ревью, а не задача. Роль, которой инвариант мешает выполнить SPEC,
эскалирует (skills/escalation-rules.md), а не переписывает тест.

Оба файла реестра — `tests/test_invariants.py` и этот документ — стоят
в `PROTECTED` job'а `protected-paths` (.github/workflows/ci.yml): их
изменение в PR помечается предупреждением, как и правка конфигов системы.
В Фазе 0 это предупреждение, после разделения токенов — fail (ADR-0001).

Источники: README «Инварианты», docs/design.md (§2 роли и права, §4 циклы
и политика гейтов, §6 runtime и FSM, §7 наблюдаемость, §10 экономика),
docs/adr/0002-integrity-principle.md, CLAUDE.md.

## Кодированные тестами

Тест назван модулем и классом; `test_invariants.py` — модуль, целиком
состоящий из инвариантов, остальные помечены шапкой-маркером.

| # | Инвариант | Тест(ы) | Откуда |
|---|---|---|---|
| 1 | Оркестратор не думает: LLM запускает только команда `run`, переходы FSM считает код | `test_invariants.AgentRunsOnlyFromRunTest` | README 1; design §2, §4 |
| 2 | Задачу двигают статусы артефактов в `tasks/<id>/`, а не что-либо ещё | `test_invariants.FreshVerdictGuardsAcceptanceTest.test_every_return_to_dev_requires_a_new_verdict` | README 2; design §3 |
| 3 | У каждого цикла числовой лимит; после лимита — Оператор, не ретрай | `test_review_freshness.ReviewFreshnessScenarioTest`; `test_agent_failure.CmdRunFailureTest`; `test_invariants.CountersNeverResetTest.test_exhausted_review_limit_is_not_reopened_by_escalation` | README 3; design §4 |
| 4 | Счётчики итераций глобальные на задачу: ни один переход, включая эскалацию и возврат из неё, их не сбрасывает | `test_invariants.CountersNeverResetTest` | design §4 |
| 5 | Транзиентный ретрай внутри шага не считается итерацией цикла | `test_agent_failure.CmdRunFailureTest.test_retries_are_not_review_iterations` | design §6 |
| 6 | Молчание ≠ согласие: сколько ни опрашивай `advance`, ручной гейт стоит | `test_invariants.ManualGatesNeedTheOperatorTest.test_repeated_polling_does_not_pass_a_gate` | README 4; design §4, §6 |
| 7 | Ручной гейт (spec_gate, acceptance, merge_gate) проходит только `approve`/`reject` Оператора | `test_invariants.ManualGatesNeedTheOperatorTest` | design §4 |
| 8 | Потолок задачи = её денежный бюджет: жёсткий, с алертом на 70% | `test_step_cost.CmdRunCostTest` | README 5; design §6, §10 |
| 9 | Исчерпанный бюджет блокирует запуск агента и не обходится переходами FSM | `test_invariants.ExhaustedBudgetIsNotBypassableTest` | design §6 |
| 10 | Поднять потолок может только Оператор командой `budget` | `test_invariants.ExhaustedBudgetIsNotBypassableTest.test_only_the_operator_ceiling_unblocks_the_run`; `test_step_cost.CmdBudgetTest` | design §4 («увеличение лимитов — manual всегда») |
| 11 | Журнал шагов пишется всегда: запуск, исход, стоимость, сбой лога, уборка | `test_agent_log.CmdRunLoggingTest`; `test_step_cost.CmdRunCostTest.test_step_cost_lands_in_spent_and_journal`; `test_kill_cleanup.KillCleanupTest.test_cleanup_is_listed_in_the_journal` | README 5; design §6, §7 |
| 12 | git merge выполняет только `approve` из merge_gate — другого пути в системе нет | `test_invariants.MergeOnlyFromMergeGateTest` | design §2, §4; CLAUDE.md |
| 13 | Переход review → acceptance невозможен без свежего вердикта ревьювера | `test_invariants.FreshVerdictGuardsAcceptanceTest`; `test_review_freshness.FreshVerdictIterationTest` | design §4; artel.py `fresh_verdict_iteration` |
| 14 | Kill switch срабатывает всегда: состояние меняется, что бы ни ответили git и ФС | `test_kill_cleanup.CleanupWithoutGitTest` | design §6 |
| 15 | `kill` не изменяет main и не удаляет содержимое, попавшее в main | `test_invariants.KillKeepsMainIntactTest` | design §6 (артефакты остаются как история) |
| 16 | История наблюдаемости переживает задачу: `.artel/logs/` уборка не трогает | `test_kill_cleanup.KillCleanupTest.test_run_logs_survive_the_kill` | design §7 |
| 17 | Оценка влияния на систему — артефакт: PLAN без секции «Влияние на систему» не проходит guard | `test_invariants.GuardKeepsTheIntegritySectionTest` | ADR-0002, правило 1 |
| 18 | Автоматизация механических команд не проходит гейты: `auto` не вызывает `approve`/`reject` и пути мимо гейта не имеет | `test_auto_cycle.AutoNeverPassesAGateTest` | design §4; tasks/T014/SPEC.md, требование 3 |

## На ревью — тестом не выражаются

Эти инварианты живут в промптах, правах доступа и CI. Юнит-тест на них
либо ничего не доказывает (проверял бы текст промпта, а не поведение),
либо требует механизмов, которых в Фазе 0 ещё нет. Их проверяет ревьювер
(skills/review-checklist.md, пункт 6) и Оператор на гейтах.

| Инвариант | Почему не кодируется | Кто проверяет |
|---|---|---|
| Всё детерминированное — код и пайплайны, а не LLM (README 1 целиком) | Тест ловит только факт «агент не запущен»; «здесь нужно суждение, а здесь нет» — проектное решение, а не наблюдаемое поведение | ревью, Оператор |
| Ревьювер работает свежим контекстом и не наследует контекст разработчика | Свойство рантайма и промпта: агент физически имеет доступ к репозиторию, изоляция контекста не проверяется изнутри процесса | ревью, дизайн запуска (`cmd_run`) |
| Артефакт — единственный канал передачи между ролями (в части «не история чата») | То же: отсутствие внеартефактного канала недоказуемо тестом оркестратора | ревью |
| Разработчик не мержит, ревьювер не правит код | В Фазе 0 один токен на все роли (ADR-0001), разделение прав существует в промптах; enforcement — branch protection и отдельные PAT | ревью, CI, ADR-0001 |
| Конфиги системы (gates.yaml, roles.yaml, .github/, templates/, skills/) меняет только Оператор | Проверка живёт в CI (job `protected-paths`), а не в коде оркестратора; в Фазе 0 деградирует до предупреждения — один аккаунт | CI, Оператор |
| Guards неотключаемы: смержить с красным CI нельзя | Свойство branch protection и настроек репозитория, вне кода | Оператор, настройки репо |
| Ручной гейт не проходится по таймауту: `awaiting-approval` шлёт напоминание, но никогда не подтверждает (design §6) | У FSM Фазы 0 нет часов и фонового процесса: `advance` времени не смотрит, автопроходить нечему. Подмена `artel.now` в тесте дала бы видимость покрытия, а не покрытие. Кодируется вместе с напоминаниями | ревью, Оператор |
| Policy проверяет оркестратор, а не агент | Policy-движка в Фазе 0 нет: gates.yaml справочный, все гейты захардкожены ручными. Кодируется вместе с движком в MVP | ревью, дизайн |
| Шаг идемпотентен, агент эфемерен, чекпоинт = последний артефакт в git | Проверяется реальным прогоном (перезапуск шага с чистого контейнера), не юнитом | Оператор, прогон конвейера |
| Прод-креды только в пайплайне; песочница агента без сети наружу | Вне объёма Фазы 0 (нет деплоя и песочницы в CI) | Оператор |
| Ослабление любой защиты — только Оператором через ADR | Мета-инвариант процесса: его субъект — роль, а не код | ревью (blocker), Оператор |

## Как добавить инвариант

1. Сформулировать как проверяемое утверждение о поведении системы, а не
   о структуре кода: «X невозможен ни одной командой», а не «в функции
   Y есть проверка Z».
2. Закодировать тестом в `tests/test_invariants.py`, если он выразим;
   иначе — строкой во второй таблице с честной причиной.
3. Проверить мутацией: умышленно сломать инвариант в коде и убедиться,
   что тест краснеет. Тест, не падающий на сломанном инварианте, —
   не защита, а декорация.
4. Добавить строку в первую таблицу: инвариант → тест → источник.
