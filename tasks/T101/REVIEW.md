---
task: T101
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 3
---

# REVIEW: Fingerprint окружения в журнале шага

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (AC-1) | OK | `orchestrator/agent_log.py::environment_fingerprint()` возвращает версию+путь Python (`platform.python_version()`, `sys.executable`), версию git и версию claude CLI (`_tool_version_text(["git","--version"])`/`(["claude","--version"])`); проверено `tests/test_agent_log.py::EnvironmentFingerprintTest` и приёмочным `test_ac1_...`. Не менялось в итерации 2. |
| 2 (AC-2) | OK | Каждое поле собирается независимо в `_tool_version_text`, таймаут 5с (`ENV_FINGERPRINT_TIMEOUT_SEC`), `OSError`/`TimeoutExpired` → `"недоступно: <причина>"` без исключения наружу; подтверждено приёмочными `test_ac2_agent_step_missing_and_timeout.py` (оба сценария) и юнит-тестами. Не менялось в итерации 2. |
| 3 (AC-6) | OK | Модульный global-кэш `_environment_fingerprint_cache`; приёмочные `test_ac1_ac4_ac6...::test_ac6_repeated_reads_do_not_repeat_subprocess_calls` и `test_ac2_...::test_ac6_missing_git_is_still_looked_up_only_once` подтверждают ровно 1 вызов на процесс, включая сценарий отказа. Не менялось в итерации 2. |
| 4а (AC-4) | OK | `orchestrator/runner.py::run_agent_once` — fingerprint суффиксом к `detail` событий `"agent run started"`/`"agent run finished"`, сигнатура `store.journal` не изменена. Не менялось в итерации 2. |
| 4б (AC-5) | OK | `orchestrator/fsm_advance.py::review()` покрыт (оба исхода). Требование 4б/AC-5 буквально называет только `fsm_advance.py`/`fsm_autogate.py` — реализация соответствует этому тексту дословно. Третий фактический вызов `acceptance.run` (`orchestrator/fsm.py:204`, R1-F1 итерации 1) лежит вне буквальной зоны AC-5/AC-8; итерация 2 закрывает этот пункт эскалацией, не кодом — см. «Реестр замечаний» и «Замечания» ниже. |
| 5 (AC-7) | OK | `catalog.py::cmd_log` печатает `detail` без урезания (`orchestrator/catalog.py:230-234`); подтверждено `test_ac7_log_command_shows_fingerprint.py`. Не менялось в итерации 2. |
| 6 (AC-8) | OK | Инкрементальный diff итерации 2 (`git diff --name-only 4c345f2212aaabb9b4ed81b274744ad9f0b85766...HEAD`) содержит только `tasks/T101/PLAN.md` и `tasks/T101/REVIEW.md` — оба в собственной зоне задачи, ни один запрещённый или защищённый путь не тронут. Полная зона от база ветки (проверено в итерации 1) не изменилась: `orchestrator/agent_log.py`, `orchestrator/runner.py`, `orchestrator/fsm_advance.py`, `docs/codebase-map.md`. |
| 7 (AC-9) | OK | Все 6 сценариев требования покрыты юнит- и приёмочными тестами; `test_ac9_coverage_manifest.py`. Не менялось в итерации 2. |
| AC-10 | OK | Полный набор `tests/` (1209 тестов) зелёный, перепрогнан в этой итерации. |

## Замечания

