# Записка analyst

## Выяснено
- ТЗ подробное, с адресами строк. Адреса сверены на ветке задачи:
  - `cleanup.py`: `_delete_origin_branch` :260, `cleanup_project_remote` :279,
    `_merged_remote_outcome` :329, `cleanup_merged_remote` :356, `_bounded` :253
    (`http.lowSpeedTime=GH_TIMEOUT_SEC`);
  - `prune.py`: `_suite_run_candidates`, `_abolished_candidates`, `_unsaved_work_reason`,
    `_print_report` :240, `_remove_dirs` :270, `cmd_prune` :285;
  - `docs/retention.md`: разделы «Ветки `task/*` пульта» :68 и «Worktree задачи» :108 на
    месте.
- SPEC написан: 9 AC (меньше порога деления 10), 4 зоны, бюджет $25 по ТЗ.

## Не сработало
- `grep` после `cd` в составной команде требует подтверждения — нужны абсолютные пути
  одной командой.

## Где остановился
- SPEC.md готов, status: ready, guard ок.
- Guard поднимал сигнал «файлы зоны»: маска `tests/` считается многими файлами. Добавлена
  секция «Оценка объёма и деление» с материалом за монолит и строкой «Прогноз диффа:
  40 КиБ». Решение о монолите — за Оператором на гейте SPEC.

## Чего не хватило
- Ничего существенного.
