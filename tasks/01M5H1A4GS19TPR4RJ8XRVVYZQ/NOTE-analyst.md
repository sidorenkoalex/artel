## Выяснено
- Факты ТЗ сверены grep'ом по ветке: строки методов совпадают (profile_callers: tests_dir 555, вызовы 565/673/701, PultUnchangedTest 1087, check_places 1089, ac10 1100/1121; spec_audit_flow: path_signal_categories 191, test_ac9 728; outcome_gate: ac4 1145/1195, ac7 1345/1389, ac8 1423, ac11 1683; pytest_own_places: PLACES 62, ac3 502/520, ac6 542).
- SPEC написан, status: ready, budget_usd 35 (верх ТЗ $25–35; сигнал деления по бюджету — config.SPLIT_SIGNAL_BUDGET_USD = 60, AC 9 < 10, зон 4 < 5 — сигналов нет).
- skip_tests не ставил: ТЗ п.5 говорит «новые тесты в tests/ не нужны», а критерии — свойства, проверяемые сценарием и прогоном (планка test_author).

## Не сработало
- Составной bash с `cd` и несколькими grep требует подтверждения — работает один grep с относительными путями.

## Где остановился
- SPEC.md готов, guard ок.

## Чего не хватило
- Ничего существенного.
