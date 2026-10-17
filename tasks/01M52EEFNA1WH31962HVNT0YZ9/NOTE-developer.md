# Записка developer — 01M52EEFNA1WH31962HVNT0YZ9

## Выяснено
- Канал профиля: `command=<Profile>` у run/collect/run_repeat/run_full_suite/full_suite/suite_result_key; `profile=` у run_plank и two_sided.run (-> `_run_side`).
- Путь артели (pult-pytest) зафиксирован частью 1 вплоть до формы вызова — pytest-own идёт отдельной веткой (`acceptance._run_in_session`).
- ANSWER-1 (итерация 2): `run_full_suite(test_ids=())` — id упавших без перевода, после целей; цель `tests` у pytest-own всегда -> `long_lived_dir`. `two_sided._root_form` приводит nodeid/location отчёта к корню (страховка поверх `--rootdir`). `run_repeat` уже давал узел от корня (`_junit_node` по хвосту пути от корня).
- Новый тест tests/test_pytest_own_result_ids.py (4 теста, мутации проверены: снятие `_root_form`+`--rootdir`, `_junit_red_tests(args)`, перевод test_ids).

## Не сработало
- Запись в /tmp из Bash требует подтверждения — мутации делать Edit-ом.

## Где остановился
- Шаг завершён: ANSWER-1 отработан, затронутые модули 149 passed, планка 3 passed, suite-run №2 зелёный (5542/0), карта регенерирована, PLAN ready (guard ок).

## Чего не хватило
- Вызывающий `test_ids` (suite_run --failed) — часть 3; сейчас параметр никто не передаёт.
