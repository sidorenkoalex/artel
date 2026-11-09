## Выяснено
- ТЗ достаточно; SPEC.md написан (status: ready, 3 AC, зона tests/test_suite_lock.py, budget 25), guard ок.
- suite_lock использует `time.monotonic` (:126, :136), `time.sleep` (:139), `time.time` (:79 `_fresh`), `time.time_ns` (:238 `defer_journal`, в тесте не зовётся) — подменный объект `time` должен нести monotonic/sleep/time.
- AC-1 ручной (Оператор, 200 прогонов под нагрузкой) — test_author помечает `# AC-1: manual`.
- Утверждения метода сохраняются; мандат на правку теста — за Оператором на гейте SPEC (раздел ТЗ «Мандат»).

## Не сработало
- —

## Где остановился
- Шаг завершён.

## Чего не хватило
- Как оформлять manual-критерий ТЗ в SPEC — нашёл по guard.py:199 (`# AC-n: manual`).
