# Записка spec_auditor — 01M6KBD9FC36WARWSY9Z0JDMG5

## Выяснено
- `project_profile.component_profiles` (project_profile.py:472) через `_with_component_fields` ставит `from_components=True` и записи `test_profile` (компонент `default`) → `in_outcome_bounds` истинно при `report`; гейт tests_writing такие записи считает вне границы. Строка doctor по букве SPEC даст ложный warn с невозможной подсказкой `description.components.default.failure_errors`.
- `targets.layers()` (targets.py:250) читает только файл `local_path()`; «layers() на новом тексте до записи» буквально не исполнить без подмены config/временного файла. Образец сверки без записи — `projects._migrate_mismatches` (projects.py:329) через `merge_local`.
- yamlmini молча роняет строки-комментарии с отступом и хвостовые `  # …` (yamlmini.py:35, :126) — отказ «строка, начинающаяся с #» их не ловит.
- Нет отказа на несуществующий компонент `<к>` в `description.components.<к>.<поле>` — путь добавить компонент (вне объёма).
- `project_entry_checks` — project_checks.py:37, не :31; notes.py:414 — без `target=` (сигнатура store.py:1610 его держит).

## Где остановился
- SPEC-AUDIT.md записан, verdict concerns.

## Чего не хватило
- Не нашлось готового шва часов для AC-2 (одна секунда) — тест вынужден будет патчить источник времени.
