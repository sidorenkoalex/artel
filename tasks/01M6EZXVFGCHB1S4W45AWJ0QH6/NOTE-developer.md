# Записка developer — 01M6EZXVFGCHB1S4W45AWJ0QH6

## Выяснено
- Итерация 4 (REVIEW iter 3: R3-F1 major, R3-F2 minor):
  - `gitcmd.write_push_policy_file(path, data)`: mkstemp в том же каталоге + `os.replace` — символическая ссылка
    на месте `artel-push-policy` заменяется, цель не трогается. Используют `_push_policy_refusal` и
    `workspace.write_push_policy` (ensure_clone, doctor --fix).
  - doctor `clone-push-hook`: `path.is_symlink()` → finding «символическая ссылка на <цель>» (fail); --fix пишет
    тем же помощником → обычный файл.
  - R3-F2: пробел в `deleting = "--delete"`.
- Следствие: файл mode 0 теперь заменяется (rename требует только права на каталог), поэтому свой тест итерации 3
  `test_unusable_policy_refuses_before_git[unreadable]` переделан в `[unwritable-dir]` (каталог .git 0o555).
- 3 новых теста `*symlink*` в tests/test_push_hook_stand.py; мутации красные. 332 passed затронутых модулей, plank 68.
- Реестр REVIEW: R3-F1, R3-F2 размечены `fixed`.

## Не сработало
- Многострочный Bash (cp + heredoc python) требует подтверждения — мутации Edit'ом.

## Где остановился
- Шаг завершён, PLAN.md status: ready (шаг 9), карта перегенерирована.

## Чего не хватило
- Ничего существенного.
