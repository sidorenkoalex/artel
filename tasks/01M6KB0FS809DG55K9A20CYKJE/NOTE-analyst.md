# Записка analyst — 01M6KB0FS809DG55K9A20CYKJE

## Выяснено
- ТЗ достаточно; вопросов нет. Строка ТЗ «Порядок: задача … смержена» — не «Порядок: после …», `merge_after` нет.
- Точки подмены: `runner.role_nproc_limit() -> int`, `runner._read_maxprocperuid() -> tuple[int | None, str]`, `runner._user_process_count() -> int`; аргумент `spawn_agent(nproc_limit=…)`.
- Отказ при исчерпанном запасе — `SystemExit` из `cmd_run`; auto останавливается «run отказался стартовать» (auto.py:1017), auto.py не меняется.
- Шаг 8 (возврат 7, С-1/С-2): расчёт предела и проверка запаса — в `runner._run_developer_step` (runner.py:302) до `_run_attempts` (вызов :333), т.е. внутри try/finally снятия захвата зоны в `_cmd_run` (:286–299). Исправлено в требованиях 1 и 3. В требование 3 добавлено: отказ по запасу не оставляет захвата зоны (finally, `zone_lock.claimed_but_not_started`). В AC-5 добавлен третий прогон: developer-шаг в in_dev → SystemExit, захвата зоны после отказа нет.
- Строки кода: `spawn_agent` — runner.py:1805, `close_pump` — :1876, «agent run finished» — :2086.

## Не сработало
- `cd … ; grep` в одной команде Bash отклоняется — нужны абсолютные пути.

## Где остановился
- SPEC.md обновлён по возврату 7, status: ready, `scripts/guard.py` — ок.

## Чего не хватило
- Ничего.
