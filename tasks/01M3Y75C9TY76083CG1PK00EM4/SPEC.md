---
task: 01M3Y75C9TY76083CG1PK00EM4
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/ci.py, orchestrator/ci_rerun.py, orchestrator/config.py, tests/test_ci_stuck_check_run.py, docs/codebase-map.md
budget_usd: 25
---

# SPEC: Проверка CI, зависшая в состоянии «идёт» при известном исходе, не останавливает задачу

## Контекст
02.10 задача 01M3XTFJCC5TG63FHW907GQM4D простояла в `verifying` с 08:31Z до 09:58Z.
GitHub отдавал check-run «Валидация артефактов» (id 110766383863, прогон
pull_request 36984521183) коммита 6cb9b55e с `status=in_progress`, хотя у него были
`conclusion=success` и `completed_at=08:31:44Z`. Оба прогона workflow при этом были
`completed/success`. `orchestrator/ci.py::verifying_status` (строки 236–240) и
`ci.branch_status` (строки 336–339; вызывается из `fsm_merge_gate.py:254`, `:301`)
считают проверку идущей только по полю `status != "completed"`. Из-за этого задача
ждёт бесконечно. `ci-rerun` (`orchestrator/ci_rerun.py::_cmd_ci_rerun`, строки
164–172) в таком случае отказывает с «не завершённо-красный (исход running)». Сбой
обошли вручную: `stop`, `gh run rerun 36984521183`, `auto`.

## Требования
1. Проверка, у которой `status` не `completed`, но заданы непустые `conclusion` и
   `completed_at`, считается завершённой с этим `conclusion`. Правило одно для
   `ci.verifying_status` и `ci.branch_status`: обе вызывают одну функцию, второй
   копии правила нет. Запись журнала статуса CI называет такую проверку отдельной
   строкой: «<имя>: GitHub отдаёт status=<…> при conclusion=<…>,
   completed_at=<…> — считаю завершённой».
2. Новая константа `config.CI_STUCK_CHECK_MINUTES` = 45. Состояние «проверка
   зависла» — проверка в `in_progress`/`queued` без `conclusion`, возраст которой
   превышает `CI_STUCK_CHECK_MINUTES`. Возраст отсчитывается от `started_at`
   check-run, а если его нет — от `created_at`. Для такой проверки пишется запись
   журнала с её именем, id и возрастом. Задача при этом не продвигается и не
   эскалирует, но `ci-rerun` такую задачу не отклоняет (требование 3).
3. `ci-rerun <id> --reason …` в состоянии «проверка зависла» (требование 2)
   выполняется без отказа. Команда перезапускает прогон workflow, к которому
   относится зависшая проверка, тем же механизмом перезапуска, что и для красного
   CI. Отказ по lease при живом цикле остаётся как есть.
4. Тесты лежат в новом файле `tests/test_ci_stuck_check_run.py`. Каждый тест несёт
   строку «Ловит мутацию: …».

## Критерии приёмки
AC-1. Check-run с `status=in_progress`, `conclusion=success` и непустым
`completed_at` (остальные проверки коммита завершены зелёными) даёт
`ci.verifying_status` исход `VERIFYING_GREEN`, а `ci.branch_status` — `True`
(зелёный на гейте мержа).

AC-2. Тот же check-run, но с `conclusion=failure`, даёт `ci.verifying_status` исход
`VERIFYING_RED`, а `ci.branch_status` — `False` с красным `note`
(`ci.status_kind(note) == "red"`).

AC-3. Решение «завершена ли проверка и с каким исходом» принимает одна функция модуля
`orchestrator/ci.py`, и её вызывают и `verifying_status`, и `branch_status`. Если
подменить эту функцию, исход меняется у обеих: у них нет собственной копии сравнения
`status != "completed"`.

AC-4. В `orchestrator/config.py` есть константа `CI_STUCK_CHECK_MINUTES`
со значением 45.

