---
task: 01M6Y44ZPXPQCNYDXQG6FMZPK5
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Слежение за ценой набора тестов по отчёту junit CI main (ADR-0032, этап 1)

## Фаза A — план
Таблица покрытия PLAN полна (требования 1–8 → шаги 1–5 и тест AC-11), шаги размера MR.
Подход (вынос `_junit_xml`/`_gh_attempt_archive` из `_junit_report`/`job_test_report`
с прежними текстами, таблица одним литералом `SUITE_COSTS_DDL` в `SCHEMA` и `migrate()`,
проверка doctor через фасад) не конфликтует с архитектурой. «Влияние на систему»
совпадает с diff: вне зон SPEC ничего не тронуто, `green_base_commit` в diff не входит,
`ci.py`/`targets.py`/`.github/` не менялись. Откат описан.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `forge.parse_junit_times` через общий `_junit_xml` (те же пределы/отказы); `_parse_junit_times` — отказ DTD, повтор ключа, пустой/нечисловой/неконечный `time`. `TestReport`/`_parse_junit` не менялись; тексты отказов `job_test_report` перенесены побайтно (сверено по diff `forge.py:400-405`, `:576-637`). |
| 2 | OK | `_GitHub.ci_suite_report`: `_gh_attempt` по тому же правилу, `skipped` → «задание не исполнялось», `job_seconds = completed_at − started_at`, архив `targets.CI_REPORT_ARTIFACT_DEFAULT`; хостинг без реализации — `_tuple_call` без сети. |
| 3 | OK | `last_executed_commit` — по статусу задания (`status == completed`, conclusion ∉ {None, skipped}) — как в указании Оператора п. 2–3 (`cancelled` исполненный). `green_base_commit` не тронут. |
| 4 | OK | `size_bucket`, `limit_level` (умножением, `>=`), `summarize` (число = ключей `times`, сортировка `(-t, node)`, четыре ориентира, прирост), `merged_tasks` (`--first-parent prev..sha`, фильтр по БД и проекту артели), `_previous` (rev-list первой линии, только записи с `tests`). |
| 5 | OK | `suite_costs(target, sha, …, PRIMARY KEY(target, sha))`, `INSERT OR IGNORE`; последняя — `ORDER BY recorded_at DESC, rowid DESC`. |
| 6 | OK | `cmd_suite_cost`: печать без записи, `--record` (отказ при `job_seconds is None`, ненулевой код), `--record-latest`; строка в «Команды:», вне `_ROLE_ALLOWED_COMMANDS`. |
| 7 | OK | `doctor/suite_cost.py`, две строки на проект, `warn`/«предупреждение»/«тревога», `raise_alert` с сообщением без чисел; `TargetsError` перехвачен; `fail` нет. `docs/triggers.md` — одна строка №33 с `suite.cost` и `SUITE_COST_ALERT_RATIO` (сверено ревью диффа по указанию Оператора п. 1), прочие строки не тронуты. |
| 8 | OK | `config.SUITE_COST_CI_LIMIT_SEC = 2400`; AC-11 зелёный. |

## Замечания

- minor — tests/test_suite_cost_units.py:1,26,36,50 — докстринг модуля по-английски (в репозитории — по-русски), докстринги методов несут только «Ловит мутацию: …» без сценария и наблюдаемого свойства (skills/review-checklist, Фаза B п. 3). Заявки при этом наблюдаемы (`times` не `None`/вызов `gh`). Предложение: при следующей правке файла дописать строку сценария. На вердикт не влияет.
- minor — orchestrator/doctor/suite_cost.py:29-31 — `seconds / limit` без защиты от `limit == 0`; при нулевом `full_suite_timeout_sec` профиля `all_checks` упал бы `ZeroDivisionError`. Сценарий маловероятен (предел профиля положителен), поэтому minor.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | tests/test_suite_cost_units.py:1,26,36,50 | докстринги без сценария, модуль по-английски | читаемость теста; заявки мутаций наблюдаемы | minor, на вердикт не влияет — дописать при следующей правке |
| R1-F2 | accepted | orchestrator/doctor/suite_cost.py:29-31 | деление на `limit` без защиты от нуля | `ZeroDivisionError` в `all_checks` только при нулевом пределе профиля | minor, принято как есть |

## Вердикт
approved — blocker/major нет; требования 1–8 реализованы, планка (долгоживущий файл
задачи) и затронутые тесты зелёные, карта свежая, CI коммита 74bee5ef зелёный.

## Проверено исполнением
- `artel.py plank-run 01M6Y44ZPXPQCNYDXQG6FMZPK5` — отказ «планки нет: в источнике нет файлов test_*.py» (планка задачи — долгоживущий файл в `tests/`), поэтому этот файл прогнан pytest напрямую.
- `python3 -m pytest -q -p no:cacheprovider -p no:xdist tests/test_suite_cost_units.py tests/test_01m6y44zpxpqcnydxqg6fmzpk5_suite_cost.py tests/test_01m6trm6h57tn8v14hgfv0nqxj_github_ci_report.py tests/test_store_schema_migration_parity.py tests/test_01m42pencs26d0656x8fr7dfa7_gitcmd_explicit_repo.py tests/test_01m5m0kqpv0fj9nsmdcq3xb76w_help_registry.py` — 130 passed, 19 subtests passed (51,5 с). С `-n 4` сессия xdist упала «node down» до сбора — среда, не код.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` — меняется только строка `built_at_sha`, по содержимому карта свежая; файл возвращён `git checkout`.

## Предложения системе
- `plank-run` отказывает «планки нет», когда вся планка задачи — долгоживущий файл `tests/test_<id>_*.py` из перечня лока; бриф ревьювера при этом велит гонять планку только этой командой (orchestrator/plank_run.py) — стоит, чтобы команда гоняла и файлы перечня лока.
