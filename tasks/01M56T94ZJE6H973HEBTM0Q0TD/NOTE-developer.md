# Записка developer — 01M56T94ZJE6H973HEBTM0Q0TD

## Выяснено
- Правка — только `tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py` и регенерированная `docs/codebase-map.md`. Основа — диф ТЗ: `ID_LETTERS`, `task_id` песочницы suite-run, `COPY_CLOCK`, `run_traces`. Сверх него `COPY_CLOCK` пишет в журнал пробника отметки `wait_enter`/`clock_jump`/`cut` с `mono`. Пробник пишет `pgid`/`mono`. Метод после прежних утверждений проверяет: cut с пределом N есть, есть clock_jump того же pgid (AC-5), `cut − max(wait_enter, start) < 5` (AC-3).
- Новые классы: `SuiteRunFixtureIdTest` (зёрна 0–2999) и `CopyClockOrderTest` (оба порядка часов и «предел не N» в процессе теста против дочернего пробника).
- `assertRaises` стирает `__traceback__`, поэтому для проверки «бросил настоящий `Popen._wait`» нужен ручной try/except.
- Файл: 11 passed за 82 с, метод suite-run — около 4,5 с. Планка 11/11. Четыре временные мутации новых тестов — каждая краснит заявленный тест.

## Не сработало
- `suite-run`: отказ — на машине шёл полный прогон задачи 01M56G23ZQDHV2BKEVWWC22R96. Полный набор не прогнан.
- Heredoc с `{…!r}` Bash шага отказывает: мутации гонялись одноразовым скриптом в рабочем каталоге, скрипт сам себя удалил.

## Где остановился
- PLAN.md status: ready, guard ок. Код не закоммичен — коммитит пульт.

## Чего не хватило
- Bash шага не даёт `ls`/`$VAR`: список каталога документов — через `python3 -c os.walk`.
