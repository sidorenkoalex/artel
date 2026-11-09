# Записка test_author

## Выяснено
- AC-1 — `# AC-1: manual` в `acceptance_tests/_marks.py` (критерий сам ручной). Других файлов в планке нет; `plank-run` без аргумента отказывает «нет файлов test_*.py», с путём долгоживущего файла работает.
- AC-2, AC-3 — долгоживущий `tests/test_01m70ryn0gmsvjrfk5y96n8mwp_wait_lock_clock.py` (размер small). Метод `WaitAcquireTest::test_wait_reports…` прогоняется в том же процессе через `unittest` (подкласс внутри функции, `PATCHED_ATTRS` без `ROOT`, поэтому нет `git init` клона-заглушки); мутанты `wait_acquire` подставляются `mock.patch.object(suite_lock, "wait_acquire")` и берут часы из `suite_lock.time`; предохранитель 10 с по настоящим часам → `MutationEscaped`.
- Красная фаза: 5 failed, 2 passed (мутации «on_wait на каждом опросе» и «поверх держателя» нынешний метод уже ловит). Стаб метода в памяти (подмена `suite_lock.time` часами, которые продвигает `sleep`, счётчик 1000 на `monotonic` и на `sleep`) → 7 passed за 1,8 с. Стаб со счётчиком только на `sleep` → красные оба варианта `no_limit_no_pause` (как требует ANSWER-1 D2).
- AC-3, счётчик: число опросов за метод обязано попасть в 950–1050.

## Не сработало
- `pytest.main` из `python3 -` → сторож «полный прогон запрещён», пока не задан `sys.argv = ["pytest", файл]`.
- test_lint отклоняет `suite_lock.time.sleep(x)` («time.sleep с ненулевой паузой») — в мутанте часы берутся в локальное `clock`.

## Где остановился
- Предпроверка пройдена целиком; прогон пультом — 5 failed / 2 passed, это ожидаемая краснота.

## Чего не хватило
- Правило test_lint о `sleep` нашёл только поиском по `orchestrator/test_lint.py::_is_sleep_call`; правило ловит любой `<x>.time.sleep`.
