# Записка developer

## Выяснено
- Итерация 2 (R1-F1): код задачи не менялся. Добавлен `tests/test_ci_callers_project_repo.py` (5 тестов, 12 подтестов): запись flake-rate при незапущенном повторе / запущенном; repo=<клон> у trigger_rerun гейта мержа; у _red_rerun (failed_check_names ×2, fsm._origin_main_sha, trigger_rerun) и _stuck_rerun (check_run_workflow_run, trigger_rerun run_id); у артели — без repo.
- Подмены: workspace.task_repo → repo_context.clone_path(<имя>), store.journal → список; признак артели — настоящий через ci._repo_kwargs.
- 8 мутаций (те, что делал ревьювер, плюс по каждому вызову) — каждая красит файл; код восстановлен, git status orchestrator/ чистый.
- 7 файлов модулей — 141 passed; планка 4/4; карта регенерирована; guard на PLAN/REVIEW — ок. R1-F1 в реестре размечен fixed.

## Не сработало
- pytest -n — воркеры падают; гонять -p no:xdist.
- ls/cat/rm в Bash нет; цепочки с `;` требуют подтверждения.

## Где остановился
- Всё сделано, PLAN status: ready. Новый файл тестов и карта не закоммичены — закоммитит пульт. Полный suite-run в этой итерации не запускался (добавлен только изолированный тестовый файл).

## Чего не хватило
- Ничего существенного.
