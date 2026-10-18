## Выяснено
- ТЗ достаточно, SPEC.md написан (6 AC, $25).
- Чекпоинт подтяжки `commit_pull_checkpoint` идёт тем же узлом `_commit_worktree_change` (refuse_on_stray=True) — расширение на него распространяется (требование 1 ТЗ).
- У `_commit_worktree_change` уже есть параметр `own_zones` (добавлен для test_author, 01M551W0TF); гейт зон берёт профиль `project_profile.decide(target)` и только при `not repo_context.is_artel(ctx)`.

## Не сработало
- —

## Где остановился
- SPEC status: ready, guard прогнан.

## Чего не хватило
- —
