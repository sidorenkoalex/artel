# Записка spec_auditor

## Выяснено
- Аудит SPEC sha d5a31337 (третий визит). Решения гейта №1, №2 внесены.
- Главное: смена значений `GITLAB_REASON`/`TARGET_HUMAN_REASON` меняет «строки модуля с именами вызова» параметризации ac2–ac6 (`UNSUPPORTED` → замыкание по именам; scripts/guard.py:1431-1447 `_bindings`, :1473-1489) → находка PARAMETRIZE_CHANGED (orchestrator/advance_gates/test_integrity.py:540-545, 602-605). Мандат поимённо на ac1/ac7/ac8 её не покрывает (`Finding.mandate_elements`, :183) → рубеж откажет, хотя SPEC говорит «ac2–ac6 под рубежом, не меняются».
- Тесты с подменой SUPPORTED_* (mr_sync, mr_delivery, awaiting_*): до unsupported_reason с плохой парой не доходят — подтверждено чтением (mr_delivery по умолчанию gitlab+target-human, 1461 github+operator; mr_sync other=gitlab+operator только mr-sync).
- Вызывающие: catalog.py:858, runner.py:188-189, doctor/cli.py:44 — префикс «проект <имя>: » есть, верно.

## Не сработало
- `cd && grep`, `$VAR`, `sed` с абсолютным путём в пайпе блокируются; пиши относительные пути без cd.

## Где остановился
- SPEC-AUDIT.md сдан: verdict concerns, status ready, guard ок. Главный пункт — мандат на ac2–ac6 (смена строк модуля параметризации), решение за Оператором.

## Чего не хватило
- Как рубеж трактует смену модульных констант параметризации — нашёл в guard._bindings / test_integrity._mark_problems.
