## Выяснено
- ТЗ достаточно, SPEC.md написан (status: ready, 6 AC, budget 35 = рамка ТЗ), guard ок.
- `target-set` берёт перечень полей из `targets.LOCAL_FIELDS` (`orchestrator/projects.py:780`, `_field_keys`) — требование 5 закрывается добавлением поля в `targets.py`, projects.py (только чтение) трогать не нужно.
- Образец: `targets.DEFAULT_COMMIT_TEMPLATE`/`COMMIT_PLACEHOLDERS` (`targets.py:418-419`), проверка `commit_template` в `_check_delivery` (`targets.py:702-714`), правило `{ref}` — `pull.commit_title` (`pull.py:926-940`).
- Места коммитов кодовой ветки: checkpoint.py:932 (код), :1887 (вызов pult_message), pull.py:473, :556, amend.py:806; сжатый коммит pull.py:1107 — не трогать.

## Не сработало
- Первый прогон guard: сигнал «число файлов зоны» → добавлена секция оценки объёма (монолит, прогноз диффа 40 КиБ при потолке 256 КиБ).

## Где остановился
- Шаг завершён.

## Чего не хватило
- Потолок гейта ёмкости искал через capacity.py → `config.REVIEW_SNAPSHOT_DIFF_MAX_BYTES` (config.py:614).
