# Записка test_author 01M5KBGK8ZZ3Y8CDBXK6RX68JJ

## Выяснено
- Все AC — факты этой задачи о файле tests/test_suite_run.py → только разовая группа, долгоживущих файлов нет.
- Планка: acceptance_tests/test_gate_argv.py (AC-1..AC-6, красен до реализации), test_diff_scope.py (AC-7, AC-8, зелёный с рождения).
- AC-1/AC-2 — разбор `ast` метода гейта (литерал сверяется через ast.dump с текстом критерия; подмена — декоратор или `with`, охватывающий run_full_suite и литерал; цель патча `acceptance.stack` или `stack`).
- AC-3/AC-6 — запуск методов разработчика через unittest.TestResult под мутантами acceptance._pytest_command (без `-p timeout`, перестановка `no:cacheprovider`; первый элемент `python3`/sys.executable).
- AC-4/AC-5 — тест требования 2 ищется как метод, в тексте которого есть `test_gate_call_argv_unchanged` и `wasSuccessful`; AC-5 подменяет тело метода гейта прежним (копия в планке).
- AC-6 — кандидаты: методы, в тексте которых есть `pytest_python_executable` и `run_full_suite`.
- Проверено стабом в tests/test_suite_run.py: 8/8 зелёные; стаб откатан (git checkout), дерево чистое. Без стаба: 7 красных, 4 зелёных (AC-7, AC-8 и часть subTest). preflight пройден.

## Не сработало
- Первый вариант AC-4 искал литерал `sys.executable` — стаб с `patch.object(stack.sys, "executable", …)` его не содержит; ослаблено до `executable`.

## Где остановился
- Шаг завершён.

## Чего не хватило
- —
