---
task: 01M48FRD9RJDBBVT2SN0FY5G2A
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

Решение Оператора 06.10 по эскалации разработчика.

Вопрос 1 — вариант (а).

Ослабление тестов разрешено: tests/test_01m45fk56dwmnbrka1vwm12h19_draft_mr.py::DraftMrHighlightTest::test_ac6_highlight_lists_no_paths_and_omits_artel_only_paths

Условия мандата (их сверит Оператор по диффу после шага):

1. Правка метода и модуля — ровно дифф раздела PLAN «Предлагаемая правка метода AC-6» (импорт `re`, константа `HIGHLIGHT_PATHS`, помощник `highlighted`, тело и докстринг метода). Иных изменений в этом файле нет; строка «Ловит мутацию» не меняется.
2. Сверено Оператором на копии ветки с наложенным диффом: исправный код — `1 passed, 36 subtests passed` в трёх прогонах подряд; мутация «подсветка сверяет дифф с config.PROTECTED_PATHS для любого проекта» — `1 failed`.
3. Вариант (б) (отдельный черновик на каждую запись) не нужен.
