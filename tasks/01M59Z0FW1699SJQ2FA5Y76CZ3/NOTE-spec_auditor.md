## Выяснено
- Повторный аудит (spec_sha 128cf82e…): решения Оператора №1 п. 1–7 перенесены в SPEC полностью; адреса SPEC сходятся с кодом c2dc427f.
- Компонент с report полный набор гонит через `_run_full_suite_reported` (acceptance.py:2288-2291) → `_report_run` → `_report_argv` (:805); ветка :2307-2311 — только pytest-own без report. AC-6 (junit-xml) её не ловит.
- targets.py:498-501 запрещает `..` и пустые сегменты, но не `.`: `web/build/./<id>` проходит «родитель с точки», шаблон info/exclude не сработает.
- Выкладка сегодня — только при plank_present / task_id (acceptance.py:1349, :1507, :1976); отказ «нет plank_layout» без такой оговорки ломал бы plank-run долгоживущего файла (plank_run.py:221-229).
- plank_rule записи из одного pytest-компонента — умолчание (project_profile.py:482-488), masks() пуст.
- test_ac11/test_ac16 после правки становятся тривиальными (отказ вместо прогона) — Оператор принял (решение №1 п. 5), не поднимал.

## Не сработало
- `cd … && sed …` и пайпы с head требуют подтверждения — бери Read и grep по абсолютному пути.

## Где остановился
- SPEC-AUDIT.md написан, verdict concerns, status ready; guard прогнан.

## Чего не хватило
- Какие профили попадают в ветку полного набора :2307 против `_run_full_suite_reported` — ключ в `_reported` (acceptance.py:366) и project_profile.reported (:317).
