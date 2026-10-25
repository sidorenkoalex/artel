# Записка spec_auditor — 01M5SCGSQN0AT0B07H7M9803RA

## Выяснено
- Факты SPEC/ТЗ о коде сверены и подтвердились: config.py:20/34/41/50/769/814, targets.py:152-258, checkpoint.py:1910-2017, doctor/cli.py:101-118/234-237, canary.py:467-471/1215-1218, test_lint.py:13/16/102-108, artel.py:2193, projects.py:44, sandbox.py:1146.
- yamlmini: кавычки в потоковом списке — YamlError (yamlmini.py:189-195); экранирования кавычек нет (yamlmini.py:76-87); `off` — строка, `~` — None.
- Мандат читается только из ANSWER-n (mandate.py:36-38); правка `call` утверждений не теряет — guard.weakened_helpers (guard.py:2345) её не ловит.
- Запись sled пина без поля sandbox (targets.yaml:74-112).

## Не сработало
- Составные bash-команды с `;`/`$W` требуют подтверждения — только `cd <abs> && …`.

## Где остановился
- SPEC-AUDIT.md написан, verdict concerns; guard прогнан.

## Чего не хватило
- Где гейт берёт мандат (ТЗ или ANSWER) — искал в orchestrator/advance_gates/mandate.py.
