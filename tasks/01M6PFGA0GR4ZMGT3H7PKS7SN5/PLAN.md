---
task: 01M6PFGA0GR4ZMGT3H7PKS7SN5
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Канарейка: синтетический ответ на батч вопросов аналитика ставит признак «батч отвечен»

## Подход
В `canary._pass_escalated_with_synthetic_answer` (`orchestrator/canary.py`)
между чтением строки задачи (`store.get_task`, после `answer.cmd_answer`) и
сбросом `escalated_from`/`answer_baseline` добавлен вызов
`fsm._mark_questions_answered(conn, task_id)` при условии
`t["escalated_from"] == "spec_writing" and t["answer_baseline"] is not None` —
дословно условие `fsm._cmd_approve` (`orchestrator/fsm.py:1870`). Вызов идёт
до `store.set_state`, поэтому строка признака в журнале раньше записи о смене
состояния. Используется тот же узел, что у approve, без дублирования логики
хэша/номера ANSWER. Докстринг функции дополнен абзацем о признаке батча.

Итерация 2 (REVIEW R1-F1): планка задачи — `Группа: разовый`, после мержа не
гоняется, поэтому свойство закрыто сторожем разработчика в новом файле
`tests/test_canary_synthetic_answer_batch_mark.py` (`LightTransitionSandbox`,
подменённый канал `canary.answer.cmd_answer`, как в
`tests/test_canary_synthetic_answer.py`, который по SPEC не трогается).

## Шаги
1. Правка `orchestrator/canary.py` (вызов + докстринг), регенерация
   `docs/codebase-map.md` (`python3 scripts/codebase_map.py`).
2. Сторож `tests/test_canary_synthetic_answer_batch_mark.py`:
   - `test_first_escalation_of_batch_marks_it_before_state_change` —
     `spec_writing` + `answer_baseline = 0`: ровно одна строка
     `fsm.QUESTIONS_ANSWERED_ACTION` с `sha256=<хэш QUESTIONS.md>; ANSWER-1`,
     раньше `state -> spec_writing`, задача в `spec_writing`;
   - `test_no_mark_when_half_of_approve_condition_fails` — подтесты
     `in_dev`/`0` и `spec_writing`/`None`: строки нет, возврат в прежнее
     состояние. Карта регенерирована.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 2 |
| 2 | 1 (условие `escalated_from == "spec_writing"` и `is not None`), 2 |
| 3 | 1 (остальной код функции не тронут; докстринг дополнен) |

Проверка: `artel.py plank-run 01M6PFGA0GR4ZMGT3H7PKS7SN5` — 7 passed (AC-1…AC-4);
`python3 -m pytest tests/test_canary_synthetic_answer_batch_mark.py
tests/test_canary_synthetic_answer.py
tests/test_01m4r4jkc28j80z82tza62rf2j_answered_batch.py` — 28 passed, 34
subtests passed. Временные мутации `orchestrator/canary.py` (Edit, откат
`git checkout -- orchestrator/canary.py`), каждая краснит новый файл:
«baseline по истинности», «вызов удалён», «вызов после `set_state`» —
`test_first_escalation_…`; «только `escalated_from`» — подтест
`spec_writing/None`; «только `answer_baseline`» — подтест `in_dev/0`;
«безусловный вызов» — оба подтеста.

## Влияние на систему
Затронута только канареечная ветка возврата из `escalated`; `fsm.py`,
`fsm_advance.py`, `answer.py`, `tests/test_canary_synthetic_answer.py` не
меняются. Признак пишется тем же узлом, что у approve, — журнал канарейки
получает ту же строку, что живая задача. Новый тест только добавлен; гейты,
лимиты, существующие тесты не ослабляются. Откат — revert одного
merge-коммита.

## Риски
`_mark_questions_answered` — закрытое имя `fsm`; его переименование или
выпадение вызова из канарейки после мержа ловит сторож
`tests/test_canary_synthetic_answer_batch_mark.py` (планка разовая и после
мержа не гоняется).

## Предложения системе
- `canary._pass_escalated_with_synthetic_answer` дублирует часть ветки
  `escalated` из `fsm._cmd_approve`; каждое новое побочное действие approve
  нужно переносить сюда руками (этот дефект — второй такой случай после
  R1-F3). Вынести общий узел «эффект возврата из эскалации» в `fsm`.
- Итерация 1 прочла запрет закрытых имён в долгоживущем файле планки как
  запрет на тест разработчика в `tests/`: skills/test-authoring.md эти два
  случая явно не разводит.
