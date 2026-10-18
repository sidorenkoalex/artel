---
task: 01M574A6YQHAPASS9716Z11G4Q
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: CI внешнего проекта при токене без права Checks — итог по Actions runs и проверка прав токена в doctor

## Фаза A — план
- Таблица покрытия полна: требования 1–9 сопоставлены шагам 1–3; шаги —
  единицы размера MR (ci.py / project_checks.py / tests / карта).
- Подход (врезка `runs is None and _actions_fallback(repo, why)` в три входа
  сразу после `check_runs`) не меняет путь check-runs и путь артели;
  конфликта с архитектурой нет. Выбор `VERIFYING_NONE` для «неизвестен»
  обоснован в PLAN (требование 2 это требует) и совпадает с исходом
  неопределённой головы ветки.
- «Влияние на систему» = diff: три файла (`orchestrator/ci.py`,
  `orchestrator/doctor/project_checks.py`, новый `tests/test_ci_actions_fallback.py`)
  + регенерированная карта; `doctor/cli.py` не тронут — строки проекта он и
  так берёт из `project_entry_checks` (заявлено в PLAN). Вне зон правок нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `ci.py` `_actions_fallback` + `checks_forbidden`: 403 + один из двух текстов, только внешний контекст; врезка в `verifying_status`, `branch_status`, `failed_check_names` (вершина main идёт тем же `failed_check_names`). |
| 2 | OK | `_actions_verdict`: чужой непустой `head_branch` — вне вердикта, без `head_branch` — в вердикте; красный → идущий → нет завершённого `pull_request` (`none` → `_no_checks_by_branch` / «статус неизвестен») → зелёный. Неполный/неразобранный/неполученный ответ (запуски и задания каждого запуска, сверка с `total_count`, отсутствие `total_count` тоже «неизвестен») → `VERIFYING_NONE`, текст без «не зелёный:». |
| 3 | OK | `_failed_names_by_actions`: все события без отбора по ветке; красный запуск без красных заданий — имя запуска (`_actions_failed_names`); нет запусков / сбой ответа → `(None, причина)`. |
| 4 | OK | Иные отказы не проходят `checks_forbidden` → прежняя ветка; AC-9 сверяет тексты с путём артели и отсутствие запросов `actions/runs?head_sha=`. |
| 5 | OK | Первые строки — формулы пути check-runs («CI коммита <sha8> не зелёный:», «… ещё идёт:», «статус CI коммита <sha8> неизвестен:», «… — статус неизвестен»); `verifying_is_red`/`red_status_sha`/`status_kind` (ci.py:1074, :1247) читают их без правки. |
| 6 | OK | `_with_actions_reason` дописывает `ACTIONS_REASON` последней строкой на каждом исходе `_verifying_by_actions`/`_branch_by_actions`. |
| 7 | OK | `_project_context` даёт `ctx is None` для артели → фолбэк не срабатывает; AC-10 зелёный. |
| 8 | OK | `check_ci_token` в `_names`/`project_entry_checks` после `project-token`; ROLE_SKIP без `gh` в роли, NOT_APPLICABLE у артели (общий путь); `gh_env`; порядок исходов соответствует SPEC с уточнением ANSWER-1 (временный отказ любого эндпоинта и не-правовой отказ Actions → `skip`; `fail` за Actions — только 403 прав/401/404). Токен в detail не попадает (там только текст `gh`). |
| 9 | OK | Все тесты на подменах `subprocess.run`/`_gh_at`, без сети. |

## Замечания
Блокеров, major и minor нет.

Проверено и не стало замечанием:
- `status_kind` на красном `note` с фразой `_inherited_from_main`/списком чужих
  запусков — те же составные части, что на пути check-runs; строка
  `ACTIONS_REASON` не содержит подстрок разборщиков («ещё идёт», «неизвестен»,
  «не зелёный:»).
- `_inherited_from_main(verdict.failed, …)` получает список `{"name": …}` —
  та же форма, что ждёт функция (ci.py:614, `c.get("name")`).
- Новый `tests/test_ci_actions_fallback.py` не повторяет долгоживущие файлы
  задачи: покрывает 403 только при коде 403, отсутствие `total_count`,
  Actions 403 лимита / оба эндпоинта лимитом / Actions 5xx и неразобранный
  ответ → `skip` (ANSWER-1 прямо просил покрыть «Actions 403 rate limit» в
  `tests/`). Заявки «Ловит мутацию» называют наблюдаемое расхождение
  (статус строки, `True/False`).
- Существующие тесты не тронуты (в diff `tests/` — только новый файл).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q tests/test_01m574a6yqhapass9716z11g4q_actions_verdict.py tests/test_01m574a6yqhapass9716z11g4q_doctor_ci_token.py tests/test_ci_actions_fallback.py` — 17 passed, 78 subtests passed.
- `python3 -m pytest -q tests/test_ci*.py tests/test_doctor*.py` — 314 passed, 84 subtests passed.
- Временная мутация: в `ci.checks_forbidden` убрана сверка `"403" in why` → `tests/test_ci_actions_fallback.py::ChecksForbiddenTest::test_only_403_with_not_accessible_text` красный (1 failed); код возвращён `git checkout -- orchestrator/ci.py`, дерево чистое.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` без строки `built_at_sha` — расхождений нет, карта свежа; файл возвращён `git checkout`.
- `artel.py plank-run 01M574A6YQHAPASS9716Z11G4Q` — отказ «планки нет: … нет файлов test_*.py» (планка задачи — только долгоживущие файлы `tests/`, они прогнаны напрямую выше).
- CI коммита 83373500 зелёный (16 проверок) — по пакету.

## Предложения системе
- `orchestrator/plank_run.py`: `plank-run` отказывает, когда планка задачи состоит только из долгоживущих `tests/test_<id>_*.py` — независимо подтверждаю наблюдение разработчика из PLAN; ревьюверу приходится гонять их pytest напрямую.
