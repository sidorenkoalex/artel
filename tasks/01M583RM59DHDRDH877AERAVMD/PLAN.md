---
task: 01M583RM59DHDRDH877AERAVMD
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Канарейка: сигнал остановки в момент запуска процесса ведения задачи не оставляет его живым

## Подход
Способ — принятый Оператором (SPEC, «Способ»): откладывающий обработчик на
участке `Popen` … `proc =` в `_drive_in_clone` (`orchestrator/canary.py`).

- Новый класс `_SignalDeferral` рядом с `_drive_in_clone`. При создании
  запоминает обработчики SIGTERM, SIGHUP, SIGINT и ставит вместо них
  обработчик-функцию Python, которая только запоминает первый пришедший
  сигнал. Сигнал, чей обработчик на входе `SIG_IGN` (или `None` — поставлен
  не из Python), не перехватывается и остаётся как был (требование 8,
  AC-11). `SIG_IGN` участок не вводит (требование 4): обработчик-функция
  при exec сбрасывается в процессе ведения в действие по умолчанию, так что
  ведение, созданное после сигнала, не игнорирует SIGTERM/SIGHUP (AC-3).
  Вне главного потока обработчик не ставится — `signal.signal` там бросил
  бы `ValueError`, а вызов `_drive_in_clone` вне `_interrupt_on_signal`
  должен работать (требование 5).
- `release()` возвращает прежние обработчики и, если сигнал отложен,
  поднимает его `signal.raise_signal` — исключение даёт прежний обработчик
  (`CanaryInterrupted` для SIGTERM/SIGHUP внутри `_interrupt_on_signal`,
  `KeyboardInterrupt` для SIGINT), то есть то же, что сигнал во время
  ожидания.
- В `_drive_in_clone` `release()` вызывается: первой строкой защищённого
  `try` (исключение уходит в `except BaseException` → снятие и ожидание
  группы — требования 1, 2); в `except OSError` до `return 127` и в новом
  `except BaseException: release(); raise` (сигнал заменяет исключение
  `Popen` — требование 3; без сигнала исходы прежние — требование 5).
  Восстановление обработчиков стоит внутри защищённого `try`, поэтому и
  повторный «живой» сигнал после восстановления попадает в ту же ветку
  снятия группы.
- Тест (мандат ANSWER-2, требования 6, 9, AC-12): общий `_CHILD`
  `CanaryLifecycleTest` пишет в наблюдение `alive_before_signal` (`poll()`
  подменённых suite и ведения), а `launch_signalled` перед `os.kill(child.pid,
  signum)` проверяет его и живость pid. Тела методов `test_ac1`–`test_ac5`,
  утверждения `assert_signal_cleanup`, предел 20 с, точка сигнала и
  `time.sleep(90)` подмен не тронуты. Новые тесты раннего окна уже
  написаны test_author (`tests/test_01m583rm59dhdrdh877aeravmd_early_signal.py`),
  не правятся.

Бюджет SPEC не пересматривается.

## Шаги
1. `_SignalDeferral` и его вызовы в `_drive_in_clone`; AC-12 в общих
   помощниках `CanaryLifecycleTest`; регенерация `docs/codebase-map.md`.
   Проверка: `python3 -m pytest tests/test_01m583rm59dhdrdh877aeravmd_early_signal.py
   tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py tests/test_canary_drive.py
   tests/test_01m4beg0003ch0qa1gy0pxat03_clone_marker.py` — 34 passed;
   `artel.py plank-run 01M583RM59DHDRDH877AERAVMD` — 5 passed (AC-6, 7, 9,
   10, 12); полный набор — `artel.py suite-run`.

## Покрытие требований
| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1 |
| 5 | 1 |
| 6 | 1 |
| 7 | 1 (тесты test_author, уборка `reap_observed`) |
| 8 | 1 |
| 9 | 1 |

## Влияние на систему
- Меняется только участок запуска процесса ведения канарейки; ожидание,
  таймаут, снятие группы (`liveness.terminate_process_group`) и уборка
  клона не тронуты. Обработчики на участке временные и восстанавливаются
  во всех ветках выхода из `Popen`.
- Тесты не ослаблены: в `CanaryLifecycleTest` правка только добавляет
  утверждения в общий путь (мандат ANSWER-2); методы `tests/test_canary_drive.py`
  и `CanaryCloneMarkerTest` не правлены и зелёные (AC-7 планки).
- Откат — revert коммита задачи.

## Риски
- `signal.raise_signal` при обработчике `SIG_DFL` (вне канарейки) завершит
  процесс — ровно как сигнал без откладывания; поведение не хуже прежнего.
- Из нескольких сигналов на участке поднимается первый; повторные прежний
  обработчик канарейки и так игнорирует.

## Предложения системе
- В шелле шага нет `ls`/`cat` (заметил и test_author) — роли тратят попытки
  на обход; стоит либо добавить их в PATH роли, либо упомянуть в миссии.

## Итог эскалации (ANSWER-3)
- Красный линт `test_invariants.py::DeterministicTestsLintTest::test_tests_tree_has_no_wall_clock_waits_or_live_file_reads`
  на `EarlySignalCanaryTest::reap_observed` закрыт Оператором по варианту (б):
  `amend-tests` перевёл ожидание на `tests/sandbox.py::wait_processes_gone`
  (коммит ffe7c593). Код задачи не менялся.
- Проверка после ответа: затронутые модули (те же 4 файла) — 34 passed;
  `artel.py suite-run 01M583RM59DHDRDH877AERAVMD --failed` (прогон №2) —
  зелёный, 1 прошло, 0 упало.
