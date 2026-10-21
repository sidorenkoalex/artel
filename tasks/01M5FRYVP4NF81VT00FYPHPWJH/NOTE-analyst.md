# Записка analyst

## Выяснено
- Круг 2 (возврат из spec_gate): все 9 решений Оператора внесены в SPEC.md, status: ready, guard — ок.
- Добавлены: пробельная форма `-p` (имя со снятыми пробелами) в треб. 3/AC-4; AC-4 для test_profile — только `command` и `env.PYTEST_ADDOPTS` при pytest-own; ленивый импорт tests_writing в fsm.py + AC-5 про подпроцесс `import orchestrator.advance_gates.acceptance`; ветка гейта в `_temp_owner_alive` до проверки маркера канарейки (треб. 6, AC-7); подмена `orchestrator.doctor.orphans._project_clones` с проверкой вызова (треб. 6, AC-8); токены AC-10 через прежний `_TOKEN_SPLIT_RE` + `strip("*_")`; AC-12 без литералов в outcome_integrity.py; новый AC-13 — `env.PYTEST_PLUGINS`.
- 13 AC, 9 файлов зоны, budget_usd 40, монолит с запасной нарезкой — без изменений.
- `_temp_owner_alive` (orphans.py:82) сейчас сначала зовёт `owner_alive(path)` (маркер канарейки) — ветку гейта ставить выше.

## Не сработало
- —

## Где остановился
- Готово, дальше аудит/гейт SPEC.

## Чего не хватило
- —
