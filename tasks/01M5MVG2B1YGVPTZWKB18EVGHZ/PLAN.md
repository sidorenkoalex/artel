---
task: 01M5MVG2B1YGVPTZWKB18EVGHZ
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: canary --parallel: строка «оборвана сигналом» не теряется у дочернего, тесты гонки говорят причину, GroupSignalTest не виснет

## Подход
- Диагностика (тр. 1): к `assertEqual` строк прогона двух тестов гонки
  добавлен третий аргумент — вывод родителя с журналами дочерних
  (`run.out` / `out`); утверждения и литералы прежние.
- Укрепление (тр. 2): запись строки «оборвана сигналом» вынесена в
  `canary._insert_interrupted_row`: цикл из `CHILD_ROW_WRITE_ATTEMPTS = 3`
  попыток, `store.db()` внутри `try` каждой попытки, повтор только на
  `sqlite3.OperationalError`, без `sleep` (ожидание — штатный таймаут
  блокировки соединения 5 с). В ветке `except CanaryInterrupted`
  `cmd_canary_run_task` любое не преодолённое `Exception` записи даёт в
  stderr «[canary] <шаблон>: строка прогона не записана: <repr>» и
  `traceback.format_exc()`; выход в любом случае `128 + сигнал`.
- Родитель (тр. 3) не меняется: stderr дочернего идёт в его журнал
  (`_start_child`: `stderr=STDOUT`), журнал печатает `_finish_child`,
  строка БД — прежняя `drive_failed`.
- `GroupSignalTest` (тр. 5): в `run_cli` дескриптор канала внука на запись
  открывается неблокирующим и сразу закрывается (до `join`) — читающий
  поток получает конец данных; `read_grandchild_pid` при пустых данных
  бросает `AssertionError("внук не появился")`.

## Шаги
1. `orchestrator/canary.py`: импорт `sqlite3`/`traceback`, константа
   `CHILD_ROW_WRITE_ATTEMPTS` рядом с `PARALLEL_STOP_GRACE_SEC`, функция
   `_insert_interrupted_row`, отчёт в stderr в ветке `except
   CanaryInterrupted`.
2. `tests/test_canary_parallel_protection.py`: сообщение к утверждению
   `BaselineTest` (:505-507), `read_grandchild_pid`, `run_cli`.
   `tests/test_canary_parallel.py`: сообщение к утверждению `StopTest`
   (:382-384).
3. Новый `tests/test_canary_child_row_write.py` (5 тестов, у каждого
   «Ловит мутацию:»; без нагрузки и серий).
4. `python3 scripts/codebase_map.py` — карта перегенерирована.
5. Возврат из verifying (CI c82c1f84, прогон 39995616858): сторож
   `tests/test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard.py::SleepGuardTreeTest::test_ac1_tests_tree_has_no_global_sleep_patch`
   засчитал подменой имя шпиона `mock.Mock(name="time.sleep")` в
   `tests/test_canary_child_row_write.py:60`. Шпион переименован в
   `name="canary_sleep"`; подмена паузы — по-прежнему
   `patch_sleep(canary, …)`. Проверка: `python3 -m pytest
   tests/test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard.py
   tests/test_canary_child_row_write.py -p no:xdist` — 9 passed,
   45 subtests passed.

Проверка: `python3 -m pytest tests/test_canary_child_row_write.py
tests/test_01m5mvg2b1ygvptzwkb18evghz_row_write_deadline.py
tests/test_canary_parallel_protection.py tests/test_canary_parallel.py` —
32 passed; `artel.py plank-run 01M5MVG2B1YGVPTZWKB18EVGHZ` — 8 passed.
Мутации кода, проверенные на новом файле: `store.db()` вне цикла + `sleep`
в попытке — 4 красных; `store.db()` в цикле вне `try` — красный
`test_failed_connection_open_is_retried`; `except Exception` + `sleep`
между попытками — 3 красных. Код возвращён.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 2 |
| 2 | 1, 3 |
| 3 | 1 (родитель не тронут), 3 (`ParentReportsUnwrittenRowTest`) |
| 4 | раздел «Риски» |
| 5 | 2 |
| 6 | 3 |
| 7 | 2 (правки только названные) |

## Влияние на систему
- Поведение `--parallel` меняется только в ветке `except CanaryInterrupted`
  дочернего: успешная запись — прежняя строка и прежний код; при сбое записи
  код `128 + сигнал` вместо 1 и отчёт в журнале. Родитель,
  `_finish_child`, `_report_child_failure`, `PARALLEL_STOP_GRACE_SEC` не
  тронуты; граница срока 3 × 3 × 5 + 3 = 48 < 60 держит
  долгоживущий тест AC-5.
- Тестовые файлы: утверждения не удалены и не ослаблены, добавлены только
  сообщения; помощники `run_cli`/`read_grandchild_pid` теперь не виснут, а
  проваливаются с причиной.
- Откат — revert коммита ветки задачи.

## Риски
- SIGHUP (или повторный сигнал) во время повторов записи: обработчик
  `_interrupt_on_signal` бросает `CanaryInterrupted` (BaseException) из
  ветки `except` — его не ловит `except Exception`, процесс выходит по
  внешнему `except CanaryInterrupted` с кодом нового сигнала без строки —
  как и в текущем коде (остаточный риск).
- Известное ограничение тр. 5: согласующий поток, не дошедший до
  `os.open(grandchild_fifo, O_RDONLY)` к концу работы родителя, —
  неблокирующее открытие на запись падает `ENXIO` (подавлено), поток может
  висеть на открытии; от зависания защищает `timeout = 120` pytest.
- Допущение модели границы срока: не более трёх ожиданий блокировки по 5 с
  на попытку — миграция при открытии соединения (`orchestrator/store.py:409`,
  `:431`, `orchestrator/schema.py:291–400`), обновление таблиц канарейки и
  вставка (`orchestrator/store.py:1620–1623`).
- Причина неустойчивости CI не установлена локально (гонка не
  воспроизводилась); задача сдаётся с диагностикой (тр. 1) и укреплением
  (тр. 2) — исход нормы по тр. 4. Если CI ветки покажет иную причину —
  эскалация.
- Планка AC-9 (`test_ac2_ac3_ac8_ac9_child_row_write.py`) подменяет
  `canary.time.sleep` — это глобальный `time.sleep`; `subprocess.run(…,
  timeout=10)` в `stale_cycles.process_start_time` (зовётся из
  `_write_child_record` до записи) опрашивает `ps` паузами `time.sleep`.
  Локально один из прогонов моего теста с той же глобальной подменой
  покраснел на `assert_not_called` (вызов не из кода задачи). Планка может
  изредка краснеть ложно; свой тест переведён на `tests.sandbox.patch_sleep`.

## Предложения системе
- Планки/тесты, подменяющие `<модуль>.time.sleep` через `mock.patch.object`,
  подменяют глобальный `time.sleep` и ловят паузы `subprocess` — класс уже
  описан в `tests/sandbox.py::TimeWithSleep`; стоит правило в
  skills/test-authoring.md: «шпион sleep — только `patch_sleep`».
- Сторож `test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard.py` считает подменой
  любую строку `time.sleep` в аргументах вызова, включая
  `mock.Mock(name=…)`. Об этом узнаёшь только по красному CI — тому же
  правилу в skills/test-authoring.md стоит назвать и этот случай.
