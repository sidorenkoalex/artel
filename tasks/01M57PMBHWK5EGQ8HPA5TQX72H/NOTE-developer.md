# Записка developer

## Выяснено
- Реализация: report.py (`_project`, `_project_suffix`/`_project_label`, `_alert_label`, `_split_metrics_html`), watch.py `_observation_events` (+None в targets, `-` в поле проекта). catalog.py не правился.
- Позиция «оповещено» уже по наблюдению — отдельной правки store не нужно.
- Долгоживущие тесты задачи + test_report + тесты наблюдения/дозора зелены; планка AC-8 зелена (plank-run). Карта регенерирована.

## Не сработало
- suite-run отказал: шёл прогон другой задачи (01M57JYJQC8VAHEWMXFNM7D1GS).

## Где остановился
- PLAN.md status: ready; suite-run №1 зелёный (5835/0/2). Шаг завершён.

## Чего не хватило
- Ничего существенного.
