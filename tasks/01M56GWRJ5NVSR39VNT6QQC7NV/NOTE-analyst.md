## Выяснено
- Возврат из spec_gate (О-1..О-3) закрыт: SPEC переписан, 8 AC, $25, guard ок.
- О-1: `commit_success_checkpoint` (checkpoint.py:828-911, вызов `_commit_worktree_change` :895) — требование 1, AC-1 проверяет и аварийный WIP, и штатный путь.
- О-2: `pult_commit_failed_paths` (:1669-1707, `_zone_paths` на :1694) — требование 2, AC-4.
- О-3: `restore_out_of_bounds_deletions` (:532-590; для developer зоны `_zone_paths` :555, `_role_may_delete` :514) — требование 3, AC-5. Пункт «Не входит» про восстановление удалений снят.
- `_commit_worktree_change` уже принимает `own_zones` (добавлено для test_author 01M551W0TF); гейт зон берёт профиль `project_profile.decide(target)` только при `not repo_context.is_artel(ctx)`.

## Не сработало
- `ls` в Bash недоступен (command not found) — каталог читается через Read.

## Где остановился
- SPEC status: ready.

## Чего не хватило
- Перечня мест `checkpoint.py`, считающих зоны developer, — нашёлся grep по `_zone_paths`/`_commit_worktree_change(`.
