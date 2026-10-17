# Записка analyst

## Выяснено
- Места без профиля в зонах: role_prompt.py:36 (префикс), :78-80, :94, :114 (текст «tests/»); checkpoint.py:376, :384 (ls_tree_files "tests"), :412 (текст журнала), :497 (_role_may_delete).
- Вне зон: runner.py:1310-1346 — _missing_required_artifact/_has_own_long_lived_test для test_author ищет долгоживущий файл только в `tests` по шаблону артели; у sled целиком долгоживущая планка в backend/tests даст отказ «нет артефакта». Это и есть вопрос 1 QUESTIONS.md.
- Уже по профилю / не касается: amend.py, preflight.py, tests_writing.py:381-402, advance_gates/acceptance.py, acceptance.py:1380; _network_address_gate — только артель; in_weakening_scope — у внешнего проекта область из профиля (test_integrity.py:661-664).
- Profile.long_lived_prefix / long_lived_example / is_long_lived — project_profile.py:106-118; источник профиля задачи — project_profile.for_task(conn, task_id).
- Текст skills/test-authoring.md про каталог — строки 93-126 (раздел про долгоживущие файлы, «tests/» в :93, :114-121, :156).

## Не сработало
- —

## Где остановился
- QUESTIONS.md (1 вопрос, дефолт B — runner.py в «Не входит»), guard ок. SPEC.md не писался. После ответа: SPEC с зонами role_prompt.py, checkpoint.py, tests/ (+runner.py при A), готовый текст правки skills/test-authoring.md.

## Чего не хватило
- Нет единого списка потребителей умолчаний guard.LONG_LIVED_DIR — искал grep'ом по вызовам.