AC-5. Check-run в `in_progress` (или `queued`) без `conclusion`, возраст которого
меньше `CI_STUCK_CHECK_MINUTES` (от `started_at`, а без него от `created_at`), даёт
`ci.verifying_status` исход «идёт» (`VERIFYING_RUNNING`), а не «проверка зависла».

AC-6. Тот же check-run старше `CI_STUCK_CHECK_MINUTES` даёт `ci.verifying_status`
именованное состояние «проверка зависла». Его `note` содержит имя проверки, её id и
возраст. Это состояние не зелёное и не красное: `ci.verifying_is_red(note)` ложно.
Возраст считается от `started_at`, а если его нет — от `created_at`: для check-run без
`started_at` с `created_at` старше порога состояние то же.

AC-7. Задача в `verifying`, у ветки которой «проверка зависла»: `ci-rerun <id>
--reason <непустое новое основание>` не отказывает. Команда вызывает перезапуск
прогона workflow, которому принадлежит зависшая проверка, тем же механизмом
перезапуска, что и для красного CI. Отказа «не завершённо-красный … повторять нечего»
нет.

AC-8. Запись журнала статуса CI (`fsm.VERIFYING_STATUS_ACTION`) для проверки из AC-1
содержит строку «<имя>: GitHub отдаёт status=in_progress при conclusion=success,
completed_at=<значение> — считаю завершённой». Запись для состояния из AC-6 называет
имя проверки, её id и возраст.

AC-9. Каждый тест в `tests/test_ci_stuck_check_run.py` несёт в докстринге строку
«Ловит мутацию: …».

## Оценка объёма и деление
Необщих файлов зоны два (`orchestrator/ci.py`, `orchestrator/ci_rerun.py`). Остальные
зоны (`orchestrator/config.py`, `tests/…`, `docs/codebase-map.md`) общие. Критериев 9,
`budget_usd` 25. Ни один сигнал не срабатывает, деление не требуется.

## Не входит
- Автоматический перезапуск зависшей проверки без команды Оператора.
- Изменение опроса CI (период 90 с, `VERIFYING_POLL_INTERVAL_SEC`) и существующего
  потолка ожидания `VERIFYING_CEILING_SEC`.
- Правка `.github/`.
- Правка `orchestrator/auto.py`, `orchestrator/fsm.py`, `orchestrator/fsm_merge_gate.py`,
  `orchestrator/github_adapter.py`, остальных файлов `tests/`, `skills/`, `docs/adr/`,
  `docs/invariants.md`, `tests/test_invariants.py`, `tasks/`: по ТЗ они только для
  чтения.
- Отдельное состояние «проверка зависла» на гейте мержа (`branch_status`): ТЗ вводит
  его для `verifying` и `ci-rerun`, а `ci-rerun` работает только в `verifying`. На гейте
  мержа проверка без `conclusion` по-прежнему не зелёная.
- Снятие отказов `ci-rerun` по основанию (пустое или повторное), по состоянию задачи
  (не `verifying`) и по lease. Отказы остаются; меняется только отказ «не
  завершённо-красный» для состояния «проверка зависла».
- Регенерация `docs/codebase-map.md` по правилу conventions-core и зелёный набор
  `tests/`: эти проверки держит пульт.

## Материалы
- ТЗ: `tasks/01M3Y75C9TY76083CG1PK00EM4/TZ.md`. Источник — строка копилки 02.10 (П2).
- Рамка Оператора в ТЗ — $20. По калибровке ни одна задача не получает меньше $25
  (skills/spec-authoring.md), поэтому `budget_usd: 25`. Это минимальное допустимое
  значение.
- Код (origin/main 28b09389): `orchestrator/ci.py:200` (`verifying_status`),
  `:317` (`branch_status`), `:375` (`find_run_id`), `:423` (`trigger_rerun`);
  `orchestrator/ci_rerun.py:158–172` (отказ «не завершённо-красный»),
  `:174–193` (сверка головы по журналу красного статуса).
