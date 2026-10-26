# Записка spec_auditor — 01M5W670PHF08VPZWDRM5BY56W (аудит 4, spec_sha 6346fc13)

## Выяснено
- Рабочий каталог (HEAD 58d9b72) позади origin/main: А0 (5705cfd) только в origin/main — сверять через `git show origin/main:…`.
- О-7, О-8, О-9 и замечания (AC-11 таймаут, AC-17 killed, accepted_full_suite) в SPEC внесены; тест А0 из зон убран.
- test_doctor.py:675 утверждает только статус; test_ac7 А0 (:346-377) смотрит только project-support-* — новые строки doctor его не ломают.
- Остались пробелы определённости (не ложный green): Н-1 AC-20 «обращения» против «вызываются» и AC-22 (except URLError вне транспорта); Н-2 старшинство итогов GitLab (конвейер running + failed-задание); Н-3 итог created/skipped не за ручным не назван; Н-4 исход строки срока токена при ошибке HTTP и для github.

## Где остановился
- Вердикт concerns, SPEC-AUDIT.md записан, guard ок.

## Чего не хватило
- Ничего существенного; форма EXEMPT — (файл, функция), unsupported_project.py:418.
