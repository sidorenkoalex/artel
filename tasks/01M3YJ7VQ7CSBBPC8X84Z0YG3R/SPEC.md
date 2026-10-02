---
task: 01M3YJ7VQ7CSBBPC8X84Z0YG3R
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: tests/test_merge_gate_ci_wait.py, tests/test_ci_status_kind_gate.py, tests/test_merge_gate_clock_isolation.py, orchestrator/fsm_merge_gate.py, docs/codebase-map.md
budget_usd: 25
---

# SPEC: Часы теста гейта мержа не ловят паузы стандартной библиотеки

## Контекст
02.10 `tests/test_merge_gate_ci_wait.py` дважды покраснил CI веток, не
имевших отношения к гейту мержа (01M3Y75C9TY76083CG1PK00EM4, прогон
37013519921: `MovedMainRetryInCycleTest::test_moved_path_pauses_a_poll_interval_before_reentry`,
ожидалось `[90]`, получено `[90, 0.001, 0.002, 0.004, … 0.05, …]`;
01M3Y75GCRESC2KDS9VPRJK4PS, прогон 37019693646:
`MovedMainRetryInCycleTest::test_wait_path_does_not_get_the_moved_pause`,
ожидалось `[]`, получено `[0.001, 0.002, … 0.05]`). Причина:
`MergeGateCiWaitUnitTest.setUp` (`tests/test_merge_gate_ci_wait.py:57-64`)
подменяет `sleep` и `monotonic` модуля `time` целиком, и `FakeClock.sleep`
записывает КАЖДЫЙ вызов в процессе — в том числе паузы
`subprocess.Popen._wait` (удвоение 0.001 → 0.05), пока дочерний git ещё
жив на медленном раннере. Тот же приём — в
`tests/test_ci_status_kind_gate.py:59-66`. Паузы самого пульта, которые
проверяют тесты, живут в `orchestrator/fsm_merge_gate.py`:
`_wait_for_branch_ci_green` (`time.sleep` на строке 335, `time.monotonic`
на 319/330), `_await_main_ci` (560/573/577), `_cmd_approve_merge_gate_cycle`
(1237/1242/1243/1260); других обращений к `time` в этом модуле нет.

Способ (ТЗ, требование 1, выбор аналитика): подмена `sleep`/`monotonic`
в пространстве имён модуля пульта, который ждёт (`fsm_merge_gate.time`
заменяется на объект, отдающий `sleep`/`monotonic` часов теста), а не в
модуле `time`. Код пульта при этом не обязан меняться; если разработчик
всё же меняет `orchestrator/fsm_merge_gate.py`, то только способ вызова
паузы (требование 5).

## Требования

1. Часы тестов `tests/test_merge_gate_ci_wait.py` (`FakeClock` базового
   класса `MergeGateCiWaitUnitTest`) учитывают только паузы пульта:
   подмена `sleep`/`monotonic` выполняется в пространстве имён модуля
   пульта, который ждёт (`orchestrator/fsm_merge_gate.py` — ссылка
   `fsm_merge_gate.time`), а не в модуле `time`. Вызовы `time.sleep`/
   `time.monotonic` из стандартной библиотеки и сторонних модулей в
   `sleep_calls` не попадают и показание часов не сдвигают.
2. Ни одно существующее утверждение на `sleep_calls`, `clock.value` и
   `monotonic` в `tests/test_merge_gate_ci_wait.py` не удаляется и не
   ослабляется: ожидаемые значения (`[config.MERGE_GATE_CI_WAIT_POLL_SEC]`,
   `[]`, `[config.MERGE_GATE_CI_WAIT_POLL_SEC] * 2`,
   `[config.MERGE_GATE_CI_WAIT_POLL_SEC] * expected_retries`, сравнения
   `clock.value` и т. п.) и состав тестовых методов остаются прежними.
   Меняется только точка подмены часов (и чтение часов самим тестом —
   например, помощник на строке 84 `start = time.monotonic()` — там, где
   без этого он перестал бы видеть часы теста).
