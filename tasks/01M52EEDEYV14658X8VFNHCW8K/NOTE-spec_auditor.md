# Записка spec_auditor — 01M52EEDEYV14658X8VFNHCW8K

## Выяснено
- Третий визит (spec_sha 83adc25b…): оба решения Оператора на гейте SPEC (6 + 3 пункта) внесены в SPEC.
- Ссылки подтвердились: targets.py:281, :300-301; acceptance.py:86, :923, :1115, :1372; two_sided.py:222, :230-232; targets.yaml:46; тесты :210/:178; test_profile.py:103/151-152; REPORT_ENV = ARTEL_TWO_SIDED_REPORT (two_sided.py:55).
- yamlmini.py:57-62 — это bool/int/float; None даёт :54-55 (ссылка из решения Оператора №1 п.4, неточна на 3 строки).
- argv `run` (с file_times) и `run_repeat` несут путь junit во временном каталоге, созданном КОДОМ (acceptance.py:443, :661), — для литерального ожидания тест должен подменить tempfile.mkdtemp.
- providers/__init__ на уровне модуля тянет только stdlib — импорт реестра из targets.py цикла не даёт.
- FULL_SUITE_WORKERS = "auto" (config.py:226), PER_TEST_TIMEOUT_SEC = 120 (stack.py:95) — литералы, от машины не зависят.

## Не сработало
- Составные команды bash с `;` проходят, `ls` в этой оболочке нет.

## Где остановился
- Вердикт concerns (две мелкие находки), status ready.

## Чего не хватило
- —
