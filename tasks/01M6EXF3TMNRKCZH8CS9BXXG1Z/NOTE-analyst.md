# Записка analyst — 01M6EXF3TMNRKCZH8CS9BXXG1Z (GitLab Б2.3), шаг 2 (возврат аудита 1 из 2)

## Выяснено
- Аудит fail, 12 пунктов. Закрываю правкой SPEC, без нового батча.
- gitcmd: три места fail-open — in_flight_refusal :768-775, _push_plan :956-961, in_repo :1242-1245. Сужение in_repo: отказ только для проекта не-артели под белым списком/с непрочитанной записью (прецедент gitcmd.py:928-932 «гейт мержа неизвестен»).
- Клоны уже имеют core.hooksPath = <ROOT>/scripts/git-hooks (workspace.set_clone_hooks :68; doctor clone-hooks warn git_hooks.py:148). Общий pre-push пропускает всё при ARTEL_PULT_GIT=1 (:14). Правила target-human — в хуке, который git реально вызывает; маркер их не снимает.
- -c core.hooksPath в gitcmd НЕТ — новое требование (сужено до клона target-human).
- Выбор по forge в doctor — через реестр forge (прецедент misc_checks.check_base_branch :91-140, IMPLEMENTATIONS.get), без литералов и без новых EXEMPT ac9.
- project-token зовёт `gh auth token` (project_checks.py:211-246) — для gitlab сверку с токеном gh не делать.
- Хук doctor-строка и --fix перенесены в часть 2 (зона doctor/git_hooks.py), клон подмодулей — в часть 2 (workspace.py); часть 3 больше не зависит от части 2.

## Не сработало
- —

## Где остановился
- SPEC.md переписан под 12 пунктов аудита, status: ready, guard ок, деление разбирается на 4 части. Добавлен раздел «Матрица неослабления» (8 строк). people_entry: сбой чтения → отказ для любой не-артели (прецедент gitcmd.py:928-932). Рамки 40/40/40/25 = $145 — подтверждение Оператору на гейте. Шаг завершён.
- guard отказывал на «orchestrator/» и misc_checks.py без классификации — исправлено («Не входит»).

## Чего не хватило
- Число рамки в ANSWER-1 п. 4 («сумма до .») — вынесено Оператору на гейт.
