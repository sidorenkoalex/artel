---
task: T087
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 2
---

# REVIEW: merge_gate — approve сам ожидает CI после подтяжки

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `orchestrator/fsm.py:1261-1274` — после `pull_outcome == "pulled"` пуш `git push -u origin branch` выполняется до возврата `("wait", branch)`, внутри мьютекса (см. требование 2). Приёмочный `test_ac1_push_before_wait_loop.py` наблюдает push непосредственно перед первым чтением статуса CI. |
| 2 | OK | `_cmd_approve_merge_gate_cycle` (`fsm.py:1350-1391`) берёт `merge_lock.acquire`/`release` напрямую вокруг каждого захода в `_cmd_approve_merge_gate`, `release` — в `finally`; `_wait_for_branch_ci_green` зовётся ПОСЛЕ `release`. Приёмочный `test_ac2_mutex_free_during_wait.py` проверяет свободу мьютекса непосредственно из моков `ci.branch_status`/`ci.trigger_rerun`/`time.sleep`. |
| 3 | OK | `_wait_for_branch_ci_green` (`fsm.py:1156-1189`) переиспользует `ci.branch_status`/`ci.status_kind`/`_ci_confirm_red_or_flake` (общий узел с однократной проверкой на пути `"fresh"`); running/unknown паузят `time.sleep(config.MERGE_GATE_CI_WAIT_POLL_SEC)` и продолжают цикл. |
| 4 | OK | Потолок вычисляется РОВНО один раз в `_cmd_approve_merge_gate_cycle` (`if deadline is None: start = time.monotonic(); deadline = start + config.MERGE_GATE_CI_WAIT_CEILING_SEC`), не пересчитывается на повторном исходе `("wait", ...)`. Подтверждено `test_ac4_ceiling_not_reset_by_repull.py` (приёмочный, честный контроль через скачок часов) и `test_ceiling_not_reset_by_a_second_wait_outcome` (юнит). |
| 5 | OK | Зелёный статус (включая флейк-ре-ран) — возврат из `_wait_for_branch_ci_green` в `confirmed_ci_note`, цикл перезаходит с тем же `sid`, тем же вызовом `approve`. `test_ac5_green_completes_same_call.py` проверяет `done` после одного `self.approve()`. |
| 6 | OK | Повторный `pull_outcome == "pulled"` на заходе после ожидания просто возвращает новый `("wait", branch)`, не читая `confirmed_ci_note` (ветка `"pulled"` в `_cmd_approve_merge_gate` этот параметр не трогает) — кэш корректно отбрасывается для нового head. `_pull_main_or_escalate` прогоняет `acceptance.run` при подтяжке (`fsm.py:321`), т.е. приёмочные тесты гоняются и на повторной подтяжке. `test_ac6_repull_on_second_main_advance.py` зелёный. |
| 7 | OK | `_ci_confirm_red_or_flake` (переиспользуется из фикс. пути T082) — подтверждённый красный `sys.exit` тем же текстом, что и раньше; тест `test_ac7_confirmed_red_stops_wait.py` (в т.ч. после нескольких "идёт"-итераций). |
| 8 | OK | Истечение `deadline` проверяется ДО `time.sleep` каждой непоследней итерации, `sys.exit` с "статус CI неизвестен". `test_ac8_ceiling_expiry_refuses.py`, `WaitLoopCeilingTest` (юнит). |
| 9 | OK | Каждая итерация: `store.journal(..., "ожидание CI (цикл merge_gate)", detail)` + `print(...)`, `detail` несёт note и `"(ожидание N сек)"`. `test_ac9_progress_logged_each_iteration.py`. |
| 10 | OK | Мьютекс не удерживается во время `_wait_for_branch_ci_green` (см. требование 2) — `KeyboardInterrupt` из `time.sleep`/чтения статуса ничего не оставляет захваченным; lease снимается в `finally` `lease.run_locked` выше по стеку. `test_ac10_ctrl_c_leaves_state_and_frees_mutex.py`. |
| 11 | OK | Путь `"fresh"` не заходит в ветку `pull_outcome == "pulled"` — ни push, ни цикл ожидания не исполняются, `ci.branch_status` читается ровно один раз. `test_ac11_fresh_branch_unchanged.py` (регресс, «зелёный с рождения» по докстрингу файла). |
| 12 | OK | Diff ограничен `orchestrator/config.py`, `orchestrator/fsm.py`, тестами и `docs/codebase-map.md`; `orchestrator/ci.py`/`orchestrator/merge_lock.py` не изменены (только новые импортёры в карте). |

## Замечания

(нет)

## Вердикт

approved

## Проверено исполнением

- `python3 -m unittest discover -s tests -p "test_*.py"` — 1106 тестов, все зелёные (включая новый `tests/test_merge_gate_ci_wait.py`, 7 тестов, и неизменённые `tests/test_ci_status_kind_gate.py`, `tests/test_merge_lock.py`, `tests/test_invariants.py` — регресс по инварианту 19 и путям T053/T082 не пойман).
- `cd tasks/T087/acceptance_tests && python3 -m unittest test_ac1_push_before_wait_loop test_ac2_mutex_free_during_wait test_ac3_pause_continues_on_non_final_status test_ac4_ceiling_not_reset_by_repull test_ac5_green_completes_same_call test_ac6_repull_on_second_main_advance test_ac7_confirmed_red_stops_wait test_ac8_ceiling_expiry_refuses test_ac9_progress_logged_each_iteration test_ac10_ctrl_c_leaves_state_and_frees_mutex test_ac11_fresh_branch_unchanged` — 13 тестов (AC-1..AC-11, включая по два теста в AC-3/AC-7), все зелёные; каждый файл содержит докстринг с обоснованием «краснóты до реализации» — проверено чтением, не только фактом прохода.
- `python3 scripts/guard.py --all` — «GUARD: ок (295 файлов)».
- `python3 scripts/codebase_map.py` (регенерация) — diff свёлся только к строке `built_at_sha` (после чего откатан `git checkout -- docs/codebase-map.md`, чтобы не оставить след в рабочем дереве ревью), т.е. содержимое карты в коммите ветки актуально относительно текущего кода.
- Точечное чтение `orchestrator/merge_lock.py` (`run_window`/`acquire`/`release`) — подтверждено, что `_cmd_approve_merge_gate_cycle` воспроизводит ровно ту же последовательность (`acquire` → отказ `sys.exit` → `body()` в `try` → `release` в `finally`), которую раньше давал `run_window`, но per-итерацию, а не на весь вызов — сверялось для проверки замечания «не потерялась ли часть поведения `run_window` при переходе на прямой `acquire`/`release`» (замечание не подтвердилось, поведение эквивалентно).
- Точечное чтение `orchestrator/lease.py` (`run_locked`) и `orchestrator/config.py` (`LEASE_STALE_AFTER_SEC = 7200`) — сверялось для проверки риска: lease задачи держится `_cmd_approve` на весь потенциально часовой цикл (SPEC «Не входит» относит конкуренцию lease к прежнему поведению), а heartbeat lease не пампится во время ожидания CI — подтверждено, что порог протухания (7200 сек) больше потолка ожидания (3600 сек) с запасом, так что чужая сессия не сможет перехватить lease как «мёртвый» в пределах одного цикла approve; риска регрессии не нашёл.
- Точечное чтение `orchestrator/fsm.py:244-330` (`_pull_main_or_escalate`) — сверялось утверждение PLAN «требование 6 переиспользует прогон приёмочных тестов»: подтверждено, `acceptance.run(wt_path / ...)` вызывается при каждой подтяжке, включая повторную (AC-6).

## Предложения системе

(нет)
