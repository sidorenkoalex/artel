# Записка developer — 01M5WDB7F14SQ30QVWJY2XYBG2

## Выяснено
- Возврат из merge_gate (3 обхода) закрыт в `orchestrator/gitcmd.py` (шаг 7 PLAN):
  - `_alias_in_argv`: `-c alias.*`/`--config-env alias.*` — отказ всегда (любой проект);
    подкоманда не из встроенных под белым списком/неизвестным гейтом — отказ при глобальной опции кроме `-C`.
  - `_location_projects`: проект по `--git-dir`/`GIT_DIR`, `--work-tree`/`GIT_WORK_TREE`, `GIT_COMMON_DIR`; разные проекты — отказ.
    Под белым списком `GIT_DIR`/`GIT_WORK_TREE`/`GIT_COMMON_DIR` в окружении — отказ.
  - `_explicit_source`: источник — HEAD, полный sha или ветка клона; refspec переписывается в `<src>:refs/heads/<имя>`.
- `store.project_branch_tasks` — COALESCE(target, 'artel').
- Тесты: `tests/test_gitcmd_push_point.py` (+5 тестов, 21 всего), `tests/test_store_project_branch_tasks.py`; мутации проверены.
- Прогоны: задача+А0+multitarget 133 passed; соседние 177 passed; планка 75 passed. Карта регенерирована.

## Не сработало
- heredoc в Bash роли запрещён — правки только через Edit.

## Где остановился
- Шаг завершён: PLAN.md status: ready.

## Чего не хватило
- Ничего существенного.
