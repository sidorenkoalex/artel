---
task: 01M3XTF1CEBXT4J7P0EKG5J342
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Эскалация разработчика через PLAN.md не зацикливается после ответа и approve

## Фаза A: план
- Таблица покрытия PLAN полна: требования 1–6 → шаги 1–4, проверки 2/3/5 явно
  отнесены к долгоживущему файлу задачи (AC-1..AC-4).
- Шаги размера MR (вызов + докстринги; один тест; карта; приложение) — не
  микрооперации и не «сделать всё».
- Подход совпадает с существующим механизмом (`_review_escalate` →
  `_mark_artifact_escalation`; чтение признака в `auto` уже есть, `in_dev`
  уже в `_REWORK_GATE_STATES`) — новой абстракции нет, общий узел
  (`store.set_state`, начало `fsm_advance.in_dev`) не тронут.
- «Влияние на систему» соответствует diff: изменены только
  `orchestrator/fsm_advance.py`, `tests/test_artifact_escalation_marker.py`,
  `docs/codebase-map.md` (+ долгоживущий файл test_author, залочен). Откат —
  revert merge-коммита, изменение аддитивное.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `orchestrator/fsm_advance.py` `_in_dev_plan_escalate`: `_mark_artifact_escalation(conn, task_id, detail)` сразу после `store.set_state(… "escalated" …, detail=detail)`, тот же `detail`. Других вызовов в путях `in_dev` нет; бюджетная эскалация признака не пишет (AC-2 зелёный). |
| 2 | OK | Сквозной AC-3 долгоживущего файла зелёный; без вызова признака — красный (мутация M1). |
| 3 | OK | Подавления «ANSWER новее» нет в diff; AC-4 зелёный, повторная эскалация после шага developer идёт штатно. |
| 4 | OK | Докстринг `_mark_artifact_escalation`: «Точек вызова пять», перечислены `spec_writing` ×2, `tests_writing`, `_review_escalate`, `_in_dev_plan_escalate`; фразы «Точек вызова три» нет (планка `test_ac5_marker_docstring.py` зелёная). |
| 5 | OK (с отклонением по месту) | Тесты а–г лежат в долгоживущем файле `tests/test_01m3xtf1cebxt4j7p0ekg5j342_plan_escalation_marker.py` (test_author, ADR-0020), а не в `tests/test_artifact_escalation_marker.py`, как буквально пишет SPEC. Это корректно: ADR-0020 п.4 запрещает разработчику повторять долгоживущее свойство; в файл зоны добавлен тест самого гейта рубежа `in_dev` (проверяет ещё и журнал отказа `REWORK_REFUSAL_ACTION` и открытие гейта после шага developer — этого AC-3 не проверяет, повтором не считаю). Заявки у всех тестов есть и исполнимы (см. мутации). |
| 6 | OK | Приложение в PLAN.md — unified-диф, пункт 4 раздела «Как эскалировать» по смыслу требования 6; `git apply --check` на текущем дереве — rc=0. |

## Замечания
Блокирующих и major замечаний нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider tests/test_artifact_escalation_marker.py tests/test_01m3xtf1cebxt4j7p0ekg5j342_plan_escalation_marker.py tasks/01M3XTF1CEBXT4J7P0EKG5J342/acceptance_tests` — 19 passed, 2 subtests passed (включая `test_ac5_marker_docstring.py`, `test_ac6_skill_appendix.py`).
- Временные мутации (код возвращён, `git status orchestrator` чист), прогон двух файлов `tests/` выше:
  - M1: убран вызов `_mark_artifact_escalation` из `_in_dev_plan_escalate` → красные AC-1 (оба subTest), AC-3, AC-4 долгоживущего файла.
  - M1b: признак записан ДО `store.set_state` → красный AC-1 (оба subTest) — заявка «пишет до перехода» исполнима.
  - M2: `in_dev` убран из `auto._REWORK_GATE_STATES` → красные AC-3, AC-4 и новый `test_marked_developer_escalation_holds_the_in_dev_pre_advance` (заявка разработчика подтверждена).
  - (Побочно: первая попытка M1 по неуникальной строке сняла вызов в `_review_escalate` — краснеет `MarkerWrittenByTheEscalationPointsTest::test_review_escalation_journals_the_marker`; существующий сторож работает.)
- `python3 scripts/codebase_map.py` → расхождение с закоммиченной картой только в строке `built_at_sha` (не дефект); рабочее дерево возвращено.
- Приложение PLAN.md извлечено и проверено `git apply --check -v -` → `Checking patch skills/escalation-rules.md...`, rc=0; `skills/escalation-rules.md` на ветке = main.
- Дифф `tests/`: в существующих тестах ни одна строка `assert` не изменена и не удалена — только добавлен метод и абзац модульного докстринга.

## Предложения системе
- Поддерживаю предложение PLAN: SPEC аналитика (требование 5) называет файл тестов для AC, которые по ADR-0020 уходят в долгоживущий файл test_author, — скилу analyst стоит не адресовать файл для таких AC, иначе разработчик и ревьювер каждый раз разбирают формальное расхождение.
