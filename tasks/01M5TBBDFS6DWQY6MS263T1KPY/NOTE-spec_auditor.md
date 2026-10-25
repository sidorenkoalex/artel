# Записка spec_auditor — 01M5TBBDFS6DWQY6MS263T1KPY (визит 6, spec_sha e54f8e94…)

## Выяснено
- Находки визита 5 закрыты решением гейта №5: привязка и `epic close` — BEGIN IMMEDIATE (req 4, AC-39); SPEC родителя не читается — отказ `--as-epic` (req 7, AC-37).
- Все ссылки SPEC на код снова сверены и верны (fsm 379/951/958/1201-1208/1242-1247/1287, catalog 860/982/992, merge_after 103/126, guard 5636, idgen 47, store 1089/1250, lease 144/334, watch 354, schema 173-183, artel 1797/2006, config 61/313, tests/test_multitarget 286-289/516, tests/test_agent_failure 355).
- Новое (concerns): `catalog._new_task_row` (catalog.py:~706) создаёт ссылку документов `_new_external_artifact_branch` ДО `store.insert_task`; req 5 требует порядок `new` «как сейчас», а проверку «эпик open/тот же проект» req 4 кладёт только в транзакцию со вставкой — отказ AC-5/AC-6 оставит осиротевшую ссылку `refs/artifacts/<id>`; AC-5/6 проверяют только строку tasks.
- `store.insert_task` сам делает commit (store.py:~600) — коммит завершает BEGIN IMMEDIATE, журнал после — совместимо с req 14.

## Не сработало
- `cd … && git` и циклы с `$` в Bash требуют подтверждения — использовал python и абсолютные пути.

## Где остановился
- SPEC-AUDIT.md написан (verdict concerns, status ready).

## Чего не хватило
- Нет.
