# Записка developer — 01M55VG9Q5A5341ZED8NRJKVTC

## Выяснено
- Python 3.13: `Popen.wait(timeout)` считает время по `subprocess._time`
  (`endtime = _time() + timeout`, `_remaining_time`). Подмена часов —
  `COPY_CLOCK` в целевом тесте, дописывается в config.py копии из
  `add_project_task(limit)`; обёртка `Popen.wait` только ставит часы на
  время вызова (thread-local) и зовёт настоящий wait с тем же пределом.
- Часы переходят на N, когда пробник группы `proc.pid` записал «start»
  (в PROBE_TEST добавлено поле pgid). Предел ≠ N: часы стоят, пробник
  отпущен stop-файлом → прогон зелёный, строки «не уложился» нет → тест красен.
- id фикстуры: `SuiteRunLimitSandbox.task_id` — без цифр (ID_LETTERS).
- Целевой тест локально зелёный за 4,5 с.

## Где остановился
- Код готов; дальше plank-run, мутации, серия 50 под нагрузкой, PLAN.md.
