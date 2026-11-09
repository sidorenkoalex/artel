# Записка developer

## Выяснено
- Правка — только обвязка метода `WaitAcquireTest::test_wait_reports…` в `tests/test_suite_lock.py`: класс `PollClock` (monotonic без настоящих часов, sleep продвигает его, счётчик 1000 отдельно на monotonic и sleep → AssertionError; time/time_ns и прочее — из настоящего `time`), подмена `mock.patch.object(suite_lock, "time", PollClock())` вместо `POLL_SEC`. Утверждения не тронуты.
- `suite_lock` читает ещё `time.time()` (`_fresh`) и `time.time_ns()` (`defer_journal`) — отсюда `__getattr__`.
- Тесты: test_suite_lock + долгоживущий — 13 passed; plank-run долгоживущего — 7 passed; D4(б) (`_pid_alive` + sleep 0.3) — зелёный.
- Карта регенерирована. PLAN status: ready.

## Не сработало
- `guard.py` на `tests/*.py` неприменим (ждёт frontmatter) — линт теста проверен `test_lint.findings` → `{}`.

## Где остановился
- Шаг завершён.

## Чего не хватило
- Ничего существенного.
