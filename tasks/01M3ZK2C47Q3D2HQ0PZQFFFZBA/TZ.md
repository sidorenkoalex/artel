---
task: 01M3ZK2C47Q3D2HQ0PZQFFFZBA
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Тесты не подменяют time.sleep всего процесса

# ТЗ: Тесты не подменяют time.sleep всего процесса

Источник: строки бэклога 02.10 «Подмены time.sleep на весь процесс в
tests/ — общий шаблон» (П2) и «Подмена time.sleep во всём процессе в
tests/test_main_ci_line.py»; задача 01M3YS928033B1QF89VN2N5KC3 (причина
нестабильного test_missing_cli_is_not_retried); решение Оператора 02.10 —
первая настоящая задача набора `codex-all`.

Факты (пин 65a128b8; номера строк аналитик сверяет):
- Подмены вида `mock.patch.object(runner.time, "sleep", …)`,
  `mock.patch.object(auto.time, "sleep", …)`, `mock.patch.object(time,
  "sleep", …)`, `mock.patch("time.sleep")` подменяют `time.sleep` всего
  процесса: `runner.time` — это общий модуль `time`. Под подмену попадают
  чужие вызовы `time.sleep` — например, ожидание выхода процесса в
  `subprocess.run(timeout=…)`; так 02.10 падал
  `tests/test_agent_failure.py::CmdRunFailureTest::test_missing_cli_is_not_retried`
  (паузы `subprocess` попали в «паузы бэкоффа»).
- Такие подмены есть, в частности, в: `tests/test_agent_failure.py`,
  `tests/test_runner_model_preflight.py`, `tests/test_acceptance_tests_flow.py`,
  `tests/test_step_cost.py`, `tests/test_runner_role_model.py`,
  `tests/test_main_ci_line.py`, `tests/test_merge_queue.py`,
  `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`,
  `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py`,
  `tests/test_01m3yxyax5pw9bm67mb4gk85d1_step_provider_preflight.py`,
  `tests/test_auto_cycle.py`; полный перечень — `grep` в SPEC.
  `tests/test_invariants.py` тоже содержит такие подмены, но это
  защищённый путь — его не трогать.
- `time.sleep` вызывают модули пульта: `orchestrator/runner.py`,
  `orchestrator/auto.py`, `orchestrator/acceptance.py`,
  `orchestrator/fsm_merge_gate.py`, `orchestrator/merge_queue.py`,
  `orchestrator/liveness.py`, `orchestrator/pause.py`,
  `orchestrator/watch.py`, `orchestrator/doctor/leases.py`.
- Уже есть пример изоляции часов: `tests/test_merge_gate_clock_isolation.py`.

Требуется:
1. Тест, проверяющий паузы пульта, подменяет паузу только той точки
   вызова пульта, которую проверяет, а не `time.sleep` всего процесса.
   Способ выбирает SPEC: например, функция-обёртка паузы в модуле пульта
   (`runner._pause`), которую подменяет тест, либо подмена с фильтром по
   вызывающему модулю. Поведение пульта (длительности и порядок пауз) не
   меняется.
2. Все подмены `time.sleep` всего процесса в `tests/` (кроме защищённого
   `tests/test_invariants.py`) переведены на способ требования 1;
   проверяемые свойства тестов (число и длительность пауз, отсутствие
   пауз) сохраняются. Правка утверждений существующих тестов — только по
   мандату Оператора через эскалацию.
3. Сторож от возврата шаблона: тест или линт в `tests/`, который краснеет
   на новой подмене `time.sleep` всего процесса в `tests/` (кроме
   перечня исключений с обоснованием, в том числе `tests/test_invariants.py`).
   Пометка «Ловит мутацию: подмена time.sleep всего процесса в тесте».
4. Регрессионный тест: вызов `time.sleep` вне проверяемой точки пульта
   (например, из `subprocess`) не попадает в паузы, которые проверяет
   тест.

Рамка: $30

Зоны: tests/, orchestrator/runner.py, orchestrator/auto.py, orchestrator/acceptance.py, orchestrator/fsm_merge_gate.py, orchestrator/merge_queue.py, orchestrator/liveness.py, orchestrator/pause.py, orchestrator/watch.py, orchestrator/doctor/leases.py.

Только чтение (не менять): tests/test_invariants.py, **/conftest.py,
orchestrator/config.py, orchestrator/store.py, scripts/guard.py, skills/,
templates/, docs/adr/, docs/invariants.md, docs/backlog.md, tasks/,
.artel/.

Не входит: изменение длительностей и логики пауз пульта; прочие
нестабильные тесты; часы гейта мержа (уже изолированы).
