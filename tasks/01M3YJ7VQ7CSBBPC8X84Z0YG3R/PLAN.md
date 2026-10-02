---
task: 01M3YJ7VQ7CSBBPC8X84Z0YG3R
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Часы теста гейта мержа не ловят паузы стандартной библиотеки

## Подход
Часы тестов переставляются из модуля `time` в пространство имён пульта:
`mock.patch.object(fsm_merge_gate, "time", types.SimpleNamespace(sleep=clock.sleep,
monotonic=clock.monotonic))`. В `orchestrator/fsm_merge_gate.py` к `time`
обращаются только `time.sleep`/`time.monotonic` (строки 319/330/335,
560/573/577, 1237/1242/1243/1260), так что объекта с двумя атрибутами
хватает; код пульта НЕ меняется (требование 5 не задействовано, карта
`docs/codebase-map.md` не регенерируется — `*.py` в `orchestrator/`/
`scripts/` не тронуты, а новый файл в `tests/` попадает в карту; см. шаг 4).
`subprocess.Popen._wait` и прочая стандартная библиотека продолжают видеть
настоящий `time.sleep` — в `sleep_calls` они больше не попадают.

## Шаги
1. `tests/test_merge_gate_ci_wait.py`: `MergeGateCiWaitUnitTest.setUp` —
   одна подмена `fsm_merge_gate.time` вместо двух `mock.patch.object(time, …)`;
   помощник `wait()` читает старт через `fsm_merge_gate.time.monotonic()`
   (иначе он видел бы настоящие часы); `import time` → `import types`.
   Тестовые методы и утверждения не тронуты.
2. `tests/test_ci_status_kind_gate.py`: `NonRedStatusSkipsRerunTest.setUp` —
   та же подмена; импорт `fsm_merge_gate`. Методы и утверждения не тронуты.
3. Новый `tests/test_merge_gate_clock_isolation.py`:
   `MergeGateClockIsolationTest(MergeGateCiWaitUnitTest)` — под часами
   базового класса `subprocess.run([sys.executable, "-c", "import time;
   time.sleep(0.3)"], check=True, timeout=10)`; после — `sleep_calls == []`
   и `fsm_merge_gate.time.monotonic()` равно показанию до запуска. Модуль
   базового класса импортирован как модуль (`from tests import
   test_merge_gate_ci_wait as ci_wait`), чтобы загрузчик не подхватил его
   тестовые классы повторно.
4. Регенерация карты: `python3 scripts/codebase_map.py` (новый файл в `tests/`).
5. Проверка: прогоны файлов, временная мутация сторожа, планка задачи.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 2 |
| 4 | раздел «Проверка остальных файлов» ниже |
| 5 | не задействовано — `orchestrator/fsm_merge_gate.py` не меняется |
| 6 | 3, 5 |

### Проверка остальных файлов (требование 4, не правились)
- `tests/test_main_ci_line.py`, класс с `_await_main_ci` (строки ~345-365):
  `mock.patch("time.sleep") as sleep` глобально и **точное утверждение
  `sleep.assert_not_called()`** — та же уязвимость: любая пауза
  стандартной библиотеки (например `Popen._wait`, если путь когда-нибудь
  позовёт подпроцесс) внутри блока покрасит тест. Сейчас в блоке
  `ci.main_line_status` и `merge_lock.touch_heartbeat` замоканы, подпроцессов
  нет — краснота не наблюдалась. Кандидат на ту же правку
  (`mock.patch.object(fsm_merge_gate.time, "sleep")`) отдельной задачей.
- `tests/test_merge_queue.py:178-179, 267-268, 307-308` — глобальные
  `mock.patch.object(time, "monotonic"/"sleep", …)` вокруг
  `merge_queue.wait_for_window`. Утверждений на точные паузы нет; есть
  нижняя граница `assertGreaterEqual(clock["value"],
  config.MERGE_QUEUE_WAIT_CEILING_SEC)` (`WaitForWindowTest::
  test_ceiling_expiry_dequeues_and_exits_without_touching_state`) — лишние
  паузы её только приближают, ложной красноты не дают. Уязвимость приёма
  есть, точного утверждения нет.
- `tests/test_invariants.py:676-677` — глобальные подмены вокруг
  `fsm.cmd_approve` в цикле случаев `NOT_GREEN`; утверждения — на отказ
  merge/состояние, не на паузы и не на точное показание часов. Лишняя
  пауза лишь раньше исчерпывает потолок — исход тот же. Точного
  утверждения нет.

## Влияние на систему
Меняются только тестовые файлы. Ни одно утверждение не снято и не
ослаблено, имена методов прежние (планка `test_assertions_and_pauses_kept.py`
сверяет с базой — зелёная). Код пульта не тронут — паузы и их длительности
прежние (AC-4 тривиально). Изоляция только сужает, что видят часы теста:
если какой-то путь гейта мержа ждёт через `time` в ДРУГОМ модуле
(`merge_queue`, `merge_lock`), под новыми часами он спал бы по-настоящему —
проверено прогоном: оба файла зелёные за ~5 с, реальных ожиданий нет.
Откат — revert коммита задачи.

Прогоны (передний план, `-p timeout -o timeout=120`):
- `tests/test_merge_gate_clock_isolation.py tests/test_merge_gate_ci_wait.py
  tests/test_ci_status_kind_gate.py` — 24 passed, 4.81 s.
- Мутация сторожа: в `MergeGateCiWaitUnitTest.setUp` временно добавлен
  `mock.patch.object(time, "sleep", self.clock.sleep)` —
  `test_child_process_wait_does_not_touch_the_test_clock` красный
  (`tests/test_merge_gate_clock_isolation.py:43`, `sleep_calls` забит
  паузами `Popen._wait`); мутация снята.
- Планка `tasks/01M3YJ7VQ7CSBBPC8X84Z0YG3R/acceptance_tests` — 9 passed.

## Риски
- Если в `fsm_merge_gate.py` появится обращение к другому атрибуту `time`
  (например `time.time()`), под подменой тестов оно упадёт
  `AttributeError` — это явный, а не тихий сигнал; добавить атрибут в
  `SimpleNamespace`.

## Предложения системе
- Класс «глобальная подмена `time.sleep` в тесте с точным утверждением на
  паузы» остался в `tests/test_main_ci_line.py` (`sleep.assert_not_called()`
  под `mock.patch("time.sleep")`) — кандидат в бэклог той же правкой.
