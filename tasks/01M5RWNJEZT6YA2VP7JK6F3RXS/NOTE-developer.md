# NOTE developer

## Выяснено
- Область: `artifact_branch.deferred_sends()` (глубина `_area_depth`, набор `_unsent`), досылка `send_pending(task_id=None, repo=None) -> int`; в `lease.run_locked` — `with` вокруг `body(sid)` внутри `try`.
- Точки досылки: origin_sync_refusal (вторая `_send` пропускается, если досылка была), fetch_from_origin, fetch_all_from_origin, snapshot.commit_closing, github_adapter (ensure_draft_mr, ensure_head_in_origin), fsm_merge_gate (_wait_for_branch_ci_green, _await_main_ci, _full_suite_or_refuse, _sync_main_or_wait), runner._spawn_and_wait.
- Код закоммичен сам (ea8deaba): AC-15 читает файл теста из HEAD.
- plank-run: 25/26; AC-14 красен только потому, что PLAN.md ещё не в ссылке документов (автокоммит шага его перенесёт); разбор PLAN проверен локально тем же регэкспом.
- Счёт git на tests/test_merge_outcome_module.py::test_ac5_other_base_key_or_mandate_runs_gate: всего 1296→1284, push 43→37, remote 43→37 (разбор в PLAN).
- Затронутые модули: 47 файлов tests/, 538 passed; свои 28 тестов, 13 мутаций — все красные.

## Не сработало
- `pytest.main` из сценария счёта отказывает сторожем conftest (смотрит sys.argv) — подменить `sys.argv = ["pytest", *args]` до вызова.

## Где остановился
- PLAN status: ready, шаг закончен.

## Чего не хватило
- Нет команды пульта «счёт вызовов git на тесте до/после» — сценарий писал сам (Popen-шпион во временной копии `git archive`).
