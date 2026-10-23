# Записка spec_auditor — 01M5KP57JXWKKKCJKY47HT21W8

## Выяснено
- Ссылки SPEC на код подтверждены: role_prompt.py:17/134/151/323/335/413, runner.py:749/759/778, roles.yaml:40, config.BUDGET_CALIBRATION_FLOOR_USD=25.0 (config.py:654).
- Оба приложения ТЗ проходят `git apply --check` на голове ветки 9b498178.
- Второй существующий тест закрепляет `suite-run` в миссии ревьювера внешнего проекта:
  tests/test_01m56g23zqdhv2bkevwwc22r96_external_missions.py:185-205
  (`test_ac8_external_reviewer_lists_pult_check_commands`, assertIn `{pult} suite-run`).
  Требование 3 SPEC его краснит, SPEC (треб. 8) и ТЗ его не называют — нужен второй мандат.
- Планка и долгоживущие на рубеже in_dev->verifying идут с приложениями (advance_gates/acceptance.py:598);
  гейт неослабления по исходам — на выписках base/head без приложений (outcome_integrity.py:770-784);
  новый красный тест там не находка (compare, :185-217), skip — находка.

## Не сработало
- Составной Bash с `cd` требует подтверждения — команды без `cd`.

## Где остановился
- SPEC-AUDIT.md: verdict concerns, status ready.

## Чего не хватило
- Поиск тестов, закрепляющих текст миссии ревьювера, — grep по «suite-run»/«Права не сужены» в tests/.
