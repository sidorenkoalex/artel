# NOTE developer

## Выяснено
- Правка — только `orchestrator/projects.py`: третья ветка `_block_keys` (`["machine", "commit_author"]`) и хвост `BLOCK_PATHS`. Проверку формы делает `targets.merge_local` при пересборке слоя.
- `artel.py:200` пишет `<путь блока>` общим — не менялся (требование 5).
- Тесты: долгоживущий файл задачи + соседние target-set/help_registry — 127 passed; plank-run — 1 passed. Карта регенерирована.

## Не сработало
- Нет.

## Где остановился
- Шаг готов, PLAN status: ready.

## Чего не хватило
- Нет.
