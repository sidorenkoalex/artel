# Записка аудитора SPEC 01M6PAJ61D4PYAP79ADRPA6MWV

## Выяснено
- Четвёртый визит, SPEC 49608e20: решения четвёртого круга 1–2 внесены; два пункта визита 3 (канал id, соотношение пределов) закрыты по содержанию.
- Новое: вызывающие узла `_report_run` ВНЕ зон без id задачи: `advance_gates/acceptance.py:174` → `run_repeat(seeded, run_cwd, command=)` (у `run_repeat` :1731 нет параметра id; файл вне зон, SPEC «Не входит»); `suite_run.py:607`, `:680` → `run_full_suite` (только чтение, нет id); `plank_run.py:267-269` → `run_plank` без `task_id` (долгоживущий файл, вне зон). С правилом «compose без id — отказ» эти места для compose всегда отказывают; повтор зерна → красный повтор → эскалация задачи.
- `run()`/`collect()` берут id из `Path(tdir).name` (acceptance.py:1424) — канал есть.
- `outcome_integrity._rerun` (:430) id не получает — передача требует параметра `_rerun` и правки двух вызовов (:757, :972).
- Подмен `report_run` в tests/ нет — сигнатурный аргумент не ломает тесты.

## Где остановился
- SPEC-AUDIT.md сдан для spec_sha 49608e20: verdict concerns, status ready. П.1 — три места вне зон без id (run_repeat ← advance_gates/acceptance.py:174, suite_run.py:607/680, plank_run.py:267-269); п.2 мелкое — новый параметр `_rerun` в outcome_integrity.

## Чего не хватило
- Перечня всех вызывающих `run_repeat`/`run_full_suite` вне acceptance.py в SPEC.
