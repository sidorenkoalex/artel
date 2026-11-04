# Записка spec_auditor — 01M6HVPMYY2Q56JZ64KD28FTWK (аудит SPEC 09b9c73, седьмой визит)

## Выяснено
- Возврат №6 (ANSWER-3, Б2, пп. 1–6) перенесён в SPEC 09b9c73 полностью.
- main сдвинулся до 5e57eab67, но файлы ссылок SPEC с 19fca3ecc не менялись.
- Pid lease = os.getpid() процесса auto (lease.py:128) — совпадает с pid детали «auto старт» по требованию 11.
- Деталь «auto старт» читает только tests/test_auto_cycle.py:1122-1124; zone_lock.py:217 — только действие.
- Вердикт: pass.

## Не сработало
- `cd … && git` и `ls` в bash отклоняются — git из рабочего каталога без cd.

## Где остановился
- SPEC-AUDIT.md записан (pass, ready); guard прогнан.

## Чего не хватило
- Карточки о том, как мандат покрывает смену ожидаемого литерала в test_integrity (_covering_source :1040).
