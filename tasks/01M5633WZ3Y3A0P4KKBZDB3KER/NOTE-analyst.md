# NOTE analyst — 01M5633WZ3Y3A0P4KKBZDB3KER

## Выяснено
- ANSWER-1: 1A (подполе `test_profile.long_lived_imports`), 2A (без подполя — прежнее правило + подсказка о подполе в тексте отказа у внешнего проекта), 3B («закрытое имя» не трогаем). Зоны расширены на orchestrator/targets.py, orchestrator/project_profile.py. Матрица требует два критерия: неверный тип подполя — отказ проверки записи / запись без подполя — прежний исход; у артели правило и тексты прежние.
- Правило: `scripts/guard.py:2612-2614` `_allowed_import_tops()`, `_import_signs` `:2709-2730`, `long_lived_sign_hits` `:2785` без параметра проекта; текст — `_SIGN_EXPLANATIONS[SIGN_FOREIGN_IMPORT]` `:2597-2598`.
- Рубежи: tests_writing.py:351, 470; preflight.py:186, 203 (`network_addresses` из :259); amend.py:512 (профиль есть: `profile or _task_profile`).
- `targets.PROFILE_FIELDS`/`PROFILE_OPTIONAL` targets.py:43-60; `Profile` project_profile.py:63-90.
- Признаки п.2: «git-модуль» — модули пульта, у внешнего молчит; «git-вызов», tasks/, номер задачи, sys.path, patch закрытого, закрытый атрибут — применимы без правок.

## Не сработало
- (прошлый шаг) чтение клона sled — вне рабочего каталога.

## Где остановился
- SPEC.md написан (8 AC, budget 30, status: ready), guard ок; QUESTIONS.md удалён.
- Сигналы объёма (файлов ≥5, budget ≥30) — в SPEC материал для монолита, решение Оператора на гейте.
- Трактовка: перечень проекта добавляется к прежнему набору (orchestrator/scripts не изымаются — в «Не входит»).

## Чего не хватило
- Ничего нового.
