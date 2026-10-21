# Записка developer — 01M5FA4NR91PCF47SZT6V0Q9HS

## Выяснено
- Код: canary.py — `live_marks` (метки без записи, уборка), `registry_view` (без уборки, для doctor),
  `cmd_canary_live`, `live_run_note` (записи, затем метки); `_drop_live_record` разложен на
  `_record_mark`/`_mark_follows_record` без смены поведения. artel.py — `_cmd_canary_live` (проверка
  аргументов до чтения реестра), строка справки. doctor/canary_pool.py — `check_canary_live`,
  `_fix_canary_live`; cli.py — строка после canary-trigger, починка в ветке --fix.
- Изоляция: setUp с подменой `canary._live_dir` у CmdCanaryTemplateSelectionTest и DoctorFixOrderTest.
- Зелёные: 4 долгоживущих файла, test_canary_live_registry_units, test_canary_template_flag,
  test_doctor_closed_ref_fix, реестр/окно части А, test_doctor, test_doctor_canary_pool.

## Не сработало
- —

- plank-run: 3 passed. Карта регенерирована. suite-run №1: 6345 прошло, 4 упали по таймауту
  (файлы вне зоны, load ~145); №2 --failed: 4/4 прошли. Время ~19–20 мин.

## Где остановился
- PLAN.md status: ready, guard ок. Шаг сдан.

## Чего не хватило
- —
