# Записка spec_auditor — 01M5KJNE39PHV9EAWJCHK7QDFS

## Выяснено
- AC-8 называет закрытые `runner._resolve_declared_tools`/`_role_path_dirs`; в долгоживущем файле обращение `runner._x` — признак «закрытый атрибут» линта (scripts/guard.py:3921-3923), импорт `_x` — «закрытое имя» (:3836-3838). Публичные обходы: `runner.declared_tool_path` (runner.py:929), `runner.role_env` (:1091-1113).
- `_role_path_dirs` для python3 берёт каталог sys.executable, не which-путь (runner.py:954) — «содержат каталог каждого объявленного инструмента» буквально ложно для python3.
- guard.py:3849 — строка `signs.append(SIGN_GIT_CALL)` в `_call_signs`; сам `_is_git_command` — guard.py:3767.
- /opt/homebrew/bin/git существует (symlink в Cellar git 2.51.0) — порядок PATH роли: venv, каталог python, git(/usr/bin), gh(/opt/homebrew/bin) — первым git роли остаётся /usr/bin/git.

## Не сработало
- Bash с `;`/`echo`/относительными путями требует подтверждения — только одиночные команды с абсолютными путями, либо Read.

## Где остановился
- SPEC-AUDIT.md сдан: status ready, verdict concerns (7 пунктов: AC-8 закрытые имена vs линт; AC-8 python3; изоляция отрицательных случаев; пропуск AC-7 без условия «первый git не /usr/bin/git»; AC-7(а) обходится самовызовом в тесте; адреса runner.py:905→907, guard.py:3849→3767; AC-5 зависит от настоящего /usr/bin/git). guard.py на файле — ок.

## Чего не хватило
- Где линт долгоживущих файлов перечисляет признаки: scripts/guard.py:3668-3696, long_lived_sign_hits :3885.
