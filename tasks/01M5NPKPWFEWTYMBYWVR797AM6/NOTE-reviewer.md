# Записка ревьювера, итерация 1

## Выяснено
- Профиль артели (`report: junit-xml`, без runner) -> `suite_run._profile_command` даёт список (acceptance.reported у pult = None) -> mutation-run не отказывает артели.
- `_signal_near_limit` в run_full_suite срабатывает только при targets == ("tests",): у mutation-run явные файлы -> ложных алертов №32 нет.
- adopt/hand/acquire — тот же порядок, что у suite-run (suite_run.py:907-937).

## Не сработало
-

## Где остановился
- Итерация 1 закрыта: REVIEW.md approved, реестр пуст, guard ок. Тесты задачи 17 passed; временные мутации classify (AC-12) и touches_tests (AC-3) пойманы; карта свежая; планки нет.

## Чего не хватило
- Где run_full_suite пишет в БД (acceptance.py:2467/2525/_signal_near_limit) — искал дольше всего.
