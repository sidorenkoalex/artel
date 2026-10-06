---
task: 01M48WRE8BHFDY011Q0HQGQ91B
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Предел полного прогона tests/ из профиля проекта

## Подход
Добавить необязательное положительное целое в проверку `test_profile` и единый резолвер действующего предела с источником. Общий раннер полного набора получает это значение в момент прогона; автогейт, approve и гейт мержа используют его через `acceptance.full_suite`, а `suite-run` — через `acceptance.run_full_suite`. Тексты исхода и doctor используют тот же резолвер. При отсутствии подполя предел читается из `config` при вызове.

## Шаги
1. Проверка подполя в `targets.py`, разрешение предела и источника в `project_profile.py`, применение и диагностика в `acceptance.py`, `fsm_merge_gate.py`, `suite_run.py`, `doctor/cli.py`.
2. Юнит-тесты проверки значений, динамического выбора предела, таймаутных текстов и строки doctor; запуск затронутых модулей, планки и полного набора командой пульта; регенерация карты и проверка guard.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1–2 | 1, 2 |
| 3–5 | 1, 2 |
| 6–7 | 1, 2 |
| 8 | 1 |

## Влияние на систему
Затронуты только предел полного набора и его диагностика; `FULL_SUITE_LOCK_WAIT_SEC`, замок, состав набора, условия гейтов и существующие тесты сохраняются. Без подполя действует прежняя константа. Откат — revert коммита задачи. После мержа Оператор добавляет `full_suite_timeout_sec: 1500` в `test_profile` проекта `artel` в `targets.yaml` и выполняет `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py doc-commit targets.yaml`.

## Риски
Нужно сохранить узнаваемое начало таймаутного текста: по нему раннер классифицирует собственный исход, а гейт вины определяет сторону отказа.

## Проверки
- `python3 -m pytest tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py tests/test_01m48wre8bhfdy011q0hqgq91b_profile_limit_field.py tests/test_full_suite_profile_timeout.py tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py tests/test_approve_acceptance_full_suite.py -p no:cacheprovider -p timeout -o timeout=120 -q --tb=short` — 44 passed, 7 subtests passed.
- `python3 -m pytest tests/test_full_suite_profile_timeout.py tests/test_01m48wre8bhfdy011q0hqgq91b_profile_limit_field.py tests/test_doctor.py tests/test_project_profile.py tests/test_suite_run.py -p no:cacheprovider -p timeout -o timeout=120 -q --tb=short` — 143 passed, 8 subtests passed.
- Временные мутации проверки типа, выбора предела и текста отчёта покрасили соответствующие новые тесты; код восстановлен.
- `python3 scripts/codebase_map.py`, `git diff --check` и `python3 scripts/guard.py <путь>/PLAN.md` — успешно.
- `plank-run` — планки `test_*.py` в источнике задачи нет; pytest не запускался. `suite-run` — отказ до запуска из-за недоступного замка (ниже).

## Предложения системе
- `suite-run` из шага роли: команда пульта пытается создать `.artel/logs/suite-run/lock.json` вне двух открытых роли каталогов и получает `PermissionError: Operation not permitted`. Нужна штатная запись этого замка командой пульта вне песочницы роли либо открытый только для неё путь; полный набор локально сейчас не стартует.
- Старые `tests/test_acceptance.py::MaterializeFromBranchGitFailureTest` и ряд `tests/test_fsm_autogate.py` отказывают в неизменённых узлах `artifact_branch`/`appendix_tree`: их фикстура оставляет БД без таблицы `tasks` (`sqlite3.OperationalError`). Нужна отдельная починка фикстур; изменение этих тестов вне зоны задачи.
