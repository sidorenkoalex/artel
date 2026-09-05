---
task: 01M1SD5RHTJ0H0SR0615SVCJM5
type: plan
author_role: developer
status: ready
schema_version: 4
---

# PLAN: R7 — `fsm_merge_gate._cmd_approve_merge_gate` разобрать на шаги

## Подход

Разбираем инлайн-тело `_cmd_approve_merge_gate` (сегодня 35 top-level
операторов на 184 строки) на именованные top-level шаг-функции, каждая
с явным исходом (`"ok"`/`"refused"`/протокольный аналог `("wait",
branch)`/`("stopped", ...)`/`"done"`), сохраняя буквально порядок шагов,
условия отказа/эскалации и тексты `store.journal`/`sys.exit`/`print`.
`_cmd_approve_merge_gate_cycle` НЕ трогается: она уже сегодня — короткая
композиция (мьютекс `merge_lock.acquire`/`release` + вызов тела + цикл
ожидания `_wait_for_branch_ci_green`), дальше decomposition не нужен, и
проверка AC-1 (`test_ac1_short_composition_and_new_step_functions.py`)
её не касается.

Существующие узлы `_handle_merge_conflict`, `_ci_confirm_red_or_flake`,
`_wait_for_branch_ci_green`, `_overlay_artifact_snapshot`,
`_origin_main_sha`, `_scratch_worktree`, `_drop_scratch_worktree`,
`_touches_protected_path` уже покрывают часть ответственностей
(защищённый путь при конфликте, ре-ран CI, ожидание CI, снимок
артефактов) — остаются нетронутыми, из тела вычленяются оставшиеся
восемь ответственностей в девять новых функций (в порядке вызова из
композиции):

1. `_ensure_branch_head_published(conn, task_id, branch)` — голова ветки
   задачи видна в origin (predусловие approve); `"ok"` / `"refused"`.
2. `_sync_main_or_wait(conn, task_id, t, state, branch)` — подтяжка main
   и проверка свежести (SPEC T053) под мьютексом; `"fresh"` /
   `("stopped",)` / `("wait", branch)` (путь `"pulled"` — push нового
   head в origin ДО цикла ожидания, требование 1 SPEC T087).
3. `_ci_ready_or_wait(task_id, confirmed_ci_note, branch)` — путь
   `"fresh"` без ещё не подтверждённого зелёного статуса уходит в
   `("wait", branch)` без единого обращения к `ci.branch_status` (AC-7
   01M1NBWPKNBXP9ZXXQDJM7AXPJ, тест
   `test_merge_gate_ci_wait.py::FreshPathDefersToWaitLoopTest`); иначе
   печатает буквальный `note` и возвращает `"ok"`.
4. `_perform_carpentry_merge(conn, task_id, state, branch)` — фетч sha
   main origin, scratch-worktree (Stage0, AC-8), `git merge --no-ff`;
   конфликт делегируется нетронутому `_handle_merge_conflict`;
   `("ok", scratch)` / `("stopped", None)`.
5. `_publish_merge_artifacts(conn, task_id, scratch)` — снимок
   артефактной ветки поверх merge (нетронутый
   `_overlay_artifact_snapshot`, ДО вычисления `merge_sha` — тот же
   порядок, что и сегодня), карта кодовой базы, RETRO, `final_sha`,
   уборка scratch-дерева; возвращает `final_sha`.
6. `_push_merged_main(conn, task_id, final_sha)` — push явного sha в
   `refs/heads/<MAIN_BRANCH>` origin (Stage0, AC-8); успех/`sys.exit`.
7. `_finalize_done_state(conn, task_id, state, branch)` — `state ->
   done` + безусловный `lease.release_any`.
8. `_publish_closing_snapshot_or_wait(conn, task_id, t)` — снапшот
   закрытия (SPEC T094, AC-13/AC-15); `"done"` (снапшот ещё в очереди —
   уборка ветки/worktree откладывается) / `"ok"` (продолжить уборку).
9. `_cleanup_merged_task(conn, task_id, branch)` — уборка worktree,
   затем ветки задачи (порядок обязателен: `-d` не даст убрать ветку,
   пока её держит worktree).

`_cmd_approve_merge_gate` становится композицией девяти вызовов + одного
внешнего `branch = t["branch"]` — ни одного нового `if` внутри цикла
условий сверх сегодняшней глубины (проверено вручную по AST-логике
`test_ac2_no_new_condition_nesting.py`: максимальная глубина вложенности
внутри `_sync_main_or_wait` и `_publish_closing_snapshot_or_wait` — 2,
как и в сегодняшнем коде, не больше).

## Шаги

1. Разобрать `_cmd_approve_merge_gate` на 9 новых шаг-функций
   (перечислены выше) + короткая композиция; `_cmd_approve_merge_gate_
   cycle` не редактируется; ни строки логики не меняется, только
   границы функций. Юнит-тесты: прогнать `tests/test_fsm_merge_gate*.py`,
   `tests/test_branch_freshness_gate.py`,
   `tasks/01M1SD5RHTJ0H0SR0615SVCJM5/acceptance_tests/` и
   `python3 scripts/guard.py`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1 (`_cmd_approve_merge_gate_cycle` не редактируется) |
| 5 | 1 (все `store.journal`/`sys.exit`/`print` скопированы буквально) |
| 6 | 1 (три сценария `acceptance_tests/test_ac5_three_smoke_scenarios.py` — записаны на сегодняшнем коде, обязаны остаться зелёными) |
| 7 | 1 |

## Влияние на систему

Единственная зона — `orchestrator/fsm_merge_gate.py` (плюс `tests/`, без
правки `assert`). Инвариант 12 (только `approve` из `merge_gate` мержит
в main) и инвариант 19 (merge требует зелёного CI головы) реализованы
буквально тем же кодом, перенесённым в новые функции без изменения
условий — не ослабляются. Мьютекс окна мержа (`merge_lock.acquire`/
`release`) остаётся в нетронутой `_cmd_approve_merge_gate_cycle` —
захват/освобождение вокруг тела не меняется. Откат — `git revert`
коммита: чистая перестановка кода без переноса состояния БД/веток.
Публичный контракт (сигнатура `_cmd_approve_merge_gate_cycle`, тексты
журнала/печати, наблюдаемое поведение трёх смоук-сценариев) — по
условиям задачи не меняется и проверен приёмочными тестами.

## Риски

Тонкий порядок внутри `_publish_merge_artifacts`: `merge_sha` обязан
вычисляться ПОСЛЕ наложения снимка артефактной ветки (иначе RETRO
адресуется на коммит без снимка `tasks/<id>/`) — сохранён буквально тем
же порядком вызовов, что и в сегодняшнем инлайн-теле.

## Предложения системе
