# Записка spec_auditor

## Выяснено
- forge.green_base_commit (orchestrator/forge.py:460-492) берёт только прогоны со status=success (:467): требование 5 «независимо от цвета прогона» с ним несовместимо — красный или оборванный прогон main через --record-latest не запишется (а AC-6 подменяет green_base_commit и этого не видит).
- targets.CI_REPORT_ARTIFACT_DEFAULT = "junit" уже есть (orchestrator/targets.py:175).
- project_profile.full_suite_limit -> (значение, источник), бросает TargetsError (project_profile.py:431-439).
- doctor.Check — статусы ok/warn/fail/skip (doctor/__init__.py:114, cli.py LABELS); у limit_level есть `alert`, соответствие статусу не задано.
- Тест паритета схемы (tests/test_store_schema_migration_parity.py) сверяет только колонки tasks — новую таблицу не держит.
- Справка: tests/test_01m5m0kqpv0fj9nsmdcq3xb76w_help_registry.py требует ключ в блоке «Команды:» artel.__doc__.
- _series (doctor/suite_duration.py:20) сбрасывает записи до ack алерта suite.duration и режет по xdist_workers — «отбор как в _series» шире, чем «по проекту».
- Остальные места SPEC (ci.py:39, acceptance.py:1653/3246/3259, cli.py:281, __init__.py:213, fsm_merge_gate.py:1384, тест :1351) подтвердились.

## Не сработало
- Опыт с git log --first-parent в /tmp: запуск shell-скрипта отклонён разрешениями, не подтверждено опытом.

## Где остановился
SPEC-AUDIT.md готов (status: ready, verdict: fail, 11 отклонений), guard — ок. Шаг завершён.

## Чего не хватило
Как в doctor отображается «алерт» ADR-0032 (Check-статус или таблица alerts) — в ТЗ/SPEC не сказано, искал по doctor/__init__.py.
