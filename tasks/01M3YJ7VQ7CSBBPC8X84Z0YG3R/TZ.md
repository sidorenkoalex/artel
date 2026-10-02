---
task: 01M3YJ7VQ7CSBBPC8X84Z0YG3R
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Часы теста гейта мержа не ловят паузы стандартной библиотеки

# ТЗ: Часы теста гейта мержа не ловят паузы стандартной библиотеки

Источник: строка копилки 02.10 (П1) «Нестабильный тест main tests/test_merge_gate_ci_wait.py»; решение Оператора 02.10.

Факты (origin/main 72a55089; номера строк аналитик сверяет):
- 02.10 тест дважды покраснил CI чужих веток: 01M3Y75C9TY76083CG1PK00EM4 (прогон 37013519921, `MovedMainRetryInCycleTest::test_moved_path_pauses_a_poll_interval_before_reentry`, ожидалось `[90]`, получено `[90, 0.001, 0.002, 0.004, … 0.05, …]`) и 01M3Y75GCRESC2KDS9VPRJK4PS (прогон 37019693646, попытка 2, `MovedMainRetryInCycleTest::test_wait_path_does_not_get_the_moved_pause`, ожидалось `[]`, получено `[0.001, 0.002, … 0.05]`). Обе задачи к тесту и к гейту мержа отношения не имели; повтор прогона — зелёный; локально тест зелёный.
- Причина: `tests/test_merge_gate_ci_wait.py::MergeGateCiWaitUnitTest.setUp` (около строки 58) подменяет `time.sleep` модуля `time` целиком (`mock.patch.object(time, "sleep", self.clock.sleep)`), и `FakeClock.sleep` записывает в `sleep_calls` КАЖДЫЙ вызов в процессе. `subprocess.run(..., timeout=…)` ждёт ещё живой дочерний процесс через `subprocess.Popen._wait`, который крутит `time.sleep(delay)` с удвоением 0.001 → 0.05 (проверено по исходнику CPython 3.13: `delay = min(delay * 2, remaining, .05)`). На медленном раннере дочерний git не успевает завершиться — в `sleep_calls` попадают сотни пауз стандартной библиотеки; подменённый `sleep` не ждёт по-настоящему, поэтому цикл ожидания крутится до выхода ребёнка.
- Тот же приём `FakeClock` с глобальной подменой `time.sleep`: `tests/test_ci_status_kind_gate.py` (около строки 60; утверждений на `sleep_calls` нет, но `monotonic` этих часов сдвигается паузами `subprocess`), `tests/test_merge_queue.py`, `tests/test_invariants.py` (около строки 676), `tests/test_main_ci_line.py` (около строки 355) — точных списков пауз там не сверяют.
- Паузы самого пульта, которые проверяет тест: `orchestrator/fsm_merge_gate.py` — `_wait_for_branch_ci_green` (около строки 335), `_await_main_ci` (около строки 577), `_cmd_approve_merge_gate_cycle` (около строки 1242).

Требуется:
1. Часы тестов `tests/test_merge_gate_ci_wait.py` учитывают только паузы пульта, а не вызовы `time.sleep` из стандартной библиотеки и сторонних модулей. Способ выбирает аналитик; приемлемые: подмена `sleep`/`monotonic` в пространстве имён модулей пульта, которые ждут (например, `fsm_merge_gate.time`), а не в модуле `time`; либо одна точка ожидания пульта (функция или ссылка в `config`/модуле), которую тест подменяет. Если меняется код пульта — только способ вызова паузы, без изменения длительностей, порядка и условий пауз.
2. Ни одно существующее утверждение на `sleep_calls` и `monotonic` в `tests/test_merge_gate_ci_wait.py` не удаляется и не ослабляется: ожидаемые списки (`[90]`, `[]`, `[config.MERGE_GATE_CI_WAIT_POLL_SEC]` и т. п.) остаются прежними. Меняется только точка подмены часов.
3. `tests/test_ci_status_kind_gate.py` переводится на тот же способ (его `FakeClock` — копия того же приёма; паузы `subprocess` сдвигают его `monotonic` и могут сдвинуть потолки ожидания). Остальные файлы из фактов — только проверить; если найдена та же уязвимость с утверждением на точные паузы или потолки — назвать в PLAN, не править (вне зон).
4. Регрессионный тест в новом файле `tests/test_merge_gate_clock_isolation.py` с «Ловит мутацию: …»: под часами теста гейта мержа запускается настоящий дочерний процесс, который живёт дольше первой паузы `Popen._wait` (например, `subprocess.run([sys.executable, "-c", "import time; time.sleep(0.3)"], timeout=10)`), — список пауз часов остаётся пустым, `monotonic` часов не сдвинулся. Мутация: вернуть глобальную подмену `time.sleep` — тест краснеет детерминированно, без зависимости от скорости машины.

Зоны: tests/test_merge_gate_ci_wait.py, tests/test_ci_status_kind_gate.py, tests/test_merge_gate_clock_isolation.py, orchestrator/fsm_merge_gate.py, docs/codebase-map.md.

Только чтение (не менять): orchestrator/ci.py, orchestrator/config.py, orchestrator/auto.py, orchestrator/fsm.py, остальные файлы tests/, tests/test_invariants.py, skills/, docs/adr/, docs/invariants.md, tasks/.

Не входит: изменение длительностей и логики ожидания CI в гейте мержа; правка тестов, не сверяющих точные паузы; `.github/`.

Рамка: $15.
