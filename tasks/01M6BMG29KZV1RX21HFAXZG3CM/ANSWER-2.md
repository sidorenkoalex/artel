---
task: 01M6BMG29KZV1RX21HFAXZG3CM
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: ответ Оператора

## Ответы

Уточнение сессии при Операторе (права волны G) к SPEC, 02.11.2026 (пятый аудит, п. 1, вариант (а)).

Требование 16: «предыдущий отказ гейта по исходам» для правила повтора — последняя запись отказа **с находками** (`OUTCOME_BROKEN_REFUSAL_ACTION` / `OUTCOME_INTEGRITY_REFUSAL_ACTION`) после последнего шага `developer`; записи ожидания и сбоя подготовки (`PREPARE_REFUSAL_ACTION`) не считаются. Добавить тест задачи: возврат с набором X → шаг `developer` → `verifying`, первый опрос — отчёт головы не готов (ожидание), второй опрос — снова X → `escalated` с причиной «повтор находки гейта по исходам».
