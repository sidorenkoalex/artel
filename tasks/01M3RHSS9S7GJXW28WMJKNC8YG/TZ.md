---
task: 01M3RHSS9S7GJXW28WMJKNC8YG
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Тест таймаута прогона приёмочных тестов не зависит от порядка тестов

# ТЗ: Тест таймаута прогона приёмочных тестов не зависит от порядка тестов

Источник: решение Оператора 30.09.2026; строки копилки 30.09 (П1) о ложном
отказе автогейта приёмки и её уточнение; повтор этапа 2 замера моделей
канарейкой 30.09 — ложный отказ автогейта в 5 прогонах из 10.

Факты (пин 6925e43d):
- `tests/test_acceptance_tests_flow.py::AcceptanceRunTest::test_timeout_blocks_the_transition_and_names_the_limit`
  подменяет `subprocess.run` модуля `orchestrator/acceptance.py` целиком
  (`mock.patch.object(acceptance.subprocess, "run", side_effect=TimeoutExpired)`
  — это общий объект модуля `subprocess`, подмена действует на все
  вызовы процесса) и сверяет таймаут ПОСЛЕДНЕГО вызова
  (`run_mock.call_args`) с `config.ACCEPTANCE_TIMEOUT_SEC`.
- После `acceptance.run` переход (`orchestrator/advance_gates/acceptance.py`,
  `_acceptance_run_refuses`) зовёт `agent_log.environment_fingerprint()`.
  Он кэшируется на процесс и при пустом кэше вызывает
  `git --version` и `claude --version` с `timeout=5`
  (`ENV_FINGERPRINT_TIMEOUT_SEC`).
- Итог: если кэш в процессе pytest ещё пуст, последний вызов — `claude
  --version`, тест видит 5 вместо 300 и красный; если кэш заполнил тест,
  прошедший раньше, — зелёный. Одиночный запуск теста на пине красный
  всегда; в полном `tests/` итог зависит от состава и порядка тестов.
  Красный полный `tests/` в worktree задачи — отказ автогейта приёмки,
  то есть ложная остановка настоящей задачи до решения Оператора.

Требуется:
1. Тест проверяет то же свойство без зависимости от порядка: вызов
   прогона приёмочных тестов (команда pytest из `acceptance.run`) получает
   `timeout=config.ACCEPTANCE_TIMEOUT_SEC`, при `TimeoutExpired` переход
   не проходит, вывод и журнал называют предел. Сверяется именно вызов
   pytest (по команде), а не последний вызов подменённой функции;
   кэш `environment_fingerprint` не влияет на итог (сброс кэша в тесте
   или подмена, не зависящая от него, — выбор PLAN).
2. Проверяемое свойство не ослабляется: удаление `timeout=` из вызова в
   `acceptance.run` по-прежнему делает тест красным («Ловит мутацию:
   убран timeout= из вызова прогона приёмочных тестов»).
3. Тест зелёный и при запуске в одиночку, и в полном `tests/`, и при
   заранее заполненном и при пустом кэше `environment_fingerprint` — оба
   случая закреплены в `tests/`.
4. Разработчик проверяет `tests/` на тот же дефект: другие тесты,
   сверяющие `call_args` подменённого `subprocess.run` на пути, где
   зовётся `environment_fingerprint`. Найденные чинятся тем же приёмом в
   этой задаче, перечень (или «не найдено» с описанием поиска) — в PLAN.

Зоны: tests/.

Только чтение (не менять): orchestrator/acceptance.py,
orchestrator/advance_gates/, orchestrator/agent_log.py,
orchestrator/config.py, orchestrator/fsm.py, orchestrator/fsm_advance.py,
orchestrator/fsm_autogate.py, scripts/guard.py, skills/, templates/,
docs/adr/, docs/invariants.md, tests/test_invariants.py, docs/backlog.md,
tasks/.

Не входит: изменение кода пульта (кэш `environment_fingerprint`, порядок
вызовов в `_acceptance_run_refuses`); сохранение причины отказа автогейта
в канарейке (отдельная задача); решение о допуске моделей (ADR-0019 п.5).

Рамка: $15.
