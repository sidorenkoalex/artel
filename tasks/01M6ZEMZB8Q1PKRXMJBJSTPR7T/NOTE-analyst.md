# Записка analyst — 01M6ZEMZB8Q1PKRXMJBJSTPR7T

## Выяснено
- `_pytest_env()` (acceptance.py:72) без аргументов, интерпретатор не знает; знает `_place_env(command, run_dir)` (:147), публичный псевдоним `place_env` (acceptance.py:4569). `_own_env` (:190) зовётся ещё из :632.
- Залоченный `tests/test_01m3y7g6t3mk7a899521vf9n7b_pycache.py`: `FakeRun` подменяет `acceptance.subprocess.run`, вызовы с элементом `"pytest"` в argv перехватывает и требует РОВНО ОДИН такой вызов (стр. 107-110). Сборка шаблона через `subprocess.run([py, "-m", "pytest", …])` его покраснит; `[py, "-c", …]` уходит в REAL_RUN.
- `config.VENV_DIR = ROOT/.artel/venv` (config.py:131): venv пульта ПОД `config.ROOT`, поэтому `config.ROOT` целиком из шаблона исключать нельзя — пропадёт pytest/xdist/pluggy. Исключаются cwd прогона, `config.WORKTREES`, `config.PROJECTS`.
- HOME роли = `.artel/home` под ROOT — место шаблонов нельзя выводить из HOME.
- Бинарь python3 в venv — симлинк на базовый интерпретатор: realpath одинаков у разных venv, поэтому в ключ добавлен `sys.prefix`.

## Не сработало
- Замер `compileall` по путям интерпретатора не сделан: составные команды Bash в шаге требуют подтверждения.

## Где остановился
- SPEC написан (13 AC, budget 50, монолит), status: ready; `scripts/guard.py` — ок.

## Чего не хватило
- Замера цены полной копии шаблона на `compileall` всех путей интерпретатора — из-за него выбран шаблон по пробному прогону (меньше файлов в копии).
