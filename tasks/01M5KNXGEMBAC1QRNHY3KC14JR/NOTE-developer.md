# Записка developer — 01M5KNXGEMBAC1QRNHY3KC14JR

## Выяснено
- Правка — `orchestrator/doctor/canary_pool.py`: `check_role_log_pool_leak` + `_home_path_sign_re` (1а/1б), `_tool_call_sign` (1г, префиксы `doctor.providers.claude` и `doctor.codex_provider`), `_pool_template_guids` (1в, пропуск под `in_role_environment()` до любого чтения пула).
- Алерт 1в: «лог роли X несёт GUID шаблона пула канарейки (<каталог>) — …»; 1а/1б/1г — прежний текст.
- `tests/test_doctor_canary_pool.py::RoleLogPoolLeakCheckTest.setUp` — добавлена только подмена `Path.home` (требование 6).
- Зелёные: оба файла тестов (27 passed), plank-run AC-9 (1 passed); карта регенерирована.

## Не сработало
- `pytest --count` не установлен — повтор зёрен отдельными прогонами.

## Где остановился
- PLAN.md status: ready, шаг завершён.

## Чего не хватило
- —
