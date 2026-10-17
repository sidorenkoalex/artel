# Записка spec_auditor

## Выяснено
- Аудит SPEC a15b6b6d: вердикт concerns, одно отклонение — нет AC на сочетание триггеров (внешний держатель/внешняя задача + задача артели в in_dev); досрочный `return None` проходит все AC.
- Факты SPEC верны: notes.py:266-282, config.py:509, schema.py:115 (target nullable), repo_context.is_artel 172-173, resolve 82-96, store.task_target 701-707, all_tasks ORDER BY id (696-698).
- Все стенды окна в tests/ — DEFAULT_TARGET; T-LOCK тест (test_notes.py:326-334) только assertIsNotNone — «Меняемое поведение» не нужно.
- store.get_task делает sys.exit на отсутствующей строке (store.py:1010-1015) — ловушка для строки держателя.

## Не сработало
- Bash с `cd ... ;`/переменными требует подтверждения — только абсолютные пути.

## Где остановился
- SPEC-AUDIT.md сдан, guard прогнан.

## Чего не хватило
- Нет.
