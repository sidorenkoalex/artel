# NOTE-reviewer (итерация 1)

## Выяснено
- Планка 10/10 зелёная (`plank-run`); долгоживущие файлы задачи + `tests/test_targets_rerun_ban_wrapper.py` + labelled_gates + outcome_gate — 59 passed.
- Код по требованиям 1–10 соответствует SPEC; дефектов корректности не найдено.
- Все четыре файла планки — `Группа: разовый`; долгоживущие `tests/` задачи покрывают только AC-4/13/14 и AC-11/12.
- Временная мутация (убран `head += NO_RERUN_PLUGINS_ARGS`, `no_rerun_plugins` в ключе, `_FILE_PATH_TOKEN_RE` в `_component_covered` → прежний `any(...)`, `GATE_TEMP_PREFIXES` из `_orphan_temp_dirs`) — 9 файлов `tests/` этих модулей зелёные (76 passed). Требования 1–2, 5–6, 8 после мержа без сторожа → R1-F1 major.

## Не сработало
- `pytest -n 4` со списком файлов роняет воркеры; гонять с `-p no:xdist`.

## Где остановился
- REVIEW.md итерации 1 записан: changes_requested, R1-F1.

## Чего не хватило
- Нет готового перечня «какие AC закрыты только разовой планкой» — собирал через `git grep Группа` по refs/artifacts.
