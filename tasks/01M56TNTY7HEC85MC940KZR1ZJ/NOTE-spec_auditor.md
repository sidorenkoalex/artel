# Записка spec_auditor

## Выяснено
- Факты SPEC о коде подтвердились: test_integrity.py:631-650 (`_helper_callers`, grep по `tests/`), guard.py:1013-1019 (`_HelperScope._module`), :1087 (только sandbox), review.py:650-652, fsm_merge_gate.py:144-146, fsm.py:1053-1060, project_profile.py:78,95 (`workdir` по умолчанию ""), :140 decide, repo_context.py:154 is_artel.
- Все три входа узла (`_test_integrity_gate`, `review_lines`, `merge_gate_escalates`) сходятся в `_evaluate(conn, task_id, …)` test_integrity.py:1074 — профиль можно читать там.
- Существующий тест tests/test_guard_helper_scope.py:62 держит умолчание TestModules (функция чужого модуля tests/ — не помощник).
- Вердикт: concerns (неоднозначность req1/req3 при пустом workdir; AC-1 без входа; относительный импорт; граница области модуля).

## Не сработало
- Составные bash-команды с `cd`/`;` требуют подтверждения — только одиночные grep/sed по абсолютным путям.

## Где остановился
- SPEC-AUDIT.md написан, guard прогнан.

## Чего не хватило
- Нет.
