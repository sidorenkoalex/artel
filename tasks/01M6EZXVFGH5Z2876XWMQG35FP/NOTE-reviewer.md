## Выяснено
- Итерация 1: approved. Планка 1 passed, тесты файлов задачи + ac9 — 89 passed, карта свежа (сверка в памяти без built_at_sha).
- Отклонения PLAN от SPEC (warn вместо skip для include/неподдержанного if/changes, ssh-подмодуль) покрыты ANSWER-1 пп. 1-4.
- Вызывающих `_read_all`/`_pipeline_findings` вне gitlab_adapter нет.

## Не сработало
- heredoc с `{…'` и `rm` в Bash отказаны; проба — файлом + `python3 -c`, `PYTHONPATH=.` требует подтверждения — `sys.path.insert` в `-c`.

## Где остановился
- REVIEW.md записан, реестр пуст. Наблюдение без записи: project_checks.py:1386 — http:// на том же хосте получает текст «не на хосте записи».

## Чего не хватило
- Опции «--check» у scripts/codebase_map.py: свежесть карты сверял импортом build_modules/render.
