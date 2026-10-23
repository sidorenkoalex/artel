# Записка spec_auditor 01M5KBGK8ZZ3Y8CDBXK6RX68JJ

## Выяснено
- Круг 2 (spec_sha 51d194fd…): все три решения гейта №1 внесены — budget 40 (config.py:646-647, 8 AC → $40), AC-8 про дифф вне зоны, AC-7 ослаблен до ТЗ.
- Факты о коде подтверждены заново: tests/test_suite_run.py:331-346, acceptance.py:37-67, stack.py:587-644, config.py:814-815, test_integrity.py:1074.
- Единственное отклонение — мандат ещё не в ANSWER-n (ANSWER-файлов нет); обещан строкой на этом гейте SPEC.

## Не сработало
- `ls` в Bash недоступен; список каталога — через `find -maxdepth 1`.

## Где остановился
- SPEC-AUDIT.md: verdict concerns, status ready; guard прогнан.

## Чего не хватило
- Ничего существенного.
