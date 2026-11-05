# Записка аудитора SPEC 01M6PAJ61D4PYAP79ADRPA6MWV

## Выяснено
- Шестой визит, SPEC 8b7154d2: решение шестого круга 1 (`compose_task_id` у `run_plank`, долгоживущий вызов plank_run.py:267-269) внесено; пункт визита 5 закрыт.
- Остаток: вызов планки plank_run.py:283-286 передаёт только `task_id`; `compose` идёт `_run_plank_reported` → `_report_run` (acceptance.py:2090, :2103) — SPEC не задаёт, откуда имя проекта (task_id или compose_task_id). Вердикт concerns, дефолт (а) `compose_task_id or task_id`.
- Якоря SPEC сверены; `_with_long_lived_pairs` определена :1329, `:268-272` — место вызова в `load` (верно).
- `run()`/`collect()` берут id из `Path(tdir).name` (acceptance.py:1590).

## Не сработало
- Составные bash-команды с `cd`/`head` требуют подтверждения — использовать абсолютные пути и Read.

## Где остановился
- SPEC-AUDIT.md: verdict concerns, status ready.

## Чего не хватило
- Явного перечня в SPEC всех вызовов `run_plank` (оба в plank_run.py) с источником id имени.
