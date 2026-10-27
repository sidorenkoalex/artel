# NOTE-spec_auditor

## Выяснено
- SPEC sha 6c235939… — после возврата Оператора 27.10 (К1, п.1–9): все девять пунктов решения отражены (AC-1 both, AC-9 base≠main, AC-14, AC-15, строки матрицы autogate/checks_local, факт импорта forge↔targets, «Не входит» про состав ci_job).
- Факты кода подтверждены: acceptance.py:355/384/3358/3368/3394-3405/3414/3421-3457; fsm.py:1508/1563/1573-1582; fsm_autogate.py:426; ci.py:1269/1275-1276; targets.py:23 FORGES,37 base,95,988,1207; project_profile.py:66/434; forge.py:16 (импорт targets), 33-63, IMPLEMENTATIONS :156; gitlab_adapter.py:449-457; fsm_merge_gate.py:1084-1093; advance_gates/acceptance.py:213-218; fsm_advance.py:874.
- Отклонения (concerns): (1) «отказ загрузки» (AC-3, подменённый реестр forge) против запрета импорта forge в targets — механизм не выбран; (2) тупик приёмки ci/both у задачи с приложением PLAN (дерево гейта ≠ голове → «неизвестно», --accept-red не принимает), выхода SPEC не называет; (3) нет строки матрицы про отказ ci.py:1275-1276 чужим проектам; (4) AC-11 «не зелёный» для красного CI в both — не ловит подмену красного на «неизвестно»; (5) статус отчёта вне success/failed/skipped/error — зелёный; (6) три раздельных чтения forge.
- Сторож литералов хостинга (tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:475) исключает targets.py — литеральный кортеж там сторож не поймает; ловит только AC-3 с подменой forge.IMPLEMENTATIONS.

## Не сработало
- `xargs` в конвейере bash требует подтверждения — искать grep -rln по одному.

## Где остановился
- SPEC-AUDIT.md записан (verdict concerns, status ready, 7 отклонений), guard ок.

## Чего не хватило
- Где реестр хостингов: forge.IMPLEMENTATIONS (forge.py:156); targets.py не может его читать без кругового импорта.
