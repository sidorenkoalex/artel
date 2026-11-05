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

## Шаги
1. Правка `orchestrator/canary.py` (вызов + докстринг), регенерация
   `docs/codebase-map.md` (`python3 scripts/codebase_map.py`).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 (условие `escalated_from == "spec_writing"` и `is not None`) |
| 3 | 1 (остальной код функции не тронут; докстринг дополнен) |

Проверка: `artel.py plank-run 01M6PFGA0GR4ZMGT3H7PKS7SN5` — 7 passed (AC-1…AC-4);
`tests/test_canary_synthetic_answer.py`, `tests/test_01m4r4jkc28j80z82tza62rf2j_answered_batch.py`
— 26 passed; `tests/test_canary.py`, `tests/test_canary_budget_ceiling.py` — 114 passed.
Мутации («по истинности», «безусловно», «только escalated_from», «только
baseline», «после set_state») планкой ловятся — проверено test_author
(NOTE-test_author.md). Отдельный тест в `tests/` не добавлен: поведение целиком
покрыто планкой, а шов — закрытое имя, которое долгоживущему файлу запрещено.

## Влияние на систему
Затронута только канареечная ветка возврата из `escalated`; `fsm.py`,
`fsm_advance.py`, `answer.py` не меняются. Признак пишется тем же узлом, что
у approve, — журнал канарейки получает ту же строку, что живая задача.
Гейты, лимиты, тесты не ослабляются. Откат — revert одного merge-коммита.

## Риски
`_mark_questions_answered` — закрытое имя `fsm`; при его переименовании
канарейка сломается — но это ловит планка/тесты признака.

## Предложения системе
- `canary._pass_escalated_with_synthetic_answer` дублирует часть ветки
  `escalated` из `fsm._cmd_approve`; каждое новое побочное действие approve
  нужно переносить сюда руками (этот дефект — второй такой случай после
  R1-F3). Вынести общий узел «эффект возврата из эскалации» в `fsm`.
