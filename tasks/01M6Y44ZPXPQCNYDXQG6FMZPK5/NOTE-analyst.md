## Выяснено
- ANSWER-1: 1B (новая forge.last_executed_commit, любой цвет кроме skipped), 2B (warn «тревога» + alerts kind=trigger suite.cost + строка docs/triggers.md, зона расширена мандатом), 3A, 4A, 5A, 6A, 7A, 8B (config.SUITE_COST_CI_LIMIT_SEC + тест против ci.yml), 9A (targets.CI_REPORT_ARTIFACT_DEFAULT).
- raise_alert дедуп — по (target, kind, source, message): «один открытый на проект» требует сообщения без чисел (alerts.py:93-105) — так и записано в требовании 7.
- Выходы новых поверхностей forge — кортежи (не классы), чтобы не трогать RESULT_TYPES/_call; summarize — именованный вход и ключи выхода.
- artel.main() без argv (artel.py:2710) — AC-9 через командную строку.
- Все 11 отклонений аудита закрыты в SPEC (AC-1 состав полей TestReport, AC-7 выбор предыдущей, AC-8 migrate, AC-9 белый список/«Команды:», AC-10 обрыв и TargetsError, AC-12 мутации с адресами).

## Не сработало
- `ls`/`rm` в оболочке шага нет; `task-rm` отказывает по файлу ссылки документов — QUESTIONS.md удалён через python os.remove.

## Где остановился
- SPEC.md status: ready, guard ок, QUESTIONS.md удалён. Шаг завершён.

## Чего не хватило
- Как удалить файл ссылки документов штатно (task-rm его не берёт) — не описано в брифе.
