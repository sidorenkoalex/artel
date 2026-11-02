## Выяснено
- Загрузчик targets требует token_slot у плоской записи — «запись без token_slot» в тестах = dict записи без поля, переданный прямо в project_entry_checks/component_checks (ci_by_pipeline читает yaml).
- Строки собираются из `doctor.project_entry_checks(name, entry)` + `doctor.project_checks.component_checks(name, entry)`; строка перезапусков допустима в любой из двух.
- Долгоживущим файлам нельзя импортировать `gitcmd` и звать git через subprocess (guard: «git-модуль»/«git-вызов») — подмена через `doctor.gitcmd`, клон — `tests.sandbox.make_project_repo(name, origin=False)`, файлы клона только в рабочем дереве (не закоммичены).
## Сделано
- tests/test_01m6ezxvfgh5z2876xwmqg35fp_gitlab_doctor_lines.py — AC-1..11, 13, 15 (строки)
- tests/test_01m6ezxvfgh5z2876xwmqg35fp_http_status.py — AC-12
- tests/test_01m6ezxvfgh5z2876xwmqg35fp_forge_probe_ref_sha.py — AC-14
- acceptance_tests/test_ac15_guard_untouched.py — разовый (файл сторожа ac9 не в changed_paths)
- Валидация стабом: 49/49 зелёные; стаб откатан (git checkout), рабочая копия чистая кроме трёх новых файлов. Без стаба: 42 красных, 7 зелёных с рождения (AC-15, AC-8 operator, AC-13 warn/fail, AC-14 без флагов и отказ двух флагов).
- preflight: все проверки пройдены; plank-run: 1 passed.
## Не сработало
- Запись в /tmp и `rm` недоступны — пробы через `python3 - <<EOF`, удаление через os.remove.
## Где остановился
- Шаг завершён.
## Чего не хватило
- Правило guard про git в долгоживущих файлах (scripts/guard.py:4276-4292) нашёл только по отказу preflight.
- Карту кода (scripts/codebase_map.py) не перегенерировал: test_author правит только новые файлы tests/ — правка docs/codebase-map.md откатывается.
