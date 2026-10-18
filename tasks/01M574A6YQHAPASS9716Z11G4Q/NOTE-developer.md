# Записка developer — 01M574A6YQHAPASS9716Z11G4Q

## Выяснено
- Путь Actions — `ci.py`: `checks_forbidden`, `_actions_fallback` (только внешний проект), `_actions_pages`/`_actions_runs`/`_actions_verdict`, входы `_verifying_by_actions`, `_branch_by_actions`, `_failed_names_by_actions`; врезки в `verifying_status`, `branch_status`, `failed_check_names` сразу после `check_runs`.
- «Неизвестен» на пути Actions у `verifying_status` — `VERIFYING_NONE` (обоснование в PLAN).
- doctor: `check_ci_token` в `project_checks.py`, строка `project-ci-token-<проект>` в `_names`; `cli.py` правки не потребовал.
- Обе долгоживущие планки зелёные; свои тесты — `tests/test_ci_actions_fallback.py` (3, мутации проверены).
- suite-run №1: зелёный, 5780 прошло, 0 упало. Карта регенерирована.
- Адреса в тестах — только localhost (инвариант NoNetworkAddressesInTestsTest).

## Не сработало
- `plank-run` отказывает: планка — только долгоживущие файлы, в acceptance_tests/ нет test_*.py. Гонял их pytest напрямую.

## Где остановился
- Шаг завершён: PLAN.md status: ready, guard ок.

## Чего не хватило
- Ничего существенного.