3. `tests/test_ci_status_kind_gate.py` переводится на тот же способ
   подмены часов (его `FakeClock` в `NonRedStatusSkipsRerunTest.setUp`
   больше не подменяет `time.sleep`/`time.monotonic` модуля `time`);
   его существующие утверждения не удаляются и не ослабляются.
4. Остальные файлы с тем же приёмом — `tests/test_merge_queue.py`,
   `tests/test_invariants.py` (около строки 676),
   `tests/test_main_ci_line.py` (около строки 355) — только проверяются:
   найденная там та же уязвимость с утверждением на точные паузы или
   потолки называется в PLAN.md (файл, класс/метод, утверждение) и не
   правится.
5. Если меняется `orchestrator/fsm_merge_gate.py` — меняется только
   способ вызова паузы/часов; длительности
   (`config.MERGE_GATE_CI_WAIT_POLL_SEC`, `config.VERIFYING_POLL_INTERVAL_SEC`,
   `MAIN_CI_WAIT_LIMIT_SEC`, потолки), порядок и условия пауз в
   `_wait_for_branch_ci_green`, `_await_main_ci`,
   `_cmd_approve_merge_gate_cycle` остаются прежними.
6. Новый файл `tests/test_merge_gate_clock_isolation.py` — регрессионный
   тест с текстом «Ловит мутацию: …»: под часами теста гейта мержа (та же
   подмена, что в `MergeGateCiWaitUnitTest`) запускается настоящий
   дочерний процесс, живущий дольше первой паузы `Popen._wait`
   (например, `subprocess.run([sys.executable, "-c", "import time;
   time.sleep(0.3)"], timeout=10)`); после его завершения список пауз
   часов пуст, а показание `monotonic` часов не сдвинулось. Мутация —
   вернуть глобальную подмену `time.sleep` (`mock.patch.object(time,
   "sleep", …)`) — делает тест красным детерминированно, без
   зависимости от скорости машины.

## Критерии приёмки

AC-1. В `tests/test_merge_gate_ci_wait.py` часы теста подменяются в
пространстве имён `orchestrator/fsm_merge_gate.py` (`fsm_merge_gate.time`),
а не через `mock.patch.object(time, "sleep", …)`/`mock.patch.object(time,
"monotonic", …)` модуля `time`: при установленных часах базового класса
`MergeGateCiWaitUnitTest` вызов `time.sleep(x)` модуля `time` из кода вне
пульта не добавляет запись в `clock.sleep_calls` и не меняет
`clock.value`, а `fsm_merge_gate.time.sleep(x)` добавляет `x` в
`clock.sleep_calls` и продвигает показание `fsm_merge_gate.time.monotonic()`
на `x`.

AC-2. Все тестовые методы `tests/test_merge_gate_ci_wait.py`, бывшие в
файле до задачи, на месте, и каждое их утверждение на `sleep_calls`,
`clock.value` и `monotonic` сохранено с прежним ожидаемым значением
(`[config.MERGE_GATE_CI_WAIT_POLL_SEC]`, `[]`,
`[config.MERGE_GATE_CI_WAIT_POLL_SEC] * 2`,
`[config.MERGE_GATE_CI_WAIT_POLL_SEC] * expected_retries`, сравнения
`clock.value`); файл зелёный.

AC-3. В `tests/test_ci_status_kind_gate.py` часы `FakeClock` подменяются
тем же способом, что в AC-1 (не через `mock.patch.object(time, "sleep"/
"monotonic", …)` модуля `time`); пауза `time.sleep` модуля `time` из
кода вне пульта не сдвигает показание его часов; все прежние тестовые
методы и их утверждения на месте, файл зелёный.

