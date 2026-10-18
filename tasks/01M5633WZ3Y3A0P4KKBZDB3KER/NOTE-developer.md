# Записка developer

## Выяснено
- Правило — `project_profile.long_lived_imports(target, profile)`: None у артели, перечень (или ()) у внешнего; guard `long_lived_errors_from_files(project_imports=…)`, текст — `guard._foreign_import_explanation`.
- preflight НЕ должен открывать БД (`test_01m4p4zp37wv81410ytzhkqc8d_preflight.py::RoleAndDatabaseTest`) — там правило считается по `target` строки, не через `workspace.task_target`.
- Сторож SentryTest сверяет функции guard перехода и preflight — новых функций guard на рубежах не вводить.

## Не сработало
- pytest -n (xdist) в шаге: узлы падают — гонять последовательно.

## Где остановился
- Реализовано, долгоживущие 12 тестов и соседние файлы зелёные, карта регенерирована, PLAN ready.

## Чего не хватило
- Что preflight запрещено звать store.db() — нашёл только по красному тесту.
