---
task: 01M6PFGA0GR4ZMGT3H7PKS7SN5
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Канарейка: синтетический ответ на батч вопросов аналитика ставит признак «батч отвечен»

# Канарейка: синтетический ответ на батч вопросов аналитика ставит признак «батч отвечен»

## Факты

1. На `approve` из эскалации, пришедшей из `spec_writing` с отвеченным батчем, пульт пишет в журнал строку `fsm.QUESTIONS_ANSWERED_ACTION` («батч вопросов отвечен», detail `sha256=<хэш QUESTIONS.md>; ANSWER-<n>`) функцией `fsm._mark_questions_answered` (`orchestrator/fsm.py:613-626`, вызов — `orchestrator/fsm.py:1867-1871`, условие: `t["escalated_from"] == "spec_writing" and baseline is not None`). По этой строке переход `spec_writing` после шага аналитика признаёт тот же батч отвеченным и не эскалирует его снова (`orchestrator/fsm_advance.py:97-124`, `_answered_batch_skip`; SPEC 01M4R4JKC28J80Z82TZA62RF2J). Удалить `QUESTIONS.md` роль не может.
2. Канарейка закрывает эскалацию своей функцией `canary._pass_escalated_with_synthetic_answer` (`orchestrator/canary.py:1445-1488`): пишет синтетический ANSWER через `answer.cmd_answer`, затем сама сбрасывает `escalated_from`/`answer_baseline` и переводит задачу в `escalated_from`, не через `fsm._cmd_approve`. Признак батча она не ставит.
3. Следствие — прогон 03.11 (`.artel/logs/canary/run-20261103T222709Z-*.log`, шаблон `canary-status-sort`, задача 01M6HRC19F72KE98JTS9PXS057): четыре эскалации подряд «analyst: батч вопросов по ТЗ» с одним и тем же `QUESTIONS.md` за 3 минуты, исход «не сошлась: 3 повторных эскалаций подряд», вердикт red. Шаблон с намеренным противоречием ТЗ проверяет именно эту ветку; прогон 04.11 на том же шаблоне сошёлся с двумя эскалациями — исход зависит от того, перепишет ли аналитик батч.

## Требуется

1. `canary._pass_escalated_with_synthetic_answer` после записи синтетического ANSWER и до смены состояния ставит признак батча тем же узлом, что `approve`: вызывает `fsm._mark_questions_answered(conn, task_id)` при том же условии, что `fsm._cmd_approve` — задача эскалирована из `spec_writing` и `answer_baseline` задачи на момент эскалации не `None`. Условие читается из строки задачи до сброса `escalated_from`/`answer_baseline`.
2. Эскалации из других состояний и эскалации с `answer_baseline = None` признака не получают — как у `approve`.
3. Прочее поведение функции (текст ANSWER, предел числа синтетических ответов, состояние возврата, записи журнала канарейки) не меняется. Докстринг функции дополняется: признак батча ставится тем же узлом, что `approve`.

Шов подмены и имена для тестов: `orchestrator.canary._pass_escalated_with_synthetic_answer`, `orchestrator.fsm._mark_questions_answered`, `orchestrator.fsm.QUESTIONS_ANSWERED_ACTION`, `orchestrator.fsm._last_questions_answered`, `orchestrator.fsm_advance.QUESTIONS_SKIPPED_ACTION`.

Критерии приёмки:
- задача канарейки в песочнице пульта в `escalated` из `spec_writing` с `answer_baseline`, не равным `None`, и с `QUESTIONS.md` в документах задачи: после `_pass_escalated_with_synthetic_answer` в журнале ровно одна новая строка `QUESTIONS_ANSWERED_ACTION` с detail `sha256=<хэш этого QUESTIONS.md>; ANSWER-<номер только что записанного синтетического ANSWER>`, строка записана до записи о смене состояния, задача в `spec_writing`;
- продолжение того же сценария: после шага аналитика (запись журнала шага analyst, подменённая так же, как в существующих тестах SPEC 01M4R4JKC28J80Z82TZA62RF2J) с тем же `QUESTIONS.md` переход `spec_writing` не эскалирует, в журнале строка `QUESTIONS_SKIPPED_ACTION`; намеренная ошибка «вызов признака удалён» делает этот критерий красным;
- эскалация из `spec_writing` с `answer_baseline = None` и эскалация из `in_dev`: строки `QUESTIONS_ANSWERED_ACTION` нет, возврат в прежнее состояние — как сейчас;
- `QUESTIONS.md` в документах нет: признака нет, функция не падает, возврат — как сейчас;
- существующие тесты канарейки (`tests/test_canary_synthetic_answer.py`, `tests/test_canary.py`, `tests/test_canary_budget_ceiling.py`) и тесты признака батча зелёные без правки.

Безопасность тестов: временная песочница пульта (`tests/sandbox.py`); без настоящего прогона канарейки, без клиента модели, без сети; настоящий каталог `tasks/` и `.artel/` не трогаются.

Существующие тесты: правка не должна сделать красным ни один существующий тест; если краснеет — эскалация с именем теста, без правки.

Зоны: `orchestrator/canary.py` (`_pass_escalated_with_synthetic_answer`), `docs/codebase-map.md`, `tests/` (долгоживущие файлы задачи).

Только чтение: `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`, `orchestrator/answer.py`, `tests/test_canary_synthetic_answer.py`, `.artel/` (журналы прогонов канарейки — материал фактов), `tasks/`.

Не входит:
- перевод синтетического возврата канарейки на `fsm._cmd_approve` целиком;
- правка шаблонов пула канарейки;
- живой прогон канарейки — Оператором после мержа (шаблон `canary-status-sort`).

Приоритет 2.

Рамка: $25. Набор моделей — по умолчанию.
