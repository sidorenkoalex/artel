# Записка аналитика

## Выяснено
- Шаг 5 (возврат с гейта, аудит 4, 26.10): решения внесены, QUESTIONS не нужен.
  - (1) AC-36 — два настоящих мягких отказа `_approve_spec_gate`: аудит `fail` без `--accept-audit-fail` (fsm.py:1201-1208) и неклассифицированный путь SPEC (fsm.py:1242-1247).
  - (2)+(4) треб. 4/5: lease по id эпика не берётся. epic new/edit/close — одна транзакция BEGIN IMMEDIATE без lease; epic add/remove — lease задачи через `lease.run_locked`; approve --as-epic — lease задачи, как сейчас (fsm.py:951); `new --epic` — как `new` сейчас (catalog.cmd_new lease не берёт); epic show — чтение. Журнал эпика — `store.journal(..., target=проект)` (store.py:1215). AC-18 переписан; ограничение lease.py:217-231 из «Не входит» убрано.
  - (3) AC-17: фикстура status с вторым эпиком, где задача в неокончательном состоянии.
  - Замечание: треб. 1 — быстрая проверка колонки вне транзакции, повторная внутри BEGIN IMMEDIATE.
- Системные записи журнала — константа task_id в config (`PIN_UPDATE_JOURNAL_TASK_ID`, config.py:313).
- «ЖДЁТ ОПЕРАТОРА» — catalog.py:992. Причина формы merge_after — guard.py:5636; store.get_task — store.py:1093.
- tests/test_multitarget.py:288-289 — правка по мандату ANSWER-1.

## Не сработало
- Составные команды Bash — только одиночные.

## Где остановился
- SPEC.md обновлён, 38 AC, guard ок, status: ready.

## Чего не хватило
- Перечня мест, где команды берут lease (new не берёт, approve берёт fsm.py:951) — искал grep'ом.
