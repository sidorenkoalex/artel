# Записка developer (G1а-2)

## Выяснено
- `full_suite_limit` бросает обычный `TargetsError` и на `multi` — признак
  `multi` берётся из `repo_context.profile_of` в `doctor/cli.py`.
- Ключ рабочего дерева зовёт только `full_suite` — туда передаётся `root=`.
- Фасад `orchestrator/doctor/__init__.py` вне зон — новая проверка зовётся
  `doctor.project_checks.component_checks`.
- Итерация 3: R2-F1 закрыт `TaskOwnProfileToolsTest` в `tests/test_component_checks.py`:
  `_task_own_profile` гоняется с учебным `config.TARGETS`, sqlite `:memory:` и
  подменённым `store.task_target`; у артели (`pult-pytest`) он даёт `None`, поэтому
  случай «пустые tools» — учебная запись `test_profile` с `runner: pytest-own`.

## Не сработало
- `sed -i` и `cd <каталог документов>` требуют подтверждения — правки через Edit.

## Где остановился
- Итерация 3: свой файл 11 passed, три файла 34 passed, планка 4 passed, мутация
  проверена, реестр R2-F1 `fixed`, PLAN `ready`; suite-run №3 запущен.

## Чего не хватило
- Нет.
