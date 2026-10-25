---
task: 01M5TBBDFS6DWQY6MS263T1KPY
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

Ослабление тестов разрешено: tests/test_multitarget.py

Основание: ночной мандат Оператора 25.10.2026 (дословно: «Даю на ночь: (1) мандат на правку существующих тестов в задачах эпиков и B без ослабления, с матрицей и независимой проверкой»). Объём — ровно одно утверждение `tests/test_multitarget.py::TargetInitTest::test_structure_is_created` (:288-289): ожидаемый список `["knowledge", "logs", "tasks", "worktrees"]` → `["epics", "knowledge", "logs", "tasks", "worktrees"]`; вид `assertEqual` на полный отсортированный список сохраняется; соседнее утверждение :286-287 и прочие методы не меняются.

Независимая проверка: подтверждено (отдельный агент без контекста сессии, 26.10.2026; прогон метода: с правкой и epics в PROJECT_DIRS — 1 passed, без epics — 1 failed).

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| tests/test_multitarget.py — `TargetInitTest::test_structure_is_created`, ожидаемый список `PROJECT_DIRS` | точный состав каталогов структуры проекта — tests/test_multitarget.py:288 | остаётся: `assertEqual` на полный список, пополнен ровно `epics` по требованию 1 | tests/test_multitarget.py:288 | ок при условии: только добавление `epics` в литерал, вид утверждения прежний |
| tests/test_multitarget.py — тот же метод, создание каталогов `target-init` | `target-init` заводит каждый каталог `PROJECT_DIRS` — tests/test_multitarget.py:286 | остаётся, теперь включая `epics` | tests/test_multitarget.py:286 | ок: не меняется |
