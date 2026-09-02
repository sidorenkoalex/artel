---
task: T101
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 3
---

# REVIEW: Fingerprint окружения в журнале шага

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (AC-1) | OK | `orchestrator/agent_log.py::environment_fingerprint()` возвращает версию+путь Python (`platform.python_version()`, `sys.executable`), версию git и версию claude CLI (`_tool_version_text(["git","--version"])`/`(["claude","--version"])`); проверено `tests/test_agent_log.py::EnvironmentFingerprintTest` и приёмочным `test_ac1_...`. |
| 2 (AC-2) | OK | Каждое поле собирается независимо в `_tool_version_text`, таймаут 5с (`ENV_FINGERPRINT_TIMEOUT_SEC`), `OSError`/`TimeoutExpired` → `"недоступно: <причина>"` без исключения наружу; подтверждено приёмочными `test_ac2_agent_step_missing_and_timeout.py` (оба сценария — git missing, claude timeout) и юнит-тестами. |
| 3 (AC-6) | OK | Модульный global-кэш `_environment_fingerprint_cache`; приёмочный `test_ac1_ac4_ac6...::test_ac6_repeated_reads_do_not_repeat_subprocess_calls` и `test_ac2_...::test_ac6_missing_git_is_still_looked_up_only_once` подтверждают ровно 1 вызов `git --version`/`claude --version` на процесс, включая сценарий отказа. |
| 4а (AC-4) | OK | `orchestrator/runner.py::run_agent_once` — fingerprint добавлен суффиксом к `detail` событий `"agent run started"` и `"agent run finished"`, сигнатура `store.journal` не изменена. |
| 4б (AC-5) | **Реализовано не полностью** | `orchestrator/fsm_advance.py::review()` покрыт (оба исхода — красный/зелёный). Но это не единственная фактическая точка вызова `acceptance.run` в кодовой базе — см. замечание R1-F1 ниже: пропущен `orchestrator/fsm.py::_pull_main_or_escalate` (строка 204). |
| 5 (AC-7) | OK | `catalog.py::cmd_log` печатает `detail` без урезания (`orchestrator/catalog.py:230-234`) — fingerprint виден без доп. кода; подтверждено `test_ac7_log_command_shows_fingerprint.py`. |
| 6 (AC-8) | OK | `git diff --name-only $(git merge-base main HEAD) HEAD` вне `tasks/T101/`/`tests/`/`docs/codebase-map.md` содержит только `orchestrator/agent_log.py`, `orchestrator/runner.py`, `orchestrator/fsm_advance.py` — все в разрешённой зоне; запрещённые файлы (`store.py`, `catalog.py`, `doctor.py` и т.д.) не тронуты. Регенерация карты сверена вручную: содержимое совпадает с перегенерированным, расходится только `built_at_sha` (легитимно). |
| 7 (AC-9) | OK | Все 6 сценариев требования покрыты и юнит-, и приёмочными тестами; структурная проверка полноты — `test_ac9_coverage_manifest.py`. |
| AC-10 | OK | Полный набор `tests/` (1209 тестов) зелёный. |

## Замечания

