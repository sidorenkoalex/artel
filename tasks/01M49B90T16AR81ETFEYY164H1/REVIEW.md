---
task: 01M49B90T16AR81ETFEYY164H1
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: CI ветки задачи — полный набор tests/ один раз на sha

## Фаза A: план

- Покрытие: в таблице PLAN есть все требования 1–8. Шаги — проверяемые единицы
  размера MR.
- Подход (вывод `open_pr` job `changes` + правило исполненного близнеца в пульте)
  не противоречит ADR-0016 и инварианту 36: в триггер не добавлены `paths`/`paths-ignore`.
  Сбой запроса PR даёт fail-safe: полный набор идёт на push.
- Замер (требование 7, AC-11): «2 → 1 на коммит» взят из одного наблюдения — задачи 01M484RNV3;
  `gh run list` в окружении роли недоступен, и PLAN об этом говорит.
  SPEC просит «по последним задачам», но указанная задача и честная оговорка
  допустимы. Замечанием не считаю.
- «Влияние на систему» соответствует diff: `orchestrator/ci.py`, тесты, карта; `ci.yml` —
  только приложением.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Приложение: `open_pr=true` только при числовом ответе > 0; `python`/`python-min` получают `skipped` на push при открытом PR и идут на `pull_request`. |
| 2 | OK | Push без PR и ошибка API дают пустой `open_pr` — набор идёт. `main` не затронут: шаг `open-pr` срабатывает только на `refs/heads/task/`. `code=false` бывает только на `main` (`scripts/ci_push_class.py:117`), поэтому на `task/**` правило не может держать пульт вечно. |
| 3 | OK | `_unexecuted_full_suite` (`orchestrator/ci.py:452`) подключён в `verifying_status` и `branch_status`. Индекс прогонов запрашивается и на зелёном пути, если пропущена проверка перечня. Неизвестное событие удерживает статус. |
| 4 | OK | `find_run_id` при нескольких красных прогонах выбирает прогон, где исполнилась проверка перечня (`orchestrator/ci.py:1041`). `trigger_rerun` идёт через тот же `find_run_id`. |
| 5 | OK | `git apply --check` приложения к дереву ветки — код 0; планка AC-1 зелёная. |
| 6 | OK (с замечанием R1-F1) | Свойства покрыты долгоживущим файлом задачи; дубль в `tests/test_ci_full_suite_once.py` — см. R1-F1. Ослабление `test_ac8_parsers_keep_outcomes_on_the_new_text` в рамках ANSWER-1, вариант А: `y` выбирается вне `ci.FULL_SUITE_CHECKS` из того же объявления, ожидание `VERIFYING_GREEN` и прочие утверждения не тронуты. |
| 7 | OK | См. Фазу A. |
| 8 | OK | `ci.FULL_SUITE_CHECKS` (`orchestrator/ci.py:27`) — одно объявление `name` проверок. Внешние target'ы (`not repo_context.is_artel(repo)`) и прочие `skipped` оцениваются по-старому. |

## Замечания

- major — `tests/test_ci_full_suite_once.py:53-164` — тест разработчика повторяет
  свойства, которые уже держит долгоживущий файл задачи
  `tests/test_01m49b90t16ar81etfeyy164h1_full_suite_once.py` (ADR-0020, п. 4;
  review-checklist «Повтор долгоживущего теста»). Метод за методом:
  - `test_skipped_push_waits_for_pr_execution` — AC-4 (`test_ac4_…`) и AC-7;
  - `test_unfinished_pr_does_not_complete_skipped_push` — AC-5 вариант 1;
  - `test_successful_pr_completes_skipped_push` — AC-6 и AC-12;
  - `test_unknown_event_of_skipped_full_suite_is_not_green` — AC-8 расклад 2;
  - `test_push_without_pr_needs_and_accepts_executed_suite` — AC-9 расклад 1;
  - `test_unrelated_skipped_check_and_external_project_keep_old_rule` — AC-13;
  - `test_declared_checks_match_workflow_job_names` — AC-14;
  - `FullSuiteRerunTest.test_failed_pull_request_is_selected_over_failed_push` — AC-10.

  Временная мутация подтверждает: всё, что ловит этот файл (`no_rule`,
  `rerun_first`, `no_external_guard`), ловит и долгоживущий файл. Новых сторожей файл не
  добавляет.

  Сценарий последствий: свойство сторожат два набора с разными фикстурами. Это два места
  правки при каждой смене механики. Кроме того, дубль с захардкоженными литералами имён
  (`PYTHON`, `PYTHON_MIN`, `test_ci_full_suite_once.py:13-14`, и regex по `ci.yml` в
  `:128`) расходится с долгоживущим, который берёт имена из `ci.yml`.

  В том же файле докстринги всех восьми методов — однострочная заявка
  «Ловит мутацию: …» без описания сценария и наблюдаемого свойства. Это отдельное
  требование review-checklist, Фаза B п. 3.

  Предложение: удалить `tests/test_ci_full_suite_once.py`. Если какой-то метод держит
  свойство, которого нет в долгоживущем файле, оставить только его — с докстрингом
  «сценарий → наблюдаемое свойство → Ловит мутацию» и пометкой, чего именно нет в
  долгоживущем. Удаление не ослабляет набор: файл новый, в базе его нет.

