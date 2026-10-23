---
task: 01M5MHVRS39CDP5V4HBWY4K7WK
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/lease.py, orchestrator/fsm.py, orchestrator/pull_main.py, orchestrator/workspace.py, orchestrator/ci_rerun.py, orchestrator/runner.py, orchestrator/answer.py, docs/codebase-map.md, tests/
budget_usd: 25
---

# SPEC: Обвязка «id задачи + блокировка задачи» команд — одна функция вместо семи копий

## Контекст
Находка ревизии кода 22.10 CR-2026-10-22-16 (`docs/audits/code-revision-2026-10-22.md`).
Семь публичных команд дословно повторяют одну обвязку: `conn = store.db()`,
`task_id = store.resolve_task_id(conn, task_id)`, затем
`lease.run_locked(conn, task_id, session_id, lambda sid: _cmd_X(conn, task_id[, …]))`.
Общей функции «развернуть префикс id и выполнить тело под блокировкой задачи»
нет, поэтому порядок «префикс разворачивается до взятия lease» держится
семью копиями. Задача сводит их к одной функции в `orchestrator/lease.py`
рядом с `run_locked` (`orchestrator/lease.py:334`).

Семь команд:

| Команда | Где | Тело |
|---|---|---|
| `cmd_spec_audit(task_id, session_id=None)` | `orchestrator/fsm.py` | `_cmd_spec_audit(conn, task_id)` |
| `cmd_reject(task_id, reason, session_id=None)` | `orchestrator/fsm.py` | `_cmd_reject(conn, task_id, reason)` |
| `cmd_pull_main(task_id, session_id=None)` | `orchestrator/pull_main.py` | `_cmd_pull_main(conn, task_id)` |
| `cmd_workspace(task_id, session_id=None)` | `orchestrator/workspace.py` | `_cmd_workspace(conn, task_id)` |
| `cmd_ci_rerun(task_id, reason, session_id=None)` | `orchestrator/ci_rerun.py` | `_cmd_ci_rerun(conn, task_id, reason)` |
| `cmd_run(task_id, session_id=None)` | `orchestrator/runner.py` (возвращает результат) | `_cmd_run(conn, task_id)` |
| `cmd_zones_extend(task_id, paths_arg, session_id=None, matrix_path=None)` | `orchestrator/answer.py` | `_cmd_zones_extend(conn, task_id, paths_arg, matrix_path)` |

## Требования

1. В `orchestrator/lease.py` рядом с `run_locked` появляется функция
   `run_task_command(task_id, session_id, body)`: `conn = store.db()`,
   `task_id = store.resolve_task_id(conn, task_id)`, затем
   `run_locked(conn, task_id, session_id, lambda sid: body(conn, task_id))`;
   возвращает то, что вернул `run_locked`. Префикс id разворачивается до
   взятия блокировки; `run_locked` вызывается без именованных аргументов
   (`on_refusal`, `same_host_ok`, `force` — прежние значения по умолчанию).
2. Семь команд таблицы делегируют обвязку `lease.run_task_command`: тело —
   их функция `_cmd_*`; для `cmd_reject`, `cmd_ci_rerun`, `cmd_zones_extend`
   добавочные аргументы передаются замыканием
   (`lambda conn, tid: _cmd_reject(conn, tid, reason)`); `cmd_run` возвращает
   результат `run_task_command`. Id задачи тело получает из своего параметра
   (параметр лямбды), а не из имени `task_id` внешней команды — иначе в
   `_cmd_*` уйдёт неразвёрнутый префикс. Вторым позиционным аргументом
   передаётся параметр `session_id` самой команды. Имена, сигнатуры (включая
   необязательный `session_id`) и поведение команд не меняются.
3. Утверждение «префикс разворачивается до взятия lease» сохраняется там, где
   оно есть сегодня, — в докстрингах `cmd_reject`, `cmd_workspace`,
   `cmd_ci_rerun`, `cmd_run`; слово «ЗДЕСЬ» в нём заменяется ссылкой на
   `lease.run_task_command`, где порядок теперь обеспечен. Докстринги
   `cmd_spec_audit`, `cmd_pull_main`, `cmd_zones_extend` не меняются (решение
   Оператора на гейте SPEC 23.10.2026, круг 1).
