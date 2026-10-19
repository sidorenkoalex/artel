# Записка spec_auditor

## Выяснено
- Все адреса SPEC сверены с кодом (brief.py:62-65/1079/1111/1129/1147/1436/1461, fsm.py:885/1089/1169/1180/1186/1215/1498/1509/1514/1617, artel.py:30-36/166-167/1730/1769/1772/1797/1805/2050, review.py:729/919/926, answer.py:95/267, config.py:529, rounds.py:42) — совпадают.
- `lease.acquire` пишет «lease взят» в журнал (lease.py:144) — отказ п. 2 в `_cmd_approve` идёт уже под lease, а AC-2 требует «журнал прежний».
- `review_package` зовёт только role_prompt.py:153; docs/codebase-map.md — в config.COMMON_ZONES.
- Вердикт: concerns (4 пункта в SPEC-AUDIT.md).

## Не сработало
- Ничего существенного.

## Где остановился
- SPEC-AUDIT.md написан, guard прогнан.

## Чего не хватило
- Знания, журналирует ли lease захват — нашёл в lease.py:144.
