# Записка spec_auditor

## Выяснено
- SPEC sha 1cfe4c5…: ссылки на код верны (guard.py:2581-2614, 2692, 2709, 2776, 2814; tests_writing.py:79/351/470; preflight.py:186/203/259; amend.py:512-515; fsm_advance.py:587-593; targets.py:43-60, 276).
- Узел long_lived_errors_from_files зовут ровно пять мест — все пять в SPEC.
- Требование 6 исполнимо без fsm_advance.py: гейты tests_writing уже получают `profile` (перечень придёт полем Profile), is_artel — через workspace.task_target(task_id), как amend.py:514.
- _check_profile(where, profile) (targets.py:276) не знает имени записи — для отказа у артели нужна правка сигнатуры (в зоне).
- Существующие тесты зовут узел позиционно (test_guard_test_groups.py, test_network_address_gate.py:161, test_01m4p4zp…_preflight.py:669) — умолчание нового параметра должно давать поведение артели.
- Находки: AC-1 не требует литерала текста (ожидание можно вычислить из _SIGN_EXPLANATIONS); сужение п.4 ТЗ «проходит выход» до «нет признака» не названо в «Не входит».

## Не сработало
- —

## Где остановился
- Вердикт concerns, SPEC-AUDIT.md записан.

## Чего не хватило
- —
