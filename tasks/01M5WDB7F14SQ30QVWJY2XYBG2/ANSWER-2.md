---
task: 01M5WDB7F14SQ30QVWJY2XYBG2
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: ответ Оператора

## Ответы

Расширение зон разрешено: orchestrator/store.py

мандат Оператора: orchestrator/store.py

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| `orchestrator/store.py` — новая функция чтения веток задач проекта (запрос из `catalog.py:670` переносится в хранилище) | SQL только в модуле хранилища — `tests/test_multitarget.py::SqlOnlyInStoreTest` | да: SQL уходит из `catalog.py` в `store.py`, сторож становится зелёным | `tests/test_multitarget.py::SqlOnlyInStoreTest` без правки; приёмочные тесты задачи на занятость имени ветки | остаётся |
