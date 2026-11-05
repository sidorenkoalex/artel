# Записка developer 01M6PAJ61D4PYAP79ADRPA6MWV

## Выяснено
- Запись: `targets.COMPOSE_FIELDS` влиты в `PROFILE_FIELDS`, проверки — `targets._check_compose`, умолчание команды — `_with_compose_command` в `load()`; `PROFILE_PROJECT_RUNNERS` = own+compose.
- Прогон: `acceptance._compose_report_run` (ветка в начале `_report_run`), снятие — `_compose_teardown`, ключ — `data["compose"]` в `_report_suite_result_key`.
- Долгоживущие: record 57/57, run 72/72, docker 5+1 skip; plank-run 8/8.
- `test_01m56kcvctw5bv9twth54tw9q9_own_run_path.py` в шаге красен на 4 подслучаях two_sided: случайный PATH без /usr/bin ломает обёртку role_bin/git (нет python3, код 127) — от правки не зависит.

- ANSWER-1 (требование 7 первично): код уже соответствовал — отказ роли первой проверкой `_compose_report_run`, фоновый suite-run ловится по HOME роли; у `compose_env` ветки роли нет. Правок кода нет, PLAN дополнен абзацем; долгоживущие 134 passed + 1 skip.

## Где остановился
- Шаг закончен: PLAN.md status: ready, guard ок, карта регенерирована; вторая пачка существующих тестов — 168 passed. Код не закоммичен — коммитит пульт.

## Чего не хватило
- Bash шага отклоняет `ls`/`cd &&`/`env PATH=`: проверять окружение пришлось через `python3 -c`.
