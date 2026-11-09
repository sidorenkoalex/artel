# Записка analyst

## Выяснено
- ТЗ достаточно, SPEC.md написан (status: ready, 12 AC, budget 35 по рамке ТЗ), guard — ок.
- Поверхности решения: `suite_hold.refusal(argv) -> str | None` (AC-5 предел, AC-10 пустая команда/основание), `suite_hold.reason_text(raw) -> str` (AC-11), `suite_lock.describe` (AC-3). Точка входа — `suite_hold.cmd_suite_lock(argv) -> int`.
- `describe` сейчас (`suite_lock.py:352-360`) для неизвестного вида падает в ветку `suite-run задачи …` — новый вид нужен отдельной веткой.
- `wait_acquire` ключует смену держателя по `(task_id, pid)` — для внешнего `task_id` = None, работает.
- `artel.main` первым зовёт `_refuse_if_worktree()`; тесты в процессе патчат его (`tests/test_mandate_matrix_form.py:93`). Отказ роли — `_refuse_if_role_restricted` (`artel.py:2648`), белый список закрыт по умолчанию — для AC-9 достаточно не вносить команду в список.
- Номера строк `config.py` в ТЗ устарели: `FULL_SUITE_TIMEOUT_SEC` — `:293`, `FULL_SUITE_LOCK_WAIT_SEC` — `:316`.

## Не сработало
- Bash с `cd`/переменной и несколькими командами требует подтверждения — читать файлы через Read и одиночный grep с абсолютным путём.

## Где остановился
- Шаг завершён: SPEC сдан.

## Чего не хватило
- Ничего существенного.
