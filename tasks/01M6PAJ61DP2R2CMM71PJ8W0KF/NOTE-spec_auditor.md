# Записка spec_auditor

## Выяснено
- Якоря SPEC верны: runner.py:1186/1246/1364, doctor/__init__.py:152-155, cli.py:305-331, test_doctor_closed_ref_fix.py:152-195, sandbox.py:1639-1641.
- Часть 1 не в main: в acceptance.py нет docker, в targets.PROFILE_RUNNERS нет compose (targets.py:83).
- run_agent_once ловит из role_env только OSError (runner.py:1819-1827).
- Опыт: os.replace непустого каталога на непустой → Errno 66 (macOS).
- Вердикт concerns, 11 отклонений (Д1–Д11) в SPEC-AUDIT.md.

## Не сработало
- Проверить Docker CLI опытом нельзя: в окружении шага нет docker.

## Где остановился
- SPEC-AUDIT.md написан, status: ready; guard прогнан.

## Чего не хватило
- Публичных имён помощников части 1: их SPEC тоже ещё на аудите.
