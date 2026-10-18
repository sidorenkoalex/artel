# Записка test_author

## Выяснено
- Планка сдана: AC-1..7, AC-9 — долгоживущий tests/test_01m56gwrj5nvsr39vnt6qqc7nv_developer_checkpoint.py (не закоммичен, коммитит пульт); AC-8 — разовый acceptance_tests/test_ac8_common_zones_unchanged.py (ast COMMON_ZONES на DIFF_BASE и HEAD).
- Песочница по образцу tests/test_01m551w0tfct2xrq71xfxjdkb9_profile_checkpoint.py (RealGitSandbox + make_project_repo + workspace.ensure), задача в in_dev.
- WIP-путь — commit_abnormal_checkpoint(conn, id, "developer", "rc=1"); штатный — commit_success_checkpoint; подтяжка — commit_pull_checkpoint(conn, id, wt).
- AC-4: запись PULT_COMMIT_GIT_FAILED_ACTION кладётся store.journal напрямую.
- AC-6 refusal: испорченный test_profile пишется в targets.yaml ПОСЛЕ workspace.ensure.
- До реализации красны AC-1, AC-2, AC-3 (коммит при подтяжке), AC-4, AC-5, AC-9 (все три); зелены с рождения AC-3 (отказ подтяжки), AC-6, AC-7, AC-8.
- Стаб (удалён): `--no-renames` в _stray_staged_paths; is_long_lived по профилю вычитается из stray в _commit_worktree_change и из outside в pult_commit_failed_paths; _role_may_delete developer + profile в restore. Под ним зелёные мой файл, 01m551w0…_profile_checkpoint, test_timeout_checkpoint, test_checkpoint_zone_filter (69 passed).
- plank-run: 1 passed; preflight: все проверки пройдены.

## Не сработало
- В шелле нет `ls`; цепочки с `;`/`for`/лишними grep требуют подтверждения — одна команда с одним пайпом.

## Где остановился
- Шаг завершён.

## Чего не хватило
- —
