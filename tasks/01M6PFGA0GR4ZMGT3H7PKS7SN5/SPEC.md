---
task: 01M6PFGA0GR4ZMGT3H7PKS7SN5
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/canary.py, docs/codebase-map.md, tests/
budget_usd: 25
---

# SPEC: Канарейка: синтетический ответ на батч вопросов аналитика ставит признак «батч отвечен»

## Контекст
На `approve` из эскалации, пришедшей из `spec_writing`, пульт пишет в
журнал строку `fsm.QUESTIONS_ANSWERED_ACTION` («батч вопросов отвечен»,
detail `sha256=<хэш QUESTIONS.md>; ANSWER-<n>`) функцией
`fsm._mark_questions_answered` (`orchestrator/fsm.py:613-626`, вызов —
`orchestrator/fsm.py:1870-1871`, условие `t["escalated_from"] ==
"spec_writing" and baseline is not None`, `baseline =
t["answer_baseline"]` — `orchestrator/fsm.py:1834`). По этой строке
`spec_writing` после шага аналитика признаёт тот же батч отвеченным и не
эскалирует снова (`orchestrator/fsm_advance.py:97`, `_answered_batch_skip`;
SPEC 01M4R4JKC28J80Z82TZA62RF2J). Канарейка закрывает эскалацию своей
функцией `canary._pass_escalated_with_synthetic_answer`
(`orchestrator/canary.py:1445-1488`), минуя `fsm._cmd_approve`, и признака
не ставит. Следствие — прогон канарейки 03.11 (шаблон
`canary-status-sort`, задача 01M6HRC19F72KE98JTS9PXS057): четыре
эскалации подряд с одним и тем же `QUESTIONS.md`, исход «не сошлась»,
вердикт red.

## Требования
1. `canary._pass_escalated_with_synthetic_answer` после записи
   синтетического ANSWER (`answer.cmd_answer`) и до смены состояния
   (`store.set_state`) ставит признак батча тем же узлом, что `approve`:
   вызывает `fsm._mark_questions_answered(conn, task_id)` при том же
   условии, что `fsm._cmd_approve`, — задача эскалирована из
   `spec_writing` и `answer_baseline` задачи на момент эскалации не
   `None`. Условие читается из строки задачи до сброса
   `escalated_from`/`answer_baseline`.
2. Эскалации из других состояний и эскалации с `answer_baseline = None`
   признака не получают — как у `approve`.
3. Прочее поведение функции не меняется: текст ANSWER, предел числа
   синтетических ответов, состояние возврата, записи журнала канарейки.
   Докстринг функции дополняется: признак батча ставится тем же узлом,
   что `approve`.

## Критерии приёмки
AC-1. Задача канарейки в песочнице пульта в `escalated` из `spec_writing`
с `answer_baseline`, не равным `None`, и с `QUESTIONS.md` в документах
задачи: после `_pass_escalated_with_synthetic_answer` в журнале ровно одна
новая строка `fsm.QUESTIONS_ANSWERED_ACTION` с detail `sha256=<хэш этого
QUESTIONS.md>; ANSWER-<номер только что записанного синтетического
ANSWER>`, эта строка записана раньше записи о смене состояния, задача в
`spec_writing`.

AC-2. Продолжение сценария AC-1: после шага аналитика (запись журнала шага
analyst, подменённая так же, как в существующих тестах SPEC
01M4R4JKC28J80Z82TZA62RF2J, `tests/test_01m4r4jkc28j80z82tza62rf2j_answered_batch.py`)
с тем же `QUESTIONS.md` переход `spec_writing` не эскалирует задачу, в
журнале строка `fsm_advance.QUESTIONS_SKIPPED_ACTION`. Намеренная ошибка
«вызов `fsm._mark_questions_answered` удалён из
`_pass_escalated_with_synthetic_answer`» делает этот критерий красным.

