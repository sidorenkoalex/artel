# Записка developer (итерация 2, после ревью 1)

## Выяснено
- R1-F1 закрыт только тестами: в `tests/test_canary_parallel.py` +7 методов (AC-21 ×2, AC-20, AC-14, AC-19, AC-5/AC-17, верхний регистр sha). Код `orchestrator/` не менялся.
- В `_CHILD` добавлены режимы `term_exit` (SIGTERM → note("term") + `os._exit`) и `term_hold` (обработчик ждёт канал `<шаблон>.term`); `run_parallel` создаёт оба FIFO на шаблон и принимает `extra` (например `--result-file`).
- Подмена `_wait_child` — `_WaitFault` (первый вызов ждёт `ready`, бросает).
- 8 временных мутаций canary.py — каждая краснит свой тест (список в PLAN «Замечания ревью»).
- tests/test_canary_parallel.py 17 passed; затронутые модули 101 passed; планка 29 passed.

## Не сработало
- Bash-heredoc с python отказан фильтром («brace with quote») — мутации гонял временным файлом `_mutations_tmp.py` в worktree, затем удалён через `os.unlink`.

## Где остановился
- suite-run №2 запущен; PLAN status: ready после guard.

## Чего не хватило
- Ничего существенного.
