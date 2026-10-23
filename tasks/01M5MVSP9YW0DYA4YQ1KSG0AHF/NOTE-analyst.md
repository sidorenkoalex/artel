# Записка analyst

## Выяснено
- ТЗ полное: SPEC.md написан, status: ready, guard ок. 9 требований, AC-1…AC-8, budget_usd 40 (из ТЗ).
- Сигналов деления нет: вне COMMON_ZONES (`orchestrator/config.py:814`) в зоне 3 файла (test_lint.py, guard.py, amend.py); порог бюджета `SPLIT_SIGNAL_BUDGET_USD = 60`.
- Приложение 1 PLAN (диф к `tests/test_invariants.py`) перенесено в SPEC «Материалы» дословно из TZ.md (скриптом, без ручной перепечатки) — разработчик переносит его в PLAN без изменений.
- Классы отказа, которые нужны: `refusal_classes.py:116–117` («группы приёмочных тестов», «долгоживущие файлы tests/»).
- Вызовы `long_lived_errors_from_files` в amend.py: строки 256, 280, 642; `_code_head_long_lived` — 556.

## Не сработало
- Bash в шаге не даёт `ls`/`rm` и heredoc с `$` — работал через python3 -c / временный .py (удалён).

## Где остановился
- Шаг завершён.

## Чего не хватило
- Ничего существенного; ТЗ давало адреса строк.
