# Записка test_author

## Выяснено
- Прошлая попытка сдачи отклонена: acceptance_tests/ не было вовсе (все AC-1..AC-25 без теста).
- Шаг начат 22.10: читаю SPEC, код guard/fsm/mandate/amend и тесты-прецеденты.
- Образцы песочниц: approve внешнего проекта — tests/test_01m5d02n3b428v8bwc3pam9qct_id_mandate_answer.py
  (IdMandateSandbox: make_project_repo, VITEST_COMPONENT, task() + checkpoint.commit_step_artifacts);
  форма раздела в CLI — tests/test_01m45fjd46bx45vhc36s4vs9qn_section_form.py; approve артели —
  tests/test_01m45fjd46bx45vhc36s4vs9qn_declared_change.py (DeclaredChangeSandbox);
  amend-tests с меткой — LabelledSandbox/Ac11AmendLabelledRefusalTest в
  tests/test_01m5aa5ts90rdj2afxb882wtpd_labelled_gates.py (шпион Popen для Vitest, locked_task, state_of).
- amend.py: отказы _refuse_traceability («трассируемость AC нарушена:»), _refuse_group_lines
  («строка группы:»), _refuse(…, «долгоживущие файлы tests/»); LABELLED_REFUSAL вызывается :722 и :1088.
- План: долгоживущие файлы tests/test_01m5gxzk2wtz89axq7qy2rjd9r_*.py для AC-1..AC-14,16..20,23..25;
  разовые в acceptance_tests для AC-15 (существующие тесты не тронуты), AC-21 (три метода), AC-22 (PLAN).

- Написан tests/test_01m5gxzk2wtz89axq7qy2rjd9r_guard_section_bans.py (AC-1 CLI, 2, 3, 10, 12, 13, 14):
  прогнан, красен по верным причинам (32 failed / 16 passed — passed: AC-3, контроли).
- Переход spec_writing -> spec_gate: guard_refuses пишет «переход отклонён guard'ом» (fsm.py:290).

- Написан tests/test_01m5gxzk2wtz89axq7qy2rjd9r_replaced_approve.py (AC-1 переход, 4..9, 11, 20, 24, 25):
  AC-9, AC-20 зелены с рождения; прочие красны по верным причинам (approve уходит в tests_writing,
  AttributeError mandate.approved_replacements / REPLACED_TESTS_ACTION / refusal_classes.REPLACEMENT_REFUSAL_ACTION).

- Написан tests/test_01m5gxzk2wtz89axq7qy2rjd9r_amend_labelled.py (AC-16..19, 23): все красны на
  LABELLED_REFUSAL «до G3б не исполняется». Правка ссылки документов --from-branch — git-плотницкой
  в клоне (worktree --detach, commit, update-ref, push, record_fixation): чекпоинт после лока не удаляет.
- Разовые написаны: acceptance_tests/test_ac15_existing_bans_tests.py (зелёный с рождения),
  test_ac21_rewritten_amend_methods.py (статика + прогон на ветке + прогон тех же методов в
  git worktree базы — там они обязаны падать по подслучаям 4/2/1), test_ac22_plan_appendices.py.
  plank-run: 6 failed, 4 passed — причины верные.
- Стаб-валидация ПРОЙДЕНА и откатана (git status — только три новых файла tests/): на стабе
  guard/spec_audit/fsm/mandate/tests_writing/refusal_classes/amend + переписанных трёх методах все
  три долгоживущих файла и AC-15/AC-21 зелёные; AC-22 — на пробном PLAN с диффами шаблона и скила.
  Мутации стаба (матрица без test_ids, DECLARED до сверки, статика --from-branch только при
  расхождении, состав --from-branch на любой глубине) красят свои тесты.
- Наблюдение для разработчика (не требование планки): переписанный Ac25 проходит только если
  маркер красноты упавшего долгоживущего .test.jsx читается по правилу планки — песочница
  FailToPassSandbox отдаёт красный прогон (стаб передавал rule в redness_marker_errors_from_files).
- preflight: все проверки «пройдена». Итог на нетронутом коде: долгоживущие — 85 failed / 18 passed
  (зелены AC-3, AC-9, AC-20 и контроли); планка — 6 failed / 4 passed (AC-15 зелёный с рождения).
- docs/codebase-map.md не регенерировал: правку вне tasks/ и вне своих tests/test_<id>_* пульт
  откатывает; карту освежит разработчик (CLAUDE: новые *.py в tests/ меняют карту).

## Не сработало
- Запись из двух компонентов как «решение профиля с отказом»: repo_context не находит клон —
  approve отказывает раньше («SPEC.md ветки не прочитан»). Взята артель без test_profile.
- Метод-помощник `run` в TestCase затеняет unittest.TestCase.run — назван `call`.
- `ls` в Bash недоступен (command not found).

## Где остановился
- Шаг завершён: все AC-1..AC-25 покрыты тестами (без пометок manual/skip/escalate).

## Чего не хватило
- Дольше всего искал, как получить «решение профиля с отказом», не сломав чтение SPEC на approve
  (запись из двух компонентов теряет клон в repo_context). Помогла артель без test_profile.
- Не хватало знания, что чекпоинт после лока не удаляет файлы планки из ссылки документов.
