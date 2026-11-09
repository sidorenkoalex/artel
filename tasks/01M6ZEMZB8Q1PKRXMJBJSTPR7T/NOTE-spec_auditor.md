# Записка spec_auditor — 01M6ZEMZB8Q1PKRXMJBJSTPR7T

## Выяснено
- Места SPEC подтверждены: acceptance.py:72-93 (_pytest_env), :190-213 (_own_env), :147 _place_env, :4569 place_env, config.py:131 VENV_DIR, stack.py:629.
- two_sided.py:304 зовёт `acceptance.place_env(profile)` БЕЗ run_dir — cwd прогона там неизвестен; файл вне зон SPEC.
- tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py:84 подменяет `acceptance._pytest_env` функцией без аргументов — смена сигнатуры `_pytest_env` его сломает.
- Опыт (tmp): venv-бинарь — symlink, realpath у двух venv одинаков (подтверждено); путь в префиксе — тем написанием, каким найден модуль (/private/var/...), а sys.prefix — /var/... (не realpath); имя `m.cpython-313.opt-1.pyc` у -O; усечённый .pyc с целым заголовком в префиксе роняет импорт (EOFError, rc 1).
- Противоречие: треб. 1 «повреждён — собирает заново» против треб. 3/AC-6 «повреждён — пустой префикс».

## Не сработало
- sed/cat через Bash с cd отклоняются — читать Read-ом.

## Где остановился
- Вердикт fail, SPEC-AUDIT.md записан (status: ready), guard: ок. Шаг закончен.
- Главные пункты возврата: А1 (повреждён — пересборка или пустой префикс), Г1 (two_sided.py:304 вне зон), Д1/Д2 (ловушки существующих тестов, настоящий каталог шаблонов), Е1 (шаблон записываем тестами роли — подмена байткода pytest для гейтов).

## Чего не хватило
- Список тестов, подменяющих `acceptance.subprocess.run` целиком, искал grep-ом по tests/ (12 файлов).
