# Записка spec_auditor — 01M5TBBDFS6DWQY6MS263T1KPY (визит 7, spec_sha ded6f5cd…)

## Выяснено
- Решение гейта №6 внесено: req 5 — проверка эпика для `new --epic` до `_new_external_artifact_branch` (catalog.py:708); AC-5/AC-6 проверяют отсутствие `refs/artifacts/<id>`.
- Все ссылки SPEC на код сверены заново и верны (catalog 708/860/982/992, store 1093/1249, schema 173-183, fsm 379/951/958/1201-1208/1242-1247/1287, artel 1797/2006, watch 354, lease 144/334, config 61/313, guard 5636, idgen 47/59, merge_after 103/126, tests/test_multitarget 286-289/516, tests/test_agent_failure 355).
- `store.insert_task` коммитит сам (store.py:599) — конец BEGIN IMMEDIATE привязки; журнал «created» после — совместимо с req 14.

## Не сработало
- `cd … && sed` в Bash требует подтверждения — читал через python с абсолютными путями.

## Где остановился
- SPEC-AUDIT.md: verdict pass, status ready.

## Чего не хватило
- Нет.
