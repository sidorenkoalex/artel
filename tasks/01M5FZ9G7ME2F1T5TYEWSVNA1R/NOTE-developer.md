# Записка developer — 01M5FZ9G7ME2F1T5TYEWSVNA1R

## Выяснено
- Реализация: `canary.cmd_canary_run_task` (+ `_write_child_record`,
  `_mark_owned_by_parent`) в конце `orchestrator/canary.py`; разбор —
  `artel._cmd_canary_run_task`, одна ветка в `_cmd_canary` после `live`.
- Итерация 2 (R1-F1, R1-F2): в `tests/test_canary_run_task.py` добавлены
  13 тестов тела подкоманды (класс `RunTaskSandboxTest` — общие фикстуры на
  `InitializedTmpRootTest`), входы фиксированы. Код не менялся.
- Мутации: убрать unlink в finally — 10 красных; не ловить
  CanaryInterrupted в (г) — 2 красных. Код возвращён.
- Справка `artel.py` — это `artel.__doc__` (print(__doc__) в main).

## Не сработало
- heredoc с `{…"…}` в Bash иногда отклоняется сторожем команд.

## Где остановился
- tests/test_canary_run_task.py: 14 passed; планка 32 passed; карта
  регенерирована; PLAN status: ready.

## Чего не хватило
- —
