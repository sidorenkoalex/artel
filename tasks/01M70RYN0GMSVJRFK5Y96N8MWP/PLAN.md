---
task: 01M70RYN0GMSVJRFK5Y96N8MWP
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Тест ожидания замка не зависит от нагрузки машины

## Подход
В `tests/test_suite_lock.py` метод
`WaitAcquireTest::test_wait_reports_holder_once_per_holder_and_gives_up_at_limit`
меняет только обвязку времени (мандат ANSWER-1): вместо подмены `POLL_SEC`
атрибут `time` модуля `orchestrator.suite_lock` на время метода заменяется
объектом `PollClock` — часы опроса: `monotonic` возвращает собственное
значение (настоящие часы не читает), `sleep(x)` продвигает его на `x`,
`time`/`time_ns` берутся из настоящего `time` (их читают `_fresh` и
`defer_journal`, не цикл ожидания). Каждый из `monotonic` и `sleep` считает
свои вызовы и после 1000 бросает исключение (ANSWER-1 D2) — мутация «без
предела» краснеет за доли секунды. Глобальный `time.monotonic` не
трогается. `POLL_SEC` остаётся настоящим (1 с): на подменённых часах
первое ожидание делает два опроса (`sleep(0.2)` доводит срок), второе —
так же, смена держателя в `on_wait` видна второму опросу независимо от
длины реальных пауз. Четыре `assertEqual` и строка «Ловит мутацию» не
меняются.

## Шаги
1. Класс `PollClock` в `tests/test_suite_lock.py` и подмена
   `mock.patch.object(suite_lock, "time", PollClock())` в методе вместо
   подмены `POLL_SEC`; прогон `tests/test_suite_lock.py` и долгоживущего
   `tests/test_01m70ryn0gmsvjrfk5y96n8mwp_wait_lock_clock.py`; регенерация
   карты.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |

## Влияние на систему
Меняется только обвязка одного тестового метода (мандат ANSWER-1, «Ослабление
тестов разрешено: tests/test_suite_lock.py»); утверждения метода те же,
код `orchestrator/suite_lock.py` не меняется. Подмена — атрибут модуля
через `mock.patch.object` с `addCleanup`, после метода `suite_lock.time`
снова модуль `time` (долгоживущий тест это проверяет). Откат — revert
коммита задачи.

## Проверки шага (ANSWER-1 D4)
- `python3 -m pytest tests/test_suite_lock.py tests/test_01m70ryn0gmsvjrfk5y96n8mwp_wait_lock_clock.py -p no:cacheprovider -p timeout -o timeout=120 -q`
  — 13 passed за 2,3 с.
- `artel.py plank-run 01M70RYN0GMSVJRFK5Y96N8MWP tests/test_01m70ryn0gmsvjrfk5y96n8mwp_wait_lock_clock.py`
  — 7 passed, код 0. (а) Три мутации (плюс вариант «без предела и без
  паузы») подставляются в память процесса этим файлом
  (`mock.patch.object(suite_lock, "wait_acquire", …)`), каждая даёт красный
  метод своим утверждением или счётчиком `PollClock`, быстрее 10 с; число
  опросов при обрыве — в 950–1050.
- (б) `timeout 30 python3 -c '…'`: `suite_lock.liveness._pid_alive`
  обёрнут `time.sleep(0.3)`, метод прогнан `unittest` в том же процессе —
  `run 1 ok True`.

## Риски
- Неучтённое обращение `suite_lock` к другому атрибуту `time` в ходе
  метода — `PollClock` отдаёт остальное через `__getattr__` настоящего
  `time`, чтобы такое обращение не упало.

## Предложения системе