4. Новый тестовый файл в `tests/` с четырьмя проверками:
   (а) `run_task_command` с префиксом id задачи в песочнице вызывает тело с
   полным id и соединением, а `run_locked` получает полный id (шпион на
   `lease.run_locked` с пропуском к настоящему);
   (б) в песочнице строка lease задачи записана на чужую сессию с живым pid
   (например, `os.getppid()`) и этой машиной; возраст heartbeat
   зафиксирован подменой `liveness`/времени так, что он одинаков для эталона
   (`lease.acquire` для того же полного id) и проверяемого вызова; вызов
   `lease.run_task_command(<префикс>, "sess-x", body)` завершается
   `SystemExit`, текст которого полностью (включая полный id задачи)
   совпадает с текстом отказа эталона — сравнение по подстроке без id
   недопустимо; `body` не вызван; строка lease не изменилась;
   (в) разбор AST семи функций таблицы: в теле каждой нет вызовов `store.db`,
   `store.resolve_task_id` и `lease.run_locked`, есть вызов
   `lease.run_task_command`, вторым позиционным аргументом которого передан
   параметр `session_id` функции; если третий аргумент — лямбда, id задачи
   в вызове `_cmd_*` в её теле — параметр этой лямбды, а не имя `task_id`
   внешней функции; (в) — линтер, его докстринг содержит «Ловит мутацию: в
   команде возвращена своя копия обвязки или потерян `session_id`»;
   (г) для каждой из семи команд: вызов команды с уникальным префиксом id
   задачи в песочнице доходит до тела `_cmd_*` с полным id — тело подменено
   шпионом через `mock.patch.object(<модуль>, "_cmd_…")`, `run_task_command`
   и `run_locked` настоящие (решение Оператора на гейте SPEC 23.10.2026,
   круг 1).
   На коде до изменения (а), (б) и (в) красные.
5. Существующие тесты не правятся.
6. Ограничение зон по смыслу: в `fsm.py`, `pull_main.py`, `workspace.py`,
   `ci_rerun.py`, `runner.py`, `answer.py` меняются только тела семи
   функций таблицы, докстринги четырёх из требования 3 (и ставшие лишними импорты); в
   `answer.py` — только `cmd_zones_extend`; `run_locked` и прочие функции
   `lease.py` не меняются.

## Критерии приёмки

AC-1. `orchestrator/lease.py` содержит функцию `run_task_command(task_id, session_id, body)`; при вызове с префиксом id существующей задачи она вызывает `body` ровно с двумя аргументами — соединением БД и полным id задачи — и возвращает то, что вернул `run_locked` (а значит, `body`).

AC-2. `run_task_command` разворачивает префикс до взятия блокировки: `lease.run_locked` получает полный id задачи (не префикс) и вызывается без именованных аргументов `on_refusal`, `same_host_ok`, `force`.

AC-3. Если строка lease задачи записана на чужую сессию с живым pid и этой машиной, а возраст heartbeat зафиксирован подменой `liveness`/времени одинаковым для эталона и проверяемого вызова, `lease.run_task_command(<префикс>, "sess-x", body)` завершается `SystemExit`, текст которого полностью (включая полный id задачи) совпадает с текстом отказа `lease.acquire` для того же полного id; `body` не вызван; строка lease не изменилась.

AC-4. Тело каждой из семи функций таблицы (`fsm.cmd_spec_audit`, `fsm.cmd_reject`, `pull_main.cmd_pull_main`, `workspace.cmd_workspace`, `ci_rerun.cmd_ci_rerun`, `runner.cmd_run`, `answer.cmd_zones_extend`) не содержит вызовов `store.db`, `store.resolve_task_id` и `lease.run_locked` и содержит вызов `lease.run_task_command`, вторым позиционным аргументом которого передан параметр `session_id` этой функции; если тело передано лямбдой, id задачи в вызове `_cmd_*` внутри неё — параметр лямбды, а не имя `task_id` внешней функции.

AC-5. `cmd_reject`, `cmd_ci_rerun` и `cmd_zones_extend` передают в тело свои добавочные аргументы (`reason`; `reason`; `paths_arg`, `matrix_path`) так, что `_cmd_*` получает их с прежними значениями; `cmd_run` возвращает результат `run_task_command`.

AC-6. Имена и сигнатуры семи команд не изменились (включая необязательный `session_id` и его позицию; у `cmd_zones_extend` — и `matrix_path`).

AC-7. Докстринги четырёх команд `fsm.cmd_reject`, `workspace.cmd_workspace`, `ci_rerun.cmd_ci_rerun`, `runner.cmd_run` не содержат слова «ЗДЕСЬ» и содержат `run_task_command` (проверяется линтером); докстринги `fsm.cmd_spec_audit`, `pull_main.cmd_pull_main`, `answer.cmd_zones_extend` не изменены относительно main.

