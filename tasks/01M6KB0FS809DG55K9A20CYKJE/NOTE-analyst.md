# Записка analyst — 01M6KB0FS809DG55K9A20CYKJE

## Выяснено
- ТЗ достаточно для SPEC; вопросов нет. Строка ТЗ «Порядок: задача … смержена» — не «Порядок: после …», поля `merge_after` нет.
- Шаг 2 (возврат по SPEC-AUDIT О-1…О-8): решения внесены; функция `runner.role_nproc_limit`, аргумент `spawn_agent` — `nproc_limit`.
- Шаг 3 (возврат 2, Н-1/Н-2): точки подмены `runner._read_maxprocperuid() -> tuple[int | None, str]` и `runner._user_process_count() -> int`.
- Шаг 4 (возврат 3, Н-3/Н-4): требование 3 — сбой счёта процессов (исключение `_user_process_count`) → шаг запускается, одна запись «счёт процессов пользователя недоступен: <причина>» на шаг; абсолютные пути /usr/sbin/sysctl и ps как `liveness._ps_executable` (liveness.py:89). Требование 6 — warn «счёт недоступен». Требование 5 — снятие группы только при `isinstance(agent_pid, int)` (runner.py:1864). AC-4 — подмена `resource.getrlimit`, вызов через модуль. Новый AC-8 — сбой счёта. Критериев 8.
- Строки кода: вызов `spawn_agent` — runner.py:1805, `close_pump` — :1876, «agent run finished» — :2086, INCOMPLETE — :2104–2115.

## Не сработало
- `cd … ; grep` в одной команде Bash отклоняется — нужны абсолютные пути.

## Где остановился
- SPEC.md обновлён, status: ready, `scripts/guard.py` — ок.

## Чего не хватило
- Ничего: решения Оператора по Н-3/Н-4 были полными.
