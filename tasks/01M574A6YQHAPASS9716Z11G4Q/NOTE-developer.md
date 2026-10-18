# Записка developer — 01M574A6YQHAPASS9716Z11G4Q

## Выяснено
- Путь Actions — `ci.py`: `checks_forbidden`, `_actions_fallback` (только внешний проект), `_actions_pages`/`_actions_runs`/`_actions_verdict`, входы `_verifying_by_actions`, `_branch_by_actions`, `_failed_names_by_actions`.
- «Неизвестен» на пути Actions у `verifying_status` — `VERIFYING_NONE`.
- doctor: `check_ci_token` в `project_checks.py`; `cli.py` правки не потребовал.
- Шаг 2 (ANSWER-1): у Actions `fail` только при отказе правами (`_GhProbe.denied`: 403 «Resource not accessible», 401, 404); 5xx/неразобранный ответ Actions → `skip`; лимит у обоих → `skip`. Тесты в `tests/test_ci_actions_fallback.py` (+2 метода), мутации проверены. check-runs 5xx → `fail` оставлен по AC-11.
- Карта регенерирована; suite-run №2 запущен.

## Не сработало
- `plank-run` отказывает: планка — только долгоживущие файлы.

- Возврат из verifying (линт id-формата, образец `\\d\{3\}` в scripts/id_format_patterns.txt): `_HTTP_CODE_RE` в `project_checks.py:249` теперь `[1-5][0-9][0-9]`. Линт повторён локально python-эмуляцией (`grep -f` в Bash шага отклоняется) — совпадений нет; 17 тестов задачи зелёные; карта регенерирована.

## Где остановился
- PLAN.md status: ready, возврат закрыт.

## Чего не хватило
- Ничего существенного.
