# Записка spec_auditor — 01M5TBBDFS6DWQY6MS263T1KPY (визит 5, spec_sha 794b3cac…)

## Выяснено
- Находки визита 4 закрыты решением гейта №4: lease по id эпика не берётся (req 4), AC-36 — настоящие мягкие отказы fsm.py:1201-1207/1242-1247, AC-17 — второй эпик с задачей.
- Все ссылки SPEC на код сверены и верны (fsm 379/951/958/1201/1242, catalog 860/982/992, merge_after 103/126, guard 5636, idgen 47, store 1089, lease 144/334, watch 354, schema 173/183, artel 1797/2006, config 61/313).
- Новое (вердикт concerns):
  - гонка `epic add`/`new --epic` (lease задачи) против `epic close` (BEGIN IMMEDIATE без lease): SPEC не требует проверки состояния эпика и записи `tasks.epic_id` в одной транзакции BEGIN IMMEDIATE — привязка к только что закрытому эпику возможна.
  - AC-37 «SPEC родителя не читается» — исход (отказ какой причиной) в требовании 7 не назван.
- Ловушки для разработчика: `store.journal` сам делает commit (store.py:1250); `SqlOnlyInStoreTest` (tests/test_multitarget.py:516) — SQL только в store.py/schema.py; `merge_after.check` отказывает на повторе префикс+полный id — дедуп до check.

## Не сработало
- Составные Bash-команды с `;` и разными файлами требуют подтверждения.

## Где остановился
- SPEC-AUDIT.md написан (verdict concerns, status ready), guard — ок.

## Чего не хватило
- Нет.
