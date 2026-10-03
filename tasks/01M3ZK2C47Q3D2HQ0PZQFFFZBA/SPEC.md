---
task: 01M3ZK2C47Q3D2HQ0PZQFFFZBA
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: tests/, orchestrator/runner.py, orchestrator/auto.py, orchestrator/acceptance.py, orchestrator/fsm_merge_gate.py, orchestrator/merge_queue.py, orchestrator/liveness.py, orchestrator/pause.py, orchestrator/watch.py, orchestrator/doctor/leases.py
budget_usd: 30
---

# SPEC: Тесты не подменяют time.sleep всего процесса

## Контекст

Подмена атрибута `sleep` у общего модуля `time` меняет его для всего
процесса, а не только для тестируемого модуля пульта. Поэтому паузы
ожидания дочернего процесса попадают в записи теста о паузах пульта; это
уже приводило к нестабильному отказу проверки отсутствующего CLI. Нужна
изоляция пауз пульта без изменения их рабочего поведения.

## Требования

1. Каждый вызов паузы в указанных зонах модулей пульта выполняется через
   локальную обёртку `_pause(seconds)`, а обёртка вызывает
   `time.sleep(seconds)` с тем же аргументом. Тесты, которым требуется
   наблюдать или ускорять паузу, подменяют эту локальную обёртку
   проверяемого модуля.
2. Все подмены `time.sleep` всего процесса в `tests/`, кроме разрешённых
   исключений, переводятся на локальные обёртки из требования 1. Число,
   длительности и отсутствие проверяемых пауз сохраняются; утверждения
   существующих тестов не изменяются без мандата Оператора через
   эскалацию.
3. В `tests/` появляется сторож, запрещающий новую подмену `time.sleep`
   всего процесса. В нём есть обоснованный перечень исключений, включая
   `tests/test_invariants.py`, и пометка «Ловит мутацию: подмена
   time.sleep всего процесса в тесте».
4. Регрессионный сценарий отделяет паузу вне проверяемой точки пульта,
   в том числе ожидание дочернего процесса через `subprocess`, от пауз,
   записываемых тестом пульта.

## Критерии приёмки

AC-1. В `orchestrator/runner.py`, `orchestrator/auto.py`,
`orchestrator/acceptance.py`, `orchestrator/fsm_merge_gate.py`,
`orchestrator/merge_queue.py`, `orchestrator/liveness.py`,
`orchestrator/pause.py`, `orchestrator/watch.py` и
`orchestrator/doctor/leases.py` каждый исполняемый вызов паузы идёт через
локальную `_pause(seconds)`, которая вызывает `time.sleep(seconds)` с
неизменённым аргументом; длительности и порядок пауз пульта не меняются.

AC-2. Во всех файлах `tests/`, кроме обоснованных исключений сторожа,
отсутствует подмена `time.sleep` всего процесса; каждая перенесённая
подмена вместо неё подменяет `_pause` проверяемого модуля и сохраняет
проверяемые свойства числа, длительности либо отсутствия пауз.

AC-3. Сторож в `tests/` краснеет при добавлении новой подмены
`time.sleep` всего процесса в тест, не включённый в обоснованный перечень
исключений; перечень содержит `tests/test_invariants.py`, а сценарий
сторожа помечен текстом «Ловит мутацию: подмена time.sleep всего процесса
в тесте».

AC-4. Регрессионный тест доказывает, что `time.sleep`, вызванный вне
проверяемой точки пульта при ожидании дочернего процесса через
`subprocess`, не записывается как пауза проверяемого модуля пульта.

## Оценка объёма и деление

Сработал сигнал большого объёма: зон модулей больше либо равно 5.

Обоснование монолита: все затронутые тесты находятся в единой зоне
`tests/`, а итоговый сторож может быть включён без временных исключений
только после перевода всех запрещённых подмен. Разрезание этой зоны
оставило бы в промежуточном состоянии либо действующую подмену всего
процесса, либо сторож с временным исключением для неё; ни одно из этих
состояний не даёт требуемой защиты от возврата шаблона. Локальные
обёртки модулей и миграция их тестов поэтому поставляются одной
самостоятельно мержимой сменой механики.

## Не входит

- Изменение длительностей, порядка или логики пауз пульта.
- Исправление нестабильных тестов, не вызванных подменой `time.sleep`
  всего процесса.
- Изменение уже изолированных часов гейта мержа.
- Изменение `tests/test_invariants.py`, `**/conftest.py`,
  `orchestrator/config.py`, `orchestrator/store.py`, `scripts/guard.py`,
  `skills/`, `templates/`, `docs/adr/`, `docs/invariants.md`,
  `docs/backlog.md`, `tasks/` и `.artel/`.

## Материалы

- Причина: задача `01M3YS928033B1QF89VN2N5KC3`, нестабильный сценарий
  `tests/test_agent_failure.py::CmdRunFailureTest::test_missing_cli_is_not_retried`.
- Пример изолированных часов: `tests/test_merge_gate_clock_isolation.py`.
- Полный перечень текущих кандидатов на миграцию на пине ТЗ:
  `tests/test_agent_failure.py`, `tests/test_runner_model_preflight.py`,
  `tests/test_acceptance_tests_flow.py`, `tests/test_step_cost.py`,
  `tests/test_runner_role_model.py`, `tests/test_main_ci_line.py`,
  `tests/test_merge_queue.py`,
  `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`,
  `tests/test_01m3sx69e8p64d77j1xthmhe40_observation.py`,
  `tests/test_01m3yxyax5pw9bm67mb4gk85d1_step_provider_preflight.py` и
  `tests/test_auto_cycle.py`; исключение — `tests/test_invariants.py`.
- Перед правкой перечень сверяется командой:
  `rg -n 'mock\\.patch' tests --glob '*.py' | rg 'time|sleep'`.
