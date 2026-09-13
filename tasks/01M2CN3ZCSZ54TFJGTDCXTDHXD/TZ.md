---
task: 01M2CN3ZCSZ54TFJGTDCXTDHXD
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Рефакторинг R4: runner.py — фазы шага роли внутри модуля

Источник: отчёт ревизии №6 docs/audits/code-revision-2026-09-13.md, находка
CR-2026-09-13-1 ★ и ТЗ-черновик Р-2; роадмап §3 фаза R, пункт R4
(runner.py; условия «после стека ч.3 и P0» наступили: 01M1RDCEF0,
01M1REVEZ1 done). Решение Оператора 13.09: волна рефакторинга, задача
класса «рефакторинг» по правилам T015.

Факты:
- orchestrator/runner.py: `run_agent_once` (:758–1019, 262 строки) — четыре
  фазы в одном теле: подготовка (промпт-файл, окружение, рабочий каталог,
  git-идентичность; пять однотипных блоков `journal + print + return
  "skipped"` с разными текстами), запуск и ожидание (spawn, pump, таймаут,
  kill группы процессов), учёт (friction, `spend.*`,
  `budget.check_program_spend`), исходы (timeout / rc != 0 / нет артефакта
  / успех).
- `_run_developer_step` (:225–431, 207 строк): отказы до старта (пауза,
  стоп-кран, скилы — через `sys.exit`; чужая ветка, pre-flight, инцидент —
  через `return`), сборка промпта, цикл попыток с бэкоффом, эскалация.
- Модуль — узел: 38 тестовых файлов, 101 `patch.object(runner, …)` по
  публичным именам (`cmd_run` 66, `role_env` 27, `role_cwd` 16,
  `run_agent_once` 4, `spawn_agent` 3). Тексты SKIPPED и исходов сверяются
  дословно: tests/test_agent_log.py:606, tests/test_agent_prompt.py:257,
  tests/test_multitarget.py:881.
- Циклы импортов вокруг runner — четыре (в том числе doctor); новый модуль
  не создаётся, разбор только внутри runner.py.

Требуется (поведение не меняется):
1. `run_agent_once` -> приватные фазы: `_prepare_step` (пять исходов
   SKIPPED с прежними текстами и прежними записями журнала),
   `_spawn_and_wait` (открытие промпта, `spawn_agent`, pump, таймаут, kill
   группы; возвращает proc/pump/rc/timed_out/killed_group),
   `_account_step` (friction, `spend.*`, `budget.check_program_spend`),
   исходы `_finish_timeout` / `_finish_failed` / `_finish_missing_artifact`
   / `_finish_ok`. Значение и тип возврата `run_agent_once` — как есть.
2. `_run_developer_step` -> `_refuse_before_start` (`sys.exit` и `return`
   сохраняются как есть: помощник возвращает признак, вызывающий код
   делает ровно то же), `_build_prompt`, `_run_attempts` (возвращает
   `attempt, reason, failure_class`; переменная `attempt` доступна после
   цикла, как сейчас), `_escalate_after_attempts`.
3. Имена `run_agent_once`, `spawn_agent`, `role_env`, `role_cwd`,
   `role_cmd`, `cmd_run`, `_cmd_run`, `step_role`,
   `wave_breaker_alerts_open` остаются глобалами модуля с прежними
   сигнатурами — их патчат тесты.
4. Поверхности неизменности: вывод команд пульта (stdout/stderr, коды
   выхода), тексты и порядок записей журнала, алерты, схема БД, имена и
   пути файлов. Зелёность полного набора tests/ = неизменность.
5. Тесты: ассерты и сценарии не меняются; допустимы только импорты и пути
   патчей (ожидаемо — нулевые правки: новый модуль не создаётся).
6. PLAN: таблица переносов, откат revert'ом одного merge, смоук до/после
   (`status`, `report`, `doctor` без изменяющих флагов) — сравнение в PLAN.
7. Никаких попутных улучшений; циклы импортов не трогать.

Зоны: orchestrator/runner.py, tests/.

Приложением: tests/test_agent_log.py, tests/test_agent_prompt.py,
tests/test_multitarget.py (дословные тексты SKIPPED/исходов — контракт).

Не входит: `finally` с `zone_lock.release_claim` в `_cmd_run` (:158–222),
тексты и коды исходов, `role_env`/`role_cwd`/`role_cmd` (контракт признака
роли ARTEL_ROLE из 01M2B6K3EM), любые новые модули.

Рамка: $45. Условие старта: тихое окно — параллельно только задачи с
непересекающимися зонами (Р-1 checkpoint.py, Р-4 canary.py, фикс утечки
тестов).
