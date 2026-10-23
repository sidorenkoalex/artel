# Записка spec_auditor — 01M5KP57JXWKKKCJKY47HT21W8

## Выяснено
- Круг 2 (spec_sha 55a73ba7…): все 5 решений гейта №1 отражены в SPEC.
- Ссылки на код подтверждены: role_prompt.py:140-164/151/173-185/323/335/413,
  test_01m56g…external_missions.py:185-204 (assertIn :203-204),
  test_01m5hdb1…:88 bare_full_run, :631 components_empty, :680 keeps_suite_run.
- Рубеж in_dev->verifying гоняет планку с приложениями (advance_gates/acceptance.py:598);
  локальный plank-run (orchestrator/plank_run.py:164) приложений НЕ накладывает —
  AC-4..AC-6 там красны при правильной реализации. Это главное отклонение круга 2.
- Guard: SPEC.md ок, SPEC-AUDIT.md ок.

## Не сработало
- Bash с `$VAR`/`;`-цепочками с переменными отклоняется («simple_expansion») — писать пути целиком.

## Где остановился
- SPEC-AUDIT.md: verdict concerns, status ready.

## Чего не хватило
- Есть ли у plank-run наложение приложений — нашёл grep'ом по appendix в plank_run.py.
