# Записка spec_auditor — 01M5T79C5GFJGQ9XCTH8W0PDFQ

## Выяснено
- SPEC-AUDIT.md сдан: status ready, verdict concerns, spec_sha 567b5b84…; guard — ок.
- Главное: `TmpRootTest` патчит глобальный `subprocess.run` (`tests/sandbox.py:1682`). Места 2, 3, 5, 6, 7 через него уже идут; место 3 получает от `SpyRun` код 1 (`sandbox.py:1268`, `:1354`). Поэтому фраза AC-9 «не уходит в заглушку» для этих мест невыполнима вместе с AC-3: `external_brief.py:236-250` и `test_outcome_gate_module.py:2525` подменяют `subprocess.run`.
- Места 1 и 4 должны остаться на `Popen` (под `SpyRun` `write-tree` фейкуется). `carpentry` для места 1 не годится: нет срока, нет `-C`, идёт через run.
- `test_outcome_gate_module.py:2525` требует, чтобы в `outcome_integrity.py` остался `import subprocess`.
- `RealGitSandbox` (`sandbox.py:1897`) не вызывает `TmpRootTest.setUp`, поэтому `SpyRun` в тестах кэша и брифа нет.
- Открытые вопросы Оператору: OSError места 1 (сейчас выходит из `suite_tree_hash` наружу); `TimeoutExpired` при запуске `Popen` у места 4 → сейчас `SOURCE_FAILED`, не `DEADLINE` (`reference_cache.py:355`).

## Не сработало
- `cd …; grep/sed` в одной команде отклоняется правами — пиши абсолютные пути, команды по одной.

## Где остановился
- Аудит закончен, артефакт сдан.

## Чего не хватило
- Дольше всего выяснял, какие песочницы на деле ставят `SpyRun`: `RealGitSandbox` переопределяет `setUp` целиком, по имени класса этого не видно.
