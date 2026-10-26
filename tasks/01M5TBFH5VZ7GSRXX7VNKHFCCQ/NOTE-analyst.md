# Записка аналитика 01M5TBFH5VZ7GSRXX7VNKHFCCQ (Э4)

## Выяснено
- ТЗ достаточно — пишу SPEC, не QUESTIONS.
- `orchestrator/board.py` в main нет: его вводит Э1 (01M5TBBDFS6DWQY6MS263T1KPY), в SPEC — `merge_after`.
- Факты ТЗ сверены: `report.STATE_ORDER` `report.py:46`, `_board_html` `:598`, `cmd_report` `:1430`.
- Тесты, зовущие внутренности отчёта напрямую: `tests/test_report.py:246,255,261` (`report._board_html(tasks)`), `tests/test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_units.py:357` (`report.STATE_ORDER`). Смена сигнатуры `_board_html` — правка теста не по значению → только мандат Оператора (ТЗ: «ночной мандат 25.10 … через гейт SPEC; иное — эскалация»).
- `external_refs`, `ref_required` в коде нет.

## Не сработало
- —

## Где остановился
- SPEC написан (status: ready, 9 AC, budget 60, merge_after Э1), guard: ок.
- Сигналы объёма (≥5 файлов, budget ≥ $30) — в SPEC обоснование монолита + вариант деления на выбор Оператора.

## Чего не хватило
- Интерфейса модели `board.py` (Э1 ещё не смержен) — поля модели взяты из ADR-0028 п. 12.
