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

## Риски
- В репозитории пульта может не быть sha из GitHub (не сделан fetch) —
  `--record` отказывает с причиной, а не пишет сводку с ложным приростом.

## Предложения системе
