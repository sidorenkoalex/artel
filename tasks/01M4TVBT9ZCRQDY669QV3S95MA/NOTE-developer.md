# Записка developer — 01M4TVBT9ZCRQDY669QV3S95MA

## Выяснено
- Реализация: targets.py (подполе min_uses, `type(v) is int`, 1..1000);
  reference_cache.py (`get_reference_for_target`, `min_uses(setting)`,
  `branch_commit(clone, branch)`, повод `reference` → источник алертов None,
  журнал с явным `target=`); projects.py (`cmd_reference`,
  `reference_summary`, `_target_init_reference`); artel.py (таблица, справка).
- Долгоживущие тесты задачи зелёные (18 passed).

## Не сработало
—

- Свой tests/test_reference_command.py (3 теста, 3 мутации пойманы).
- Тесты затронутых модулей (226), планка, suite-run №1 (5449 прошло, 0 упало) —
  зелёные. Карта перегенерирована.

## Где остановился
PLAN.md status: ready, guard ок. Шаг завершён.

## Чего не хватило
pytest из каталога tests/ сторож conftest считает полным прогоном — гонять
из корня с путями tests/…; запись временных файлов в /tmp недоступна.
