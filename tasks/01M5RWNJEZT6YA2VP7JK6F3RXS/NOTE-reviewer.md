## Выяснено
- Новый файл тестов + CmdRunReviewPackageTest: 38 passed; plank-run: 26 passed, код 0.
- fetch_all_from_origin: оба вызывающих берут repo из repo_for_target/клона — та же Path, что пишет _write; фильтр по repo работает.
- Временные мутации (commit_closing, `and not sent` в origin_sync_refusal, runner._spawn_and_wait) — все красные; код восстановлен.
- Карта: расхождение только built_at_sha.

## Не сработало
- Составная bash-команда с sed -i потребовала подтверждения — мутации делал через Edit.

## Где остановился
- REVIEW.md итерации 1 записан: approved, реестр пуст.

## Чего не хватило
- Ничего существенного.
