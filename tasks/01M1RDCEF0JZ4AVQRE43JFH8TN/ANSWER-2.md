---
task: 01M1RDCEF0JZ4AVQRE43JFH8TN
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: ответ Оператора

## Ответы

1. CI кодовой ветки КРАСНЫЙ (коммит 3d6bea81, джоб «Синтаксис и тесты
   оркестратора»): падают `tests/test_step_cost.py::
   test_warning_at_seventy_percent`, `test_timeout_with_usage_events_
   charges_a_partial_token_sum`, `test_step_friction_lands_in_journal_
   from_the_live_stream` и `tests/test_step_refixation.py::
   test_no_integrity_incident_on_next_run` — все ждут запуск CLI роли
   (`claude_launches == 1`, `spent_usd > 0`), а получают SKIPPED: на
   раннере GitHub нет исполняемых `claude` и `gh`, поэтому новый
   `_resolve_declared_tools()` бросает OSError и шаг роли не стартует.
   Локально тесты зелёные только потому, что инструменты стоят на
   машине Оператора — это ровно тот класс зависимости от окружения,
   который задача призвана убрать. «Коммитить нечего» — неверный вывод.
2. Требуется правка: тесты, запускающие `cmd_run`/`run_agent_once` с
   поддельным CLI (`popen`-дубль), обязаны подменять разрешение
   инструментов (`mock.patch.object(runner, "_resolve_declared_tools",
   return_value={...})` либо `shutil.which`), чтобы не зависеть от PATH
   машины; при необходимости — общая фикстура в `tests/sandbox.py`.
   Воспроизведение локально: `PATH=/usr/bin:/bin python3 -m unittest
   tests.test_step_cost tests.test_step_refixation` (без pyenv/claude в
   PATH). Приёмка — зелёный CI ветки, не локальный прогон.
