# Записка developer

## Выяснено
- Источник профиля везде — `project_profile.for_task(conn, id)` / `decide(target)`; у артели в песочницах профиль сеет `seed_artel_targets`.
- role_prompt: `_long_lived_paths` → (каталог, префикс) или None; абзацы 2а/5 test_author и фраза п.3 developer — помощники `_long_lived_*_note`, текст артели прежний.
- runner: `_missing_required_artifact(..., conn=None)` — `conn=None` = артель (его зовёт tests/test_test_author_long_lived_artifact.py тремя аргументами); при refusal — запись `LONG_LIVED_NOT_COUNTED_ACTION`.
- checkpoint: `_test_author_own_paths(..., profile)`, `_role_may_delete(..., profile)`, `_commit_worktree_change(..., own_zones=)` — свои отобранные файлы как зона; refusal — запись `TEST_AUTHOR_NOT_COMMITTED_ACTION` с причиной, worktree не тронут.

## Не сработало
- Запись во /tmp через heredoc и составные Bash-команды требуют подтверждения — правки только через Edit.

## Где остановился
- Готово: код, карта регенерирована, PLAN.md status: ready (guard ок). Долгоживущие файлы задачи 18/18, тесты затронутых модулей 175 зелёных, suite-run №1 зелёный (5617/0/2), plank-run 1 passed.
- `conn=None` в `role_prompt.mission_brief_package` зовёт `tests/test_01m3vfyp4rxby0bg8d3a0b18hd_role_missions.py` — поэтому `_long_lived_paths` трактует None как артель.

## Чего не хватило
- —
