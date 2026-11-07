# Записка developer — 01M6TT4FKD1JWSJFVJ7328K03Y

## Выяснено
- Реализовано: targets.py (`_check_ci_base`, `ci_base_branch`/`ci_base_push_options`/`ci_base_jobs`),
  gitcmd.py (эталон политики + белый список `_ci_base_source_refusal`), хук pre-push (ключ ci_base_branch=),
  outcome_integrity.py (`_ci_attempt`, `_NoBaseReport`, `_BasePending`, `_push_ci_base`, `early_base_push`),
  fsm_advance.tests_writing (ранняя отправка).
- Зелёные: планка (plank-run 17/17), tests/..._ci_base_fields.py (10), ..._ci_base_gate.py (32, ~3.5 мин).
- pytest с `-n` в шаге отказан сторожем — гонять последовательно.

## Не сработало
- `pytest -n 6` — сторож роли считает это полным прогоном.

## Где остановился
- Дальше: doctor (project_checks.component_checks), карта, тесты затронутых модулей.

## Чего не хватило
