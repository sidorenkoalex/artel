# Записка spec_auditor

## Выяснено
- Визит 4 (spec_sha dab3dd67): решения №3.1–3.7 и ANSWER-1 (без `-v`, возраст по имени) внесены в SPEC.
- Якоря верны: runner.py:1186/1246/1364/1819-1827, doctor/cli.py:221-226/305-331, __init__.py:152-155, lease.py:399/409/414, acceptance.py:156, sandbox.py:1639-1641, :676-704 (isolate_keychain_and_role снимает ARTEL_ROLE), test_doctor.py:1040-1043, test_doctor_closed_ref_fix.py:152-195.
- Опыт: os.replace ссылки поверх ссылки на каталог — проходит; поверх непустого каталога — Errno 21.
- Вердикт concerns, Д1–Д7: Д1 разбор Labels по запятой падает на чужих стендах с несколькими -f (config_files через запятую); Д2 единица времени в имени `.v<нс>` не закреплена критерием сборки; Д3 start_new_session без утверждения; Д4 Docker Desktop делит /Users — доступ роли к Docker шире «власти над ВМ»; Д5 проба AC-6 без предела; Д6 неразбираемые записи compose_role_dir и «Docker не отвечает» при уборке каталогов не заданы; Д7 живость только по pid не ловится.

## Не сработало
- docker в шаге требует подтверждения — опыт с CLI невозможен.

## Где остановился
- SPEC-AUDIT.md записан (status: ready, verdict: concerns), guard ок.

## Чего не хватило
- Опыта с Docker CLI в шаге; чтения настоящего `.artel/targets.yaml` (вне каталогов шага).
