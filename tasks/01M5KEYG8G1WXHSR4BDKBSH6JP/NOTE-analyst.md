# Записка analyst — 01M5KEYG8G1WXHSR4BDKBSH6JP

## Выяснено
- ТЗ полное, вопросов нет — пишу SPEC.md.
- Ссылки ТЗ сверены на HEAD ветки: `_cmd_canary` теперь `orchestrator/artel.py:1547` (в ТЗ 1541 — сдвиг на 6 строк), ветка `live` — 1565, справка `canary live` — 185, разбор `_cmd_canary_live` — 1658.
- `canary.py`: `_acceptance_summary` 2031 (возвращает строку с ведущими двумя пробелами или ""; при refusal=None и reached=False — ""), `_run_verdict` 2050, `_diagnostics_dir(outer_root, run_stamp, task_id)` 2067, `RUN_STAMP_RE` 2803, `cmd_canary_live` 3129.
- `store.all_canary_runs` 1710 — `SELECT * ... ORDER BY id` с `_ensure_canary_tables`; схема 1563.
- Бюджет: ТЗ даёт $15, ниже пола калибровки $25 (`config.BUDGET_CALIBRATION_FLOOR_USD`); guard пол не держит, `budget.calibration_warning` только предупреждает. Взято $15 из ТЗ.

## Не сработало
- Bash с `cd …;` и с переменной в составной команде требует подтверждения — простые одиночные команды из рабочего каталога проходят.

## Где остановился
- SPEC.md написан (status: ready, 9 AC, budget 15), guard: ок.
- Guard сначала отказал по сигналу «число модулей/файлов»: `_zone_paths` считает пути `orchestrator/*.py` по всему тексту SPEC, включая перечень только для чтения. Закрыто разделом «Оценка объёма и деление» (обоснование монолита для Оператора + «Прогноз диффа: 20 КиБ»). Монолит утверждает Оператор на гейте SPEC.

## Чего не хватило
- Ничего существенного.
