## Выяснено
- Возврат аудита 1 из 2 (11 отклонений). Пункты 1, 2 аудита — прямо «вопрос Оператору»; написан QUESTIONS.md (9 вопросов, guard ок), SPEC.md не тронут.
- forge.green_base_commit — только status=success (forge.py:467); единственный внешний вызов — doctor/project_checks.py:580.
- doctor.Check: ok/warn/fail/skip; fail → exit 1 (doctor/cli.py:361-364); suite_duration поднимает alerts kind=trigger (suite_duration.py:67).
- _series: сброс по ack suite.duration, только записи с seconds_per_test, обрезка по xdist_workers.
- targets.CI_REPORT_ARTIFACT_DEFAULT="junit" (targets.py:175); ci.yml:216 timeout-minutes: 40; full_suite_limit бросает TargetsError (project_profile.py:435).
- Остальные отклонения аудита (3,4,7,8,9,11-справка) — правка текста SPEC после ответа: простые выходы поверхностей, ключи summarize, сверка полей TestReport, критерий migrate() создаёт таблицу, вывод команды = вывод функции, нет в белом списке роли, «Размер проверки» AC-8, блок «Команды:» artel.__doc__, фильтр «задача проекта в БД» в AC-5.

## Не сработало
- Ничего.

## Где остановился
- QUESTIONS.md сдан; ждём ANSWER. После ответа — переписать SPEC с учётом ответов и пунктов выше, удалить QUESTIONS.md.

## Чего не хватило
- Как ADR-0032 «алерт» ложится на doctor — нигде не сказано; вынесено вопросом 2.
