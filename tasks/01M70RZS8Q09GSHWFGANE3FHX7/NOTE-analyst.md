# Записка analyst

## Выяснено
- ТЗ достаточно; SPEC.md написан, status: ready, guard ок. 7 AC, budget $35 (рамка ТЗ), сработал сигнал budget ≥ $30 — дано обоснование монолита.
- Номера строк ТЗ устарели: `is_protected_path` — `orchestrator/config.py:883-914`, `PROTECTED_PATHS` — `:860-866`, `mask_matches` — `orchestrator/project_profile.py:46-62`, `targets.check` — `orchestrator/targets.py:971`, `TargetsError` — `:232`.
- Гейт зон: `orchestrator/advance_gates/zones.py:37-44` зовёт формулу напрямую.
- Запись `**/*.env` (звезда в остатке после `**/`) в SPEC отнесена к новой семантике, не к прежней форме `**/<имя>` (см. «Материалы» SPEC).

## Не сработало
- `ls` в оболочке шага недоступен (command not found).

## Где остановился
- Шаг завершён.

## Чего не хватило
- Существующие тесты, ждущие незащищённости `*`-масок, не искал — по ТЗ это эскалация разработчика.
