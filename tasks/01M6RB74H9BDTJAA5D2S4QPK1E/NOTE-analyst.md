## Выяснено
- Шаг 4 (второй возврат со spec_gate 07.11, решения 1–2): SPEC правлен, 6 AC, budget 45, guard ок, status: ready.
- AC-3: отказ записи вызывается GET /user с username "   " и годным commit_email. gitlab_adapter.py:584 проверяет только тип, targets.merge_local (:517) → _check_delivery (:715-720) отказывает. Причина — «сверка до записи не прошла».
- Номера projects.py на main сдвинуты на +5 от рабочей копии ветки (ветка ещё без мержа 01M6R8W7TSA6G85PVZZFDMRY25): на main одиночный лист 894-898, _target_set_block_mismatches 905-932, _backup_copy 991, _block_keys уже принимает machine.commit_author (:380, :664).
- Прежнее остаётся: требование 6 — тесты не правятся; GitLab определять через forge.ci_by_pipeline; отказ new — в catalog.cmd_new (epics.py:796).

## Не сработало
- В Bash отклоняется `$?` (simple_expansion), guard запускал без него.

## Где остановился
- Шаг завершён.

## Чего не хватило
- Рабочая копия отстаёт от main: номера строк сверял через `git show main:orchestrator/projects.py`.
