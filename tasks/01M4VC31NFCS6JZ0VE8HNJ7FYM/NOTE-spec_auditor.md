# Записка spec_auditor 01M4VC31NFCS6JZ0VE8HNJ7FYM

## Выяснено
- catalog.py:667 заводит задачу сразу в `spec_writing` (`insert_task`), в журнал пишет `created` (:670), НЕ `state -> spec_writing` (то же — докстринг auto.py:400). Первая эскалация аналитика в канарейке не имеет предшествующего `state -> X` → по AC-3 SPEC («нет предшествующего перехода» → неизвестная роль) она станет неизвестной ролью, и прогон-ловушка analyst+spec_auditor останется не чистым. Главная находка, вердикт fail.
- Метрики считает код клона (`canary_drive.build_result` → `canary._task_metrics`, canary_drive.py:71-78), пульт проверяет поля по `_DRIVE_METRIC_FIELDS` (canary.py:291, 2333). В результате есть и `steps` (action/detail по порядку).
- Факты SPEC о строках подтвердились: models.py:1128/1136/1174, canary.py:1848/1867/2416/2645/2762, store.py:1442, config.py:805 (STATE_ROLE без spec_writing).
- COMMON_ZONES (config.py:799) покрывает config.py и codebase-map — зоны достаточны.

## Не сработало
- grep с `cd ... ;` в одной команде отклоняется песочницей — нужны абсолютные пути.

## Где остановился
- SPEC-AUDIT.md написан, verdict fail; guard прогнан.

## Чего не хватило
- Где пишется первый вход в spec_writing — нашёл по докстрингу auto.py:400.