AC-8. В `tests/` добавлен новый файл с проверками (а), (б), (в), (г) требования 4; проверка (в) — линтер AST семи функций, её докстринг содержит строку «Ловит мутацию: в команде возвращена своя копия обвязки или потерян `session_id`»; на коде до изменения проверки (а), (б), (в) красные.

AC-9. Диф ветки относительно main не меняет ни одного существующего файла в `tests/` (только добавляет новый файл); в `orchestrator/lease.py` функция `run_locked` и прочие функции, кроме добавленной `run_task_command`, не изменены; в `orchestrator/answer.py` изменена только `cmd_zones_extend` (и, при необходимости, ставшие лишними импорты).

AC-10. Для каждой из семи команд таблицы вызов команды с уникальным префиксом id задачи в песочнице доходит до её тела `_cmd_*` с полным id задачи: тело подменено шпионом через `mock.patch.object(<модуль>, "_cmd_…")`, `lease.run_task_command` и `lease.run_locked` — настоящие; шпион вызван ровно один раз, его аргумент id — полный id (не префикс).

## Оценка объёма и деление

Сработавшие сигналы: число файлов зоны ≥ 5 (7 модулей `orchestrator/` + `docs/codebase-map.md` + новый файл `tests/`); число критериев приёмки ≥ 10 (AC-10 добавлен решением Оператора на гейте SPEC 23.10.2026, круг 1 — поведенческая проверка тех же семи команд, объём кода не растёт).

**Обоснование монолита (материал для решения Оператора).** Правка в каждом из шести модулей команд — замена трёх строк обвязки одним вызовом и правка одного докстринга; объём диффа мал, сигнал срабатывает от числа файлов, а не от объёма. Возможный разрез — (1) `lease.run_task_command` с проверками (а), (б); (2) перевод семи команд с линтером (в) — оставляет после части 1 функцию без единого вызывателя: само по себе это работоспособное состояние, но смысл задачи (одна точка обвязки вместо семи копий) достигается только частью 2, а линтер (в) проверяет все семь команд разом и без функции части 1 неприменим. Разрез удвоил бы постоянные шаги (аналитик, аудит, ревью) при бюджете ТЗ $25 на всё. Решение — за Оператором на гейте SPEC.

## Не входит

- Удаление необязательного `session_id` у команд `cmd_*` (тестовый шов: его передают тесты `cmd_workspace`, `tests/test_workspace.py::CmdWorkspaceLeaseTest`).
- Перевод на `run_task_command` команд `answer` (`answer.cmd_answer`), `budget` (`orchestrator/budget.py`), `amend-tests` (`orchestrator/amend.py`) — иные тела или аргументы `run_locked`.
- Изменение диспетчера `orchestrator/artel.py`, `orchestrator/store.py`, `orchestrator/session.py`, `orchestrator/auto.py` (только чтение).
- Изменение `run_locked` и прочих функций `lease.py`; прочих функций `fsm.py`, `answer.py` и др. модулей зоны (в т.ч. докстрингов с «ЗДЕСЬ» у функций вне таблицы — например `fsm.py:732`, `fsm.py:921`, `answer.py:309`).
- Зелёность полного набора `tests/` (требование 4 ТЗ, «остаются зелёными») — её держит пульт.
- Регенерация `docs/codebase-map.md` после правки `*.py` — конвенция разработчика, свежесть держит CI/пульт; отдельного критерия нет.

## Материалы

- `tasks/01M5MHVRS39CDP5V4HBWY4K7WK/TZ.md`; `docs/audits/code-revision-2026-10-22.md`, CR-2026-10-22-16.
- Тесты, держащие поведение (не правятся): `tests/test_workspace.py` (`CmdWorkspaceLeaseTest`, `CmdWorkspaceTest`), `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py` (подменяет `workspace.cmd_workspace`, `fsm.cmd_reject`, `ci_rerun.cmd_ci_rerun` по имени), `tests/test_01m4pmr5evfk4kqdpwb1kegm7v_pull_main.py` (ac1, ac2, ac3, ac14), `tests/test_pull_conflict_marker_states.py`, `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_flow.py::test_ac21_spec_audit_command_from_gate_and_refusal_elsewhere`, `tests/test_task_id_prefix_regression.py`.
- `cmd_run` получает `session_id` от `auto` (`orchestrator/auto.py:928`).
