# Записка spec_auditor — 01M5NNDYGQ8G6VFDEEXYBB0W3D

## Выяснено
- Счёт подтверждён: 43/13/16/8 тестов, 17/13/16/8 строк «Ловит мутацию», 1728 строк; импортов файлов волны нет (только докстринги tests/sandbox.py:1815, tests/test_doc_commit.py:6 и литерал-путь tests/test_doc_commit.py:94).
- Под ролью `-n auto -p xdist` невозможен: conftest.py:80-86 роняет воркеры xdist (у воркера нет позиционных путей) — воспроизведено: «node down», «no tests ran». Последовательно 4 файла: 80 passed, 55 subtests, 12.7 с.
- Запись вне worktree и каталога документов шагу недоступна (mktemp -d требует подтверждения); подкаталог каталога документов — посторонний (guard.py:3027-3048); копия под tests/ уйдёт в ветку WIP-чекпоинтом (checkpoint.py:1843, `add -A`, путь в зоне).
- Голые `assertRaises(SystemExit)` (tests/test_notes.py:91 и др., test_notes_apply.py:125) против AC-3 «pytest.raises(..., match=…)»; subTest по вычисляемым наборам (config.NOTE_SILENCE_WINDOW_STATES, OUTSIDE_WINDOW, rng) против «parametrize литералами».
- Мандат по пути снимает находки и test_integrity (:1061), и outcome_integrity (:278-300).

## Не сработало
- Bash с `$VAR`, `cd &&`, `cat` вне каталогов — отказ песочницы; работают простые команды из worktree.

## Где остановился
- SPEC-AUDIT.md: verdict concerns, status ready; guard прогнан.

## Чего не хватило
- Знания, что xdist под ARTEL_ROLE отключён сторожем conftest.py — нашёл только прогоном.
