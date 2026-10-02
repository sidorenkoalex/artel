---
task: 01M3Y75C9TY76083CG1PK00EM4
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Проверка CI, зависшая в состоянии «идёт» при известном исходе, не останавливает задачу

# ТЗ: Проверка CI, зависшая в состоянии «идёт» при известном исходе, не останавливает задачу

Источник: строка копилки 02.10 (П2) «01M3XTFJCC… стояла в verifying 1 ч 20 мин»; решение Оператора 02.10.

Факты (origin/main 28b09389; номера строк аналитик сверяет):
- 02.10 задача 01M3XTFJCC5TG63FHW907GQM4D стояла в `verifying` с 08:31Z до 09:58Z. У коммита ветки 6cb9b55e check-run «Валидация артефактов» (id 110766383863, прогон pull_request 36984521183) GitHub отдавал с `status=in_progress`, но с `conclusion=success` и `completed_at=08:31:44Z`; оба прогона workflow (`gh run list`) были `completed/success`.
- `orchestrator/ci.py::verifying_status` (около строки 236) и `ci.branch_status` (около строки 336; его зовёт гейт мержа, `fsm_merge_gate.py:254`, `:301`) считают проверку идущей по одному полю `status != "completed"`; задача ждёт бесконечно, записи «статус CI ветки (verifying)» каждые 90 с.
- `ci-rerun` (`orchestrator/ci_rerun.py::_cmd_ci_rerun`, около строки 171) отказывает «CI ветки … не завершённо-красный (исход running) — повторять нечего»; при живом `auto` — отказ по lease. Обход 02.10: `stop`, ручной `gh run rerun 36984521183`, `auto`.

Требуется:
1. Проверка с `status` не `completed`, у которой есть непустые `conclusion` и `completed_at`, считается завершённой с этим исходом — одним правилом для `verifying_status` и `branch_status` (одна функция, без второй копии). Запись журнала статуса CI называет такую проверку отдельно: «<имя>: GitHub отдаёт status=<…> при conclusion=<…>, completed_at=<…> — считаю завершённой».
2. Проверка без `conclusion` в состоянии `in_progress`/`queued` дольше `config.CI_STUCK_CHECK_MINUTES` (новая константа, 45 мин, отсчёт от `started_at`, иначе от `created_at` check-run) — именованное состояние «проверка зависла»: запись журнала с именем проверки, id и возрастом; задача не продвигается и не эскалирует, но отказ `ci-rerun` её не блокирует (требование 3).
3. `ci-rerun <id> --reason …` принимает и состояние «проверка зависла» (требование 2) — перезапускает прогон workflow, к которому относится зависшая проверка (тот же механизм перезапуска, что для красного). Отказ по lease при живом цикле сохраняется (это не меняется).
4. Тесты в новом файле `tests/test_ci_stuck_check_run.py`, каждый с «Ловит мутацию: …»: а) `in_progress` + `conclusion=success` + `completed_at` → зелёный в `verifying` и на гейте мержа; б) то же с `conclusion=failure` → красный; в) `in_progress` без `conclusion` моложе порога → «идёт»; г) старше порога → «проверка зависла», `ci-rerun` не отказывает; д) запись журнала называет проверку и поля.

Зоны: orchestrator/ci.py, orchestrator/ci_rerun.py, orchestrator/config.py, tests/test_ci_stuck_check_run.py, docs/codebase-map.md.

Только чтение (не менять): orchestrator/auto.py, orchestrator/fsm.py, orchestrator/fsm_merge_gate.py, orchestrator/github_adapter.py, остальные файлы tests/, skills/, docs/adr/, docs/invariants.md, tests/test_invariants.py, tasks/.

Не входит: автоматический перезапуск зависшей проверки без команды Оператора; изменение опроса CI (период 90 с); правка `.github/`.

Рамка: $20.
