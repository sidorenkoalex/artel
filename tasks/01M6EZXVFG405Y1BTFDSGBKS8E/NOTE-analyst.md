# Записка analyst

## Выяснено
- ТЗ достаточно, SPEC.md написан, status: ready, guard ок. 7 AC, зоны из ТЗ, budget 25 (рамка ТЗ).
- merge_after — три части деления из `show`: 01M6EZXVFGXC6WBDA9QJESAZRW, 01M6EZXVFGCHB1S4W45AWJ0QH6, 01M6EZXVFGH5Z2876XWMQG35FP.
- Имя множества пар в SPEC задано как `targets.SUPPORTED_PAIRS` (в ТЗ имени нет — выбор аналитика, нужен test_author до кода).
- Тексты причин: «гейт мержа target-human не поддержан для хостинга github», «гейт мержа operator не поддержан для хостинга gitlab» — точное равенство, без суффикса «(ADR-0029)».
- Сторож А0: константы GITLAB_REASON/TARGET_HUMAN_REASON (строки 41-42) и кортежи в ac1 (165-166) — смена не скалярная, поэтому едет по мандату из ANSWER этой задачи, а не разделом «Меняемое поведение».
- tests/test_awaiting_human_units.py и tests/test_01m5xz9z68v75vxf5z66c708t4_awaiting_holds.py открывают github+target-human подменой SUPPORTED_MERGE_GATES; по чтению до unsupported_reason не доходят (вставка в БД), но надо подтвердить прогоном.

## Не сработало
- ничего.

## Где остановился
- Шаг завершён.

## Чего не хватило
- id частей 1–3 в ТЗ нет («после части 1, 2, 3») — взял из `artel.py show`.
