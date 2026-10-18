# NOTE analyst — 01M5633WZ3Y3A0P4KKBZDB3KER

## Выяснено
- ANSWER-1: 1A (подполе `test_profile.long_lived_imports`), 2A, 3B. Первый возврат 18.10 (пп.1–7) закрыт вторым SPEC.
- Второй возврат 18.10 закрыт третьей правкой: AC-1 требует литерал «только стандартная библиотека, orchestrator, scripts, tests — помощники из tests/sandbox.py» (сверен по guard.py:2596-2597), ожидание в тесте — литерал, не вычисленное из `_SIGN_EXPLANATIONS`; сужение AC-2…AC-4 («нет признака» вместо «проходит выход»; сухой сбор и прогон в окружении проекта) вынесено в «Не входит» как принятое Оператором.
- `targets.check(name, entry)` (targets.py:153) знает имя записи; `_check_profile(where, profile)` — нет (правка сигнатуры в зоне).
- tests/test_01m4kaj0bj9ec37rwxnfkqn7dw_amend_network_scope.py:410 оборачивает long_lived_errors_from_files `(files, task_id, **kwargs)` — новые аргументы только именованные, умолчание = поведение артели.

## Не сработало
- —

## Где остановился
- SPEC.md: 8 AC, budget 30, status: ready, guard ок.

## Чего не хватило
- Ничего нового.