- (нет новых замечаний по коду — итерация 2 не меняет ни одного `*.py`, только `tasks/T101/PLAN.md`/`tasks/T101/REVIEW.md`.)
- Закрытие R1-F1 (было major в итерации 1): итерация 1 требовала не самовольной правки `orchestrator/fsm.py`, а эскалации Оператору за решением по зоне («changes_requested — исправить R1-F1 эскалацией..., не самовольным выходом за неё»). PLAN.md итерации 2 (секция «Эскалация») делает ровно это: формулирует вопрос Оператору с вариантами и дефолтом («нет, зона не расширяется» — если Оператор промолчит), фиксирует причину, почему разработчик не может решить это сам (два независимых механических барьера — локед-тест и SPEC-зона), и явно помечает пробел как документированное ограничение задачи, а не молчаливый дефект. Обе фактические претензии, на которых держится эта эскалация, проверены заново в этой итерации и подтвердились (см. «Проверено исполнением»): `ALLOWED_EXACT` в `test_ac8_change_zone_restricted.py` не включает `fsm.py` (правка красит локед-тест), и `acceptance.run` в кодовой базе действительно вызывается ровно в двух местах (`fsm_advance.py:177`, `fsm.py:204`) — второе вне буквальной зоны AC-5/AC-8. Обоснование `rejected` выдерживает критику: запись переведена в `accepted`.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/fsm.py:204 (`_pull_main_or_escalate`) | Третий фактический вызов `acceptance.run`, чей red-исход журналируется (`store.set_state`→`journal`), не снабжён fingerprint; вне буквальной зоны AC-5/AC-8 | Диагностическая цель требования 1 не достигается именно в сценарии подтяжки main — задокументированное ограничение, не скрытый дефект | Разработчик не мог закрыть это кодом (локед-тест `test_ac8_change_zone_restricted.py` и роль-барьер на правку SPEC/зоны) и корректно эскалировал Оператору в `tasks/T101/PLAN.md` («Эскалация») с дефолтом «не расширять». Ревьювер подтвердил оба фактических основания эскалации (grep по `acceptance.run(`, чтение `ALLOWED_EXACT`) и принимает это как выполнение требования итерации 1 («исправить эскалацией, не выходом за зону»). Дальнейшее решение — за Оператором по существу вопроса из PLAN.md; на статус этой задачи (AC-5/AC-8 в их буквальной формулировке выполнены) не влияет. |

## Вердикт
approved — все требования SPEC реализованы (AC-1..AC-10), зона соблюдена, тесты зелёные. R1-F1 закрыт: требуемая итерацией 1 эскалация Оператору выполнена корректно (роль разработчика не может решить вопрос зоны самостоятельно), фактические основания эскалации перепроверены и подтвердились. Открытый вопрос о расширении зоны на `orchestrator/fsm.py` остаётся за Оператором в `tasks/T101/PLAN.md` («Эскалация») — это решение по объёму будущей работы, не блокер текущей реализации по SPEC T101.

## Проверено исполнением
- `python3 -m scripts.guard tasks/T101/SPEC.md tasks/T101/PLAN.md tasks/T101/REVIEW.md` — «GUARD: ок (3 файлов)».
- `python3 -m unittest discover -s tests` — 1209 тестов, все зелёные (AC-10).
- `python3 -m unittest tasks.T101.acceptance_tests.test_ac10_full_suite_stays_green tasks.T101.acceptance_tests.test_ac1_ac4_ac6_agent_step_available tasks.T101.acceptance_tests.test_ac2_agent_step_missing_and_timeout tasks.T101.acceptance_tests.test_ac3_agent_step_outcome_unaffected tasks.T101.acceptance_tests.test_ac5_acceptance_run_fingerprint tasks.T101.acceptance_tests.test_ac7_log_command_shows_fingerprint tasks.T101.acceptance_tests.test_ac8_change_zone_restricted tasks.T101.acceptance_tests.test_ac9_coverage_manifest -v` — 15 тестов, все зелёные (AC-1..AC-10 приёмочные сценарии; все 8 файлов `test_ac*.py`, включая `test_ac10`, покрыты).
- `git diff --name-only 4c345f2212aaabb9b4ed81b274744ad9f0b85766...HEAD` — инкрементальный diff итерации 2 содержит только `tasks/T101/PLAN.md` и `tasks/T101/REVIEW.md`; кода вне зоны задачи нет.
- `grep -n "acceptance\.run(" orchestrator/*.py` — подтверждает ровно два фактических вызова в кодовой базе: `orchestrator/fsm_advance.py:177` (в зоне AC-5) и `orchestrator/fsm.py:204` (вне зоны) — фактическое основание R1-F1 и его эскалации проверено заново.
- Чтение `tasks/T101/acceptance_tests/test_ac8_change_zone_restricted.py` — `ALLOWED_EXACT` буквально перечисляет 6 путей и не включает `orchestrator/fsm.py`; проверка на точное множество (`f not in ALLOWED_EXACT`), не на префикс — правка `fsm.py` действительно покрасила бы этот локед-тест, подтверждая механический барьер, на который ссылается эскалация.

## Предложения системе
(нет)