AC-3. Два сценария, в каждом всё остальное условие AC-1 выполнено: в
документах задачи лежит `QUESTIONS.md`, а `_pass_escalated_with_synthetic_answer`
записывает новый синтетический ANSWER после эскалации, — различается
только проверяемая половина условия: (а) `escalated_from = spec_writing`
при `answer_baseline = None`; (б) `escalated_from = in_dev` при
`answer_baseline`, не равном `None`. В обоих после
`_pass_escalated_with_synthetic_answer` новой строки
`fsm.QUESTIONS_ANSWERED_ACTION` в журнале нет, задача возвращена в прежнее
состояние (`escalated_from`, при его отсутствии `in_dev`) — как до правки.
Намеренные ошибки «условие убрано целиком (вызов безусловный)», «проверяется
только `escalated_from`» и «проверяется только `answer_baseline`» делают
этот критерий красным.

AC-4. Эскалация из `spec_writing` с `answer_baseline`, не равным `None`,
`_pass_escalated_with_synthetic_answer` записывает новый синтетический
ANSWER, но `QUESTIONS.md` в документах задачи нет: строки
`fsm.QUESTIONS_ANSWERED_ACTION` нет, функция не бросает исключение,
задача возвращена в `spec_writing` — как до правки.

## Не входит
- Перевод синтетического возврата канарейки на `fsm._cmd_approve` целиком.
- Правка шаблонов пула канарейки.
- Живой прогон канарейки — его проводит Оператор после мержа (шаблон
  `canary-status-sort`).
- Правка `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`,
  `orchestrator/answer.py`, `tests/test_canary_synthetic_answer.py` — по
  ТЗ только чтение.
- Зелёность существующих тестов без правки (`tests/test_canary_synthetic_answer.py`,
  `tests/test_canary.py`, `tests/test_canary_budget_ceiling.py`, тесты
  признака батча) — отдельным критерием не оформляется, её держит пульт
  (полный зелёный набор `tests/` и гейт неослабления). Краснеет
  существующий тест — эскалация с именем теста, без его правки (ТЗ).

## Материалы
- ТЗ: `tasks/01M6PFGA0GR4ZMGT3H7PKS7SN5/TZ.md`.
- Шов подмены и имена для тестов: `orchestrator.canary._pass_escalated_with_synthetic_answer`,
  `orchestrator.fsm._mark_questions_answered`,
  `orchestrator.fsm.QUESTIONS_ANSWERED_ACTION`,
  `orchestrator.fsm._last_questions_answered`,
  `orchestrator.fsm_advance.QUESTIONS_SKIPPED_ACTION`.
- Безопасность тестов (ТЗ): временная песочница пульта (`tests/sandbox.py`);
  без настоящего прогона канарейки, без клиента модели, без сети;
  настоящий каталог `tasks/` и `.artel/` не трогаются.
- `answer.cmd_answer` поля `answer_baseline`/`escalated_from` не меняет
  (`grep` по `orchestrator/answer.py` на этой ветке) — строка задачи,
  прочитанная после записи ANSWER и до сброса, несёт значения на момент
  эскалации.
- Решение 1 Оператора на гейте SPEC (форма отрицательных сценариев AC-3,
  AC-4): сверено с кодом — `orchestrator/fsm.py:617-624`, без
  `QUESTIONS.md` или без номера ANSWER `_mark_questions_answered` строки
  не пишет, поэтому сценарий без батча не отличает безусловный вызов от
  условного; образец формулировки «всё остальное условие выполнено» —
  `tests/test_01m4r4jkc28j80z82tza62rf2j_answered_batch.py:424-444`.
  Проверяется AC-3 и AC-4 тестами задачи против временного дублёра
  (песочница пульта `tests/sandbox.py`), настоящие `tasks/` и `.artel/`
  не меняются. С требованиями 1-3 и зонами не расходится.
- Журнал прогона-основания: `.artel/logs/canary/run-20261103T222709Z-*.log`.
