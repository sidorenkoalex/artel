# Записка analyst — 01M51YKZNES22DZQY13D3QKF89 (визит 3, после возврата аудита 2 из 2)

## Выяснено
- Все 7 отклонений SPEC-AUDIT (spec_sha f6631082) подтверждены по коду.
- two_sided.py:227-235 `_run_side` — subprocess pytest с _pytest_env, зовётся из
  test_integrity.py:1527 (гейт) и :1429 (наблюдение). Вне зон ТЗ → вопрос 1.
- amend.py:715,718 зовут collect/run без cwd; tdir = wt_path/tasks/<id> — проект выводим из tdir.
- full suite: task — suite_lock.my_task_id() (suite_lock.py:155); suite_run.py:524,564 без task.
- suite_result_key (acceptance.py:1609) без sandbox/runner/workdir/image.
- Фикстуры: 8 файлов «своя запись + ARTEL_TEST_PROFILE» (grep ARTEL_TEST_PROFILE tests/*.py);
  dict-запись только в test_profile.py:120-124 (grep `test_profile=`). test_invariants.py
  правки не требует (только комментарий :187).
- test_profile.py::test_ac1_each_profile_defect... — `runner` там как «неизвестное подполе»
  со значением "x": после введения runner отказ по неверному значению всё равно должен
  называть `runner` и `test_profile`; image-проверку ставить после проверки подполей,
  иначе текст отказа не назовёт поле дефекта. Учесть в SPEC/для разработчика.

## Где остановился
- QUESTIONS.md (батч 2, 7 вопросов, дефолты A) записан, guard ок. SPEC.md не трогал.
- После ANSWER-2: переписать SPEC по дефолтам/ответам, удалить QUESTIONS.md.

## Чего не хватило
- Полного перечня мест запуска subprocess pytest: надо было grep `_pytest_command|_pytest_env`
  по orchestrator/ ещё в визите 1.
