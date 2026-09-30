---
task: 01M3RHSS9S7GJXW28WMJKNC8YG
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: tests/
# Рамка ТЗ — $15, но планка потолка задачи не ниже $25
# (skills/spec-authoring.md, config.BUDGET_CALIBRATION_TABLE): класс
# «до 5 критериев, до 3 файлов зоны» — ~25, ставим нижнюю планку.
budget_usd: 25
---

# SPEC: Тест таймаута прогона приёмочных тестов не зависит от порядка тестов

## Контекст
`tests/test_acceptance_tests_flow.py::AcceptanceRunTest::test_timeout_blocks_the_transition_and_names_the_limit`
(стр. 1037–1062 на пине 6925e43d) подменяет `subprocess.run` модуля
`orchestrator/acceptance.py` целиком — это общий объект модуля `subprocess`,
подмена действует на все вызовы процесса — и сверяет `timeout` ПОСЛЕДНЕГО
вызова (`run_mock.call_args`) с `config.ACCEPTANCE_TIMEOUT_SEC`. После
`acceptance.run` переход (`orchestrator/advance_gates/acceptance.py`,
`_acceptance_run_refuses`) зовёт `agent_log.environment_fingerprint()`, который
кэшируется на процесс и при пустом кэше вызывает `git --version` и
`claude --version` с `timeout=5` (`agent_log.ENV_FINGERPRINT_TIMEOUT_SEC`).
Поэтому при пустом кэше тест видит 5 вместо 300 и красный (одиночный запуск
красный всегда), а в полном `tests/` итог зависит от состава и порядка тестов.
Красный полный `tests/` в worktree задачи — отказ автогейта приёмки, то есть
ложная остановка настоящей задачи до решения Оператора (повтор этапа 2
замера моделей канарейкой 30.09: ложный отказ в 5 прогонах из 10).

## Требования
1. Тест проверяет то же свойство без зависимости от порядка: вызов прогона
   приёмочных тестов (команда pytest из `acceptance.run`) получает
   `timeout=config.ACCEPTANCE_TIMEOUT_SEC`, при `TimeoutExpired` переход не
   проходит, вывод и журнал называют предел. Сверяется именно вызов pytest
   (опознанный по команде), а не последний вызов подменённой функции; кэш
   `environment_fingerprint` не влияет на итог. Способ (сброс кэша в тесте
   или подмена, не зависящая от него) — выбор PLAN.
2. Проверяемое свойство не ослабляется: удаление `timeout=` из вызова в
   `acceptance.run` по-прежнему делает тест красным («Ловит мутацию: убран
   timeout= из вызова прогона приёмочных тестов»).
3. Тест зелёный при запуске в одиночку и в полном `tests/`, при заранее
   заполненном и при пустом кэше `environment_fingerprint`; оба случая кэша
   закреплены в `tests/`.
4. Разработчик проверяет `tests/` на тот же дефект: другие тесты, сверяющие
   `call_args` подменённого `subprocess.run` на пути, где зовётся
   `environment_fingerprint`. Найденные чинятся тем же приёмом в этой задаче;
   перечень найденного (или «не найдено» с описанием поиска) — в PLAN.md.

## Критерии приёмки
AC-1. Тест таймаута прогона приёмочных тестов сверяет `timeout` именно того
вызова подменённого `subprocess.run`, чья команда — прогон pytest из
`acceptance.run`, и требует `timeout=config.ACCEPTANCE_TIMEOUT_SEC`; при
`TimeoutExpired` состояние задачи остаётся `in_dev`, вывод `cmd_advance`
содержит `превысил {config.ACCEPTANCE_TIMEOUT_SEC}с`, в журнале ровно одна
запись «переход отклонён: приёмочные тесты» со словом «превысил».

AC-2. Если из вызова прогона приёмочных тестов в `acceptance.run` убрать
`timeout=`, тест из AC-1 красный (мутация «убран timeout= из вызова прогона
приёмочных тестов» ловится).

AC-3. Тест из AC-1 зелёный при пустом кэше `environment_fingerprint` и при
заранее заполненном кэше — оба случая закреплены в `tests/`; тест зелёный и
при запуске в одиночку, и в составе полного `tests/`.

AC-4. PLAN.md содержит перечень тестов `tests/`, сверяющих `call_args`
подменённого `subprocess.run` на пути, где зовётся `environment_fingerprint`
(либо «не найдено» с описанием поиска); каждый найденный тест исправлен в
этой задаче тем же приёмом и зелёный независимо от состояния кэша
`environment_fingerprint`.

## Оценка объёма и деление
Сработавшие сигналы (по `scripts/guard.py::split_signal_names`): «число
затрагиваемых модулей/файлов» и «затронут инвариантный механизм» —
оба от упоминаний путей в тексте SPEC, прежде всего от списка «только
чтение» раздела «Не входит» (в том числе `tests/test_invariants.py`,
`docs/invariants.md`), а не от объёма правки; «прогноз диффа не дан» —
следствие первых двух.

Прогноз диффа: 6 КиБ.

Фактическая зона правки — `tests/`: один тест в
`tests/test_acceptance_tests_flow.py` (плюс закрепление двух случаев кэша) и,
если поиск по требованию 4 что-то найдёт, такие же точечные правки соседних
тестов. Код пульта и `tests/test_invariants.py` не меняются.

**Обоснование монолита.** Резать нечего: требования 1–3 — одна правка
одного теста, требование 4 — проверка того же дефекта тем же приёмом, и
разнесение его в отдельную подзадачу оставило бы `tests/` частично
зависимым от порядка, то есть не сняло бы ложный отказ автогейта, ради
которого задача заведена. Решение утверждает Оператор на гейте SPEC.

## Не входит
- Изменение кода пульта: кэш `environment_fingerprint`, порядок вызовов в
  `_acceptance_run_refuses`. Только чтение: `orchestrator/acceptance.py`,
  `orchestrator/advance_gates/`, `orchestrator/agent_log.py`,
  `orchestrator/config.py`, `orchestrator/fsm.py`,
  `orchestrator/fsm_advance.py`, `orchestrator/fsm_autogate.py`,
  `scripts/guard.py`, `skills/`, `templates/`, `docs/adr/`,
  `docs/invariants.md`, `tests/test_invariants.py`, `docs/backlog.md`,
  `tasks/`.
- Сохранение причины отказа автогейта в канарейке (отдельная задача).
- Решение о допуске моделей (ADR-0019 п.5).

## Материалы
- ТЗ: `tasks/01M3RHSS9S7GJXW28WMJKNC8YG/TZ.md` (решение Оператора 30.09.2026;
  строки копилки 30.09 о ложном отказе автогейта приёмки и её уточнение).
- `orchestrator/agent_log.py:21` (`ENV_FINGERPRINT_TIMEOUT_SEC = 5`),
  `:39` (`_environment_fingerprint_cache`), `:57` (`environment_fingerprint`).
- `tests/test_acceptance_tests_flow.py:1037` — текущий тест.
