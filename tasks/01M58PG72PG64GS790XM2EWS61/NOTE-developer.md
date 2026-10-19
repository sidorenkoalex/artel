# Записка developer (G1а-2)

## Выяснено
- `full_suite_limit` бросает обычный `TargetsError` и на `multi` — признак
  `multi` берётся из `repo_context.profile_of` в `doctor/cli.py`.
- Ключ рабочего дерева зовёт только `full_suite` — туда передаётся
  `root=`; в `full_suite` дерево всегда настоящий git tree.
- Фасад `orchestrator/doctor/__init__.py` вне зон — новая проверка зовётся
  `doctor.project_checks.component_checks`.
- Итерация 2: R1-F1/R1-F2 закрыты сторожами в `tests/test_component_checks.py`
  (`ToolsKeyTest`, `DecideToolsTest`, `test_unclosed_class_at_zero_depth_is_unparseable`);
  `decide` на учебной записи работает с одним лишь подменённым `config.TARGETS`.
- Мутации удобно гонять python-скриптом «заменить → pytest → вернуть» в одном вызове.

## Не сработало
- `sed -i` и `cd <каталог документов> && python3 …` требуют подтверждения —
  правки документов через Edit.

## Где остановился
- Итерация 2 готова: свой файл 10 passed, три файла 33 passed, планка 4 passed,
  реестр REVIEW размечен `fixed`, PLAN `ready`, suite-run №2 зелёный (5923 passed).

## Чего не хватило
- Нет.
