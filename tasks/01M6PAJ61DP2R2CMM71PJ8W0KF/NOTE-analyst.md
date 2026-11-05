# Записка analyst

## Выяснено
- Итерация 8 (шестой возврат, решения №6.1–№6.4) внесена в SPEC; AC по-прежнему три.
- №6.1: os.getpgid после killpg убран из треб. 17, AC-2, AC-3; группа — только записанная подменённым docker; любой зависший вызов порождает дочерний процесс, после предела тест утверждает «дочерний не жив» (AC-2: ps/network ls/context inspect/down; AC-3: строка записи).
- №6.2: предел down — config.COMPOSE_TEARDOWN_TIMEOUT_SEC (orchestrator/config.py, SPEC части 1 треб. 8, 9); исправлены «Контекст», треб. 14, 17, «Не входит», «Материалы».
- №6.3: runner.in_role_environment() (runner.py:1364-1381: ARTEL_ROLE или HOME == дом роли) — обе строки skip «в шаге роли Docker не вызывается»; тесты прочих случаев без ARTEL_ROLE/дома роли.
- №6.4: подмена починок по test_doctor_closed_ref_fix.py:154-160 + :177-183, включая _fix_canary_live (cli.py:322).

## Не сработало
- —

## Где остановился
- SPEC.md status: ready, guard ок.

## Чего не хватило
- —
