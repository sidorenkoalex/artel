# Записка developer

## Выяснено
- Ядро `_judge_ci` (outcome_integrity.py) годно для verifying без изменений.
  Голова — `gitcmd.branch_head_sha` той же локальной ветки, что читает
  `ci.verifying_status`.
- Отказ, видимый брифу, должен идти ПОСЛЕ записи `state -> in_dev`
  (store.refusal_history).
- Шаг developer в журнале — actor `developer`, action `agent run started`.
- Реализация:
  - `verifying_gate` / `_verifying_refusal` / `_cycle_reason` в
    outcome_integrity.py;
  - `_Pending` (подкласс `_Prepare`) отличает ожидание от сбоя;
  - возврат помечен деталью `RETURN_DETAIL` записи `state -> in_dev` —
    по ней считается предел.
- Долгоживущий файл задачи: 45 passed. Планка: 4 passed. Соседние файлы:
  369 passed.

## Не сработало
- `pytest -n 6` в этой среде роняет воркеры (xdist). Гонять последовательно.

## Где остановился
- Шаг завершён. PLAN status: ready, guard ок, карта регенерирована.

## Чего не хватило
- Как отличить «ожидание» от «эскалации сразу» в причине `_ci_report`:
  у функции не было признака — пришлось добавить третий элемент.
