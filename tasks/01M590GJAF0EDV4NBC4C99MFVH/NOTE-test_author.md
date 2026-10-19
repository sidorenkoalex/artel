# Записка test_author — 01M590GJAF0EDV4NBC4C99MFVH

## Выяснено
- Визит 2: шаг закончен эскалацией. Батч В1–В5 с вариантами и дефолтами — в докстринге acceptance_tests/test_escalation.py. Пометки escalate стоят у AC-2, 6, 7, 8, 9, 10, 21.
- Главное (В1): требование 7 велит отказывать в подготовке pult-vitest, пока флаг кэша не подтверждён для версии. Подтверждение — «проба этапа 2», после задачи. Значит, положительные сценарии AC-6…AC-10 недостижимы, а где записано «версия подтверждена», SPEC не говорит.
- В2: формат JSON отчётчика не задан. В3: нет носителя итога по каждому тесту. В4: AC-21 «падает при мутациях» — места мутации планка не знает. В5: узел полного прогона гейта мержа закрытый (`fsm_merge_gate._full_suite_or_refuse`) — разовый файл.
- Эскалация обрабатывается в `fsm_advance.tests_writing` (строка ~541) РАНЬШЕ ошибок трассируемости и сухого сбора, поэтому AC без тестов переход не заваливают.
- Канал профиля в места прогона — `command=` (`run`, `collect`, `run_repeat`, `run_full_suite`, `full_suite`), у `run_plank`/`two_sided.run` — `profile=`. Прецедент обёртки-зонда (argv/cwd/env) — tests/test_01m52eefna1wh31962hvnt0yz9_pytest_own_places.py.
- Фикстура профиля компонента: targets.yaml песочницы, запись с одним компонентом → `project_profile.decide(<проект>).profile` (нужен `make_project_repo`). Запись из двух — образец YAML в tests/test_01m58pg72pg64gs790xm2ews61_doctor_components.py (`HEAD`, `add_components`).
- Прецеденты:
  - `approve` при «не начат»: tests/test_suite_lock.py:172 (`ApproveAcceptanceSandbox` из tests/test_approve_acceptance_full_suite.py:38 патчит `acceptance.run_full_suite`);
  - гейт мержа с приложениями: tests/test_plan_appendix.py:643 `MergeAppendixTest`;
  - подсказка гейта мержа: tests/test_worktree_db_files.py:69;
  - `suite-run` сквозной: tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py (`PytestSpy`, `Detached`);
  - сторож: `doctor._find_hung_test_runs`, `check_hung_test_runs(conn)`; `ps` идёт через `doctor.subprocess.run` (публичное имя, патч допустим).

## Не сработало
- `ls` в Bash недоступен (command not found).

## Где остановился
- Эскалация сдана. После ANSWER: написать тесты AC-1…AC-21 по ответу и снять пометки escalate в test_escalation.py (или удалить файл).

## Чего не хватило
- SPEC не задаёт формат отчётчика pult-vitest и способ задать «подтверждённую» версию Vitest — без них планка Vitest не пишется.
