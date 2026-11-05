# Записка аудитора SPEC 01M6PAJ61D4PYAP79ADRPA6MWV

## Выяснено
- Пятый визит, SPEC 79b39475: решения пятого круга 1–2 (решение гейта №4) внесены; пункты визита 4 (места вне зон без id, `_rerun`) закрыты по содержанию; якоря :174, :607, :680, :267-269, :430, :757, :972, :1731, :2042, :2338 сверены.
- Новое: `run_plank(task_id=…)` (acceptance.py:2056-2073) уже значит «цели в планке задачи, выкладка `_plank_layout`», не «id для имени проекта». Передача `task_id` в вызов долгоживущего файла (plank_run.py:267-269), как велит SPEC треб. 3, у pytest-own с `long_lived_dir` под `workdir` зовёт `plank_layout.plank_layout` → `shutil.copytree` несуществующего `tasks/<id>/acceptance_tests` → FileNotFoundError (проверено опытом: copytree отсутствующего каталога — FileNotFoundError). Ломается `tests/test_01m56g23zqdhv2bkevwwc22r96_plank_run_long_lived.py::test_ac5…` при безусловной передаче; для compose — тот же путь, если compose идёт через `_own`/`layout_mode`.
- `mutation_run.py:516` зовёт `run_full_suite` без id — для compose отказ; mutation_run в контейнере вне задачи — не отклонение.
- Подмены `run_full_suite` в tests/ — MagicMock/лямбды; suite_run-тесты читают только kwargs `limit`.

## Где остановился
- SPEC-AUDIT.md: verdict concerns, status ready, п.1 — смысл `task_id` у `run_plank`.

## Чего не хватило
- В SPEC — смысла существующего параметра `run_plank.task_id` (докстринг acceptance.py:2056-2061).
