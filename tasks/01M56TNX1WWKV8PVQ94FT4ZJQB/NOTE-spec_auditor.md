# Записка spec_auditor — 01M56TNX1WWKV8PVQ94FT4ZJQB

## Выяснено
- Визит 3, SPEC sha b495b2b1. Все 5 отклонений визита 2 закрыты: zones без docs/invariants.md; try/except/with определены (треб. 4); as/AnnAssign — в «Не входит»; AC-8 с tests/marks.py; AC-10 с литералами.
- guard.protected_zones(зоны SPEC) = [], guard.spec_unclassified_paths(SPEC) = [] — механического отказа гейта SPEC нет.
- Ссылки кода на HEAD 4b0efef0 верны. Вердикт: pass (к сведению — ~$40 при budget 25).

## Не сработало
- `cd … && git` и составные ls/wc в bash просят подтверждения — давать абсолютные пути одной командой.

## Где остановился
- SPEC-AUDIT.md записан, guard прогнан.

## Чего не хватило
- Сигнатура guard.spec_unclassified_paths(text, meta, root) — нужен meta из yamlmini.frontmatter.
