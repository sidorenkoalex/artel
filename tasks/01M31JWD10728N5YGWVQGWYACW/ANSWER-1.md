---
task: 01M31JWD10728N5YGWVQGWYACW
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

Решение Оператора по эскалации автора тестов (AC-8 противоречит AC-1).

Признание: противоречие внесено ТЗ — в перечне «остаются зелёными»
назван `tests/test_artifact_escalation_marker.py`, не сверенный с тем,
что один его тест закрепляет сам исправляемый дефект.

Вопрос 1 — вариант A. AC-8 читается как «четыре файла зелёные по итогам
задачи». Тест `MarkerWrittenByTheEscalationPointsTest::
test_review_escalation_does_not_journal_the_marker`
(`tests/test_artifact_escalation_marker.py:341-356`) закрепляет прежнее
ошибочное решение SPEC 01M2XFSJ1Z7BS6HR69SAT1D81Y («случай review
невоспроизводим») и опровергнут фактами 20.09 и 21.09. Разработчик
ПЕРЕПИСЫВАЕТ его под новое ожидание: после эскалации ревьювера маркер
ЕСТЬ отдельной записью сразу после `state -> escalated`, detail равен
detail эскалации. Имя метода — ровно
`test_review_escalation_journals_the_marker` (на него опирается планка,
см. вопрос 2), докстринг — со ссылкой на эту задачу. Это усиление проверки, а не ослабление: тест продолжает
ловить мутацию «маркер вынесен в общий узел эскалации» через
отдельный существующий или новый тест на эскалацию по бюджету из
`review` (маркера НЕТ) — эта половина прежнего теста сохраняется.
Файл не защищён (`config.PROTECTED_PATHS` содержит из tests/ только
`tests/test_invariants.py`) и лежит в зоне `tests/`. Перечень
изменённых ожиданий — в PLAN.

Вопрос 2 — вариант B. AC-8 крыть тестом-прогоном четырёх модулей со
сверкой, что существующие тестовые методы не исчезли, по образцу
`tasks/01M2XFSJ1Z7BS6HR69SAT1D81Y/acceptance_tests/
test_ac7_existing_rework_gate_suite_stays_green.py`; имя
`test_review_escalation_does_not_journal_the_marker` исключить из
перечня «не исчезли» и вместо него требовать присутствия
переименованного метода.
