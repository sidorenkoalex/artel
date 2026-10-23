# Записка spec_auditor — 01M5MVSP9YW0DYA4YQ1KSG0AHF

## Выяснено
- Круг 2: проверен SPEC с sha 1cb5eb3e… на d95b7d59. Все пять решений Оператора с гейта №1 в SPEC перенесены.
- Новые места подтверждены: `_group_line_errors` (amend.py:172), его вызовы 859/957/1207, from-branch — 1109/1170.
- Ключи `_branch_tests_snapshot` — `tasks/<id>/acceptance_tests/…` (amend.py:1060). Метки `acceptance_test_files` — `acceptance_tests/…` (guard.py:4128). Для базы планки их нужно привести к одной форме.
- AC-6 не проверяет базу для планки: нет случая «правка другого метода — отказа нет».
- На `--from-branch` долгоживущие файлы проверяются только при `long_diverged` (amend.py:1228). Без базы этот путь отказывает за старый метод, который пропустил worktree-путь. Это тупик восстановления (amend.py:1002–1005).

## Не сработало
- Составные Bash-команды (`;` с shasum, `ls`) требуют подтверждения. Для sha пользуйся `git hash-object`.

## Где остановился
- SPEC-AUDIT.md сдан: verdict concerns, status ready, guard ок.

## Чего не хватило
- Пришлось искать, откуда берётся база планки и в какой форме у неё ключи: `_branch_tests_snapshot`, amend.py:1048.
