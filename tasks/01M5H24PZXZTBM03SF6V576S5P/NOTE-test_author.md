# Записка test_author

## Выяснено
- ANSWER-1 назначил имена: canary.PARALLEL_STOP_GRACE_SEC (60), canary.PARALLEL_CHILD_LIMIT (2), canary._wait_child (шов ожидания), canary._child_argv (планке не нужен).
- Шов дочернего в планке: перехват `subprocess.Popen` (argv с `run-task`) → интерпретатор `-c _CHILD` с исходным argv и теми же stdout/группой/cwd (`_harness.py`); ожидание — FIFO на шаблон.
- Подпись `_wait_child` SPEC не задаёт: `_harness.WaitFault` принимает *args/**kwargs, первый вызов (после `ready` координатора) бросает исключение, остальные — настоящая функция. Какой дочерний «упал» — по записи `term` в calls.jsonl.
- `_CHILD`: `ignore_term` — обработчик SIGTERM пишет `term` с `time.monotonic()` и ждёт дальше; `term_exit` — пишет `term` и выходит 143.
- AC-13: снятие записи дочернего родителем видно шпионом `os.unlink`/`os.remove` (`record_unlinks`): листинг реестра в момент снятия.
- B-2 тесты: tests/test_01m5fa4nr91pcf47szt6v0q9hs_*.py; CanaryHelpTest — tests/test_01m4axpy1py4ps1yafamd47vby_canary_detach.py.

## Сделано
- Круг 1: _harness.py; test_cli.py (AC-2,3,4,9); test_parallel.py (AC-6..16); test_preserved.py (AC-1,5,17,18).
- Круг 2 (после ANSWER-1): пометки escalate сняты; AC-6 + константа предела; AC-13, AC-19 (StopGraceTest), AC-20, AC-21 ×2 (WaitFailureTest). До кода красны (AttributeError имён).
- Валидация круга 2 стабом (родитель: поток-ожидатель на дочерний через `_wait_child`, очередь результатов, остановка под `_SignalDeferral`): test_parallel.py 19/19 зелёные. Мутации пойманы: SIGKILL без срока (AC-13), снятие метки вместе с записью дочернего (AC-13), красная строка за SIGKILL без сверки строк (AC-19), исключение ожидания обрывает очередь (AC-21 ×2), поздний сигнал не в коде выхода (AC-20), красная строка за прерванное ожидание без сверки (AC-21b). Стаб откачен `git checkout`, рабочая копия чистая.
- Без кода: планка 29 failed / 10 passed (зелёные — test_preserved и проверки отказов); preflight — все проверки пройдены; пометок escalate не осталось.

## Не сработало
- Составные bash-команды, `ls` недоступны.

## Где остановился
- Шаг сдан: все AC покрыты тестами (AC-1/AC-18 — плюс пометки ci).

## Чего не хватило
- Стаба реализации круга 1 — его пришлось писать заново (контур стаба описан выше).
