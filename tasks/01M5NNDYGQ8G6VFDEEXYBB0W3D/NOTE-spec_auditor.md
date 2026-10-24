# Записка spec_auditor — 01M5NNDYGQ8G6VFDEEXYBB0W3D (круг 2, spec_sha 76b102eb)

## Выяснено
- `orchestrator/mutation_run.py` есть на origin/main 4e1c8a18 и в пине пульта (корень пульта на 4e1c8a18), но НЕТ в базе ветки 16f9ab43 — не мешает: команда исполняется кодом пульта (config.ROOT), не рабочей копией.
- `mutation-run` разрешён роли: origin/main orchestrator/artel.py:2189-2192 `_ROLE_ALLOWED_COMMANDS`.
- Таблица пишется в `config.LOGS/suite-run/<id>/<id>-mutation-run-<n>.mutations.tsv` (mutation_run.py:122-123, suite_lock.py:40-44). Шаг на Claude её НЕ читает: Read `.artel/logs/suite-run/lock.json` — «requested permissions… haven't granted»; `--add-dir` суiте-каталога есть только у Codex (suite_lock.py:41-43). `--wait` печатает только сводку (mutation_run.py:691-696).
- Узлы: junit → `path::Class::method` (reporters/outcome.py:106-133) — форма требования 8 подтверждена.
- classify (mutation_run.py:379-397): любой FAILED → «убита». Ошибка в unittest setUp под pytest — FAILED; в pytest-фикстуре — ERROR → «ошибка сбора, импорта или setup». SchemaTmpRootTest.setUp зовёт store.create_schema (tests/sandbox.py:1819-1821).
- Тесты импортируют orchestrator на уровне модуля → ломка импорта = COLLECTION, не «убита».
- guard: скрытые файлы (`.`-префикс) в каталоге задачи — посторонние (guard.py:3040-3041).

## Где остановился
- SPEC-AUDIT.md готов: verdict concerns, status ready; guard (artel.py guard) — ок.
- Отклонения: (1) роль на Claude не может прочитать/приложить таблицы mutation-run; (2) падение unittest setUp = «убита», а в фикстуре = «ошибка setup».

## Чего не хватило
- Знания, где роль берёт таблицу mutation-run: в коде канала нет, нашёл проверкой прав чтения.
