---
task: 01M5MHVRS39CDP5V4HBWY4K7WK
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Обвязка «id задачи + блокировка задачи» команд — одна функция вместо семи копий

# Обвязка «id задачи + блокировка задачи» команд — одна функция вместо семи копий

## Факты

Находка ревизии кода 22.10 CR-2026-10-22-16 (`docs/audits/code-revision-2026-10-22.md`, раздел «Находки»). Сверено с `origin/main` edbbc059 (пин 870aa7e9; `orchestrator/` и `tests/` совпадают).

Семь публичных команд повторяют одну обвязку — открыть БД, развернуть префикс id задачи в полный id до блокировки, выполнить тело под блокировкой задачи (lease):

```python
conn = store.db()
task_id = store.resolve_task_id(conn, task_id)
lease.run_locked(conn, task_id, session_id,
                 lambda sid: _cmd_X(conn, task_id[, reason]))
```

| Команда | Где | Тело |
|---|---|---|
| `cmd_spec_audit(task_id, session_id=None)` | `orchestrator/fsm.py:1766` | `_cmd_spec_audit(conn, task_id)` |
| `cmd_reject(task_id, reason, session_id=None)` | `orchestrator/fsm.py:1678` | `_cmd_reject(conn, task_id, reason)` |
| `cmd_pull_main(task_id, session_id=None)` | `orchestrator/pull_main.py:35` | `_cmd_pull_main(conn, task_id)` |
| `cmd_workspace(task_id, session_id=None)` | `orchestrator/workspace.py:255` | `_cmd_workspace(conn, task_id)` |
| `cmd_ci_rerun(task_id, reason, session_id=None)` | `orchestrator/ci_rerun.py:44` | `_cmd_ci_rerun(conn, task_id, reason)` |
| `cmd_run(task_id, session_id=None)` | `orchestrator/runner.py:153` (возвращает результат `run_locked`) | `_cmd_run(conn, task_id)` |
| `cmd_zones_extend(task_id, paths_arg, session_id=None, matrix_path=None)` | `orchestrator/answer.py:488` | `_cmd_zones_extend(conn, task_id, paths_arg, matrix_path)` |

Ни одна не передаёт `run_locked` именованных аргументов (`on_refusal`, `same_host_ok`, `force`); аргумент `sid` лямбды не используется. `lease.run_locked` (`orchestrator/lease.py:334`) — общая точка блокировки (`resolve_session_id` → `acquire` → отказ → тело → снятие); `lease` уже импортирует `store`. Общей функции «развернуть id и выполнить под блокировкой» нет; похожий приём есть ещё в `answer.cmd_answer`, `budget.py`, `amend.py` (там тела или аргументы `run_locked` другие — в задачу не входят).

Параметр `session_id` у пяти команд Оператора продукт не передаёт (диспетчер `orchestrator/artel.py` зовёт их с id и причиной); `cmd_run` его получает от `auto` (`auto.py:928`); тесты передают его `cmd_workspace` (`tests/test_workspace.py::CmdWorkspaceLeaseTest`, позиционно). Докстринг `session.resolve_session_id` называет явный параметр тестовым швом.

Тесты, которые держат поведение и не правятся: `tests/test_workspace.py` (`CmdWorkspaceLeaseTest`, `CmdWorkspaceTest`), `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py` (подменяет `workspace.cmd_workspace`, `fsm.cmd_reject`, `ci_rerun.cmd_ci_rerun` по имени), `tests/test_01m4pmr5evfk4kqdpwb1kegm7v_pull_main.py` (ac1, ac2, ac3, ac14), `tests/test_pull_conflict_marker_states.py`, `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`, `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_flow.py::test_ac21_spec_audit_command_from_gate_and_refusal_elsewhere`, `tests/test_task_id_prefix_regression.py` (префикс разворачивается до блокировки).

## Требования

1. В `orchestrator/lease.py` рядом с `run_locked` появляется функция `run_task_command(task_id, session_id, body)`: `conn = store.db()`, `task_id = store.resolve_task_id(conn, task_id)`, затем `run_locked(conn, task_id, session_id, lambda sid: body(conn, task_id))`; возвращает то, что вернул `run_locked`. Префикс разворачивается до взятия блокировки; `run_locked` вызывается без именованных аргументов, то есть с прежними значениями по умолчанию.
2. Семь команд таблицы делегируют обвязку `lease.run_task_command`: тело — их функция `_cmd_*`; для `cmd_reject`, `cmd_ci_rerun`, `cmd_zones_extend` добавочные аргументы передаются замыканием (`lambda conn, tid: _cmd_reject(conn, tid, reason)`); `cmd_run` возвращает результат `run_task_command`. Вторым позиционным аргументом передаётся параметр `session_id` самой команды. Имена, сигнатуры (включая необязательный `session_id`) и поведение команд не меняются. Докстринги сохраняют утверждение «префикс разворачивается до взятия lease»; слово «ЗДЕСЬ» заменяется ссылкой на `lease.run_task_command`, где порядок теперь обеспечен.
3. Тест (новый файл в `tests/`): (а) `run_task_command` с префиксом id задачи в песочнице вызывает тело с полным id и соединением, а `run_locked` получает полный id (шпион на `lease.run_locked` с пропуском к настоящему); (б) в песочнице строка lease задачи записана на чужую сессию с живым pid (например, `os.getppid()`) и этой машиной; вызов `lease.run_task_command(<префикс>, "sess-x", body)` завершается `SystemExit`, текст которого совпадает с отказом `lease.acquire` для того же полного id; `body` не вызван; строка lease не изменилась; (в) разбор AST семи функций таблицы: в теле каждой нет вызовов `store.db`, `store.resolve_task_id` и `lease.run_locked`, есть вызов `lease.run_task_command`, вторым позиционным аргументом которого передан параметр `session_id` функции; (в) — линтер, в докстринге — «Ловит мутацию: в команде возвращена своя копия обвязки или потерян `session_id`». На текущем коде (а) и (б) красные (функции нет), (в) красный.
4. Существующие тесты не правятся и остаются зелёными.

Зоны: orchestrator/lease.py, orchestrator/fsm.py, orchestrator/pull_main.py, orchestrator/workspace.py, orchestrator/ci_rerun.py, orchestrator/runner.py, orchestrator/answer.py, docs/codebase-map.md, tests/

Ограничение зон по смыслу: в `fsm.py`, `pull_main.py`, `workspace.py`, `ci_rerun.py`, `runner.py`, `answer.py` меняются только тела и докстринги семи функций таблицы (и ставшие лишними импорты); в `answer.py` — только `cmd_zones_extend`; `run_locked` и прочие функции `lease.py` не меняются.

Только чтение: orchestrator/store.py (`db`, `resolve_task_id`), orchestrator/session.py, orchestrator/artel.py (диспетчер — не меняется), orchestrator/auto.py, orchestrator/budget.py, orchestrator/amend.py, orchestrator/ (каталог; меняются только файлы Зон).

Не входит: удаление необязательного `session_id` у команд `cmd_*` (тестовый шов, его передают тесты `cmd_workspace`); перевод на новую функцию команд `answer`, `budget`, `amend-tests` (иные тела или аргументы `run_locked`).

Бюджет: $25.
