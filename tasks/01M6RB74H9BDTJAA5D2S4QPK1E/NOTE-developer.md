# Записка developer

## Выяснено
- Реализация: forge.TokenUser(name, commit_email); gitlab_adapter.token_user; projects.set_commit_author + _local_layer_for (вынос рубежей _target_set_load); doctor/project_checks.py: commit_author_applies/check_commit_author/commit_author_checks/fix_commit_authors; doctor/cli.py — строка после project_entry_checks, автопоиск в блоке --fix до all_checks; catalog._commit_author_gate после unsupported_reason (ленивый импорт doctor.project_checks — doctor тянет catalog).
- doctor/__init__.py вне зон — новые функции зовутся как doctor.project_checks.<имя>, doctor.projects.<имя>.
- Долгоживущие 29/29 зелёные; связанные файлы tests — зелёные (541 + 196); свои tests/test_commit_author_units.py — 4, мутации проверены.

## Не сработало
- ls/cat/grep после cd в Bash отклоняются — git grep / git -C / Read.

## Где остановился
- PLAN.md status: ready, карта регенерирована. Полный набор — за CI.

## Чего не хватило
- Формат записи локального слоя для своего теста (long_lived_dir, weakening_scope и др. обязательны) — взял из долгоживущего файла задачи.
