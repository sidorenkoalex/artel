# Записка spec_auditor

## Выяснено
- Визит 8 (spec_sha 711cfbf7): решения №7.1, №7.2 внесены; Д1/Д2 визита 7 сняты.
- Якоря верны: cli.py:221-226, :305-331 (:322 `doctor._fix_canary_live`); __init__.py:152-159; runner.py:1364-1381; acceptance.py:156; lease.py:399/408/414; test_lint.py:75-94; test_doctor_closed_ref_fix.py:154-162 (уводит canary._live_dir), :177-183.
- Опыт (tempfile.mkdtemp, python3 -c, 40 запусков): после killpg(SIGKILL)+wait() пробы os.killpg(pgid,0) отвечают PermissionError (EPERM) в 35/40, 1–116 проб подряд, до 0,33 мс; затем ProcessLookupError, и os.kill(дочерний,0) → ProcessLookupError 40/40. Правило №7.1 «до ProcessLookupError» молчит об EPERM: либо исключение наружу, либо ранний выход. liveness.py:75-86 `_group_exists` уже трактует EPERM как «группа есть».

## Не сработало
- Heredoc в Bash отклоняется парсером; Write в /tmp — нет прав; `ls` нет в PATH; `$?` в команде отклоняется. Опыт — `python3 -c '…'` с tempfile.

## Где остановился
- SPEC-AUDIT.md записан: status ready, verdict concerns (Д1 EPERM в пробах группы — дефолт: EPERM = группа есть; Д2 число проб не задано — дефолт ≥100000); guard — ок.

## Чего не хватило
- Текста SPEC части 1 в брифе (требование 6, правило PATH) — `git show refs/artifacts/01M6PAJ61D4PYAP79ADRPA6MWV:tasks/…/SPEC.md`.
