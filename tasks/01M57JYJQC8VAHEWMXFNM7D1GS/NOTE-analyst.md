# Записка analyst

## Выяснено
- Планка выкладывается в `<code_dir>/tasks/<id>/acceptance_tests/` (`acceptance.materialize_from_branch` :929, `plank_in_code_copy` :1146 с уборкой `drop_from_code_copy` в finally).
- У pytest-own прогоны (`run` :600, `collect` :737, `run_plank` :1166) идут из `workdir` с путями, переведёнными `_own_target`; rootdir pytest берётся от общего предка аргументов → планка вне workdir видит конфиг артели/корня, не `backend/pyproject.toml`.

- Все прогоны планки идут через `acceptance.run`/`collect`/`run_plank` (вызывающие: advance_gates/acceptance.py:405, tests_writing.py:573, pull.py:668, amend.py:550/725, plank_run.py:227/241) — правка в этих трёх функциях покрывает всё, вызывающие вне зон трогать не нужно.
- Двусторонний прогон (`advance_gates/two_sided.py`) гоняет узлы `tests/` из «Меняемого поведения», не планку — в «Не входит».
- Выбор способа: выкладка в подкаталог `long_lived_dir` на время прогона. `--rootdir`/`-c`/`confcutdir` не дают фикстур: conftest.py действует только на тесты в своём каталоге.
- Риск: чекпоинт коммитит `git add -A` (checkpoint.py:1796), файлы под long_lived_dir для developer считаются своими (own_long_lived) → остаток после SIGKILL попал бы в коммит. Отсюда требование «остаток игнорируется git и убирается `drop_from_code_copy`» (runner.py:1218 зовёт его на старте шага).

## Не сработало
- Первый прогон guard: `orchestrator/runner.py` упомянут, но не классифицирован. Добавил его в «Не входит» как «только чтение».

## Где остановился
- SPEC.md написан, status: ready, budget 35 (рамка ТЗ), 8 AC, монолит обоснован. guard ок.

## Чего не хватило
- Дольше всего выяснял, ловит ли чекпоинт остаток выкладки под long_lived_dir: ловит (`checkpoint.py:1796`, `git add -A` + own_long_lived). Готовой карточки на эту тему нет.
