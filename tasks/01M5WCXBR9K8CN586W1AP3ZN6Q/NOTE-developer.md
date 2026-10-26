# Записка developer — 01M5WCXBR9K8CN586W1AP3ZN6Q

## Выяснено
- Выбор реализации без литералов: `doctor.forge.IMPLEMENTATIONS.get(entry["forge"])`
  + `hasattr(impl, "project_info"/"token_expiry")` (у `_GitHub` их нет → путь gh / строки нет).
- Строка срока токена: `misc_checks.check_token_expiry` → `token-expiry-<проект>`, в `cli.all_checks` за base-branch.
- `forge-probe` — `_cmd_forge_probe` в artel.py (новый модуль вне зон), вне белого списка ролей, строка в блоке «Команды:».
- Песочница: снимок `_GITLAB_TRANSPORT` при импорте; подмена только если транспорт ещё исходный.
- Долгоживущие 35/35 зелёные.

## Не сработало
- `ls` в Bash недоступен — `find`.

## Где остановился
- Шаг завершён: код в worktree (незакоммичен — коммитит пульт), карта
  регенерирована, тесты затронутых модулей зелёные, guard ок, PLAN ready.

## Чего не хватило
- —
