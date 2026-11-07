# Записка ревьювера, итерация 1

## Выяснено
- Вердикт approved, реестр пуст. Требования 1–7 реализованы: `targets.py:404,436,442,782-788`, `gitcmd.py:585-599`.
- Планка 8 passed; связанные tests/ (commit_trailer, rewrite_flow, role_author, record_fields, targets_field, branch_template, gitcmd_carpentry, gitcmd_reads) — 136 passed. Карта свежая.
- Minor (не в реестре): регэксп пропускает ` `/`\x85`; git делит сообщение только по `\n`.

## Не сработало
- Bash-команды с `$(...)` и `ls` отклоняются песочницей — список файлов брал через `git ls-files`.

## Где остановился
- REVIEW.md записан, шаг завершён.

## Чего не хватило
- Нет флага `--check` у `scripts/codebase_map.py` — свежесть проверял вызовом `build_modules`/`render` в памяти.
