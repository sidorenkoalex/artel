---
task: 01M5QR7KGYZNVWDP5H86S9PY04
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

Ослабление тестов разрешено: tests/test_review_package.py::CmdRunReviewPackageTest::test_developer_step_has_no_package

Основание: решение Оператора 25.10.2026 (ответ «ок по рекомендациям» на вопрос о мандате на `tests/test_review_package.py`) — в `test_developer_step_has_no_package` убрать из ожидаемого списка вызовов git ровно элемент `["-C", clone, "remote"]` (вторую проверку remote перед отправкой, которую убирает требование 1 ТЗ); остальные элементы списка, порядок и строгое сравнение `assertEqual` не меняются. Ограничение зон «в `tests/` — только новые файлы» снимается для этой одной строки ожидаемого списка `tests/test_review_package.py`. Иные правки существующих тестов не разрешены.

Независимая проверка: сессия при Операторе сверяет дифф `tests/test_review_package.py` (ровно одна удалённая строка ожидаемого списка) и зелень CI ветки до approve на merge_gate.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит | Остаётся ли свойство после изменения | Чем покрыто после | Решение |
|---|---|---|---|---|
| tests/test_review_package.py::CmdRunReviewPackageTest::test_developer_step_has_no_package — элемент `["-C", clone, "remote"]` ожидаемого списка | точная последовательность вызовов git шага разработчика без пакета ревью | остаётся | `tests/test_review_package.py::CmdRunReviewPackageTest::test_developer_step_has_no_package` — то же строгое сравнение с новым списком; новый тест задачи на ровно один вызов `git remote …` перед `push` | ок при условии: удалён ровно один элемент, сравнение строгое |
