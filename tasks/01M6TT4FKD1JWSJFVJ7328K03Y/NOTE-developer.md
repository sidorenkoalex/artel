# Записка developer — 01M6TT4FKD1JWSJFVJ7328K03Y

## Выяснено
- Реализовано (закоммичено WIP-чекпоинтом 92fddd463): targets.py (`_check_ci_base`, `ci_base_branch`/`ci_base_push_options`/`ci_base_jobs`),
  gitcmd.py (эталон политики + белый список `_ci_base_source_refusal`), хук pre-push (ключ ci_base_branch=),
  outcome_integrity.py (`_ci_attempt`, `_NoBaseReport`, `_BasePending`, `_push_ci_base`, `early_base_push`),
  fsm_advance.tests_writing (ранняя отправка), doctor `check_ci_base_branch`.
- Зелёные: планка (plank-run 17/17), tests/..._ci_base_fields.py, ..._ci_base_doctor.py (14 вместе), ..._ci_base_gate.py (32, ~3.5 мин).
- Долгоживущие файлы: tests/test_01m6tt4fkd1jwsjfvj7328k03y_ci_base_{gate,fields,doctor}.py.
- pytest с `-n` в шаге отказан сторожем — гонять последовательно.

## Не сработало
- `pytest -n 6` — сторож роли считает это полным прогоном.

## Где остановился
- Шаг 2 завершён: карта регенерирована, тесты затронутых модулей зелёные (перечень — в PLAN), guard ок, PLAN ready.
- Самый долгий файл — test_01m6bmg29kzv1rx21hfaxzg3cm_verifying_outcome_gate.py (7.5 мин): гонять отдельным вызовом.

## Чего не хватило
