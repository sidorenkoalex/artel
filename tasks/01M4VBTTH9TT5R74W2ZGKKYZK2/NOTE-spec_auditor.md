# Записка spec_auditor — 01M4VBTTH9TT5R74W2ZGKKYZK2 (аудит SPEC 106efd53)

## Выяснено
- Ссылки SPEC на код подтверждены (suite_duration.py:36-40,54-59,65-68; acceptance.py:292-303; тесты 150-185; test_suite_duration.py:45-51).
- Нормальная форма: assertTrue(checks) == assertTrue(rows) (guard.py:783, 878: все локальные имена — одна метка) — перенос пяти форм гейтом выполним.
- НО doctor.all_checks (orchestrator/doctor/cli.py:41-58) всегда возвращает непустой список (role_providers, models_catalog…): assertTrue(<весь результат doctor>) — тавтология, ровно то, что запретил reject Оператора. SPEC (AC-4, инвентаризация 2/4/6/8/10) не требует фильтра по `suite-duration:<target>`.
- Публичный путь записи: acceptance.journal_suite_metrics (acceptance.py:316); suite_load_line (307-313) требует top_processes и load_end_* — SPEC форму контролируемой записи не задаёт.
- pytest -n 2 на 3 тестах холодно ~0.7 с — таймаут 4 с для test_ac2 не тесный.
- Комментарий suite_observation.py:158-162 «AC-2: skip — решение Оператора» конфликтует с именем нового test_ac2.

## Где остановился
- SPEC-AUDIT.md записан: verdict fail, status ready, О-1..О-4; guard: ок. Шаг завершён.

## Чего не хватило
- Где гейт берёт утверждения помощника: guard.py:1094-1116, 1161.
