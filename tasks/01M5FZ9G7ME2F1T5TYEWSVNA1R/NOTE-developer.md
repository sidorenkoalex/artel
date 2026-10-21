# Записка developer — 01M5FZ9G7ME2F1T5TYEWSVNA1R

## Выяснено
- Реализация: `canary.cmd_canary_run_task` (+ `_write_child_record`,
  `_mark_owned_by_parent`) в конце `orchestrator/canary.py`; разбор —
  `artel._cmd_canary_run_task`, одна ветка `if rest and rest[0] == "run-task"`
  в `_cmd_canary` после `live`.
- Отказ под ролью даёт прежний `_refuse_if_role_restricted` — правок не нужно.
- Планка (`plank-run`): 32/32 зелёные, ~97 с.

## Не сработало
- heredoc с `{…"…}` в Bash отклоняется сторожем команд — правки через Edit.

## Где остановился
- Сделано: tests/test_canary_run_task.py (мутация «разбор по позиции»
  поймана), карта регенерирована, guard PLAN ок, PLAN status: ready.
- Тесты затронутых модулей (8 файлов canary/role) — 149 passed.
- Полный suite-run ждал машинного замка (прогон гейта 01M5FRYVP4…).

## Чего не хватило
- —
