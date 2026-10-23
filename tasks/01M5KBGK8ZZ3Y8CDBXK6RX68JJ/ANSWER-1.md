---
task: 01M5KBGK8ZZ3Y8CDBXK6RX68JJ
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

# Мандат Оператора (решение 23.10.2026)

Ослабление тестов разрешено: tests/test_suite_run.py::GateArgvTest::test_gate_call_argv_unchanged

Основание: решение Оператора 23.10 по находке ревизии CR-2026-10-22-20 — ожидание argv становится литералом при подменённом acceptance.stack.pytest_python_executable; правка усиливает тест.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| tests/test_suite_run.py::GateArgvTest::test_gate_call_argv_unchanged: ожидание — литерал вместо вызова _pytest_command | прогон гейта по умолчанию без флагов suite-run и с прежним порядком путей — tests/test_suite_run.py:345 | да | tests/test_suite_run.py (AC-1) | ок |
| tests/test_suite_run.py::GateArgvTest::test_gate_call_argv_unchanged: литерал называет каждый элемент общей части команды pytest | общая часть команды pytest не меняется незаметно — не держит (ожидание собирала та же функция) | да, усиливается | tests/test_suite_run.py (AC-3) | ок |
| tests/test_suite_run.py::GateArgvTest::test_gate_call_argv_unchanged: stack.pytest_python_executable подменён значением | первый элемент argv — интерпретатор от stack.pytest_python_executable — tests/test_suite_run.py:345 (косвенно) | да | tests/test_suite_run.py (AC-6) | ок |
| tests/test_suite_run.py::GateArgvTest::test_gate_call_argv_unchanged: подмена снимает зависимость от интерпретатора процесса | вердикт не зависит от имени интерпретатора и вида копии — не держит | да, усиливается | tests/test_suite_run.py (AC-4) | ок |
| tests/test_suite_run.py::GateArgvTest::test_gate_call_argv_unchanged — единственный изменяемый метод | остальные методы файла и код пульта не меняются — ревью | да | tests/test_suite_run.py (AC-7) | ок |

Независимая проверка: матрица проверена независимым проверяющим ТЗ 23.10 — все строки верны, правка усиливает тест и ничего другого не трогает.
