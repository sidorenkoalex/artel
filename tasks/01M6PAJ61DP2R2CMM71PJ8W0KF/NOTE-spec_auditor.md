# Записка spec_auditor

## Выяснено
- Визит 6 (spec_sha ad48adbc): решения №5.1–5.5 внесены в SPEC; якоря верны (cli.py:224/226, :305-331; __init__.py:152-155; lease.py:399-416; acceptance.py:156; test_doctor_closed_ref_fix.py:152-195, :177-183; test_doctor.py:1040-1043; stale_cycles.py:42; targets.TargetsError :180).
- role_env (runner.py:1246-1361) от раннера не зависит — AC-1 зелёный с рождения.
- Опыт (tmp, без Docker): после os.killpg по пределу os.getpgid(<pid зависшего>) → ProcessLookupError; дочерний процесс снят. AC-2/AC-3 «getpgid ≠ getpgrp» после завершения строки неисполним на верной реализации.
- SPEC части 1 (refs/artifacts/01M6PAJ61D4PYAP79ADRPA6MWV): COMPOSE_TEARDOWN_TIMEOUT_SEC — в orchestrator/config.py (треб. 8, 9), а не в acceptance; помощник окружения — «требования 6–7» (7 — отказ в процессе роли).
- Вердикт: concerns (Д1 getpgid; Д2 модуль константы; Д3 строки doctor в процессе роли не заданы; Д4 «все прочие починки» против образца без _fix_canary_live).

## Не сработало
- heredoc в Bash отклоняется парсером — временный скрипт писать файлом и убирать task-rm.
- Docker в шаге не запускал сознательно (решение №4.1).

## Где остановился
- SPEC-AUDIT.md записан (status: ready, verdict: concerns, Д1, Д1-бис AC-3 без снятия группы, Д2–Д4), guard — ок.

## Чего не хватило
- Текста SPEC части 1 в брифе — читал git show refs/artifacts/<id части 1>.
