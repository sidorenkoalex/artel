---
task: 01M2CN3ZCSZ54TFJGTDCXTDHXD
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/runner.py, tests/
budget_usd: 45
---

# SPEC: Рефакторинг R4: runner.py — фазы шага роли внутри модуля

## Контекст
`run_agent_once` (262 строки) и `_run_developer_step` (207 строк) в
`orchestrator/runner.py` несут каждый по четыре разных фазы шага роли в
одном теле функции: подготовку, запуск и ожидание агента, учёт
стоимости, разбор исходов — у первой; отказы до старта, сборку промпта,
цикл попыток с бэкоффом, эскалацию — у второй. Модуль — узел: 38
тестовых файлов патчат его публичные имена 101 раз, поэтому разбор на
фазы делается только внутри модуля, без создания нового. Поведение не
меняется — задача переносит код, не логику.

## Требования
1. `run_agent_once` разложен на приватные фазы `_prepare_step`,
   `_spawn_and_wait`, `_account_step` и функции исходов
   `_finish_timeout`, `_finish_failed`, `_finish_missing_artifact`,
   `_finish_ok`. Значение и тип возврата `run_agent_once` не меняются.
2. `_run_developer_step` разложен на `_refuse_before_start`,
   `_build_prompt`, `_run_attempts`, `_escalate_after_attempts`.
   `sys.exit` и `return` сохраняются как есть: `_refuse_before_start`
   возвращает признак отказа, а вызывающий код выполняет ровно то же
   действие (`sys.exit`/`return`), что выполнялось до разбора.
3. Имена `run_agent_once`, `spawn_agent`, `role_env`, `role_cwd`,
   `role_cmd`, `cmd_run`, `_cmd_run`, `step_role`,
   `wave_breaker_alerts_open` остаются глобалами модуля
   `orchestrator/runner.py` с прежними сигнатурами — их патчат тесты.
4. Поверхности неизменности: вывод команд пульта (stdout/stderr, коды
   выхода), тексты и порядок записей журнала, алерты, схема БД, имена
   и пути файлов. Зелёность полного набора `tests/` = подтверждение
   неизменности.
5. Правки тестов ограничены импортами и путями патчей — ассерты,
   тексты и сценарии тестов не меняются.
6. Никаких попутных улучшений; циклы импортов вокруг `runner.py` не
   трогаются; новый модуль не создаётся.

## Критерии приёмки

AC-1. `run_agent_once` разложен на приватные функции `_prepare_step`,
`_spawn_and_wait`, `_account_step` и на функции исходов
`_finish_timeout`, `_finish_failed`, `_finish_missing_artifact`,
`_finish_ok`; сигнатура, тип и значение возврата `run_agent_once` не
меняются.

AC-2. `_prepare_step` воспроизводит все пять исходов SKIPPED (промпт не
записан; окружение роли не создано; рабочий каталог роли не создан;
промпт не прочитан; claude CLI не найден) с прежними текстами возврата
и прежними записями журнала.

AC-3. `_spawn_and_wait` открывает файл промпта, вызывает `spawn_agent`,
запускает перекачку вывода (pump), обрабатывает таймаут и снятие
группы процессов и возвращает `proc`, `pump`, `rc`, `timed_out`,
`killed_group`; `_account_step` выполняет учёт шага (friction,
`spend.*`, `budget.check_program_spend`) без изменения вызовов и их
порядка.

AC-4. `_run_developer_step` разложен на `_refuse_before_start`,
`_build_prompt`, `_run_attempts`, `_escalate_after_attempts`.

AC-5. `_refuse_before_start` сохраняет прежнее поведение отказов до
старта шага: `sys.exit` (пауза, стоп-кран волны, скилы) и `return`
(чужая ветка worktree, pre-flight, инцидент целостности) выполняются
вызывающим кодом `_run_developer_step` ровно там же и с тем же
эффектом, что до разбора — помощник только возвращает признак отказа.

AC-6. `_run_attempts` возвращает `(attempt, reason, failure_class)`;
переменная `attempt` доступна вызывающему коду после завершения цикла
попыток — как в текущей реализации.

AC-7. Имена `run_agent_once`, `spawn_agent`, `role_env`, `role_cwd`,
`role_cmd`, `cmd_run`, `_cmd_run`, `step_role`,
`wave_breaker_alerts_open` остаются глобалами модуля
`orchestrator/runner.py` с прежними сигнатурами; новый модуль не
создаётся — разбор выполнен целиком внутри `orchestrator/runner.py`.

AC-8. Полный набор `tests/` зелен после рефакторинга; правки тестов
ограничены импортами и путями патчей (`patch.object`) — ассерты,
тексты и сценарии тестов не меняются.

AC-9. Вывод команд пульта (stdout/stderr, коды выхода), тексты и
порядок записей журнала, алерты, схема БД и имена/пути файлов на диске
не изменились — подтверждено смоук-прогоном `status`, `report`,
`doctor` (без изменяющих флагов) до и после рефакторинга, а также
таблицей переносов и способом отката (`revert` одного merge-коммита) в
`PLAN.md`.

## Не входит

- `finally` с `zone_lock.release_claim` в `_cmd_run` — не трогается.
- Тексты и коды исходов шага — не меняются.
- Контракт `role_env`/`role_cwd`/`role_cmd` (признак роли ARTEL_ROLE из
  01M2B6K3EM) — не трогается.
- Любые новые модули — не создаются, разбор только внутри
  `orchestrator/runner.py`.
- Попутные улучшения и правка циклов импортов вокруг `runner.py`.

## Материалы
- docs/audits/code-revision-2026-09-13.md, находка CR-2026-09-13-1 ★ и
  ТЗ-черновик Р-2.
- tests/test_agent_log.py:606, tests/test_agent_prompt.py:257,
  tests/test_multitarget.py:881 — дословные тексты SKIPPED/исходов.
