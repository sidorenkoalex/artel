## Выяснено
- SPEC sha 9dbddb8d… совпадает; вердикт concerns, 5 отклонений, guard ок.
- Все места pytest-own идут через acceptance._place_env → _own_env (acceptance.py:144-172); правка PATH в одном _own_env закрывает и suite-run (дочерний процесс с os.environ роли, suite_run.py:798-805), и two_sided.
- Готовый перечень 8 мест: tests/test_01m52eefna1wh31962hvnt0yz9_pytest_own_places.py:62-65 (PLACES); полный прогон — три пути (acceptance.py:1543/1564/1591).
- Отказ workdir в полном прогоне идёт как FULL_SUITE_NOT_STARTED (не кешируется, :2028); красный итог кешируется на 24 ч (:1905, config.py:124) — отказ «команда не найдена» тем же каналом, что workdir.
- Существующие тесты PATH не фиксируют (ALLOWED_VARS содержит PATH, :76); deselected в tests/ нет.

## Не сработало
- grep с `cd …;` и переменными в Bash требовал подтверждения — помогли `cd … &&` и литеральные пути.

## Где остановился
- SPEC-AUDIT.md готов (status ready, verdict concerns).

## Чего не хватило
- Канал отказа каждого места пришлось собирать по acceptance.py вручную (_own_cwd-отказы :601, :717, :833, :1113, :1379).
