# Записка spec_auditor — 01M5MVSP9YW0DYA4YQ1KSG0AHF

## Выяснено
- sha SPEC = 536c0d71…; приложение 1 проходит `git apply --check` на d95b7d59; дерево tests/ даёт 61 находку = 61 запись `_EXCEPTIONS`.
- Все места кода из SPEC подтверждены (guard 3599/3982/4081/4112, refusal_classes 116–117, fsm_advance 598, amend 256/280/642/556); класс линта — 1999–2563, а не 2565.
- У артели правило планки по умолчанию (`project_profile.plank_rule`: 652–653), поэтому `_by_rule` ложно: в amend-tests файлы планки не проходят через `long_lived_errors_from_files` (amend.py:859, 957, 1207). Туда попадают только долгоживущие файлы (amend.py:642).
- В `--from-branch` функция `_code_head_long_lived` (amend.py:1170) возвращает голову, которая уже несёт правку. Если взять её базой `lint_base`, гасятся все методы.
- `acceptance_test_files` (guard.py:4124) отдаёт только `test_*.py`, а `_*.py` и `markers.py` в планке допустимы (guard.py:2721–2722). Помощники линт не проверяет.

## Не сработало
- Составные команды Bash с `cd`, `awk` и `head` требуют подтверждения — пользуйся абсолютными путями и одной командой на вызов.

## Где остановился
- SPEC-AUDIT.md сдан: verdict concerns, status ready.

## Чего не хватило
- Дольше всего искал, через какие функции amend-tests проверяет планку артели: путь по умолчанию — `_group_line_errors`, а не `long_lived_errors_from_files`.
