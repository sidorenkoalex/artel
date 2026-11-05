# Записка spec_auditor

## Выяснено
- Визит 2 (spec_sha b9bc04bb): решения гейта 1–10 сняли Д1–Д11 прошлого аудита.
- Якоря верны: runner.py:1246/1819-1827, doctor/cli.py:221-226/305-331, __init__.py:152-155, test_doctor_closed_ref_fix.py:152-200, sandbox.py:1639-1642, lease.py:399-416.
- role_env с task_id зовётся только из runner.py:1820; песочничные тесты cmd_doctor(fix=True) без compose — skip.
- Вердикт concerns, Д1–Д7: каталоги версий в compose_role_dir и обход doctor; формат `compose version`; распознавание отказа config; компоненты в строке записи; испорченные метки → ValueError в process_alive; окружение пропуска AC-6; DOCKER_HOST tcp:// пульта.

## Не сработало
- Docker в окружении шага нет; системные пути (/usr/bin/which, /bin/test) отклоняются — опыт с Docker CLI невозможен.

## Где остановился
- SPEC-AUDIT.md написан (status: ready), guard прогоняется.

## Чего не хватило
- Нормальной оболочки: ls/cd в каталог документов отклоняются, читать только Read/git grep.
