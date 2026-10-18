# Записка spec_auditor — 01M58FNWBV25FF26E7AZ9Q9912

## Выяснено
- `targets.yaml` разбирает `orchestrator/yamlmini.py` (`targets.load`, targets.py:111): нет блочных списков `- `, потоковых отображений `{}`, вложенных списков `[[ ]]`, кавычек в потоковом списке (yamlmini.py:16-20, 147-148, 177-195). `components:` (список отображений), `depends_on`, `install: [[...]]`, regex `paths` с `[...]`/кавычками в файл не записать. `yamlmini.py` не в зонах ТЗ/SPEC и делится с guard — главная находка (fail).
- `suite_tree_hash` (acceptance.py:2029-2078) — git write-tree рабочего дерева: отслеживаемые lock-файлы (у sled `backend/uv.lock`, `frontend/package-lock.json` — в no_paths, т.е. в git) уже входят в `tree` ключа; AC-12 по lock-файлу через смену дерева проходит и без правки.
- `profile_of` читают вне `decide`: acceptance.py:2393 (`_task_own_profile`, вне разрешённой части acceptance.py), suite_run.py:278 (вне зон), project_profile.full_suite_limit:181 и doctor/cli.py:13. SPEC не говорит, что они делают с записью из нескольких компонентов.
- Формы новых полей (tools "22 (frontend/.nvmrc)", test_support — глоб, paths — regex, knowledge — список, install/checks_local — список списков в ADR) в SPEC не заданы.

## Где остановился
SPEC-AUDIT.md записан, verdict fail.

## Чего не хватило
Сразу не видно, что targets.yaml читает не PyYAML, а yamlmini с узким подмножеством — нашёл по targets.py:8.
