# Записка developer (итерация 2 — замечания ревью 1)

## Выяснено
- R1-F1: `_added_lines` — в argv `--no-textconv --no-relative --src-prefix=a/ --dst-prefix=b/`; заголовок `+++ ` не `/dev/null` и не `b/…` — `_Prepare`. Тесты в tests/test_outcome_integrity_added_lines.py (noprefix через GIT_CONFIG_COUNT, неожиданный заголовок, удаление файла).
- R1-F2: `_code_exception_findings` решает вид файла по пути головы; исключение «новый путь под weakening_scope с записями головы» у компонента без `tests` распространено с `A` на `R`/`C` (иначе ложная находка на переименованный тест). Тесты там же (CodeExceptionRenameTest).
- R1-F3: tests/test_fsm_autogate_plank_rule.py — `_plank_rule_refusal` с настоящим `_bounds`, подменён только `project_profile.decide`.
- Все новые тесты проверены мутациями (скрипт в worktree, сам себя удаляет) — красные.

## Не сработало
- heredoc с `{…"…}` в Bash отклоняется («expansion obfuscation»), запись в /tmp требует подтверждения — файлы через Write в worktree.
- `pytest -n` — «node down», гонять с `-p no:xdist`.

## Где остановился
- Итерация 2 сдана: затронутые файлы (156 passed), plank-run 4 passed, карта регенерирована, реестр REVIEW размечен fixed, PLAN ready, guard ок. Код не закоммичен (коммитит пульт).

## Чего не хватило
- —
