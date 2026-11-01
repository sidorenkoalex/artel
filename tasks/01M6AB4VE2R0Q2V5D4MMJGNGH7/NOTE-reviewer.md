# NOTE-reviewer (итерация 1)

## Выяснено
- Прогоны: 6 файлов задачи — 102 passed; планка — 1 passed; приложение к test_invariants применяется (`git apply --check`).
- Мандаты ANSWER-1..3 на правки существующих тестов соблюдены точно.
- R1-F1 (major) воспроизведён: `mr_sync._diff_sign` на файле в cp1251 → UnicodeDecodeError мимо GitFailure (`_git` ловит только OSError).
- R1-F2..F4 — minor: прямой subprocess.run без срока в `_apply_passes`; нет точки ответвления → тупик «неизвестно»; повтор AC-14 в test_mr_sync_units.

## Не сработало
- —

## Где остановился
- REVIEW.md итерации 1 записан, status: changes_requested.

## Чего не хватило
- Ничего существенного; пакет был полным.
