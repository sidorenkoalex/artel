# Записка developer 01M5KBGK8ZZ3Y8CDBXK6RX68JJ

## Выяснено
- Правка только tests/test_suite_run.py (+ карта): метод гейта под одной подменой `acceptance.stack.pytest_python_executable`, ожидание — литерал из SPEC; новые классы `GateArgvInterpreterIndependenceTest` (git init + worktree add во временном каталоге, подмены `_MODULE_ROOT`/`VENV_DIR`/`stack.sys.executable`) и `GateArgvInterpreterSourceTest` (первый элемент argv).
- `tests/test_suite_run.py`: 19 passed; plank-run: 8 passed.
- Временные мутации acceptance.py (первый элемент `python3`; без `-p timeout`) краснят соответствующие тесты; файл возвращён `git checkout`.
- Мандат на смену утверждения — ANSWER-1.

## Не сработало
- Запись в /tmp для бэкапа отклонена — откат мутаций через `git checkout -- <файл>`.

## Где остановился
- Шаг завершён, PLAN.md status: ready.

## Чего не хватило
- —