Наблюдение без замечания: условие `not skipped_events.issubset(...)` в
`_unexecuted_full_suite` (`orchestrator/ci.py:474`) на тестах эквивалентно одному
`not executed`: мутация «условие снято» зелёная в обоих файлах. Без индекса событие
близнеца тоже неизвестно, а `executed` его требует. Расхождение возможно, только когда
пропущенная проверка не попала в индекс, а близнец попал (пагинация). Тогда условие —
законная дополнительная защита fail-closed. Оставить можно.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | tests/test_ci_full_suite_once.py:53-164 | Файл повторяет AC-4…AC-14 долгоживущего `tests/test_01m49b90t16ar81etfeyy164h1_full_suite_once.py` (ADR-0020 п. 4); докстринги — только однострочная заявка без сценария | Двойная правка при каждой смене механики; литералы имён расходятся с источником в `ci.yml`; нарушено правило докстрингов | Удалить файл либо оставить только метод с уникальным свойством, оформив докстринг по test-authoring |

## Вердикт

changes_requested — закрыть R1-F1. Код пульта и приложение к `ci.yml` по существу
соответствуют SPEC; блокирующих дефектов в логике не найдено.

## Проверено исполнением

- `python3 artel.py plank-run 01M49B90T16AR81ETFEYY164H1` — `test_workflow_appendix.py`: 1 passed, код 0.
- Приложение, извлечённое из PLAN.md, проверено `git apply --check` на дереве ветки: код 0.
  `ci.yml` ветки совпадает с `main` (`git diff --quiet main -- .github/workflows/ci.yml` — 0).
- `python3 -m pytest -q tests/test_01m49b90t16ar81etfeyy164h1_full_suite_once.py tests/test_ci_full_suite_once.py tests/test_01m46d5zzqy7gbew5tbvq0p3zv_ci_event.py tests/test_ci_status.py tests/test_ci_rerun_command.py tests/test_ci_push_class.py` — 134 passed, 126 subtests passed.
- Временные мутации `orchestrator/ci.py`; код возвращён, `git status` чистый.
  Результат — долгоживущий / `test_ci_full_suite_once.py`:
  - `_unexecuted_full_suite` → `return []`: 28 failed / 2 failed;
  - `find_run_id` без `preferred`: 2 failed / 1 failed;
  - снят фильтр внешнего проекта: 4 failed / 1 failed;
  - снято условие события пропуска: зелёные оба (см. наблюдение выше);
  - «исполнен» = любое не-`skipped`: зелёные оба. Мутация эквивалентна: незавершённую
    проверку раньше ловит ветка `unfinished`.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md`: расходится только
  `built_at_sha` — карта свежая. Регенерация откачена.
- `grep` вызывателей `branch_status`/`verifying_status` в orchestrator/: все работают с ветками
  задач. `code=false` бывает только у push в `main` (`scripts/ci_push_class.py:117`), поэтому
  вечного `RUNNING` для документного коммита ветки задачи нет.

## Предложения системе

- В песочнице роли нет `ls`/`cp`/`patch` в PATH, а составные bash-команды отклоняются.
  Проверить `plan_appendix_ci.py --check-workflow` на дереве с наложенным приложением
  ревьювер сам не может — остаётся опираться на планку. Стоит дать в `plank-run`/пульте
  команду «наложить приложение PLAN во временное дерево и прогнать check-workflow».