AC-4. Если `orchestrator/fsm_merge_gate.py` изменён, то в
`_wait_for_branch_ci_green`, `_await_main_ci` и
`_cmd_approve_merge_gate_cycle` паузы идут с прежними длительностями
(`config.MERGE_GATE_CI_WAIT_POLL_SEC`, `config.VERIFYING_POLL_INTERVAL_SEC`),
в прежнем порядке и при прежних условиях — существующие тесты на эти
паузы зелёные без изменения ожидаемых значений.

AC-5. Файл `tests/test_merge_gate_clock_isolation.py` существует и несёт
текст «Ловит мутацию: …»; его тест под часами теста гейта мержа запускает
настоящий дочерний процесс, живущий не меньше 0.3 с
(`subprocess.run([sys.executable, "-c", "import time; time.sleep(0.3)"],
timeout=10)` или равноценный), и утверждает, что `clock.sleep_calls == []`
и показание `monotonic` часов равно показанию до запуска процесса.

AC-6. Тест AC-5 краснеет при мутации «вернуть глобальную подмену
`time.sleep` модуля `time` часами теста» детерминированно — на любой
скорости машины (дочерний процесс гарантированно жив дольше первой паузы
`Popen._wait`, поэтому хотя бы одна пауза стандартной библиотеки
попадает в `sleep_calls`).

## Оценка объёма и деление

Сработавшие сигналы: число файлов зоны = 5 (порог
`SPLIT_SIGNAL_ZONE_FILES = 5`); прогноз диффа не был дан.

Прогноз диффа: 8 КиБ (две точки подмены часов в `setUp` двух тестовых
файлов плюс новый файл регрессионного теста на один-два метода;
`orchestrator/fsm_merge_gate.py` при выбранном способе не меняется, и
тогда `docs/codebase-map.md` не регенерируется).

Обоснование монолита (материал для решения Оператора): по фактическому
объёму сигнал зон формальный — из пяти зон `docs/codebase-map.md` и
`tests/` входят в общие зоны (`config.COMMON_ZONES`), а
`orchestrator/fsm_merge_gate.py` указан на случай, если разработчик
выберет правку способа вызова паузы. Резать нечего атомарно-независимого:
регрессионный тест `tests/test_merge_gate_clock_isolation.py`
(требование 6) проверяет именно часы базового класса
`MergeGateCiWaitUnitTest` и без перевода `tests/test_merge_gate_ci_wait.py`
на новую точку подмены (требование 1) красный — отдельно от неё он не
мержим с зелёной планкой. Перевод `tests/test_ci_status_kind_gate.py`
(требование 3) — правка той же формы в несколько строк; отдельная
подзадача стоила бы ещё один цикл шагов (~$15–25) ради диффа меньше
1 КиБ.

## Не входит

- Изменение длительностей и логики ожидания CI в гейте мержа
  (`orchestrator/fsm_merge_gate.py` — только способ вызова паузы).
- Правка тестов, не сверяющих точные паузы, в том числе
  `tests/test_merge_queue.py`, `tests/test_invariants.py`,
  `tests/test_main_ci_line.py` — только проверка и упоминание в PLAN.md
  (требование 4).
- Правка `orchestrator/ci.py`, `orchestrator/config.py`,
  `orchestrator/auto.py`, `orchestrator/fsm.py`,
  `orchestrator/merge_queue.py`, остальных файлов `tests/`, `skills/`,
  `docs/adr/`, `docs/invariants.md`, `tasks/` — только чтение.
- `.github/`.
- Полный зелёный набор `tests/` и зелёный CI ветки — её держит пульт.

## Материалы

- ТЗ: `tasks/01M3YJ7VQ7CSBBPC8X84Z0YG3R/TZ.md` (строка копилки 02.10, П1).
- Прогоны CI: 37013519921, 37019693646 (попытка 2).
- CPython 3.13 `subprocess.Popen._wait`: `delay = min(delay * 2, remaining, .05)`.
- Рамка Оператора в ТЗ — $15; `budget_usd` поднят до планки $25
  (`config.BUDGET_CALIBRATION_FLOOR_USD`), ниже которой SPEC не ставится.
