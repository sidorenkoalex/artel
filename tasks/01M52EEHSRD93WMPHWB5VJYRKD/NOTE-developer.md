# Записка developer — 01M52EEHSRD93WMPHWB5VJYRKD

## Выяснено
- Приём: где у вызывающего есть `decision.profile` — `acceptance._own(profile) or list(profile.command)` (гейт мержа, рубеж in_dev, сухой сбор); где не передавалось ничего — `acceptance._task_own_profile(conn, task_id)` и передача только при не-None (plank-run, pull, amend; у `_amend_plank_only` ещё `cwd=wt_path`); test_integrity — свой `_own_profile`, `two_sided.run(..., profile=own)` только у pytest-own.
- suite_run: `_profile_command` отдаёт `Profile` при `runner: pytest-own`; `--failed` у own — ids каналом `test_ids` (тест `tests/test_suite_run.py::FailedIdsByProfileTest`, мутацией проверен).
- Долгоживущий файл задачи: 26 passed; адресные тесты модулей ~320 passed; suite-run №1 — зелёный (5580/0/2).

## Не сработало
- sed/heredoc в /tmp требуют подтверждения — правки только Edit.
- `-n 8 -p xdist` на перечне файлов — сторож conftest отказывает; только последовательно.

## Где остановился
- Шаг завершён: PLAN.md status: ready, guard ок, карта регенерирована; код не закоммичен (коммитит пульт).

## Чего не хватило
- Дольше всего — понять, какие места у pult-pytest на main брали команду профиля, а какие команду пульта (ответ — таблица `places()` в долгоживущем файле).
