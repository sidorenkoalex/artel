# Записка analyst — 01M5TB6VDVV6AM8DWPGVQE8CDW

## Выяснено
- Чистые перечисления ("done","killed") в orchestrator/: models.py:1413, zone_lock.py:538, cleanup.py:543, prune.py:209, watch.py:41, doctor/branch_freshness.py:40, doctor/ignored_artifacts.py:36, doctor/orphans.py:188, doctor/artifact_branches.py:85,97,230. Смешанные (не только окончательные): auto.py:64 `_NO_ALERT_FINAL_STATES`, fixation.py:236 — в «Не входит».
- tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_units.py:357 читает `report.STATE_ORDER` — имя должно остаться (алиасом fsm.STATES), иначе правка существующего теста.
- guard требует `Порядок:` у КАЖДОЙ части (scripts/guard.py ~6097) — «часть без Порядок» в ТЗ прочитана как «Порядок без «после …»» (ослаблять guard нельзя).
- `spend.cli_number("$30")` → None: префикс `$` снимается до разбора.
- catalog.cmd_status уже печатает «[поделена: ids]» (`_division_suffix`, catalog.py:936); тестами текст родителя не держится.
- Циклы импорта: fsm импортирует cleanup/catalog/models на уровне модуля — обратный импорт fsm там даст цикл; дело разработчика.
- Сигнал объёма: 17 файлов зоны; рамка Оператора $45 (таблица классов дала бы ~85). В SPEC — обоснование монолита + альтернативная нарезка прозой.

## Не сработало
- bash с `cd … &&` и составными командами требует подтверждения — работать одиночными командами из рабочего каталога.

## Где остановился
- SPEC.md написан (status: ready, 10 требований, AC-1..AC-9, budget 45), `scripts/guard.py` — ок. Шаг закончен.
- Трактовка: отказ деления по «Порядок:» (включая провал merge_after.check/цикл) — всё-или-ничего, части не заводятся; значение части пишется как заявленное (record_declared).

## Чего не хватило
- Нет единого места, где перечислены все «смешанные» списки состояний — искал grep'ом.
