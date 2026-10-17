# Записка spec_auditor

## Выяснено
- Аудит SPEC sha 05cad0f2: пять пунктов решения Оператора №1 перенесены; номера строк ci.py/ci_rerun.py/fsm_merge_gate.py/acceptance.py/github_adapter.py верны (ci.py:73 → фактически :72).
- Подмены вне перечня требования 2: tests/test_ci_rerun_command.py:238 (trigger_rerun `trigger(branch)`), :242 (failed_check_names `failed_names(sha)`), tests/test_ci_stuck_check_run.py:220 (check_run_workflow_run `lambda cid:`), tests/test_main_ci_fetched_repo.py:64 (check_runs `lambda sha:` под main_line_status(repo=config.ROOT)).
- `_repo_kwargs(config.ROOT)` → {"repo": ROOT}: is_artel(Path) сравнивает с clone_path артели (repo_context.py:170-171); pin.py:86 и doctor/main_ci.py:33 — артель, но не «клон артели».

## Не сработало
- grep с `--include=*.py` и сложные пайпы в Bash режет песочница — простые grep по абсолютному пути проходят.

## Где остановился
- SPEC-AUDIT.md написан, verdict concerns (Ф-1 неполный перечень подмен/функций, Ф-2 признак артели для config.ROOT, О-3 нет сценария main_line_status в AC-2); guard ок.

## Чего не хватило
- Нет помощника «путь клона → запись targets.yaml» в ci.py; SPEC механизм различения не задаёт.
