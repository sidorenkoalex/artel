# Записка spec_auditor — 01M6TT4FKD1JWSJFVJ7328K03Y (аудит 2, spec_sha dd14a9f1)

## Выяснено
- Все 10 отклонений аудита 1 закрыты по ANSWER-1; хук в зонах; факты SPEC о коде подтверждены.
- Остаток (concerns): SPEC 3 «ждать до потолка» против SPEC 7 «прежний отказ» (эскалация сразу) для негодного задания базы (canceled, allow_failure, «отчёт не разобран» — у головы проходяще, outcome_integrity.py:1096-1097).
- `gitcmd.diff_base` считает базу от origin/main (gitcmd.py:1977, config.MAIN_BRANCH), а проверка предка — от origin/<base>: при base≠main отправка базы не пройдёт.
- Проверка предка читает локальный refs/remotes/origin/<base> клона, пульт его перед проверкой не обновляет (gitcmd.py:1943-1948) — PLAUSIBLE обход ответа 7.
- Очередь по журналу: `store.steps_of_action` (store.py:1529) — правка store.py не нужна.

## Не сработало
- `cd … && python3 …` в Bash отклонён («simple_expansion»); guard прогнан абсолютным путём — ок.

## Где остановился
- SPEC-AUDIT.md: verdict concerns, status ready, guard ок.

## Чего не хватило
- Может ли роль в своём шаге сдвинуть refs/remotes/origin/<base> клона (role_git) — не проверял.
