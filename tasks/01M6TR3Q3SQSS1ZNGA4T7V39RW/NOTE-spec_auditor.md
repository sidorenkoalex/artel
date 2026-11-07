# Записка spec_auditor — 01M6TR3Q3SQSS1ZNGA4T7V39RW (аудит 2, spec_sha dceee4c6)

## Выяснено
- Новый SPEC закрывает отклонения аудита 1 (А1, Б1, Б5, В1, В2, Г1/Г2, Е1, Е2, AC-3) по ANSWER-1.
- compose_project_name(task_id, run_id) (acceptance.py:885): run_id = os.urandom(4).hex() внутри _compose_report_run (:1365) — исполнитель «сам» имя не вычислит; ложный факт ANSWER-1 п.2 / SPEC треб. 13.
- Опыт: SIGTERM -> rc -15, finally не исполнен; SIGINT -> finally исполнен.
- Предел снятия стенда — COMPOSE_TEARDOWN_TIMEOUT_SEC=120 (config.py:238), не COMPOSE_UP_DOWN_SEC; teardown — down -v (acceptance.py:1313), явный down SPEC — без -v (как doctor).
- run.json/result.json/failed.json — общие для suite-run задачи (suite_run.py:127-139); как в них живут запросы планки — не задано.
- cmd_plank_run(task_id, file_arg) зовут позиционно 6 тестов.
- Гейты каталог suite-run не читают (только fullsuite-results, acceptance.py:3537).

## Не сработало
- ls / составные команды с xargs/awk требуют подтверждения.

## Где остановился
- SPEC-AUDIT.md сдан: verdict concerns, status ready.

## Чего не хватило
- Как тест доберётся до исполнителя (FakeProc.wait возвращается сразу) — в SPEC не задано.