- major — `orchestrator/fsm.py:204` (функция `_pull_main_or_escalate`, строки 127-213) — в кодовой базе есть ТРЕТЬЯ фактическая точка вызова `acceptance.run` (`grep -n "acceptance\.run(" orchestrator/*.py` находит её наряду с `fsm_advance.py:177`), которую PLAN вообще не упоминает и не инструментирует. Её red-исход журналируется: `store.set_state(conn, task_id, "escalated", "fsm", detail=f"приёмочные тесты красные после подтяжки {config.MAIN_BRANCH}...")`, а `set_state` сама вызывает `journal(...)` (`orchestrator/store.py:540`) — то есть это ровно "событие журнала, фиксирующее исход прогона приёмочных тестов задачи" из требования 4б/AC-5, просто без fingerprint. Функция не мёртвый код — активно вызывается из `orchestrator/fsm_advance.py:390` (файл уже в diff этой задачи), `orchestrator/fsm_merge_gate.py:203`, `orchestrator/canary.py:69`, `orchestrator/fsm.py:577` (постмерж-подтяжка main в ветку задачи с повторным прогоном приёмки — сценарий, для которого fingerprint особенно ценен: расхождение версий инструментов между моментом review и моментом подтяжки main). Последствие: диагностическая цель требования 1 ("расхождение версий... невосстановимо задним числом") не достигается именно в сценарии, где расхождение вероятнее всего — после подтяжки main. При этом покрыть это без нарушения зоны нельзя: AC-8 явно не включает `orchestrator/fsm.py` в разрешённую зону, а AC-5 буквально называет только `fsm_advance.py`/`fsm_autogate.py`. Предложение: не решать это молча — по правилу требования 6 SPEC ("конфликт зон по ходу реализации — эскалация, не выход за границу") эскалировать Оператору вопрос расширения зоны AC-8 на `orchestrator/fsm.py::_pull_main_or_escalate`, либо получить явное решение, что подтяжка main вне охвата задачи (тогда стоит дописать это в SPEC «Не входит», а не оставлять как непроверенный пробел).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | rejected | orchestrator/fsm.py:204 (`_pull_main_or_escalate`) | Третий фактический вызов `acceptance.run`, чей red-исход журналируется (`store.set_state`→`journal`), не снабжён fingerprint; не упомянут в PLAN; вне зоны AC-8 | Диагностическая цель задачи не достигается для сценария подтяжки main в ветку задачи — именно там расхождение версий инструментов вероятнее всего | Код не менялся — эскалировано Оператору в `tasks/T101/PLAN.md` (секция «Эскалация»): правка `orchestrator/fsm.py` красит локед `test_ac8_change_zone_restricted.py` (`ALLOWED_EXACT` не включает файл), а расширение зоны/SPEC — не полномочие роли разработчика (нужны новые итерации analyst и test_author). Default при молчании Оператора — зона не расширяется, пробел остаётся документированным ограничением задачи. |

## Вердикт
changes_requested — исправить R1-F1 (эскалацией к Оператору за решением по зоне, не самовольным выходом за неё). Остальное реализовано по SPEC, тесты зелёные, зона (кроме отмеченного пробела) соблюдена.

## Проверено исполнением
- `python3 -m unittest discover -s tests` — 1209 тестов, все зелёные (AC-10).
- Все 7 файлов `tasks/T101/acceptance_tests/test_ac*.py` прогнаны индивидуально (`python3 -m unittest tasks.T101.acceptance_tests.test_ac...`) — 20 тестов, все зелёные (AC-1..AC-10 приёмочные сценарии).
- `python3 scripts/codebase_map.py` (регенерация в рабочую копию, затем `git checkout -- docs/codebase-map.md` для отката служебного прогона) — сравнение содержимого без строки `built_at_sha` показало полное совпадение с закоммиченной картой.
- `python3 -m scripts.guard tasks/T101/SPEC.md tasks/T101/PLAN.md` — «GUARD: ок (2 файлов)».
- `grep -n "acceptance\.run(" orchestrator/*.py` — нашёл вызов вне зоны diff (`orchestrator/fsm.py:204`), легший в основу R1-F1.
- Ручная сверка `orchestrator/runner.py::role_cmd()` — бинарь `"claude"` литералом совпадает с бинарём, версию которого снимает fingerprint.
- Ручная сверка `orchestrator/fsm_autogate.py` — вызывает только `acceptance.run_full_suite`, не `acceptance.run`; подтверждает утверждение PLAN, что этот файл вне требования 4б.
- Ручная сверка `orchestrator/catalog.py::cmd_log` — печатает `detail` без урезания (AC-7).

## Предложения системе
(нет)
