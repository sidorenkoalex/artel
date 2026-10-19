# Записка developer (G1а-2)

## Выяснено
- `full_suite_limit` бросает обычный `TargetsError` и на `multi` — признак
  `multi` берётся из `repo_context.profile_of` в `doctor/cli.py`.
- Ключ рабочего дерева зовёт только `full_suite` — туда передаётся
  `root=`; в `full_suite` дерево всегда настоящий git tree (файлы БД в
  дереве — ранний выход), поэтому `git ls-tree <tree>` годен.
- Фасад `orchestrator/doctor/__init__.py` вне зон — новая проверка зовётся
  `doctor.project_checks.component_checks` (атрибут подмодуля пакета).
- `-n 4 -p xdist` на ручном прогоне файлов tests/ роняет воркеры — гонять
  последовательно.

## Не сработало
- `sed -i` в Bash требует подтверждения — мутации делать через Edit.

## Где остановился
- Реализация готова, PLAN.md `ready`; долгоживущий файл 12/12, планка 4/4,
  затронутые модули 252 passed; suite-run №1 запущен.

## Чего не хватило
- Нет.
