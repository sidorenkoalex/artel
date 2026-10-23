# Записка spec_auditor

## Выяснено
- Адреса SPEC верны на HEAD: `_cmd_canary` artel.py:1547, `live` 1565, справка 185, `_k_arg` 1484; canary.py 2031/2067/2803/3129; store.py 1563/1710.
- `store._ensure_canary_tables` (store.py:1605) делает UPDATE `set_name IS NULL` → набор по умолчанию и миграцию `canary_baseline` — `набор=—` недостижим через `all_canary_runs`.
- `artel.main` не открывает БД до разбора `canary` — подмена `store.db` в AC-4 работает.
- `docs/codebase-map.md` входит через `config.COMMON_ZONES` (config.py:814).

## Не сработало
- `cd ...; cmd` и переменные оболочки в Bash требуют подтверждения — звать команды по абсолютным путям без `cd`.

## Где остановился
SPEC-AUDIT.md: verdict concerns, status ready; guard — ок. Шаг завершён.

## Чего не хватило
Нигде не описано, что `all_canary_runs` пишет в БД (докстринг store.py:1710 молчит) — нашёл чтением `_ensure_canary_tables`.
