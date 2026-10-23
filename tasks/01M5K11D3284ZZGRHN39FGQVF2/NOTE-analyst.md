# Записка analyst — 01M5K11D3284ZZGRHN39FGQVF2

## Выяснено
- Круг 2 (возврат с spec_gate 23.10): в SPEC внесены пять решений Оператора — AC-10 («сеть» без повтора), AC-11 (без --force/--force-with-lease/«+»), AC-12 (`(failed to update ref)`/`(failure)` — non-ff), AC-13 («попыток 2» в успехе), AC-14 (пауз = попыток − 1). Требования 1(б), 2, 4 уточнены под них.
- Признак «сервер» по `(failed)` — только скобка с одним словом в конце строки отказа; `(failure)` в AC-2 остаётся «сервер» лишь через `fatal error in commit_refs`.
- Критериев 14, зон 3 → budget_usd 45 (`config.BUDGET_CALIBRATION_TABLE`, ниже дефолта $50).
- Факты кода круга 1: `_classify_push_failure` artifact_branch.py:320, `_attempt_push` :336, `push` :378, `_send` :404, `send_pending` :418; `store.last_task_step_of` store.py:1185. Сторож sleep_guard запрещает глобальную подмену `time.sleep` → подмена объекта `artifact_branch.time`.

## Не сработало
- Круг 1: SPEC без секции «Оценка объёма» — guard отказал.

## Где остановился
- SPEC готов (status: ready), guard ок.

## Чего не хватило
- Guard считает пути `orchestrator/*.py` по всему тексту SPEC (`scripts/guard.py::_zone_paths`).
