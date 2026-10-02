---
task: 01M3YCHP14179R32SFJVKQB32G
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: ответ Оператора

## Ответы

1. CI ветки красный на инварианте «SQL только в store.py»: `tests/test_multitarget.py::SqlOnlyInStoreTest::test_no_sql_outside_store` — запрос `conn.execute("SELECT …")` в `orchestrator/models.py:1154`. Перенести чтение `canary_runs` в функцию `orchestrator/store.py` (рядом с прочими функциями этой таблицы) и вызывать её из `models.py`. Тест `test_no_sql_outside_store` не менять и не ослаблять. Расширение зон — только `orchestrator/store.py`, только под эту функцию (без миграций схемы и правок других таблиц). Перед сдачей прогнать полный набор `tests/`.

Расширение зон разрешено: orchestrator/store.py
