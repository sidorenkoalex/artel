# Записка analyst — 01M6BMG29KZV1RX21HFAXZG3CM

## Выяснено
- Строки ТЗ сверены по коду после мержа В1.2: `fsm_advance.in_dev` :759, гейт исходов :843, сжатие :855, `_origin_push_gate` :868; `fsm_advance.verifying` :441 (зелёный CI → `review` :469). В `outcome_integrity.py` номера сдвинулись: `merge_gate_escalates` :1396 (в ТЗ :1153 — это теперь `head_sha` в `_judge_ci`), ядро CI `_judge_ci` :1148, `_ci_report` :1044 (перезапуск во время чтения :1062–1063), `_ci_base_report` :1084, `_gate` :1336 (ветка `merge and full_suite == ci` :1343 — `both` на мерже идёт локальным путём).
- КОНФЛИКТ: `tests/test_01m5xzskk8h096fd3cpn05bqnm_ci_outcome_gate.py::test_ac9_in_dev_gate_of_ci_component_judges_local_checkouts` (:918) утверждает ровно то, что ТЗ п.1 отменяет (отказ на `in_dev`, выписки, полные прогоны). ТЗ: «ожидается — нет. Иное — эскалация» → батч QUESTIONS.md.
- Отказ гейта на `in_dev` не меняет состояния (`_run_gates`, `advance_gates/_base.py:21`); отдельной колонки «счётчик возвратов» в `schema.py` нет (есть `review_iters`, `accept_rejects`, `verifying_attempts`).

## Не сработало
- `cd … && grep` в Bash требует подтверждения — использовал абсолютные пути.

## Где остановился
- Написан QUESTIONS.md (3 вопроса), SPEC.md не писался.

## Чего не хватило
- Какой «счётчик возвратов» имеет в виду ТЗ п.2 — в коде такого счётчика у гейта `in_dev` не нашёл.
