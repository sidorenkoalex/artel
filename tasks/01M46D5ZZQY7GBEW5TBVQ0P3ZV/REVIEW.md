---
task: 01M46D5ZZQY7GBEW5TBVQ0P3ZV
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Статус CI называет событие прогона (push / pull_request)

## Фаза A: план
- Таблица покрытия полна: требования 1–5 сведены к шагу 1. Шаг один,
  потому что зона кода — один файл `orchestrator/ci.py`; SPEC сам
  обосновывает монолит.
- Подход совпадает с архитектурой. Источник событий — тот же
  `actions/runs?head_sha=`, что у `find_run_id`. Сопоставление идёт по
  `check_suite.id`, запасной путь — id прогона из `details_url`. Исходы и
  префиксы, на которых стоят разборщики, не меняются.
- «Влияние на систему» сверено с diff: изменены только `orchestrator/ci.py`,
  `tests/test_ci_status.py` (одни добавления) и карта; долгоживущий файл
  изменён Оператором через `amend-tests` (ANSWER-1, коммит 6065c546).
- Откат — revert, это описано в плане.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Подпись строит `_run_label`. Красный: `_failed_listing`; «ещё идёт»: `_running_listing`; «зависла»: `_stuck_checks`, где подпись идёт после `status=S;` в тех же скобках. Всё это подключено в `verifying_status`, `branch_status` и `main_line_status`/`_main_line_note`. На main прогоны запрашиваются у того коммита линии, где проверка упала или идёт (`_main_line_runs`, `runs_at`). Событие вне push/pull_request выводится строкой как есть (AC-5). |
| 2 | OK | Фразу строит `_event_divergence`. `skipped` зелёной стороной не считается (`_EXECUTED_GREEN`); фразы нет, если проверка красная в обоих событиях или есть только одно событие. В тексте фразы нет подстрок, на которых стоят разборщики. |
| 3 | OK | `_commit_workflow_runs` возвращает `None` при ненулевом коде, неразборном JSON и неверной форме ответа. Тогда проверка подписывается «событие не определено», исход не меняется. |
| 4 | OK | Префиксы «CI коммита <sha> не зелёный:», «ещё идёт:», «main красный с» не тронуты. Номер прогона стоит не в форме «check-run id», поэтому `stuck_check_ids` его не забирает. Формат закреплён AC-8 долгоживущего файла. |
| 5 | OK | Долгоживущий `tests/test_01m46d5zzqy7gbew5tbvq0p3zv_ci_event.py` и 4 новых метода `RunEventLabelTest` с заявками «Ловит мутацию». Заявки исполнимы: проверено мутациями, см. ниже. Повторов долгоживущего нет: новые методы покрывают запасной путь по ссылке, отсутствие запроса прогонов на зелёном исходе и без связки, `skipped` вне фразы о расхождении. |

Попутное наблюдение, не дефект: `_main_line_runs` строит подписи и для
идущих проверок при исходе `MAIN_RED`, хотя в `note` красного они не
выводятся. Это не больше одного лишнего запроса на коммит и только на
не-зелёном исходе; зелёный путь запросов не прибавляет (при пустых
`failed`/`running` список коммитов пуст).

## Замечания
Нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q tests/test_01m46d5zzqy7gbew5tbvq0p3zv_ci_event.py
  tests/test_ci_status.py tests/test_ci_stuck_check_run.py
  tests/test_ci_status_kind_gate.py
  tests/test_01m3y75c9ty76083cg1pk00em4_stuck_check.py
  tests/test_main_ci_fetched_repo.py tests/test_merge_gate_ci_wait.py
  tests/test_verifying_ceiling.py`: 133 passed, 68 subtests passed.
- `python3 -m pytest -q tests/test_invariants.py -k NoNetworkAddresses`:
  2 passed.
- Временные мутации `orchestrator/ci.py` (каждая возвращена
  `git checkout`, дерево чистое), прогон
  `tests/test_ci_status.py::RunEventLabelTest`:
  - убран запасной путь `index.by_id.get(_url_run_id(check))` в
    `_run_of` → красный `test_run_is_found_by_details_url_without_check_suite`;
  - `_EXECUTED_GREEN` → `GREEN` в `_event_divergence` → красный
    `test_skipped_is_not_the_green_side_of_divergence`;
  - убрана ранняя проверка связки в `_commit_workflow_runs` → красный
    `test_unlinked_check_runs_do_not_ask_workflow_runs`;
  - условие `if unfinished or failed` → `if True` (2 места) → красный
    `test_green_outcome_does_not_ask_workflow_runs`.
- `python3 scripts/codebase_map.py` даёт расхождение с картой ветки только
  в `built_at_sha`, то есть карта свежая; регенерация откачена.
- `git diff dff5a425 -- tests/test_ci_status.py`: удалённых строк нет,
  существующие тесты не ослаблены.
- `artel.py plank-run 01M46D5ZZQY7GBEW5TBVQ0P3ZV`: отказ «планки нет»,
  потому что вся планка — долгоживущий файл в `tests/`; он прогнан
  напрямую (выше).

## Предложения системе
- `orchestrator/plank_run.py`: если планка задачи состоит только из
  долгоживущей группы, `plank-run` отказывает «планки нет». Повторяю
  наблюдение разработчика: стоит прогонять файлы из перечня
  `long_lived.sha256.txt`.
