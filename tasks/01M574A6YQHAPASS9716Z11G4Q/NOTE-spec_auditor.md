# Записка spec_auditor — 01M574A6YQHAPASS9716Z11G4Q

## Выяснено
- Вердикт fail (spec_sha 544bdebe…). Главное: текст статуса читают подстроками verifying_is_red (ci.py:835), red_status_sha (ci.py:848), status_kind (ci.py:1014) → auto.py:485, ci_rerun.py:89-90, fsm_merge_gate.py:363; SPEC не требует сохранить их на пути Actions.
- Источник триггера (pull_request) для ci.py в SPEC не определён; для вершины main фильтр pull_request обычно даёт пусто (ci.py:611, ci_rerun.py:291).
- На пути Actions не потребован отбор по head_branch (_branch_checks ci.py:562).
- Факты SPEC о строках подтвердились (fsm_merge_gate 583/626 — строки охраны is_artel, вызов на 591/630).

## Не сработало
- grep с --include под zsh в этой оболочке падает (no matches found) — без флага.

## Где остановился
- SPEC-AUDIT.md записан, guard прогнан.

## Чего не хватило
- Карты потребителей текста note статуса CI (кто разбирает подстроки) — искал grep'ом по orchestrator/.
