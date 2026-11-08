---
task: 01M6Y44ZPXPQCNYDXQG6FMZPK5
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Слежение за ценой набора тестов по отчёту junit CI main

## Подход
- `forge.py`: распаковка архива junit выносится из `_junit_report` в
  `_junit_xml` (те же пределы и тексты отказов), поиск/скачивание архива
  попытки — из `job_test_report` в `_gh_attempt_archive` (тексты отказов
  побайтно прежние). `_junit_report`, `_parse_junit`, `TestReport`,
  `green_base_commit` по поведению не меняются. Новые: `parse_junit_times`
  (тот же `_junit_xml`, свой разбор времени, отказ DTD и повтора ключа),
  `_GitHub.ci_suite_report`, `_GitHub.last_executed_commit` и публичные
  обёртки, выбирающие реализацию реестром `IMPLEMENTATIONS` (хостинг без
  реализации — отказ без сети).
- `orchestrator/suite_cost.py`: `size_bucket`, `summarize`, `merged_tasks`
  (`git log --first-parent` через `gitcmd.git`), `limit_level`
  (сравнение `seconds >= limit * ratio`), запись/чтение таблицы
  `suite_costs`, выбор предыдущей сводки (`git rev-list --first-parent sha`
  — первая встреченная запись проекта с отчётом), команда `cmd_suite_cost`.
- Таблица `suite_costs(target, sha, recorded_at, reason, summary JSON,
  PRIMARY KEY(target, sha))` — одним литералом `SUITE_COSTS_DDL` в `SCHEMA` и
  `migrate()`; запись `INSERT OR IGNORE` — повтор не пишет и не меняет.
- `doctor/suite_cost.py`: две строки на проект (CI против
  `config.SUITE_COST_CI_LIMIT_SEC`, локальный против
  `project_profile.full_suite_limit`), уровень `alert` — `raise_alert`
  с постоянным сообщением (дедуп). Коллаборанты — через фасад `doctor`.
- `config`: `SUITE_COST_CI_LIMIT_SEC = 2400`, `SUITE_COST_WARN_RATIO = 0.75`,
  `SUITE_COST_ALERT_RATIO = 0.85`. `docs/triggers.md` — строка 33.

## Шаги
1. `forge.py`: вынос помощников, `parse_junit_times`, `ci_suite_report`,
   `last_executed_commit`.
2. `config.py`, `schema.py` (таблица), `suite_cost.py` (сводка, запись, команда).
3. `artel.py`: команда `suite-cost` в таблице и в «Команды:».
4. `doctor/suite_cost.py`, подключение в `doctor/__init__.py` и `all_checks`.
5. `docs/triggers.md` строка `suite.cost`; карта `scripts/codebase_map.py`.
6. Свои юнит-тесты `tests/test_suite_cost_units.py` на свойства вне
   долгоживущего файла (неконечный `time`, отказы DTD/повтора ключа,
   хостинг без реализации — отказ без `gh`); прогон долгоживущего файла
   задачи (55/55) и затронутых модулей: `github_ci_report`,
   `registry_without_report`, `hosting_registry`, `ci_result`,
   `store_schema_migration_parity`, `help_registry`, `doctor_duration`,
   `suite_duration`, `doctor_lines`, `suite_near_limit`, `invariants`,
   `test_doctor` — зелёные.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 2 |
| 5 | 2 |
| 6 | 2, 3 |
| 7 | 4, 5 |
| 8 | 2 (константа), тест задачи AC-11 |

## Влияние на систему
- `job_test_report`/`_junit_report` перестроены на общие помощники без
  смены текстов и исходов; держат залоченные тесты
  `tests/test_01m6trm6h57tn8v14hgfv0nqxj_github_ci_report.py` — прогоняются
  в шаге. `green_base_commit` не тронут.
- Новая таблица не меняет `tasks` (паритет схемы
  `tests/test_store_schema_migration_parity.py` не затронут).
- Новая проверка doctor выдаёт только `ok`/`warn`/`skip`, исключений не
  бросает — коды выхода doctor прежние.
- Команда вне белого списка ролей.
- Откат — revert merge-коммита; таблица `suite_costs` в БД остаётся
  неиспользуемой (безвредно).

## Возврат из verifying (CI 42511586844)
1. `tests/test_01m42pencs26d0656x8fr7dfa7_gitcmd_explicit_repo.py::…::test_ac8_every_call_without_repo_is_in_the_allow_list`
   — исправлено: три вызова в `orchestrator/suite_cost.py`
   (`merged_tasks`, `_full_sha`, `_previous`) идут через
   `gitcmd.in_repo(config.ROOT, …)` — репозиторий пульта явный, перечень
   разрешённых не тронут. Тест зелёный.
2. `tests/test_01m574a6yqhapass9716z11g4q_actions_verdict.py::ArtelUnchangedTest::test_ac10_artel_check_runs_refusals_keep_previous_texts`
   («403 rate limit») — путь отказов check-runs задача не меняла:
   `git diff main -- orchestrator/ci.py` пуст, а дифф `forge.py` касается
   только `job_test_report` (вынос `_gh_attempt_archive`/`_junit_xml` с
   побайтно прежними текстами) и новых функций; `ci.verifying_status`/
   `branch_status`/`failed_check_names` артели в `forge` не заходят
   (`ci._pipeline_project` для артели отдаёт `""` до `forge`). Локально тест
   зелёный: 150 прогонов файла подряд (каждый со своим зерном), прогон в
   одном процессе с тестами задачи и `gitcmd_explicit_repo`, прогон с
   окружением CI (`CI`, `GITHUB_ACTIONS`, `GH_TOKEN`, `GH_REPO`). Лог CI
   роли недоступен (`gh run view` требует подтверждения) — текста
   расхождения в CI я не видел. Возвращать нечего: тексты уже прежние.
   Если тест краснеет в CI снова — нужен текст расхождения из лога (зерно
   печатается тестом «зерно: N»), чтобы воспроизвести его локально.

## Риски
- В репозитории пульта может не быть sha из GitHub (не сделан fetch) —
  `--record` отказывает с причиной, а не пишет сводку с ложным приростом.
- `actions_verdict` AC-10 в CI может оказаться зависимым от порядка в
  воркере xdist (локально не воспроизводится, см. «Возврат»).

## Предложения системе
- Причина возврата из verifying по красному CI называет упавший тест, но
  не несёт текста ассерта и зерна; роли `gh run view --log-failed`
  недоступен — нечем воспроизвести падение, зависящее от зерна или порядка
  (`orchestrator/fsm_advance.py` verifying → причина возврата).
