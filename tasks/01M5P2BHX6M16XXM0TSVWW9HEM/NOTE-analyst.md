## Выяснено
- ТЗ достаточно; SPEC написан (6 AC), status: ready.
- Таблица: `mutation_run._table_path` (mutation_run.py:122); отчёт `--wait` — `_wait` (~строка 685), печатает `result["report"]`.
- `artifact_branch.docs_dir(task_id, target)` — artifact_branch.py:636.
- guard `is_extraneous_task_root_file` (guard.py:3470): `.tsv` первого уровня без точки — не посторонний.
- Бюджет: ТЗ $20 ниже планки `BUDGET_CALIBRATION_FLOOR_USD`=25 → в SPEC 25 (обосновано в «Материалах»).

## Не сработало
- Первый прогон guard отказал по сигналам объёма: `_zone_paths` считает все пути `orchestrator|scripts/*.py` во всём тексте SPEC, включая перечень «Только чтение»; `scripts/guard.py` совпал с docs/invariants.md. Закрыто секцией «Оценка объёма и деление» (обоснование монолита, прогноз 15 КиБ).

## Где остановился
- SPEC готов, guard прогнан.

## Чего не хватило
- Ничего существенного.
