# Записка spec_auditor

## Выяснено
- spec_sha 27caa81c… совпал с git hash-object SPEC.md. Все ссылки файл:строка SPEC (canary.py, artel.py, liveness, suite_lock, reference_cache, store, тесты) сошлись с кодом (HEAD f653a66a).
- Вердикт concerns, 6 отклонений + наблюдения: код 0 при незапущенном шаблоне (SPEC:179); дубль строки SIGKILL (SPEC:150 против 166); место «причины» красной строки (строка БД или вывод); AC-17 без режима --parallel (в последовательном режиме main уже держит, canary.py:3288-3291); AC-12 без проверки canary_baseline (потеря ТЗ п.9); без AC ветви SPEC:148-149 и 75-76.
- `canary live --drop` снимает метку только при отсутствии живых записей (canary.py:3162) — AC-16 строится файлами реестра.
- guard на SPEC-AUDIT.md: ок.

## Не сработало
- sed/awk с cd в Bash и `$?` требуют подтверждения — читать через Read, guard звать абсолютным путём.

## Где остановился
- SPEC-AUDIT.md сдан (status ready, verdict concerns).

## Чего не хватило
- Нет готовой выжимки, как _report_drive_failure разносит причину между строкой БД и выводом; пришлось читать canary.py:2740.
