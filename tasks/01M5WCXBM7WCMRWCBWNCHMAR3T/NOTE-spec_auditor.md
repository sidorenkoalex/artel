# Записка spec_auditor

## Выяснено
- Строки ci.py из SPEC сходятся (204/250/341-344/977/1074/1100/1115/1155/1247/1282/1422/1532/1609/1636/1679); targets.py:29 SUPPORTED_FORGES, :270 unsupported_reason — да.
- `policy.ci_required_jobs` неизвестен загрузчику: targets.py:330-334 (LOCAL_FIELDS["policy"]) — merge_local отказывает «неизвестное поле» (:441), `_flatten` (:585-588) его не переносит. targets.py вне зон SPEC.
- `token_slot` обязателен (targets.py:38, check :624-626; machine :335) — «запись без token_slot» из AC-3 через targets.target недостижима; gitcmd.hosting_token (:121) на записи без слота даёт (None, None) — «прежняя авторизация», не отказ.
- Сторож А0 (tests/test_01m5w27…:453) ловит только Compare с литералом; сравнение с `targets.FORGES[1]` или выбор без реестра он не видит; у требования 1 (реестр) нет своего AC.
- github: ci.verifying_status ставит running раньше red (ci.py:1034-1045), `action_required` там — red (GREEN :27); forge github по SPEC — red раньше running, action_required → unknown. Это из ТЗ, не отклонение.

## Не сработало
- `cd … ;` в Bash требует подтверждения — работать относительными путями без cd.

## Где остановился
- SPEC-AUDIT.md сдан: status ready, verdict concerns (Д-1 реестр без AC, Д-2 ci_required_jobs вне схемы targets.py, Д-3 старшинство итогов, Ф-2 hosting_token (None,None), О-2 сторож AC-17 и импорты); guard.py — ок.

## Чего не хватило
- Схемы полей `policy` записи проекта в карте — искал в targets.py LOCAL_FIELDS.
