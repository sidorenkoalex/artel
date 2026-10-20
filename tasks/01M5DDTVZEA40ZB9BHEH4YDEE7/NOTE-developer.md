# Записка developer — 01M5DDTVZEA40ZB9BHEH4YDEE7

## Выяснено
- Реализовано: outcome_integrity (ядро `_gate`/`_judge` с базой-функцией `_diff_base`/`_merge_base_of`,
  ключ `_component_key`, строка доказательства, `_proven`, `merge_gate_escalates`, `review_lines`),
  fsm_merge_gate `_outcome_integrity_merge_gate` после «fresh», refusal_classes ключ мержа,
  review `_outcome_gate_lines`, two_sided `_run_side_report` + `_verdict` по `kind`.
- Долгоживущий файл задачи — 19 passed (~2.3 мин); планка — 3 passed.
- tests/test_component_report_gates.py — добавлена подмена `_outcome_integrity_merge_gate` в `merge`.
- tests/test_full_suite_reuse.py гоняет цикл мержа с `conn=object()`: новый шаг мержа не должен трогать БД
  до проверки границы по `store.task_target` (подменён). Исправлено; suite-run --failed зелёный.

## Не сработало
- Длинный heredoc python в Bash — парсер инструмента обрывается; правки — через Edit.

## Где остановился
Шаг завершён: PLAN ready, guard ок, карта регенерирована.

## Чего не хватило
Что существующие тесты цикла мержа подменяют conn на object() — узнал только из suite-run.
