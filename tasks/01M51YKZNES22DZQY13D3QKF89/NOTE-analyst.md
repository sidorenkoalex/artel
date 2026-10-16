# Записка analyst — 01M51YKZNES22DZQY13D3QKF89

## Выяснено
- Возврат аудита (SPEC-AUDIT fail, 1 из 2). Часть отклонений требует правки
  вне зон ТЗ (ТЗ: «Правка вне зон — эскалация до SPEC») → шаг 2 пишет
  QUESTIONS.md, SPEC.md не трогает.
- Подтверждено кодом: вызывающие мест запуска вне зон — pull.py:664/666,
  plank_run.py:187, amend.py:545/549/715/718, advance_gates/acceptance.py:169/402/405,
  advance_gates/tests_writing.py:560/563, suite_run.py:524/564, notes.py:1040,
  fsm_merge_gate.py:962-967. Сигнатуры: run(tdir,cwd,…) :384, run_plank(targets,cwd) :923,
  full_suite(root, task_id) :1697 (task_id есть), acceptance_suite :1807 → full_suite без command :1847.
- fsm_autogate.py:326 и fsm.py:1294 зовут acceptance.acceptance_suite — п.6 ложится в acceptance.py.
- Носитель профиля project_profile.Profile (project_profile.py:63-74) вне зон.
- Фикстуры без sandbox/image: tests/sandbox.py:1057 (_PROJECT_TARGET_ENTRY), :1074 (ARTEL_TEST_PROFILE),
  :1097 artel_target_entry, :1117 declared_without_profile; external_flow TARGET_ENTRY/PROFILE :45-61;
  test_profile base_entry :31 + метод :107. 27 файлов tests/ используют фикстуры sandbox.py.
- test_profile.py:103 — «неизвестное подполе» может выпасть `runner` со значением "x":
  после правки отказ останется (неверное значение), смены ожидания нет.
- Пункты аудита 5–7 (AC-5 «ровно», AC-7 -e NAME/--env-file, AC-3 realpath в прогоне) —
  прямые следствия ТЗ п.3/п.2, решаются в SPEC без вопроса.

## Где остановился
- QUESTIONS.md (5 вопросов: зоны/доставка проекта, гейт мержа, image+фикстуры,
  том кэша в D1а-1, «полный набор зелёный»), guard: ок. SPEC.md не тронут.
- После ANSWER: переписать SPEC с закрытием всех 9 отклонений аудита (5–7, 9 —
  без вопроса: AC-5 точный набор флагов, AC-7 только -e ИМЯ=значение без
  --env-file, AC-3 realpath в прогоне, адрес п.6 = acceptance.py:1847), удалить QUESTIONS.md.

## Чего не хватило
- Как launch-функции узнают проект/задачу — сигнатуры без них, вызывающие вне зон.
