# Записка analyst — 01M5MVG2B1YGVPTZWKB18EVGHZ

## Выяснено
- ТЗ достаточно, пишется SPEC (без QUESTIONS).
- Запись строки «оборвана сигналом» — orchestrator/canary.py:3759-3767 (`cmd_canary_run_task`); сейчас исключение записи → выход с кодом 1 без строки.
- PARALLEL_STOP_GRACE_SEC = 60 (canary.py:3423), GROUP_TERMINATE_GRACE_SEC = 3.0 (liveness.py:50): 3×3×5+3 = 48 < 60.
- Помощники: `read_grandchild_pid` tests/test_canary_parallel_protection.py:260, `run_cli` :281; тесты гонки — там же :475 (утверждение :500) и tests/test_canary_parallel.py:361 (утверждение :382). `_GRANDCHILD` — :55.
- tests/ и docs/codebase-map.md — общие зоны (config.COMMON_ZONES), сигнал деления по файлам не срабатывает; budget 30 < SPLIT_SIGNAL_BUDGET_USD 60.

## Не сработало
- Bash `ls`/`cat` в каталоге документов недоступны в шаге — читать через Read.

## Где остановился
- SPEC.md написан (7 AC, матрица неослабления по 2 тестам и помощникам `run_cli`/`read_grandchild_pid` класса `_ProtectionSandbox`), status: ready, guard: ок.

## Чего не хватило
- Формат «Матрицы неослабления» искал в docs/operator-gates.md:53-96.
