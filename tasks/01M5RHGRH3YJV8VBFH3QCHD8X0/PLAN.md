---
task: 01M5RHGRH3YJV8VBFH3QCHD8X0
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: сведение тестов, волна 3м-2б — шесть файлов `merge_after` в `tests/test_merge_after_module.py`

## Подход

Перенос, не улучшение: 33 теста шести долгоживущих файлов (`answer`,
`guard`, `plan`, `spec_gate`, `status_show` — SPEC 01M44EP0D47F498TEE08MNGBYT;
`new_declares` — SPEC 01M45D29BQJE8FJYJA4JQWSYFZ) дописаны в конец
`tests/test_merge_after_module.py` в стиле pytest, шесть файлов удалены
(мандат ANSWER-1). Доказательство неослабления — один набор из 50 патчей
мутаций кода `orchestrator/` и `scripts/guard.py` против шести файлов на
базе («до») и против модуля на рабочей копии («после») теми же частями.

- Патчи — `make_patches.py` каталога документов (замены текста, у каждой —
  комментарий с заявкой; `git apply --check` на каждом). Альтернативы
  заявок, убиваемые лишь при части зёрен, переписаны на мутацию того же
  кода, убиваемую при любом зерне (см. «Мутации»); там, где такой мутации
  нет, — находка; заявки тестов в модуле переписаны под новые мутации.
- Свод — `convert.py` (перевод текста по позициям `ast` исходника:
  `self.` → стенд, методы → функции `<префикс>_<метод>(stand, …)`,
  `self.assertX(…)` → `assert …` по соответствию требования 11, `subTest`
  → прежний цикл с ярлыком `+ "; " + f"<ключ>={<значение>!r}"` в каждом
  сообщении, параметр `case: str = ""`/`label: str = ""` у помощников с
  ярлыком) и `assemble.py` (абзац докстринга, недостающие импорты новыми
  строками, переписанные заявки, удаление шести файлов). Комментарии и
  разбивка строк исходников сохранены.
- Части «до» и «после» — `run_part.py` (один вызов `mutation-run … --wait
  5`, затем копия таблицы в этот PLAN — `add_table.py`, до старта следующей
  части; перед частью «после» — проверка пустого `git status --porcelain --
  orchestrator/ scripts/`). Патч, меняющий строки узлов `check`,
  `_cycle_path`, `declared_from_tz`, `_ORDER_LINE_RE`, `merge_after_items`,
  — один в своей части.
- PLAN собирает `make_plan.py` (строки падения «до → после» из логов
  патчей, места утверждений подготовки, перечни имён, числа и время).

Бюджет SPEC ($60) не пересматривается.

## Шаги

1. Патчи мутаций 001–050, таблица «до» (прогоны №1–20) — сделано.
2. Свод в модуль, удаление шести файлов, регенерация карты — сделано
   (коммит 8d6a6cb1).
3. Таблица «после» (прогоны №21–40) теми же диапазонами и `--workers` —
   сделано; сравнение «до → после» и строки падения — ниже.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 патчи и заявки | 1, «Мутации» |
| 2 таблица «до», части | 1, «Мутации до» |
| 3 строки падения | «Строки падения» |
| 4 не доказательство | «Подготовка и предпосылки», «Строки падения» |
| 5 зерно, находки | «Мутации», «Находки» |
| 6 красный контроль | контроль всех 40 частей зелёный, повторов не было |
| 7 временные файлы | только файлы каталога документов (`*.py`, `*.txt`, `*.tsv`) |
| 8 свод в конец модуля | 2 |
| 9 имена | 2, «Имена» |
| 10 стенды-фикстуры | 2, «Имена» |
| 11 перенос тел | 2 |
| 12 дубли | «Удалённые дубли» |
| 13 таблица «после» | 3, «Мутации после» |
| 14 прогоны и замеры | «Числа и время» |
| 15 удаление, мандат | 2 (ANSWER-1) |
| 16 зоны | 2 — менялись только модуль, шесть файлов и карта |
| 17 независимая проверка | вне роли |

## Влияние на систему

Меняются только тесты: дописка в `tests/test_merge_after_module.py`
(20 прежних тестов, их фикстуры, функции, константы и `DivisionSandbox`
не тронуты — дифф модуля только добавления), удаление шести файлов волны
по мандату ANSWER-1 и вывод генератора `docs/codebase-map.md`. Код
`orchestrator/` и `scripts/` не менялся (мутации — только во временной
копии `mutation-run`); дерево `orchestrator/` базы ad3608c6 и HEAD — 739a7b06b59e / 739a7b06b59e, `scripts/` — 609d2d314b1a / 609d2d314b1a. Каждое утверждение шести файлов
перенесено в той же форме, `skip`/`xfail` нет, пределы не тронуты; свойство
каждого удалённого файла держит его раздел модуля — таблица «после».
Откат — revert коммита свода.

## Риски

- Строки, удлинённые заменой `self.` на имя стенда, местами длиннее
  79 знаков (линтера длины в проекте нет); переразбивка строк не делалась,
  чтобы не трогать тела.
- Убийцы-соседи разных файлов (например, `012` роняет `approve` гейта SPEC
  в стендах `plan`/`status_show`) убивают через подготовку — их строки не
  служат доказательством; доказательство — строки заявивших тестов ниже.

## Имена

Прежнее имя → новое имя:
- константы: `MARKER` (`answer`) → `ANSWER_MARKER` (литерал, не `MANDATE`);
  `SPEC_TEXT` → `GUARD_SPEC_TEXT`, `PLAN_SPEC_TEXT`, `SPEC_GATE_SPEC_TEXT`,
  `STATUS_SHOW_SPEC_TEXT`; `UNFINISHED_STATES` → `STATUS_SHOW_UNFINISHED_STATES`,
  `NEW_DECLARES_UNFINISHED_STATES`; `FIELD` (`guard`) и `ZONES` (`spec_gate`,
  `new_declares`) не переопределены — у модуля тот же литерал; `CROCKFORD` —
  одно определение в разделе `spec_gate`, `WAIT_PREFIX` — в разделе
  `status_show`, `ids_of` (с докстрингом) — в разделе `answer`; остальные
  константы — прежними именами;
- стенды: `AnswerMandateSandbox.setUp` → фикстура `answer_stand(real_git)`,
  `GuardMergeAfterFieldTest.setUp` → `guard_stand(tmp_dir)` (три первые
  строки), `PlanChannelSandbox.setUp` → `plan_stand(light_transition)`,
  `MergeAfterSpecGateSandbox.setUp` → `spec_gate_stand(light_transition)`,
  `DependencyOutputSandbox.setUp` → `status_show_stand(light_transition)`,
  `DeclaredMergeAfterSandbox.setUp` → `new_declares_stand(light_transition)`;
- методы → функции модуля (первый параметр `stand`): `answer_accepted`, `answer_answers`, `answer_assert_refused`, `answer_deps`, `answer_element`, `answer_insert`, `answer_journal_since`, `answer_last_step_id`, `answer_mandate_line`, `answer_note`, `answer_role_env`, `answer_run_answer`, `answer_set_state`, `answer_stand`, `answer_unique_prefix`, `guard_element`, `guard_field_errors`, `guard_note`, `guard_stand`, `new_declares_all_ids`, `new_declares_assert_refused_without_traces`, `new_declares_declared`, `new_declares_deps`, `new_declares_element`, `new_declares_insert`, `new_declares_journal`, `new_declares_live_task`, `new_declares_missing_id`, `new_declares_note`, `new_declares_run_new`, `new_declares_set_state`, `new_declares_stand`, `new_declares_status_line`, `new_declares_suffix`, `new_declares_tz`, `new_declares_unique_prefix`, `plan_advance_with_plan`, `plan_approve_spec`, `plan_branch_not_behind`, `plan_deps`, `plan_element`, `plan_field_line`, `plan_journal_since`, `plan_last_step_id`, `plan_new_task`, `plan_note`, `plan_prepared_task`, `plan_rejected_case`, `plan_set_task_state`, `plan_stand`, `plan_state_of`, `plan_unique_prefix`, `plan_write_doc`, `spec_gate_all_ids`, `spec_gate_approve_spec`, `spec_gate_assert_refused`, `spec_gate_deps`, `spec_gate_element`, `spec_gate_insert`, `spec_gate_journal_since`, `spec_gate_last_step_id`, `spec_gate_new_task`, `spec_gate_note`, `spec_gate_row`, `spec_gate_set_task_state`, `spec_gate_stand`, `spec_gate_unique_prefix`, `spec_gate_write_spec`, `status_show_dependency_scenario`, `status_show_element`, `status_show_new_task`, `status_show_note`, `status_show_set_state`, `status_show_stand`, `status_show_status_line`, `status_show_wait_suffix`, `status_show_with_dependencies`;
  `branch_not_behind` → `plan_branch_not_behind(repo, *args)`;
- локальные: `journal` → `entries` (`test_ac11_escalated_answer_sets_and_clears_value`,
  три теста `plan`, `spec_gate_assert_refused`,
  `test_ac1_order_line_declares_full_ids_in_line_order`,
  `test_ac3_order_line_without_after_declares_nothing`); `task` → `task_id`
  (четыре теста `guard`, `test_ac2_missing_task_keeps_spec_gate_and_column_empty`);
  параметр только по имени `task` у `guard_field_errors` и `task=` вызовов
  прежние.

Совпадения тел (не объединены, требование 9): `answer_note`, `guard_note`,
`plan_note`, `spec_gate_note`, `status_show_note`, `new_declares_note`;
`answer_set_state`, `plan_set_task_state`, `spec_gate_set_task_state`,
`status_show_set_state`, `new_declares_set_state`; `answer_unique_prefix`,
`plan_unique_prefix`, `spec_gate_unique_prefix`, `new_declares_unique_prefix`;
`*_last_step_id`, `*_journal_since` (`answer`, `plan`, `spec_gate`);
`plan_new_task`, `spec_gate_new_task`, `status_show_new_task` и
`new_declares_live_task`; `spec_gate_insert`/`new_declares_insert`; `ids_of`
пяти файлов (у `status_show` — без докстринга).

## Удалённые дубли

Удалённых нет: все 33 теста перенесены (модуль — 20 + 33).

## Мутации

- mutation-001 — заявка AnswerMandateAcceptedTest::test_ac11_escalated_answer_sets_and_clears_value (прежний файл `test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py`): `orchestrator/merge_after.py` `value_refusals`: снят ранний возврат для `["нет"]` — «нет» проверяется как id (альтернатива «„нет“ читается как id задачи»); может зациклить общий узел: нет — строк узлов `check`/`_cycle_path`/разбора «Порядок:»/`merge_after_items`/префикса не меняет; зерно: вторая строка мандата сценария — всегда «Зависимости мержа: нет», её отказ роняет вызов :174 при любом зерне.
- mutation-002 — заявка AnswerMandateAcceptedTest::test_ac11_escalated_answer_sets_and_clears_value (прежний файл `test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py`): `orchestrator/merge_after.py` `mandate_value`: `check(…)[0]` → `check(…)[1]` — значение строки не применяется (переписанная альтернатива «копируется как есть»: сырой перенос убивался не при каждом зерне — при полных id); может зациклить общий узел: нет — строк узлов `check`/`_cycle_path`/разбора «Порядок:»/`merge_after_items`/префикса не меняет; зерно: зависимостей всегда 1–3, колонка остаётся пустой при любой форме элементов.
- mutation-003 — заявка AnswerMandateAcceptedTest::test_ac11_merge_gate_answer_outside_role_env_accepted (прежний файл `test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py`): `orchestrator/answer.py` `cmd_answer`: ветка `merge_gate` не принимает ответ (`state == "merge_gate_"`); может зациклить общий узел: нет — строк узлов `check`/`_cycle_path`/разбора «Порядок:»/`merge_after_items`/префикса не меняет; зерно: задача всегда на `merge_gate`, ответ любого вида (нет/живые) уходит в отказ.
- mutation-004 — заявка AnswerMandateRefusedTest::test_ac12_invalid_mandate_element_refused_before_commit (прежний файл `test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py`): `orchestrator/merge_after.py` `value_refusals`: только форма строки (`if True:` вместо условия без БД); может зациклить общий узел: нет — строк узлов `check`/`_cycle_path`/разбора «Порядок:»/`merge_after_items`/префикса не меняет; зерно: все четыре варианта перебираются при любом зерне; «нет такой задачи» и «убитая» годны по форме.
- mutation-005 — заявка AnswerMandateRefusedTest::test_ac12_invalid_mandate_element_refused_before_commit (прежний файл `test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py`): `orchestrator/answer.py` `cmd_answer`: проверка строк мандата в `escalated` — после коммита ANSWER; может зациклить общий узел: нет — строк узлов `check`/`_cycle_path`/разбора «Порядок:»/`merge_after_items`/префикса не меняет; зерно: все четыре варианта перебираются при любом зерне, каждый негодный — ANSWER уже в ссылке.
- mutation-006 — заявка AnswerMandateRefusedTest::test_ac12_merge_gate_without_line_or_from_role_env_refused (прежний файл `test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py`): `orchestrator/answer.py` `cmd_answer`: снят отказ `merge_gate` без строки мандата; может зациклить общий узел: нет — строк узлов `check`/`_cycle_path`/разбора «Порядок:»/`merge_after_items`/префикса не меняет; зерно: первый вызов — файл без строки мандата, вход от зерна не зависит.
- mutation-007 — заявка AnswerMandateRefusedTest::test_ac12_merge_gate_without_line_or_from_role_env_refused (прежний файл `test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py`): `orchestrator/answer.py` `cmd_answer`: снят рубеж `runner.in_role_environment` в ветке `merge_gate`; может зациклить общий узел: нет — строк узлов `check`/`_cycle_path`/разбора «Порядок:»/`merge_after_items`/префикса не меняет; зерно: второй вызов — годная строка (и «нет», и живая задача годны) в окружении роли при любом зерне.
- mutation-008 — заявка GuardMergeAfterFieldTest::test_ac1_self_reference_names_field_and_element (прежний файл `test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py`): `scripts/guard.py` `merge_after_form_errors`: снята сверка элемента с полем `task:`; может зациклить общий узел: нет — строк узлов `check`/`_cycle_path`/разбора «Порядок:»/`merge_after_items`/префикса не меняет; зерно: элемент — ровно полный id задачи, версия схемы на ветку проверки не влияет.
- mutation-009 — заявка GuardMergeAfterFieldTest::test_ac1_repeated_element_is_a_repeat_error (прежний файл `test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py`): `scripts/guard.py` `merge_after_form_errors`: элементы схлопываются `dict.fromkeys` до проверки; может зациклить общий узел: нет — строк узлов `check`/`_cycle_path`/разбора «Порядок:»/`merge_after_items`/префикса не меняет; зерно: оба входа — один и тот же текст дважды при любом зерне.
- mutation-010 — заявка GuardMergeAfterFieldTest::test_ac1_element_not_in_task_id_format_is_a_form_error (прежний файл `test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py`): `scripts/guard.py` `merge_after_form_errors`: проверка формата элемента снята (`if False:`); может зациклить общий узел: нет — строк узлов `check`/`_cycle_path`/разбора «Порядок:»/`merge_after_items`/префикса не меняет; зерно: вход «foo bar» постоянный, зерно его не меняет.
- mutation-011 — заявка GuardMergeAfterFieldTest::test_ac1_valid_list_and_missing_field_pass (прежний файл `test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py`): `scripts/guard.py` `spec_merge_after_errors`: поле объявлено обязательным; может зациклить общий узел: нет — строк узлов `check`/`_cycle_path`/разбора «Порядок:»/`merge_after_items`/префикса не меняет; зерно: SPEC без поля перебирается для каждой версии 1–5 без зерна.
- mutation-012 — заявка GuardMergeAfterFieldTest::test_ac1_valid_list_and_missing_field_pass (прежний файл `test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py`): `scripts/guard.py` `merge_after_items`: разделитель `,` → `;` — список читается одним элементом; может зациклить общий узел: да — меняет строки узла из перечня, прогнан один в части; зерно: корректный список всегда из двух элементов через «, ».
- mutation-013 — заявка PlanChannelAppliesTest::test_ac9_justified_plan_value_replaces_db_value (прежний файл `test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py`): `orchestrator/merge_after.py` `apply_plan`: `ids == old` → `ids != old` — отличное от БД значение не применяется (переписанная альтернатива «применяется сырым»: префиксы ломали её не при каждом зерне); может зациклить общий узел: нет — строк узлов `check`/`_cycle_path`/разбора «Порядок:»/`merge_after_items`/префикса не меняет; зерно: новое значение PLAN всегда несёт хотя бы одну свежую задачу — оно отлично от прежнего.
- mutation-014 — заявка PlanChannelAppliesTest::test_ac9_justified_plan_value_replaces_db_value (прежний файл `test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py`): `orchestrator/merge_after.py` `rewrite`: запись «было → стало» не называет новое значение (переписанная альтернатива «не называет прежнее»: прежнее могло стоять и в новом — не при каждом зерне); может зациклить общий узел: нет — строк узлов `check`/`_cycle_path`/разбора «Порядок:»/`merge_after_items`/префикса не меняет; зерно: новый перечень всегда содержит свежую задачу, которой нет в прежнем.
- mutation-015 — заявка PlanChannelAppliesTest::test_ac9_empty_plan_value_clears_dependencies (прежний файл `test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py`): `orchestrator/merge_after.py` `apply_plan`: пустое поле читается как «поля нет» (`not meta.get(FIELD)`); может зациклить общий узел: нет — строк узлов `check`/`_cycle_path`/разбора «Порядок:»/`merge_after_items`/префикса не меняет; зерно: поле PLAN пусто без зерна, прежнее значение всегда непусто.
- mutation-016 — заявка PlanChannelAppliesTest::test_ac9_plan_without_field_keeps_db_value (прежний файл `test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py`): `orchestrator/merge_after.py` `apply_plan`: отсутствие поля очищает колонку (переписанная альтернатива «читается как пустое»: её гасила проверка обоснования не при каждом зерне); может зациклить общий узел: нет — строк узлов `check`/`_cycle_path`/разбора «Порядок:»/`merge_after_items`/префикса не меняет; зерно: прежнее значение всегда 1–2 зависимости, ветка обоснования не участвует.
- mutation-017 — заявка PlanChannelRejectsTest::test_ac10_rejected_plan_value_keeps_db_and_transition (прежний файл `test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py`): `orchestrator/merge_after.py` `apply_plan` + `orchestrator/fsm_advance.py`: отказ значения возвращает `True`, переход останавливается; может зациклить общий узел: нет — строк узлов `check`/`_cycle_path`/разбора «Порядок:»/`merge_after_items`/префикса не меняет; зерно: все пять вариантов перебираются при любом зерне, каждый отклоняется.
- mutation-018 — заявка PlanChannelRejectsTest::test_ac10_rejected_plan_value_keeps_db_and_transition (прежний файл `test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py`): `orchestrator/merge_after.py` `apply_plan`: снята проверка обоснования смены; может зациклить общий узел: нет — строк узлов `check`/`_cycle_path`/разбора «Порядок:»/`merge_after_items`/префикса не меняет; зерно: вариант «без обоснования» перебирается при любом зерне.
- mutation-019 — заявка PlanChannelRejectsTest::test_ac10_rejected_plan_value_keeps_db_and_transition (прежний файл `test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py`): `orchestrator/merge_after.py` `apply_plan`: причины `check` по элементам отбрасываются; может зациклить общий узел: нет — строк узлов `check`/`_cycle_path`/разбора «Порядок:»/`merge_after_items`/префикса не меняет; зерно: варианты негодных элементов перебираются при любом зерне.
- mutation-020 — заявка SpecGateMissingOrAmbiguousTest::test_ac2_missing_task_keeps_spec_gate_and_column_empty (прежний файл `test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py`): `orchestrator/merge_after.py` `check`: отсутствующий элемент молча отбрасывается; может зациклить общий узел: да — меняет строки узла из перечня, прогнан один в части; зерно: отсутствующий id в значении есть всегда; с соседом и без колонка/состояние расходятся.
- mutation-021 — заявка SpecGateMissingOrAmbiguousTest::test_ac2_ambiguous_prefix_keeps_spec_gate_and_column_empty (прежний файл `test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py`): `orchestrator/merge_after.py` `check`: `task_id_matches(…)[:1]` — первое совпадение; может зациклить общий узел: да — меняет строки узла из перечня, прогнан один в части; зерно: две задачи с общим префиксом заводятся всегда, длина префикса не меняет совпадение двух.
- mutation-022 — заявка SpecGateKilledForeignSelfTest::test_ac3_killed_dependency_refused (прежний файл `test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py`): `orchestrator/merge_after.py` `check`: снята проверка `killed`; может зациклить общий узел: да — меняет строки узла из перечня, прогнан один в части; зерно: зависимость всегда в `killed`, её элемент однозначен в любой форме.
- mutation-023 — заявка SpecGateKilledForeignSelfTest::test_ac3_dependency_of_other_target_refused, NewRefusesTest::test_ac6_invalid_dependency_refused_without_traces (прежний файл `test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py`, `test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py`): `orchestrator/merge_after.py` `check`: снята сверка target (у `new_declares` — альтернатива «target заводимой задачи не сверяется»); может зациклить общий узел: да — меняет строки узла из перечня, прогнан один в части; зерно: target зависимости всегда отличен от target задачи; вариант «чужой target» перебирается всегда.
- mutation-024 — заявка SpecGateKilledForeignSelfTest::test_ac3_prefix_resolving_to_own_id_refused (прежний файл `test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py`): `orchestrator/merge_after.py` `check`: самоссылка по буквальному элементу (`item == task_id`); может зациклить общий узел: да — меняет строки узла из перечня, прогнан один в части; зерно: элемент — всегда префикс короче id (полный тест заменяет `own[:-1]`).
- mutation-025 — заявка SpecGateCycleTest::test_ac4_cycle_through_existing_values_refused (прежний файл `test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py`): `orchestrator/merge_after.py` `check`: проверка цикла снята (переписанная альтернатива «только прямая обратная ссылка»: убивалась лишь при цепочке длины 2 — не при каждом зерне); может зациклить общий узел: да — меняет строки узла из перечня, прогнан один в части; зерно: цикл есть при обеих длинах цепочки.
- mutation-026 — заявка SpecGateCycleTest::test_ac4_cycle_through_existing_values_refused (прежний файл `test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py`): `orchestrator/merge_after.py` `check`: граф строится без нового значения задачи; может зациклить общий узел: да — меняет строки узла из перечня, прогнан один в части; зерно: путь B → A находится по рёбрам БД при любой длине цепочки — для сценария мутация эквивалентна, не убита ни при каком зерне.
- mutation-027 — заявка SpecGateWritesColumnTest::test_ac5_prefixes_written_as_full_ids_in_spec_order (прежний файл `test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py`): `orchestrator/fsm.py` `cmd_approve`: колонка `merge_after` не пишется (переписанная альтернатива «сырое значение»; «id сортируются» — находка); может зациклить общий узел: нет — строк узлов `check`/`_cycle_path`/разбора «Порядок:»/`merge_after_items`/префикса не меняет; зерно: зависимостей всегда 1–3, пустая колонка расходится с ними при любом зерне.
- mutation-028 — заявка SpecGateWritesColumnTest::test_ac5_spec_without_field_leaves_column_empty (прежний файл `test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py`): `orchestrator/merge_after.py` `spec_gate_value`: отсутствие поля — причина отказа; может зациклить общий узел: нет — строк узлов `check`/`_cycle_path`/разбора «Порядок:»/`merge_after_items`/префикса не меняет; зерно: SPEC без поля при любом зерне.
- mutation-029 — заявка SpecGateWritesColumnTest::test_ac5_spec_without_field_leaves_column_empty (прежний файл `test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py`): `orchestrator/merge_after.py` `spec_gate_value`: отсутствие поля пишет строку «None»; может зациклить общий узел: нет — строк узлов `check`/`_cycle_path`/разбора «Порядок:»/`merge_after_items`/префикса не меняет; зерно: SPEC без поля при любом зерне.
- mutation-030 — заявка StatusSuffixTest::test_ac13_status_suffix_lists_unfinished_and_disappears_after_done, DeclaredStatusShowTest::test_ac8_status_and_show_carry_declared_dependencies (прежний файл `test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py`, `test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py`): `orchestrator/merge_after.py` `_dependency_states`: состояния зависимостей кэшируются по id задачи; может зациклить общий узел: нет — строк узлов `check`/`_cycle_path`/разбора «Порядок:»/`merge_after_items`/префикса не меняет; зерно: оба теста переводят все зависимости в `done` и зовут `status` снова при любом зерне.
- mutation-031 — заявка StatusSuffixTest::test_ac13_status_suffix_lists_unfinished_and_disappears_after_done, StatusSuffixTest::test_ac13_no_suffix_without_field_or_all_done (прежний файл `test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py`, `test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py`): `orchestrator/merge_after.py` `status_suffix`: снят фильтр `s != "done"` (добавка включает завершённые); может зациклить общий узел: нет — строк узлов `check`/`_cycle_path`/разбора «Порядок:»/`merge_after_items`/префикса не меняет; зерно: у `StatusSuffixTest::test_ac13_status_suffix_lists_unfinished_and_disappears_after_done` после перевода всех в `done` перечень непуст при любом зерне.
- mutation-032 — заявка StatusSuffixTest::test_ac13_no_suffix_in_other_state (прежний файл `test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py`): `orchestrator/merge_after.py` `status_suffix`: фильтр состояния задачи снят — «[ждёт мержа:» в любом состоянии; может зациклить общий узел: нет — строк узлов `check`/`_cycle_path`/разбора «Порядок:»/`merge_after_items`/префикса не меняет; зерно: любое состояние `OTHER_STATES` (включая `spec_writing`) получает добавку при любом зерне.
- mutation-033 — заявка StatusSuffixTest::test_ac13_no_suffix_without_field_or_all_done (прежний файл `test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py`): `orchestrator/merge_after.py` `status_suffix`: снято условие пустоты перечня (переписанные альтернативы; «пустая колонка — ждём всех» убивалась не при каждом зерне); может зациклить общий узел: нет — строк узлов `check`/`_cycle_path`/разбора «Порядок:»/`merge_after_items`/префикса не меняет; зерно: обе ветки сценария дают пустой перечень незавершённых в `acceptance`/`merge_gate`.
- mutation-034 — заявка ShowDependenciesTest::test_ac14_show_lists_all_dependencies_with_states (прежний файл `test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py`): `orchestrator/merge_after.py` `show_line`: фильтр добавки `s != "done"`; может зациклить общий узел: нет — строк узлов `check`/`_cycle_path`/разбора «Порядок:»/`merge_after_items`/префикса не меняет; зерно: завершённая зависимость есть всегда (тест добавляет её, если зерно не дало).
- mutation-035 — заявка ShowDependenciesTest::test_ac14_show_without_dependencies_has_no_line (прежний файл `test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py`): `orchestrator/merge_after.py` `show_line`: строка печатается безусловно; может зациклить общий узел: нет — строк узлов `check`/`_cycle_path`/разбора «Порядок:»/`merge_after_items`/префикса не меняет; зерно: зависимостей нет при любом зерне.
- mutation-036 — заявка NewDeclaresTest::test_ac1_order_line_declares_full_ids_in_line_order (прежний файл `test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py`): `orchestrator/merge_after.py` `record_declared`: значение не пишется в колонку (переписанная альтернатива «сырой хвост»: убивалась не при каждом зерне); может зациклить общий узел: нет — строк узлов `check`/`_cycle_path`/разбора «Порядок:»/`merge_after_items`/префикса не меняет; зерно: оба подслучая (1 и 2–3 зависимости) — колонка пуста при любой форме элементов.
- mutation-037 — заявка NewDeclaresTest::test_ac1_order_line_declares_full_ids_in_line_order (прежний файл `test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py`): `orchestrator/merge_after.py` `record_declared`: порядок id обращён (переписанная альтернатива «id сортируются»); может зациклить общий узел: нет — строк узлов `check`/`_cycle_path`/разбора «Порядок:»/`merge_after_items`/префикса не меняет; зерно: подслучай `count` 2–3 идёт всегда: обращение перечня из ≥2 различных id его меняет.
- mutation-038 — заявка NewDeclaresTest::test_ac1_order_line_declares_full_ids_in_line_order (прежний файл `test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py`): `orchestrator/merge_after.py` `record_declared`: запись журнала не делается; может зациклить общий узел: нет — строк узлов `check`/`_cycle_path`/разбора «Порядок:»/`merge_after_items`/префикса не меняет; зерно: записи нет ни в одном подслучае при любом зерне.
- mutation-039 — заявка NewDeclaresTest::test_ac2_list_ends_at_parenthesis_or_dot (прежний файл `test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py`): `orchestrator/merge_after.py` `declared_from_tz`: перечень до конца строки (ни «(», ни «.» не режут); может зациклить общий узел: да — меняет строки узла из перечня, прогнан один в части; зерно: обе ветки зерна ставят «(» или «.» за перечнем — хвост даёт негодный элемент.
- mutation-040 — заявка NewDeclaresTest::test_ac3_order_line_without_after_declares_nothing (прежний файл `test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py`): `orchestrator/merge_after.py` `_ORDER_LINE_RE`: слово «после» необязательно; может зациклить общий узел: да — меняет строки узла из перечня, прогнан один в части; зерно: варианты «Порядок: без …» перебираются все при любом зерне.
- mutation-041 — заявка NewDeclaresTest::test_ac3_order_line_without_after_declares_nothing (прежний файл `test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py`): `orchestrator/merge_after.py` `_ORDER_LINE_RE`: «после» ищется по всему ТЗ; может зациклить общий узел: да — меняет строки узла из перечня, прогнан один в части; зерно: пункт «Требуется» несёт «после <id>.» во всех вариантах.
- mutation-042 — заявка NewRefusesTest::test_ac4_unparsed_element_refused_without_traces (прежний файл `test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py`): `orchestrator/merge_after.py` `declared_from_tz`: строка с негодным элементом молча отбрасывается; может зациклить общий узел: да — меняет строки узла из перечня, прогнан один в части; зерно: негодный элемент в хвосте есть всегда, с соседом или без.
- mutation-043 — заявка NewRefusesTest::test_ac4_unparsed_element_refused_without_traces, NewRefusesTest::test_ac6_invalid_dependency_refused_without_traces (прежний файл `test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py`, `test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py`): `orchestrator/catalog.py` `cmd_new`: строка «Порядок:» проверяется после заведения строки задачи; может зациклить общий узел: нет — строк узлов `check`/`_cycle_path`/разбора «Порядок:»/`merge_after_items`/префикса не меняет; зерно: каждый вариант негоден при любом зерне — строка задачи появляется.
- mutation-044 — заявка NewRefusesTest::test_ac5_repeated_order_line_refused_without_traces (прежний файл `test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py`): `orchestrator/merge_after.py` `declared_from_tz`: повтор строки не сверяется — берётся первая; может зациклить общий узел: да — меняет строки узла из перечня, прогнан один в части; зерно: обе строки годны при любом зерне.
- mutation-045 — заявка NewRefusesTest::test_ac5_repeated_order_line_refused_without_traces (прежний файл `test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py`): `orchestrator/merge_after.py` `declared_from_tz`: повтор строки не сверяется — берётся последняя (переписанная альтернатива «значения объединяются»: при одной задаче в обеих строках её ловил отказ «повтор» — не при каждом зерне); может зациклить общий узел: да — меняет строки узла из перечня, прогнан один в части; зерно: обе строки годны при любом зерне.
- mutation-046 — заявка NewRefusesTest::test_ac6_invalid_dependency_refused_without_traces (прежний файл `test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py`): `orchestrator/merge_after.py` `declared_from_tz`: строка разбирается только по форме, без `check`; может зациклить общий узел: да — меняет строки узла из перечня, прогнан один в части; зерно: варианты «нет такой задачи», «убитая», «чужой target» годны по форме и перебираются всегда.
- mutation-047 — заявка NewRefusesTest::test_ac7_path_refusal_and_order_refusal_printed_together (прежний файл `test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py`): `orchestrator/catalog.py` `cmd_new`: отказ сверки путей выходит раньше разбора «Порядок:»; может зациклить общий узел: нет — строк узлов `check`/`_cycle_path`/разбора «Порядок:»/`merge_after_items`/префикса не меняет; зерно: отказ сверки путей есть всегда, элемент любой ветки зерна в вывод не попадает.
- mutation-048 — заявка NewRefusesTest::test_ac7_path_refusal_and_order_refusal_printed_together (прежний файл `test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py`): `orchestrator/catalog.py` `cmd_new`: отказ «Порядок:» вытесняет отказ сверки путей; может зациклить общий узел: нет — строк узлов `check`/`_cycle_path`/разбора «Порядок:»/`merge_after_items`/префикса не меняет; зерно: и элемент не в форме, и несуществующий id дают отказ «Порядок:» при любом зерне.
- mutation-049 — заявка DeclaredStatusShowTest::test_ac8_status_and_show_carry_declared_dependencies (прежний файл `test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py`): `orchestrator/merge_after.py` `status_suffix`: снята ветка ранних состояний; может зациклить общий узел: нет — строк узлов `check`/`_cycle_path`/разбора «Порядок:»/`merge_after_items`/префикса не меняет; зерно: оба ранних состояния перебираются при любом зерне.
- mutation-050 — заявка DeclaredStatusShowTest::test_ac8_status_and_show_carry_declared_dependencies (прежний файл `test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py`): `orchestrator/merge_after.py` `status_suffix`: в ранних состояниях «[ждёт мержа:» вместо «[мерж после:»; может зациклить общий узел: нет — строк узлов `check`/`_cycle_path`/разбора «Порядок:»/`merge_after_items`/префикса не меняет; зерно: оба ранних состояния перебираются при любом зерне.

## Находки

- Находка: mutation-026 (`SpecGateCycleTest::test_ac4_cycle_through_existing_values_refused`, альтернатива «граф строится без нового значения A») «до» и «после» не убита никем: путь B → A находится по рёбрам БД без рёбер A. Тест не удалён; его заявка переписана на mutation-025.
- Находка: `SpecGateWritesColumnTest::test_ac5_prefixes_written_as_full_ids_in_spec_order`, альтернатива «id сортируются»: при одной зависимости или уже упорядоченных id сортировка ничего не меняет — мутации порядка, убиваемой при любом зерне, у теста нет; заявка переписана на mutation-027.
- Находка: `NewDeclaresTest::test_ac2_list_ends_at_parenthesis_or_dot`, альтернатива «склеивает продолжение на следующей строке»: перечень режется на «(»/«.» первой строки, склейка следующей строки не наблюдается ни при каком зерне; заявка переписана на mutation-039.

## Строки падения

Формат: мутация, убийца «до» — `файл:строка` упавшего утверждения (для
помощника результата — и строка вызова-действия в теле теста) → функция
модуля — `файл:строка` её утверждения и вызова; «то же утверждение» —
соответствие требования 11. Строки — из логов прогонов патчей
(`<id>-mutation-run-<n>-p<nnn>.log`).

- mutation-001: AnswerMandateAcceptedTest::test_ac11_escalated_answer_sets_and_clears_value — tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py:128 (вызов в теле теста tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py:174) → test_merge_after_module.py::test_ac11_escalated_answer_sets_and_clears_value — tests/test_merge_after_module.py:1024 (вызов в теле теста tests/test_merge_after_module.py:1070) (то же утверждение)
- mutation-002: AnswerMandateAcceptedTest::test_ac11_escalated_answer_sets_and_clears_value — tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py:169 → test_merge_after_module.py::test_ac11_escalated_answer_sets_and_clears_value — tests/test_merge_after_module.py:1065 (то же утверждение)
- mutation-003: AnswerMandateAcceptedTest::test_ac11_merge_gate_answer_outside_role_env_accepted — tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py:128 (вызов в теле теста tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py:205) → test_merge_after_module.py::test_ac11_merge_gate_answer_outside_role_env_accepted — tests/test_merge_after_module.py:1024 (вызов в теле теста tests/test_merge_after_module.py:1102) (то же утверждение)
- mutation-004: AnswerMandateRefusedTest::test_ac12_invalid_mandate_element_refused_before_commit — tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py:142 (вызов в теле теста tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py:245) → test_merge_after_module.py::test_ac12_invalid_mandate_element_refused_before_commit — tests/test_merge_after_module.py:1039 (вызов в теле теста tests/test_merge_after_module.py:1139) (то же утверждение)
- mutation-005: AnswerMandateRefusedTest::test_ac12_invalid_mandate_element_refused_before_commit — tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py:143 (вызов в теле теста tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py:245) → test_merge_after_module.py::test_ac12_invalid_mandate_element_refused_before_commit — tests/test_merge_after_module.py:1040 (вызов в теле теста tests/test_merge_after_module.py:1139) (то же утверждение)
- mutation-006: AnswerMandateRefusedTest::test_ac12_merge_gate_without_line_or_from_role_env_refused — tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py:142 (вызов в теле теста tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py:264) → test_merge_after_module.py::test_ac12_merge_gate_without_line_or_from_role_env_refused — tests/test_merge_after_module.py:1039 (вызов в теле теста tests/test_merge_after_module.py:1159) (то же утверждение)
- mutation-007: AnswerMandateRefusedTest::test_ac12_merge_gate_without_line_or_from_role_env_refused — tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py:142 (вызов в теле теста tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py:270) → test_merge_after_module.py::test_ac12_merge_gate_without_line_or_from_role_env_refused — tests/test_merge_after_module.py:1039 (вызов в теле теста tests/test_merge_after_module.py:1165) (то же утверждение)
- mutation-008: GuardMergeAfterFieldTest::test_ac1_self_reference_names_field_and_element — tests/test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py:101 → test_merge_after_module.py::test_ac1_self_reference_names_field_and_element — tests/test_merge_after_module.py:1246 (то же утверждение)
- mutation-009: GuardMergeAfterFieldTest::test_ac1_repeated_element_is_a_repeat_error — tests/test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py:122 → test_merge_after_module.py::test_ac1_repeated_element_is_a_repeat_error — tests/test_merge_after_module.py:1268 (то же утверждение)
- mutation-010: GuardMergeAfterFieldTest::test_ac1_element_not_in_task_id_format_is_a_form_error — tests/test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py:144 → test_merge_after_module.py::test_ac1_element_not_in_task_id_format_is_a_form_error — tests/test_merge_after_module.py:1289 (то же утверждение)
- mutation-011: GuardMergeAfterFieldTest::test_ac1_valid_list_and_missing_field_pass — tests/test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py:173 → test_merge_after_module.py::test_ac1_valid_list_and_missing_field_pass — tests/test_merge_after_module.py:1319 (то же утверждение)
- mutation-012: StatusSuffixTest::test_ac13_status_suffix_lists_unfinished_and_disappears_after_done убивает её лишь на части зёрен — из сравнения «до → после» выведен (требование 13).
- mutation-012: GuardMergeAfterFieldTest::test_ac1_valid_list_and_missing_field_pass — tests/test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py:169 → test_merge_after_module.py::test_ac1_valid_list_and_missing_field_pass — tests/test_merge_after_module.py:1316 (то же утверждение)
- mutation-013: PlanChannelAppliesTest::test_ac9_justified_plan_value_replaces_db_value — tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py:220 → test_merge_after_module.py::test_ac9_justified_plan_value_replaces_db_value — tests/test_merge_after_module.py:1541 (то же утверждение)
- mutation-014: PlanChannelAppliesTest::test_ac9_justified_plan_value_replaces_db_value — tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py:221 → test_merge_after_module.py::test_ac9_justified_plan_value_replaces_db_value — tests/test_merge_after_module.py:1542 (то же утверждение)
- mutation-015: PlanChannelAppliesTest::test_ac9_empty_plan_value_clears_dependencies — tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py:243 → test_merge_after_module.py::test_ac9_empty_plan_value_clears_dependencies — tests/test_merge_after_module.py:1566 (то же утверждение)
- mutation-016: PlanChannelAppliesTest::test_ac9_plan_without_field_keeps_db_value — tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py:264 → test_merge_after_module.py::test_ac9_plan_without_field_keeps_db_value — tests/test_merge_after_module.py:1588 (то же утверждение)
- mutation-017: PlanChannelRejectsTest::test_ac10_rejected_plan_value_keeps_db_and_transition — tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py:319 → test_merge_after_module.py::test_ac10_rejected_plan_value_keeps_db_and_transition — tests/test_merge_after_module.py:1620 (то же утверждение)
- mutation-018: PlanChannelRejectsTest::test_ac10_rejected_plan_value_keeps_db_and_transition — tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py:320 → test_merge_after_module.py::test_ac10_rejected_plan_value_keeps_db_and_transition — tests/test_merge_after_module.py:1622 (то же утверждение)
- mutation-019: PlanChannelRejectsTest::test_ac10_rejected_plan_value_keeps_db_and_transition — tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py:320 → test_merge_after_module.py::test_ac10_rejected_plan_value_keeps_db_and_transition — tests/test_merge_after_module.py:1622 (то же утверждение)
- mutation-020: SpecGateMissingOrAmbiguousTest::test_ac2_missing_task_keeps_spec_gate_and_column_empty — tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py:163 (вызов в теле теста tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py:194) → test_merge_after_module.py::test_ac2_missing_task_keeps_spec_gate_and_column_empty — tests/test_merge_after_module.py:1772 (вызов в теле теста tests/test_merge_after_module.py:1801) (то же утверждение)
- mutation-021: SpecGateMissingOrAmbiguousTest::test_ac2_ambiguous_prefix_keeps_spec_gate_and_column_empty — tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py:163 (вызов в теле теста tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py:216) → test_merge_after_module.py::test_ac2_ambiguous_prefix_keeps_spec_gate_and_column_empty — tests/test_merge_after_module.py:1772 (вызов в теле теста tests/test_merge_after_module.py:1824) (то же утверждение)
- mutation-022: SpecGateKilledForeignSelfTest::test_ac3_killed_dependency_refused — tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py:163 (вызов в теле теста tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py:236) → test_merge_after_module.py::test_ac3_killed_dependency_refused — tests/test_merge_after_module.py:1772 (вызов в теле теста tests/test_merge_after_module.py:1842) (то же утверждение)
- mutation-023: SpecGateKilledForeignSelfTest::test_ac3_dependency_of_other_target_refused — tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py:163 (вызов в теле теста tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py:256) → test_merge_after_module.py::test_ac3_dependency_of_other_target_refused — tests/test_merge_after_module.py:1772 (вызов в теле теста tests/test_merge_after_module.py:1863) (то же утверждение)
- mutation-023: NewRefusesTest::test_ac6_invalid_dependency_refused_without_traces — tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py:162 (вызов в теле теста tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py:368) → test_merge_after_module.py::test_ac6_invalid_dependency_refused_without_traces — tests/test_merge_after_module.py:2360 (вызов в теле теста tests/test_merge_after_module.py:2563) (то же утверждение)
- mutation-024: SpecGateKilledForeignSelfTest::test_ac3_prefix_resolving_to_own_id_refused — tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py:165 (вызов в теле теста tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py:279) → test_merge_after_module.py::test_ac3_prefix_resolving_to_own_id_refused — tests/test_merge_after_module.py:1774 (вызов в теле теста tests/test_merge_after_module.py:1887) (то же утверждение)
- mutation-025: SpecGateCycleTest::test_ac4_cycle_through_existing_values_refused — tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py:163 (вызов в теле теста tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py:310) → test_merge_after_module.py::test_ac4_cycle_through_existing_values_refused — tests/test_merge_after_module.py:1772 (вызов в теле теста tests/test_merge_after_module.py:1916) (то же утверждение)
- mutation-027: SpecGateWritesColumnTest::test_ac5_prefixes_written_as_full_ids_in_spec_order — tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py:338 → test_merge_after_module.py::test_ac5_prefixes_written_as_full_ids_in_spec_order — tests/test_merge_after_module.py:1941 (то же утверждение)
- mutation-028: SpecGateWritesColumnTest::test_ac5_spec_without_field_leaves_column_empty — tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py:359 → test_merge_after_module.py::test_ac5_spec_without_field_leaves_column_empty — tests/test_merge_after_module.py:1963 (то же утверждение)
- mutation-029: SpecGateWritesColumnTest::test_ac5_spec_without_field_leaves_column_empty — tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py:360 → test_merge_after_module.py::test_ac5_spec_without_field_leaves_column_empty — tests/test_merge_after_module.py:1964 (то же утверждение)
- mutation-030: StatusSuffixTest::test_ac13_status_suffix_lists_unfinished_and_disappears_after_done — tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py:177 → test_merge_after_module.py::test_ac13_status_suffix_lists_unfinished_and_disappears_after_done — tests/test_merge_after_module.py:2126 (то же утверждение)
- mutation-030: DeclaredStatusShowTest::test_ac8_status_and_show_carry_declared_dependencies — tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py:440 → test_merge_after_module.py::test_ac8_status_and_show_carry_declared_dependencies — tests/test_merge_after_module.py:2634 (то же утверждение)
- mutation-031: StatusSuffixTest::test_ac13_no_suffix_without_field_or_all_done убивает её лишь на части зёрен — из сравнения «до → после» выведен (требование 13).
- mutation-031: StatusSuffixTest::test_ac13_status_suffix_lists_unfinished_and_disappears_after_done — tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py:177 → test_merge_after_module.py::test_ac13_status_suffix_lists_unfinished_and_disappears_after_done — tests/test_merge_after_module.py:2126 (то же утверждение)
- mutation-031: DeclaredStatusShowTest::test_ac8_status_and_show_carry_declared_dependencies — tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py:440 → test_merge_after_module.py::test_ac8_status_and_show_carry_declared_dependencies — tests/test_merge_after_module.py:2634 (то же утверждение)
- mutation-032: StatusSuffixTest::test_ac13_no_suffix_in_other_state — tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py:195 → test_merge_after_module.py::test_ac13_no_suffix_in_other_state — tests/test_merge_after_module.py:2146 (то же утверждение)
- mutation-033: StatusSuffixTest::test_ac13_no_suffix_without_field_or_all_done — tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py:224 → test_merge_after_module.py::test_ac13_no_suffix_without_field_or_all_done — tests/test_merge_after_module.py:2174 (то же утверждение)
- mutation-034: ShowDependenciesTest::test_ac14_show_lists_all_dependencies_with_states — tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py:253 → test_merge_after_module.py::test_ac14_show_lists_all_dependencies_with_states — tests/test_merge_after_module.py:2201 (то же утверждение)
- mutation-035: ShowDependenciesTest::test_ac14_show_without_dependencies_has_no_line — tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py:271 → test_merge_after_module.py::test_ac14_show_without_dependencies_has_no_line — tests/test_merge_after_module.py:2220 (то же утверждение)
- mutation-036: NewDeclaresTest::test_ac1_order_line_declares_full_ids_in_line_order — tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py:217 → test_merge_after_module.py::test_ac1_order_line_declares_full_ids_in_line_order — tests/test_merge_after_module.py:2414 (то же утверждение)
- mutation-037: NewDeclaresTest::test_ac1_order_line_declares_full_ids_in_line_order — tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py:217 → test_merge_after_module.py::test_ac1_order_line_declares_full_ids_in_line_order — tests/test_merge_after_module.py:2414 (то же утверждение)
- mutation-038: NewDeclaresTest::test_ac1_order_line_declares_full_ids_in_line_order — tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py:218 → test_merge_after_module.py::test_ac1_order_line_declares_full_ids_in_line_order — tests/test_merge_after_module.py:2416 (то же утверждение)
- mutation-039: NewDeclaresTest::test_ac2_list_ends_at_parenthesis_or_dot — tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py:146 (вызов в теле теста tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py:246) → test_merge_after_module.py::test_ac2_list_ends_at_parenthesis_or_dot — tests/test_merge_after_module.py:2342 (вызов в теле теста tests/test_merge_after_module.py:2442) (то же утверждение)
- mutation-040: NewDeclaresTest::test_ac3_order_line_without_after_declares_nothing — tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py:146 (вызов в теле теста tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py:271) → test_merge_after_module.py::test_ac3_order_line_without_after_declares_nothing — tests/test_merge_after_module.py:2342 (вызов в теле теста tests/test_merge_after_module.py:2467) (то же утверждение)
- mutation-041: NewDeclaresTest::test_ac3_order_line_without_after_declares_nothing — tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py:275 → test_merge_after_module.py::test_ac3_order_line_without_after_declares_nothing — tests/test_merge_after_module.py:2471 (то же утверждение)
- mutation-042: NewRefusesTest::test_ac4_unparsed_element_refused_without_traces — tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py:162 (вызов в теле теста tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py:301) → test_merge_after_module.py::test_ac4_unparsed_element_refused_without_traces — tests/test_merge_after_module.py:2360 (вызов в теле теста tests/test_merge_after_module.py:2496) (то же утверждение)
- mutation-043: NewRefusesTest::test_ac4_unparsed_element_refused_without_traces — tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py:166 (вызов в теле теста tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py:301) → test_merge_after_module.py::test_ac4_unparsed_element_refused_without_traces — tests/test_merge_after_module.py:2364 (вызов в теле теста tests/test_merge_after_module.py:2496) (то же утверждение)
- mutation-043: NewRefusesTest::test_ac6_invalid_dependency_refused_without_traces — tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py:166 (вызов в теле теста tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py:368) → test_merge_after_module.py::test_ac6_invalid_dependency_refused_without_traces — tests/test_merge_after_module.py:2364 (вызов в теле теста tests/test_merge_after_module.py:2563) (то же утверждение)
- mutation-044: NewRefusesTest::test_ac5_repeated_order_line_refused_without_traces — tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py:162 (вызов в теле теста tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py:319) → test_merge_after_module.py::test_ac5_repeated_order_line_refused_without_traces — tests/test_merge_after_module.py:2360 (вызов в теле теста tests/test_merge_after_module.py:2515) (то же утверждение)
- mutation-045: NewRefusesTest::test_ac5_repeated_order_line_refused_without_traces — tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py:162 (вызов в теле теста tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py:319) → test_merge_after_module.py::test_ac5_repeated_order_line_refused_without_traces — tests/test_merge_after_module.py:2360 (вызов в теле теста tests/test_merge_after_module.py:2515) (то же утверждение)
- mutation-046: NewRefusesTest::test_ac7_path_refusal_and_order_refusal_printed_together убивает её лишь на части зёрен — из сравнения «до → после» выведен (требование 13).
- mutation-046: NewRefusesTest::test_ac6_invalid_dependency_refused_without_traces — tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py:162 (вызов в теле теста tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py:368) → test_merge_after_module.py::test_ac6_invalid_dependency_refused_without_traces — tests/test_merge_after_module.py:2360 (вызов в теле теста tests/test_merge_after_module.py:2563) (то же утверждение)
- mutation-047: NewRefusesTest::test_ac7_path_refusal_and_order_refusal_printed_together — tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py:163 (вызов в теле теста tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py:391) → test_merge_after_module.py::test_ac7_path_refusal_and_order_refusal_printed_together — tests/test_merge_after_module.py:2361 (вызов в теле теста tests/test_merge_after_module.py:2587) (то же утверждение)
- mutation-048: NewRefusesTest::test_ac7_path_refusal_and_order_refusal_printed_together — tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py:165 (вызов в теле теста tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py:391) → test_merge_after_module.py::test_ac7_path_refusal_and_order_refusal_printed_together — tests/test_merge_after_module.py:2363 (вызов в теле теста tests/test_merge_after_module.py:2587) (то же утверждение)
- mutation-049: DeclaredStatusShowTest::test_ac8_status_and_show_carry_declared_dependencies — tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py:431 → test_merge_after_module.py::test_ac8_status_and_show_carry_declared_dependencies — tests/test_merge_after_module.py:2625 (то же утверждение)
- mutation-050: DeclaredStatusShowTest::test_ac8_status_and_show_carry_declared_dependencies — tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py:431 → test_merge_after_module.py::test_ac8_status_and_show_carry_declared_dependencies — tests/test_merge_after_module.py:2625 (то же утверждение)

## Подготовка и предпосылки

Утверждения и вызовы, не служащие доказательством (требование 4), и их
места после свода:

- tests/test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py:160 (утверждение в `test_ac1_valid_list_and_missing_field_pass`) → tests/test_merge_after_module.py:1307 (`test_ac1_valid_list_and_missing_field_pass`) — не доказательство.
- tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py:160 (утверждение в `approve_spec`) → tests/test_merge_after_module.py:1456 (`plan_approve_spec`) — не доказательство.
- tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py:276 (утверждение в `test_ac3_prefix_resolving_to_own_id_refused`) → tests/test_merge_after_module.py:1884 (`test_ac3_prefix_resolving_to_own_id_refused`) — не доказательство.
- tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py:305 (утверждение в `test_ac4_cycle_through_existing_values_refused`) → tests/test_merge_after_module.py:1910 (`test_ac4_cycle_through_existing_values_refused`) — не доказательство.
- tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py:104 (утверждение в `with_dependencies`) → tests/test_merge_after_module.py:2051 (`status_show_with_dependencies`) — не доказательство.
- tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py:108 (утверждение в `with_dependencies`) → tests/test_merge_after_module.py:2055 (`status_show_with_dependencies`) — не доказательство.
- tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py:116 (утверждение в `status_line`) → tests/test_merge_after_module.py:2064 (`status_show_status_line`) — не доказательство.
- tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py:180 (утверждение в `status_line`) → tests/test_merge_after_module.py:2380 (`new_declares_status_line`) — не доказательство.
- tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py:198 (вызов-подготовка `accepted` в `test_ac11_merge_gate_answer_outside_role_env_accepted`) → tests/test_merge_after_module.py:1095 (`answer_accepted`) — не доказательство.
- tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py:233 (вызов-подготовка `accepted` в `test_ac12_invalid_mandate_element_refused_before_commit`) → tests/test_merge_after_module.py:1127 (`answer_accepted`) — не доказательство.
- tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py:242 (вызов-подготовка `accepted` в `test_ac12_invalid_mandate_element_refused_before_commit`) → tests/test_merge_after_module.py:1136 (`answer_accepted`) — не доказательство.
- tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py:261 (вызов-подготовка `accepted` в `test_ac12_merge_gate_without_line_or_from_role_env_refused`) → tests/test_merge_after_module.py:1156 (`answer_accepted`) — не доказательство.
- tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py:419 (вызов-подготовка `declared` в `test_ac8_status_and_show_carry_declared_dependencies`) → tests/test_merge_after_module.py:2613 (`new_declares_declared`) — не доказательство.

## Числа и время

- До свода (база ad3608c6): шесть файлов волны — 33 тестов, 1867 строк (`test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py` — 4 тестов, 274 строк, `test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py` — 4 тестов, 179 строк, `test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py` — 4 тестов, 329 строк, `test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py` — 8 тестов, 365 строк, `test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py` — 5 тестов, 275 строк, `test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py` — 8 тестов, 445 строк); `tests/test_merge_after_module.py` — 20 тестов, 882 строк.
- После свода (HEAD): `tests/test_merge_after_module.py` — 53 тестов (20 + 33, удалённых дублей нет), 2636 строк; шести файлов волны на ветке нет.
- Контрольные прогоны `mutation-run` (без патча): «до» — №1: 5,09 с, №2: 4,83 с, №3: 5,20 с, №4: 5,14 с, №5: 4,92 с, №6: 4,95 с, №7: 4,88 с, №8: 4,87 с, №9: 5,09 с, №10: 5,25 с, №11: 4,93 с, №12: 4,85 с, №13: 4,95 с, №14: 4,81 с, №15: 4,82 с, №16: 5,10 с, №17: 4,95 с, №18: 4,89 с, №19: 5,02 с, №20: 4,80 с; «после» — №21: 2,33 с, №22: 2,63 с, №23: 2,46 с, №24: 2,67 с, №25: 2,40 с, №26: 2,67 с, №27: 2,64 с, №28: 2,35 с, №29: 2,68 с, №30: 2,40 с, №31: 2,39 с, №32: 2,66 с, №33: 2,52 с, №34: 2,53 с, №35: 2,68 с, №36: 2,42 с, №37: 2,69 с, №38: 2,51 с, №39: 2,52 с, №40: 2,39 с.

## Мутации до

Команда частей: `mutation-run 01M5RHGRH3YJV8VBFH3QCHD8X0 --ref base --tests <шесть файлов волны> --copy-table --wait-lock 4 --patches <a>-<b>`, рабочих процессов — по умолчанию (`auto`). Части: 1-11, 12, 13-19, 20, 21, 22, 23, 24, 25, 26, 27-38, 39, 40, 41, 42, 43, 44, 45, 46, 47-50.

Часть №1:

```
# mutation-run №1 задачи 01M5RHGRH3YJV8VBFH3QCHD8X0
# источник патчей: каталог на диске
# ревизия прогона: base ad3608c6d2ceedd43f2d91ad569a6b8684804782
# тесты: tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py, tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py
# рабочих процессов: auto
# патч 1 mutation-001.diff sha256 b3309d055b1b47e0fce351402e347e47b5fca4407261b647a201cbbef7b12d8e
# патч 2 mutation-002.diff sha256 6f1403596aadf7995636660dcaaaf71615e408a018a9ee408db8f86f83e7c7ce
# патч 3 mutation-003.diff sha256 143266dae32ea8c6ec5de68b8b0e400984ac656becb3f0602ffc7c58db4fefb2
# патч 4 mutation-004.diff sha256 95947f974b47f8a40ebb9d5802d67a7ced7d23c172a255b4349e3bb66b3cbc07
# патч 5 mutation-005.diff sha256 2d0e364f910a700af91c0c40d3bbf059dbc9f38fe19fbb64a56460bd2f4b6fbe
# патч 6 mutation-006.diff sha256 56586fc4e65fbfe14d5a5456eea4acebb80d8f254cb98a4f22828fb820fb6dbb
# патч 7 mutation-007.diff sha256 b4f3eb89507bacedde2e6cfc58187b87c5f0bc6a8aef6d1b22a7a3d67407e8f3
# патч 8 mutation-008.diff sha256 d8158f2ae72c316ae402dd108cbef3c01ac09ebdaad50e6a805ffa7b3d6fa092
# патч 9 mutation-009.diff sha256 df9b2db4fa0a9b223969433944659f1c3fca4300d31fbacb3a290b220363e504
# патч 10 mutation-010.diff sha256 b5b17202281d659d35e434fd444e629449366bfd51387dfdbf0ee5eaf445782e
# патч 11 mutation-011.diff sha256 4880e8e47e428e2ef5db129aa99985d2ce31fc42aaa5e1497423142b154da3c4
номер	исход	узлы
1	убита	tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py::AnswerMandateAcceptedTest::test_ac11_escalated_answer_sets_and_clears_value
2	убита	tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py::AnswerMandateAcceptedTest::test_ac11_escalated_answer_sets_and_clears_value,tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py::AnswerMandateRefusedTest::test_ac12_invalid_mandate_element_refused_before_commit,tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py::AnswerMandateAcceptedTest::test_ac11_merge_gate_answer_outside_role_env_accepted
3	убита	tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py::AnswerMandateAcceptedTest::test_ac11_merge_gate_answer_outside_role_env_accepted
4	убита	tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py::AnswerMandateRefusedTest::test_ac12_invalid_mandate_element_refused_before_commit
5	убита	tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py::AnswerMandateRefusedTest::test_ac12_invalid_mandate_element_refused_before_commit
6	убита	tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py::AnswerMandateRefusedTest::test_ac12_merge_gate_without_line_or_from_role_env_refused
7	убита	tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py::AnswerMandateRefusedTest::test_ac12_merge_gate_without_line_or_from_role_env_refused
8	убита	tests/test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py::GuardMergeAfterFieldTest::test_ac1_self_reference_names_field_and_element
9	убита	tests/test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py::GuardMergeAfterFieldTest::test_ac1_repeated_element_is_a_repeat_error
10	убита	tests/test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py::GuardMergeAfterFieldTest::test_ac1_element_not_in_task_id_format_is_a_form_error
11	убита	tests/test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py::GuardMergeAfterFieldTest::test_ac1_valid_list_and_missing_field_pass
```

Часть №2:

```
# mutation-run №2 задачи 01M5RHGRH3YJV8VBFH3QCHD8X0
# источник патчей: каталог на диске
# ревизия прогона: base ad3608c6d2ceedd43f2d91ad569a6b8684804782
# тесты: tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py, tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py
# рабочих процессов: auto
# патч 12 mutation-012.diff sha256 28ebaadb67a982f43c97245ace0be3a0b869f1a341534442103625eb3d17a705
номер	исход	узлы
12	убита	tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py::NewDeclaresTest::test_ac2_list_ends_at_parenthesis_or_dot,tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py::StatusSuffixTest::test_ac13_status_suffix_lists_unfinished_and_disappears_after_done,tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py::StatusSuffixTest::test_ac13_no_suffix_in_other_state,tests/test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py::GuardMergeAfterFieldTest::test_ac1_repeated_element_is_a_repeat_error,tests/test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py::GuardMergeAfterFieldTest::test_ac1_valid_list_and_missing_field_pass,tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py::NewRefusesTest::test_ac6_invalid_dependency_refused_without_traces,tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py::NewDeclaresTest::test_ac1_order_line_declares_full_ids_in_line_order,tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py::ShowDependenciesTest::test_ac14_show_lists_all_dependencies_with_states,tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py::PlanChannelRejectsTest::test_ac10_rejected_plan_value_keeps_db_and_transition
```

Часть №3:

```
# mutation-run №3 задачи 01M5RHGRH3YJV8VBFH3QCHD8X0
# источник патчей: каталог на диске
# ревизия прогона: base ad3608c6d2ceedd43f2d91ad569a6b8684804782
# тесты: tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py, tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py
# рабочих процессов: auto
# патч 13 mutation-013.diff sha256 7675a1ebafce60997d81b5e71f41683edf89ed31e0f16716c2d8a0eebccb6568
# патч 14 mutation-014.diff sha256 3a828d119a13a6e5d80ed78560d33789e3c4f6bfe72fdc4a60eda795ce1a9c8b
# патч 15 mutation-015.diff sha256 4d9c07c5ec5e3f83100bf12f69d31f27fd48fda7a651b9fee025a9233d709025
# патч 16 mutation-016.diff sha256 b1620e505b197af1edba012019409f110a723ee513e3ef390b8287ae368687a8
# патч 17 mutation-017.diff sha256 c6ac2f6a10727737e81a94a8297f7d271d93b32cc4d99786ff791a1be5e71510
# патч 18 mutation-018.diff sha256 6bd4f0f9603534e90ff04a75df05641d8f49c2e3142152fb2162a2ac01d9697d
# патч 19 mutation-019.diff sha256 4dc2f44b122ba91f15d0c91a06de971945c46f36f076855f337165d74a28d4c0
номер	исход	узлы
13	убита	tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py::PlanChannelAppliesTest::test_ac9_empty_plan_value_clears_dependencies,tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py::PlanChannelAppliesTest::test_ac9_justified_plan_value_replaces_db_value,tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py::PlanChannelRejectsTest::test_ac10_rejected_plan_value_keeps_db_and_transition
14	убита	tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py::AnswerMandateAcceptedTest::test_ac11_escalated_answer_sets_and_clears_value,tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py::PlanChannelAppliesTest::test_ac9_justified_plan_value_replaces_db_value
15	убита	tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py::PlanChannelAppliesTest::test_ac9_empty_plan_value_clears_dependencies
16	убита	tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py::PlanChannelAppliesTest::test_ac9_plan_without_field_keeps_db_value
17	убита	tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py::PlanChannelRejectsTest::test_ac10_rejected_plan_value_keeps_db_and_transition
18	убита	tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py::PlanChannelRejectsTest::test_ac10_rejected_plan_value_keeps_db_and_transition
19	убита	tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py::PlanChannelRejectsTest::test_ac10_rejected_plan_value_keeps_db_and_transition
```

Часть №4:

```
# mutation-run №4 задачи 01M5RHGRH3YJV8VBFH3QCHD8X0
# источник патчей: каталог на диске
# ревизия прогона: base ad3608c6d2ceedd43f2d91ad569a6b8684804782
# тесты: tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py, tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py
# рабочих процессов: auto
# патч 20 mutation-020.diff sha256 7ad7f09479bc3b204a0a83dba6e6b6dce60f1f0fa6363b16ba1498df68b9dc37
номер	исход	узлы
20	убита	tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py::AnswerMandateRefusedTest::test_ac12_invalid_mandate_element_refused_before_commit,tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py::NewRefusesTest::test_ac7_path_refusal_and_order_refusal_printed_together,tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py::SpecGateMissingOrAmbiguousTest::test_ac2_missing_task_keeps_spec_gate_and_column_empty,tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py::NewRefusesTest::test_ac6_invalid_dependency_refused_without_traces,tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py::PlanChannelRejectsTest::test_ac10_rejected_plan_value_keeps_db_and_transition
```

Часть №5:

```
# mutation-run №5 задачи 01M5RHGRH3YJV8VBFH3QCHD8X0
# источник патчей: каталог на диске
# ревизия прогона: base ad3608c6d2ceedd43f2d91ad569a6b8684804782
# тесты: tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py, tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py
# рабочих процессов: auto
# патч 21 mutation-021.diff sha256 01e97cc5008433518beca03b9f0dc020f69222bee95dcf67728d09e811d36f8c
номер	исход	узлы
21	убита	tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py::SpecGateMissingOrAmbiguousTest::test_ac2_ambiguous_prefix_keeps_spec_gate_and_column_empty,tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py::NewRefusesTest::test_ac6_invalid_dependency_refused_without_traces
```

Часть №6:

```
# mutation-run №6 задачи 01M5RHGRH3YJV8VBFH3QCHD8X0
# источник патчей: каталог на диске
# ревизия прогона: base ad3608c6d2ceedd43f2d91ad569a6b8684804782
# тесты: tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py, tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py
# рабочих процессов: auto
# патч 22 mutation-022.diff sha256 28701215bd85e927caba6fa72d057498601cc5178029fa4d0ac6e9c87e2ca971
номер	исход	узлы
22	убита	tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py::AnswerMandateRefusedTest::test_ac12_invalid_mandate_element_refused_before_commit,tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py::NewRefusesTest::test_ac6_invalid_dependency_refused_without_traces,tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py::SpecGateKilledForeignSelfTest::test_ac3_killed_dependency_refused,tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py::PlanChannelRejectsTest::test_ac10_rejected_plan_value_keeps_db_and_transition
```

Часть №7:

```
# mutation-run №7 задачи 01M5RHGRH3YJV8VBFH3QCHD8X0
# источник патчей: каталог на диске
# ревизия прогона: base ad3608c6d2ceedd43f2d91ad569a6b8684804782
# тесты: tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py, tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py
# рабочих процессов: auto
# патч 23 mutation-023.diff sha256 57f2df25d2f1e46b1a78dd4179693f81a0387b08345e7bd49259f02c3241ab7e
номер	исход	узлы
23	убита	tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py::SpecGateKilledForeignSelfTest::test_ac3_dependency_of_other_target_refused,tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py::NewRefusesTest::test_ac6_invalid_dependency_refused_without_traces
```

Часть №8:

```
# mutation-run №8 задачи 01M5RHGRH3YJV8VBFH3QCHD8X0
# источник патчей: каталог на диске
# ревизия прогона: base ad3608c6d2ceedd43f2d91ad569a6b8684804782
# тесты: tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py, tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py
# рабочих процессов: auto
# патч 24 mutation-024.diff sha256 bf128847abd7648dc1f82dabe1bd7998b355eea4426de684a214178270e23d57
номер	исход	узлы
24	убита	tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py::SpecGateKilledForeignSelfTest::test_ac3_prefix_resolving_to_own_id_refused
```

Часть №9:

```
# mutation-run №9 задачи 01M5RHGRH3YJV8VBFH3QCHD8X0
# источник патчей: каталог на диске
# ревизия прогона: base ad3608c6d2ceedd43f2d91ad569a6b8684804782
# тесты: tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py, tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py
# рабочих процессов: auto
# патч 25 mutation-025.diff sha256 0829aa652fd3d78ab7a598967a20be57a16a8c8b9c6a8be6d37c1ea18224c69e
номер	исход	узлы
25	убита	tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py::AnswerMandateRefusedTest::test_ac12_invalid_mandate_element_refused_before_commit,tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py::SpecGateCycleTest::test_ac4_cycle_through_existing_values_refused,tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py::PlanChannelRejectsTest::test_ac10_rejected_plan_value_keeps_db_and_transition
```

Часть №10:

```
# mutation-run №10 задачи 01M5RHGRH3YJV8VBFH3QCHD8X0
# источник патчей: каталог на диске
# ревизия прогона: base ad3608c6d2ceedd43f2d91ad569a6b8684804782
# тесты: tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py, tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py
# рабочих процессов: auto
# патч 26 mutation-026.diff sha256 84ab46b24bb84870d226cf6a82bdc5c0429fbd33087c3d9fd9d687860fad97b4
номер	исход	узлы
26	не убита	
```

Часть №11:

```
# mutation-run №11 задачи 01M5RHGRH3YJV8VBFH3QCHD8X0
# источник патчей: каталог на диске
# ревизия прогона: base ad3608c6d2ceedd43f2d91ad569a6b8684804782
# тесты: tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py, tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py
# рабочих процессов: auto
# патч 27 mutation-027.diff sha256 1a48b0a4431f769308471709cecaafbb9fe71a33a7659e5b555ecc09877d0bbb
# патч 28 mutation-028.diff sha256 6ee6e9c7aeecabc1556ceb68bb7a452cc91938b92673623e41328eb5ad4d2d8f
# патч 29 mutation-029.diff sha256 51219ae0b0b5fb4cb01685dbfa4a6c6379c509b7f752ff39f6680d424515a6f5
# патч 30 mutation-030.diff sha256 43af1d7401dfdfd4a7143551ed59424e81d003109f1207df01b95a6da859b939
# патч 31 mutation-031.diff sha256 c70ea3ba96850685b4dff4e0a0fc04c44ca330474ece96691b4a95f98fc9225c
# патч 32 mutation-032.diff sha256 bb955d793d3b7df7daf32f7ef3ee9e7539d34c89a9ab58abbf5b96711c7033a5
# патч 33 mutation-033.diff sha256 9c426d41e1fb1f4e0f92457876785803a4d6751e0ac05051c6df3fc8b6093903
# патч 34 mutation-034.diff sha256 1801418cff8c1ee659a9dc98b64a0cb029ecf54657b0a597cd5341421504559f
# патч 35 mutation-035.diff sha256 881518c24f6adfc99c364a2104652ff658b77fe07492925b56532d93d916c15d
# патч 36 mutation-036.diff sha256 5900940c4b62d4bf70d84d20be42b07d952da1b103650735bd1fa85b1eeb17bf
# патч 37 mutation-037.diff sha256 a853fc01755a5671392601ff62841c6c37fb30f84683002f21afb547f795e2b4
# патч 38 mutation-038.diff sha256 934b982b9a28015f3080af392ab4b7ebb5a2d17db9d5b32773691709f2480ced
номер	исход	узлы
27	убита	tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py::PlanChannelAppliesTest::test_ac9_plan_without_field_keeps_db_value,tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py::StatusSuffixTest::test_ac13_status_suffix_lists_unfinished_and_disappears_after_done,tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py::SpecGateWritesColumnTest::test_ac5_prefixes_written_as_full_ids_in_spec_order,tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py::StatusSuffixTest::test_ac13_no_suffix_in_other_state,tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py::PlanChannelAppliesTest::test_ac9_empty_plan_value_clears_dependencies,tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py::SpecGateCycleTest::test_ac4_cycle_through_existing_values_refused,tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py::PlanChannelRejectsTest::test_ac10_rejected_plan_value_keeps_db_and_transition,tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py::PlanChannelAppliesTest::test_ac9_justified_plan_value_replaces_db_value,tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py::ShowDependenciesTest::test_ac14_show_lists_all_dependencies_with_states
28	убита	tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py::ShowDependenciesTest::test_ac14_show_without_dependencies_has_no_line,tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py::SpecGateWritesColumnTest::test_ac5_spec_without_field_leaves_column_empty
29	убита	tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py::ShowDependenciesTest::test_ac14_show_without_dependencies_has_no_line,tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py::SpecGateWritesColumnTest::test_ac5_spec_without_field_leaves_column_empty
30	убита	tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py::StatusSuffixTest::test_ac13_status_suffix_lists_unfinished_and_disappears_after_done,tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py::DeclaredStatusShowTest::test_ac8_status_and_show_carry_declared_dependencies
31	убита	tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py::StatusSuffixTest::test_ac13_status_suffix_lists_unfinished_and_disappears_after_done,tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py::StatusSuffixTest::test_ac13_no_suffix_without_field_or_all_done,tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py::DeclaredStatusShowTest::test_ac8_status_and_show_carry_declared_dependencies
32	убита	tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py::StatusSuffixTest::test_ac13_no_suffix_in_other_state,tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py::DeclaredStatusShowTest::test_ac8_status_and_show_carry_declared_dependencies
33	убита	tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py::StatusSuffixTest::test_ac13_status_suffix_lists_unfinished_and_disappears_after_done,tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py::StatusSuffixTest::test_ac13_no_suffix_without_field_or_all_done,tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py::DeclaredStatusShowTest::test_ac8_status_and_show_carry_declared_dependencies
34	убита	tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py::ShowDependenciesTest::test_ac14_show_lists_all_dependencies_with_states
35	убита	tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py::ShowDependenciesTest::test_ac14_show_without_dependencies_has_no_line
36	убита	tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py::NewDeclaresTest::test_ac2_list_ends_at_parenthesis_or_dot,tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py::NewDeclaresTest::test_ac1_order_line_declares_full_ids_in_line_order,tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py::DeclaredStatusShowTest::test_ac8_status_and_show_carry_declared_dependencies
37	убита	tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py::NewDeclaresTest::test_ac2_list_ends_at_parenthesis_or_dot,tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py::NewDeclaresTest::test_ac1_order_line_declares_full_ids_in_line_order
38	убита	tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py::NewDeclaresTest::test_ac1_order_line_declares_full_ids_in_line_order
```

Часть №12:

```
# mutation-run №12 задачи 01M5RHGRH3YJV8VBFH3QCHD8X0
# источник патчей: каталог на диске
# ревизия прогона: base ad3608c6d2ceedd43f2d91ad569a6b8684804782
# тесты: tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py, tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py
# рабочих процессов: auto
# патч 39 mutation-039.diff sha256 96d253fa97abd8a74dbb9c2c0d42d406f75bd8df029c3c6ea40f31ff9f38b70f
номер	исход	узлы
39	убита	tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py::NewDeclaresTest::test_ac2_list_ends_at_parenthesis_or_dot
```

Часть №13:

```
# mutation-run №13 задачи 01M5RHGRH3YJV8VBFH3QCHD8X0
# источник патчей: каталог на диске
# ревизия прогона: base ad3608c6d2ceedd43f2d91ad569a6b8684804782
# тесты: tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py, tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py
# рабочих процессов: auto
# патч 40 mutation-040.diff sha256 3b23b723f15a80517b0cc772e557c88bc507ce6a5c7ac4ff0bba14100c007dd0
номер	исход	узлы
40	убита	tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py::NewDeclaresTest::test_ac3_order_line_without_after_declares_nothing
```

Часть №14:

```
# mutation-run №14 задачи 01M5RHGRH3YJV8VBFH3QCHD8X0
# источник патчей: каталог на диске
# ревизия прогона: base ad3608c6d2ceedd43f2d91ad569a6b8684804782
# тесты: tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py, tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py
# рабочих процессов: auto
# патч 41 mutation-041.diff sha256 0d848c1620df2dd58216587663a86296bb6e573fb0464f585bdc2f6fc2175180
номер	исход	узлы
41	убита	tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py::NewDeclaresTest::test_ac3_order_line_without_after_declares_nothing
```

Часть №15:

```
# mutation-run №15 задачи 01M5RHGRH3YJV8VBFH3QCHD8X0
# источник патчей: каталог на диске
# ревизия прогона: base ad3608c6d2ceedd43f2d91ad569a6b8684804782
# тесты: tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py, tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py
# рабочих процессов: auto
# патч 42 mutation-042.diff sha256 6359ed99b45b5c36cc529a6a846518a01fbc8871736f38b3a7bcbff1e5f4f95a
номер	исход	узлы
42	убита	tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py::NewRefusesTest::test_ac4_unparsed_element_refused_without_traces
```

Часть №16:

```
# mutation-run №16 задачи 01M5RHGRH3YJV8VBFH3QCHD8X0
# источник патчей: каталог на диске
# ревизия прогона: base ad3608c6d2ceedd43f2d91ad569a6b8684804782
# тесты: tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py, tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py
# рабочих процессов: auto
# патч 43 mutation-043.diff sha256 656bb2fd4f7fc917a428e769d356e5701201644ac99b3c00df7ece9e5a6565f1
номер	исход	узлы
43	убита	tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py::NewRefusesTest::test_ac5_repeated_order_line_refused_without_traces,tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py::NewRefusesTest::test_ac4_unparsed_element_refused_without_traces,tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py::NewRefusesTest::test_ac7_path_refusal_and_order_refusal_printed_together,tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py::NewRefusesTest::test_ac6_invalid_dependency_refused_without_traces
```

Часть №17:

```
# mutation-run №17 задачи 01M5RHGRH3YJV8VBFH3QCHD8X0
# источник патчей: каталог на диске
# ревизия прогона: base ad3608c6d2ceedd43f2d91ad569a6b8684804782
# тесты: tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py, tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py
# рабочих процессов: auto
# патч 44 mutation-044.diff sha256 7ab1f165b056c401c70e2d1ddb6a20161b572f24afca7724f6de997b83bb3295
номер	исход	узлы
44	убита	tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py::NewRefusesTest::test_ac5_repeated_order_line_refused_without_traces
```

Часть №18:

```
# mutation-run №18 задачи 01M5RHGRH3YJV8VBFH3QCHD8X0
# источник патчей: каталог на диске
# ревизия прогона: base ad3608c6d2ceedd43f2d91ad569a6b8684804782
# тесты: tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py, tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py
# рабочих процессов: auto
# патч 45 mutation-045.diff sha256 3a6b0c6a92d0378c9c69b8d52d97875f2690d9709bb355791515996265aaa5e0
номер	исход	узлы
45	убита	tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py::NewRefusesTest::test_ac5_repeated_order_line_refused_without_traces
```

Часть №19:

```
# mutation-run №19 задачи 01M5RHGRH3YJV8VBFH3QCHD8X0
# источник патчей: каталог на диске
# ревизия прогона: base ad3608c6d2ceedd43f2d91ad569a6b8684804782
# тесты: tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py, tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py
# рабочих процессов: auto
# патч 46 mutation-046.diff sha256 4f0815c9ecd2a677bd0b75a53b4add824a8ea1fad25623c5eba0a9d3b5c2d148
номер	исход	узлы
46	убита	tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py::NewDeclaresTest::test_ac2_list_ends_at_parenthesis_or_dot,tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py::NewRefusesTest::test_ac6_invalid_dependency_refused_without_traces,tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py::NewRefusesTest::test_ac7_path_refusal_and_order_refusal_printed_together,tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py::NewDeclaresTest::test_ac1_order_line_declares_full_ids_in_line_order
```

Часть №20:

```
# mutation-run №20 задачи 01M5RHGRH3YJV8VBFH3QCHD8X0
# источник патчей: каталог на диске
# ревизия прогона: base ad3608c6d2ceedd43f2d91ad569a6b8684804782
# тесты: tests/test_01m44ep0d47f498tee08mngbyt_answer_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_guard_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_plan_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_spec_gate_merge_after.py, tests/test_01m44ep0d47f498tee08mngbyt_status_show_merge_after.py, tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py
# рабочих процессов: auto
# патч 47 mutation-047.diff sha256 162393c4d098bfa2062c6becaa3b28d0928948cdf773dac57499ded4f0e50c6d
# патч 48 mutation-048.diff sha256 480e8c23496049703b6fb08a0007a79b9d13ebcf21b08e1f1ec37bd3fe479ea8
# патч 49 mutation-049.diff sha256 4acf5f52f8b9efbdc714599c59390d61be192fcab5e5528e428d39eb14c77a3e
# патч 50 mutation-050.diff sha256 1b7eddad8d45d7f466c10baf9f10120bdb039d840d4b0b7af35096f7aaedd06b
номер	исход	узлы
47	убита	tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py::NewRefusesTest::test_ac7_path_refusal_and_order_refusal_printed_together
48	убита	tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py::NewRefusesTest::test_ac7_path_refusal_and_order_refusal_printed_together
49	убита	tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py::DeclaredStatusShowTest::test_ac8_status_and_show_carry_declared_dependencies
50	убита	tests/test_01m45d29bqje8fjyja4jqwsyfz_new_declares_merge_after.py::DeclaredStatusShowTest::test_ac8_status_and_show_carry_declared_dependencies
```

<!-- конец мутаций до -->

## Мутации после

Команда частей: `mutation-run 01M5RHGRH3YJV8VBFH3QCHD8X0 --ref worktree --tests tests/test_merge_after_module.py --copy-table --wait-lock 4 --patches <a>-<b>` теми же диапазонами, рабочих процессов — `auto`.

<!-- начало мутаций после -->
Перед частью №21: `git status --porcelain -- orchestrator/ scripts/` — вывод пуст

```
# mutation-run №21 задачи 01M5RHGRH3YJV8VBFH3QCHD8X0
# источник патчей: каталог на диске
# ревизия прогона: worktree 8d6a6cb1b7ef043bc36ae4e0ffad1fe54c387d02
# тесты: tests/test_merge_after_module.py
# рабочих процессов: auto
# патч 1 mutation-001.diff sha256 b3309d055b1b47e0fce351402e347e47b5fca4407261b647a201cbbef7b12d8e
# патч 2 mutation-002.diff sha256 6f1403596aadf7995636660dcaaaf71615e408a018a9ee408db8f86f83e7c7ce
# патч 3 mutation-003.diff sha256 143266dae32ea8c6ec5de68b8b0e400984ac656becb3f0602ffc7c58db4fefb2
# патч 4 mutation-004.diff sha256 95947f974b47f8a40ebb9d5802d67a7ced7d23c172a255b4349e3bb66b3cbc07
# патч 5 mutation-005.diff sha256 2d0e364f910a700af91c0c40d3bbf059dbc9f38fe19fbb64a56460bd2f4b6fbe
# патч 6 mutation-006.diff sha256 56586fc4e65fbfe14d5a5456eea4acebb80d8f254cb98a4f22828fb820fb6dbb
# патч 7 mutation-007.diff sha256 b4f3eb89507bacedde2e6cfc58187b87c5f0bc6a8aef6d1b22a7a3d67407e8f3
# патч 8 mutation-008.diff sha256 d8158f2ae72c316ae402dd108cbef3c01ac09ebdaad50e6a805ffa7b3d6fa092
# патч 9 mutation-009.diff sha256 df9b2db4fa0a9b223969433944659f1c3fca4300d31fbacb3a290b220363e504
# патч 10 mutation-010.diff sha256 b5b17202281d659d35e434fd444e629449366bfd51387dfdbf0ee5eaf445782e
# патч 11 mutation-011.diff sha256 4880e8e47e428e2ef5db129aa99985d2ce31fc42aaa5e1497423142b154da3c4
номер	исход	узлы
1	убита	tests/test_merge_after_module.py::test_ac11_escalated_answer_sets_and_clears_value,tests/test_merge_after_module.py::test_ac9_escalated_answer_unblocks_same_spec_and_other_refusals_unchanged
2	убита	tests/test_merge_after_module.py::test_ac12_invalid_mandate_element_refused_before_commit,tests/test_merge_after_module.py::test_ac11_escalated_answer_sets_and_clears_value,tests/test_merge_after_module.py::test_ac11_merge_gate_answer_outside_role_env_accepted
3	убита	tests/test_merge_after_module.py::test_ac11_merge_gate_answer_outside_role_env_accepted
4	убита	tests/test_merge_after_module.py::test_ac12_invalid_mandate_element_refused_before_commit
5	убита	tests/test_merge_after_module.py::test_ac12_invalid_mandate_element_refused_before_commit
6	убита	tests/test_merge_after_module.py::test_ac12_merge_gate_without_line_or_from_role_env_refused
7	убита	tests/test_merge_after_module.py::test_ac12_merge_gate_without_line_or_from_role_env_refused
8	убита	tests/test_merge_after_module.py::test_ac1_self_reference_names_field_and_element
9	убита	tests/test_merge_after_module.py::test_ac1_repeated_element_is_a_repeat_error
10	убита	tests/test_merge_after_module.py::test_ac1_element_not_in_task_id_format_is_a_form_error
11	убита	tests/test_merge_after_module.py::test_ac1_valid_list_and_missing_field_pass
```

Перед частью №22: `git status --porcelain -- orchestrator/ scripts/` — вывод пуст

```
# mutation-run №22 задачи 01M5RHGRH3YJV8VBFH3QCHD8X0
# источник патчей: каталог на диске
# ревизия прогона: worktree 8d6a6cb1b7ef043bc36ae4e0ffad1fe54c387d02
# тесты: tests/test_merge_after_module.py
# рабочих процессов: auto
# патч 12 mutation-012.diff sha256 28ebaadb67a982f43c97245ace0be3a0b869f1a341534442103625eb3d17a705
номер	исход	узлы
12	убита	tests/test_merge_after_module.py::test_ac1_valid_list_and_missing_field_pass,tests/test_merge_after_module.py::test_ac1_repeated_element_is_a_repeat_error,tests/test_merge_after_module.py::test_short_prefix_inside_other_id_is_not_justification,tests/test_merge_after_module.py::test_ac9_empty_plan_value_clears_dependencies,tests/test_merge_after_module.py::test_ac2_dependent_journal_names_old_and_new_value,tests/test_merge_after_module.py::test_ac9_justified_plan_value_replaces_db_value,tests/test_merge_after_module.py::test_ac9_escalated_answer_unblocks_same_spec_and_other_refusals_unchanged,tests/test_merge_after_module.py::test_ac10_rejected_plan_value_keeps_db_and_transition,tests/test_merge_after_module.py::test_ac2_missing_task_keeps_spec_gate_and_column_empty,tests/test_merge_after_module.py::test_ac1_parent_replaced_by_last_subtask_in_every_dependent,tests/test_merge_after_module.py::test_ac2_list_ends_at_parenthesis_or_dot,tests/test_merge_after_module.py::test_ac1_order_line_declares_full_ids_in_line_order,tests/test_merge_after_module.py::test_ac14_show_lists_all_dependencies_with_states,tests/test_merge_after_module.py::test_ac5_prefixes_written_as_full_ids_in_spec_order,tests/test_merge_after_module.py::test_ac13_no_suffix_in_other_state,tests/test_merge_after_module.py::test_ac3_merge_gate_of_dependent_does_not_refuse_on_parent,tests/test_merge_after_module.py::test_ac6_invalid_dependency_refused_without_traces,tests/test_merge_after_module.py::test_ac8_status_and_show_carry_declared_dependencies
```

Перед частью №23: `git status --porcelain -- orchestrator/ scripts/` — вывод пуст

```
# mutation-run №23 задачи 01M5RHGRH3YJV8VBFH3QCHD8X0
# источник патчей: каталог на диске
# ревизия прогона: worktree 8d6a6cb1b7ef043bc36ae4e0ffad1fe54c387d02
# тесты: tests/test_merge_after_module.py
# рабочих процессов: auto
# патч 13 mutation-013.diff sha256 7675a1ebafce60997d81b5e71f41683edf89ed31e0f16716c2d8a0eebccb6568
# патч 14 mutation-014.diff sha256 3a828d119a13a6e5d80ed78560d33789e3c4f6bfe72fdc4a60eda795ce1a9c8b
# патч 15 mutation-015.diff sha256 4d9c07c5ec5e3f83100bf12f69d31f27fd48fda7a651b9fee025a9233d709025
# патч 16 mutation-016.diff sha256 b1620e505b197af1edba012019409f110a723ee513e3ef390b8287ae368687a8
# патч 17 mutation-017.diff sha256 c6ac2f6a10727737e81a94a8297f7d271d93b32cc4d99786ff791a1be5e71510
# патч 18 mutation-018.diff sha256 6bd4f0f9603534e90ff04a75df05641d8f49c2e3142152fb2162a2ac01d9697d
# патч 19 mutation-019.diff sha256 4dc2f44b122ba91f15d0c91a06de971945c46f36f076855f337165d74a28d4c0
номер	исход	узлы
13	убита	tests/test_merge_after_module.py::test_ac9_empty_plan_value_clears_dependencies,tests/test_merge_after_module.py::test_plan_value_equal_to_db_after_resolution_is_silent,tests/test_merge_after_module.py::test_ac9_justified_plan_value_replaces_db_value,tests/test_merge_after_module.py::test_ac10_rejected_plan_value_keeps_db_and_transition
14	убита	tests/test_merge_after_module.py::test_ac2_dependent_journal_names_old_and_new_value,tests/test_merge_after_module.py::test_ac11_escalated_answer_sets_and_clears_value,tests/test_merge_after_module.py::test_ac9_justified_plan_value_replaces_db_value
15	убита	tests/test_merge_after_module.py::test_ac9_empty_plan_value_clears_dependencies
16	убита	tests/test_merge_after_module.py::test_ac9_plan_without_field_keeps_db_value
17	убита	tests/test_merge_after_module.py::test_ac10_rejected_plan_value_keeps_db_and_transition
18	убита	tests/test_merge_after_module.py::test_ac10_rejected_plan_value_keeps_db_and_transition
19	убита	tests/test_merge_after_module.py::test_ac10_rejected_plan_value_keeps_db_and_transition
```

Перед частью №24: `git status --porcelain -- orchestrator/ scripts/` — вывод пуст

```
# mutation-run №24 задачи 01M5RHGRH3YJV8VBFH3QCHD8X0
# источник патчей: каталог на диске
# ревизия прогона: worktree 8d6a6cb1b7ef043bc36ae4e0ffad1fe54c387d02
# тесты: tests/test_merge_after_module.py
# рабочих процессов: auto
# патч 20 mutation-020.diff sha256 7ad7f09479bc3b204a0a83dba6e6b6dce60f1f0fa6363b16ba1498df68b9dc37
номер	исход	узлы
20	убита	tests/test_merge_after_module.py::test_ac12_invalid_mandate_element_refused_before_commit,tests/test_merge_after_module.py::test_ac2_missing_task_keeps_spec_gate_and_column_empty,tests/test_merge_after_module.py::test_ac10_rejected_plan_value_keeps_db_and_transition,tests/test_merge_after_module.py::test_ac7_path_refusal_and_order_refusal_printed_together,tests/test_merge_after_module.py::test_ac6_invalid_dependency_refused_without_traces
```

Перед частью №25: `git status --porcelain -- orchestrator/ scripts/` — вывод пуст

```
# mutation-run №25 задачи 01M5RHGRH3YJV8VBFH3QCHD8X0
# источник патчей: каталог на диске
# ревизия прогона: worktree 8d6a6cb1b7ef043bc36ae4e0ffad1fe54c387d02
# тесты: tests/test_merge_after_module.py
# рабочих процессов: auto
# патч 21 mutation-021.diff sha256 01e97cc5008433518beca03b9f0dc020f69222bee95dcf67728d09e811d36f8c
номер	исход	узлы
21	убита	tests/test_merge_after_module.py::test_ac2_ambiguous_prefix_keeps_spec_gate_and_column_empty,tests/test_merge_after_module.py::test_ac6_invalid_dependency_refused_without_traces
```

Перед частью №26: `git status --porcelain -- orchestrator/ scripts/` — вывод пуст

```
# mutation-run №26 задачи 01M5RHGRH3YJV8VBFH3QCHD8X0
# источник патчей: каталог на диске
# ревизия прогона: worktree 8d6a6cb1b7ef043bc36ae4e0ffad1fe54c387d02
# тесты: tests/test_merge_after_module.py
# рабочих процессов: auto
# патч 22 mutation-022.diff sha256 28701215bd85e927caba6fa72d057498601cc5178029fa4d0ac6e9c87e2ca971
номер	исход	узлы
22	убита	tests/test_merge_after_module.py::test_ac12_invalid_mandate_element_refused_before_commit,tests/test_merge_after_module.py::test_ac3_killed_dependency_refused,tests/test_merge_after_module.py::test_ac10_rejected_plan_value_keeps_db_and_transition,tests/test_merge_after_module.py::test_ac6_invalid_dependency_refused_without_traces
```

Перед частью №27: `git status --porcelain -- orchestrator/ scripts/` — вывод пуст

```
# mutation-run №27 задачи 01M5RHGRH3YJV8VBFH3QCHD8X0
# источник патчей: каталог на диске
# ревизия прогона: worktree 8d6a6cb1b7ef043bc36ae4e0ffad1fe54c387d02
# тесты: tests/test_merge_after_module.py
# рабочих процессов: auto
# патч 23 mutation-023.diff sha256 57f2df25d2f1e46b1a78dd4179693f81a0387b08345e7bd49259f02c3241ab7e
номер	исход	узлы
23	убита	tests/test_merge_after_module.py::test_ac3_dependency_of_other_target_refused,tests/test_merge_after_module.py::test_ac6_invalid_dependency_refused_without_traces
```

Перед частью №28: `git status --porcelain -- orchestrator/ scripts/` — вывод пуст

```
# mutation-run №28 задачи 01M5RHGRH3YJV8VBFH3QCHD8X0
# источник патчей: каталог на диске
# ревизия прогона: worktree 8d6a6cb1b7ef043bc36ae4e0ffad1fe54c387d02
# тесты: tests/test_merge_after_module.py
# рабочих процессов: auto
# патч 24 mutation-024.diff sha256 bf128847abd7648dc1f82dabe1bd7998b355eea4426de684a214178270e23d57
номер	исход	узлы
24	убита	tests/test_merge_after_module.py::test_ac3_prefix_resolving_to_own_id_refused
```

Перед частью №29: `git status --porcelain -- orchestrator/ scripts/` — вывод пуст

```
# mutation-run №29 задачи 01M5RHGRH3YJV8VBFH3QCHD8X0
# источник патчей: каталог на диске
# ревизия прогона: worktree 8d6a6cb1b7ef043bc36ae4e0ffad1fe54c387d02
# тесты: tests/test_merge_after_module.py
# рабочих процессов: auto
# патч 25 mutation-025.diff sha256 0829aa652fd3d78ab7a598967a20be57a16a8c8b9c6a8be6d37c1ea18224c69e
номер	исход	узлы
25	убита	tests/test_merge_after_module.py::test_ac12_invalid_mandate_element_refused_before_commit,tests/test_merge_after_module.py::test_ac10_rejected_plan_value_keeps_db_and_transition,tests/test_merge_after_module.py::test_ac4_cycle_through_existing_values_refused
```

Перед частью №30: `git status --porcelain -- orchestrator/ scripts/` — вывод пуст

```
# mutation-run №30 задачи 01M5RHGRH3YJV8VBFH3QCHD8X0
# источник патчей: каталог на диске
# ревизия прогона: worktree 8d6a6cb1b7ef043bc36ae4e0ffad1fe54c387d02
# тесты: tests/test_merge_after_module.py
# рабочих процессов: auto
# патч 26 mutation-026.diff sha256 84ab46b24bb84870d226cf6a82bdc5c0429fbd33087c3d9fd9d687860fad97b4
номер	исход	узлы
26	не убита	
```

Перед частью №31: `git status --porcelain -- orchestrator/ scripts/` — вывод пуст

```
# mutation-run №31 задачи 01M5RHGRH3YJV8VBFH3QCHD8X0
# источник патчей: каталог на диске
# ревизия прогона: worktree 8d6a6cb1b7ef043bc36ae4e0ffad1fe54c387d02
# тесты: tests/test_merge_after_module.py
# рабочих процессов: auto
# патч 27 mutation-027.diff sha256 1a48b0a4431f769308471709cecaafbb9fe71a33a7659e5b555ecc09877d0bbb
# патч 28 mutation-028.diff sha256 6ee6e9c7aeecabc1556ceb68bb7a452cc91938b92673623e41328eb5ad4d2d8f
# патч 29 mutation-029.diff sha256 51219ae0b0b5fb4cb01685dbfa4a6c6379c509b7f752ff39f6680d424515a6f5
# патч 30 mutation-030.diff sha256 43af1d7401dfdfd4a7143551ed59424e81d003109f1207df01b95a6da859b939
# патч 31 mutation-031.diff sha256 c70ea3ba96850685b4dff4e0a0fc04c44ca330474ece96691b4a95f98fc9225c
# патч 32 mutation-032.diff sha256 bb955d793d3b7df7daf32f7ef3ee9e7539d34c89a9ab58abbf5b96711c7033a5
# патч 33 mutation-033.diff sha256 9c426d41e1fb1f4e0f92457876785803a4d6751e0ac05051c6df3fc8b6093903
# патч 34 mutation-034.diff sha256 1801418cff8c1ee659a9dc98b64a0cb029ecf54657b0a597cd5341421504559f
# патч 35 mutation-035.diff sha256 881518c24f6adfc99c364a2104652ff658b77fe07492925b56532d93d916c15d
# патч 36 mutation-036.diff sha256 5900940c4b62d4bf70d84d20be42b07d952da1b103650735bd1fa85b1eeb17bf
# патч 37 mutation-037.diff sha256 a853fc01755a5671392601ff62841c6c37fb30f84683002f21afb547f795e2b4
# патч 38 mutation-038.diff sha256 934b982b9a28015f3080af392ab4b7ebb5a2d17db9d5b32773691709f2480ced
номер	исход	узлы
27	убита	tests/test_merge_after_module.py::test_ac9_empty_plan_value_clears_dependencies,tests/test_merge_after_module.py::test_ac9_plan_without_field_keeps_db_value,tests/test_merge_after_module.py::test_ac13_no_suffix_in_other_state,tests/test_merge_after_module.py::test_ac9_justified_plan_value_replaces_db_value,tests/test_merge_after_module.py::test_ac10_rejected_plan_value_keeps_db_and_transition,tests/test_merge_after_module.py::test_ac5_prefixes_written_as_full_ids_in_spec_order,tests/test_merge_after_module.py::test_ac4_cycle_through_existing_values_refused,tests/test_merge_after_module.py::test_ac14_show_lists_all_dependencies_with_states,tests/test_merge_after_module.py::test_ac13_status_suffix_lists_unfinished_and_disappears_after_done
28	убита	tests/test_merge_after_module.py::test_ac2_dependent_journal_names_old_and_new_value,tests/test_merge_after_module.py::test_ac1_parent_replaced_by_last_subtask_in_every_dependent,tests/test_merge_after_module.py::test_ac5_spec_without_field_leaves_column_empty,tests/test_merge_after_module.py::test_ac13_no_suffix_without_field_or_all_done,tests/test_merge_after_module.py::test_ac14_show_without_dependencies_has_no_line,tests/test_merge_after_module.py::test_ac3_merge_gate_of_dependent_does_not_refuse_on_parent
29	убита	tests/test_merge_after_module.py::test_ac5_spec_without_field_leaves_column_empty,tests/test_merge_after_module.py::test_ac14_show_without_dependencies_has_no_line
30	убита	tests/test_merge_after_module.py::test_ac13_status_suffix_lists_unfinished_and_disappears_after_done,tests/test_merge_after_module.py::test_ac8_status_and_show_carry_declared_dependencies
31	убита	tests/test_merge_after_module.py::test_ac13_status_suffix_lists_unfinished_and_disappears_after_done,tests/test_merge_after_module.py::test_ac8_status_and_show_carry_declared_dependencies
32	убита	tests/test_merge_after_module.py::test_ac13_no_suffix_in_other_state,tests/test_merge_after_module.py::test_ac8_status_and_show_carry_declared_dependencies
33	убита	tests/test_merge_after_module.py::test_ac13_no_suffix_without_field_or_all_done,tests/test_merge_after_module.py::test_ac13_status_suffix_lists_unfinished_and_disappears_after_done,tests/test_merge_after_module.py::test_ac8_status_and_show_carry_declared_dependencies
34	убита	tests/test_merge_after_module.py::test_ac14_show_lists_all_dependencies_with_states
35	убита	tests/test_merge_after_module.py::test_ac14_show_without_dependencies_has_no_line
36	убита	tests/test_merge_after_module.py::test_ac9_escalated_answer_unblocks_same_spec_and_other_refusals_unchanged,tests/test_merge_after_module.py::test_ac2_list_ends_at_parenthesis_or_dot,tests/test_merge_after_module.py::test_ac1_order_line_declares_full_ids_in_line_order,tests/test_merge_after_module.py::test_ac8_status_and_show_carry_declared_dependencies
37	убита	tests/test_merge_after_module.py::test_ac9_escalated_answer_unblocks_same_spec_and_other_refusals_unchanged,tests/test_merge_after_module.py::test_ac2_list_ends_at_parenthesis_or_dot,tests/test_merge_after_module.py::test_ac1_order_line_declares_full_ids_in_line_order
38	убита	tests/test_merge_after_module.py::test_ac1_order_line_declares_full_ids_in_line_order
```

Перед частью №32: `git status --porcelain -- orchestrator/ scripts/` — вывод пуст

```
# mutation-run №32 задачи 01M5RHGRH3YJV8VBFH3QCHD8X0
# источник патчей: каталог на диске
# ревизия прогона: worktree 8d6a6cb1b7ef043bc36ae4e0ffad1fe54c387d02
# тесты: tests/test_merge_after_module.py
# рабочих процессов: auto
# патч 39 mutation-039.diff sha256 96d253fa97abd8a74dbb9c2c0d42d406f75bd8df029c3c6ea40f31ff9f38b70f
номер	исход	узлы
39	убита	tests/test_merge_after_module.py::test_explicit_target_of_new_task_is_used,tests/test_merge_after_module.py::test_ac2_list_ends_at_parenthesis_or_dot
```

Перед частью №33: `git status --porcelain -- orchestrator/ scripts/` — вывод пуст

```
# mutation-run №33 задачи 01M5RHGRH3YJV8VBFH3QCHD8X0
# источник патчей: каталог на диске
# ревизия прогона: worktree 8d6a6cb1b7ef043bc36ae4e0ffad1fe54c387d02
# тесты: tests/test_merge_after_module.py
# рабочих процессов: auto
# патч 40 mutation-040.diff sha256 3b23b723f15a80517b0cc772e557c88bc507ce6a5c7ac4ff0bba14100c007dd0
номер	исход	узлы
40	убита	tests/test_merge_after_module.py::test_label_must_start_line_and_word_must_be_whole,tests/test_merge_after_module.py::test_ac3_order_line_without_after_declares_nothing
```

Перед частью №34: `git status --porcelain -- orchestrator/ scripts/` — вывод пуст

```
# mutation-run №34 задачи 01M5RHGRH3YJV8VBFH3QCHD8X0
# источник патчей: каталог на диске
# ревизия прогона: worktree 8d6a6cb1b7ef043bc36ae4e0ffad1fe54c387d02
# тесты: tests/test_merge_after_module.py
# рабочих процессов: auto
# патч 41 mutation-041.diff sha256 0d848c1620df2dd58216587663a86296bb6e573fb0464f585bdc2f6fc2175180
номер	исход	узлы
41	убита	tests/test_merge_after_module.py::test_label_must_start_line_and_word_must_be_whole,tests/test_merge_after_module.py::test_ac3_order_line_without_after_declares_nothing
```

Перед частью №35: `git status --porcelain -- orchestrator/ scripts/` — вывод пуст

```
# mutation-run №35 задачи 01M5RHGRH3YJV8VBFH3QCHD8X0
# источник патчей: каталог на диске
# ревизия прогона: worktree 8d6a6cb1b7ef043bc36ae4e0ffad1fe54c387d02
# тесты: tests/test_merge_after_module.py
# рабочих процессов: auto
# патч 42 mutation-042.diff sha256 6359ed99b45b5c36cc529a6a846518a01fbc8871736f38b3a7bcbff1e5f4f95a
номер	исход	узлы
42	убита	tests/test_merge_after_module.py::test_ac4_unparsed_element_refused_without_traces
```

Перед частью №36: `git status --porcelain -- orchestrator/ scripts/` — вывод пуст

```
# mutation-run №36 задачи 01M5RHGRH3YJV8VBFH3QCHD8X0
# источник патчей: каталог на диске
# ревизия прогона: worktree 8d6a6cb1b7ef043bc36ae4e0ffad1fe54c387d02
# тесты: tests/test_merge_after_module.py
# рабочих процессов: auto
# патч 43 mutation-043.diff sha256 656bb2fd4f7fc917a428e769d356e5701201644ac99b3c00df7ece9e5a6565f1
номер	исход	узлы
43	убита	tests/test_merge_after_module.py::test_ac7_path_refusal_and_order_refusal_printed_together,tests/test_merge_after_module.py::test_ac5_repeated_order_line_refused_without_traces,tests/test_merge_after_module.py::test_ac4_unparsed_element_refused_without_traces,tests/test_merge_after_module.py::test_ac6_invalid_dependency_refused_without_traces
```

Перед частью №37: `git status --porcelain -- orchestrator/ scripts/` — вывод пуст

```
# mutation-run №37 задачи 01M5RHGRH3YJV8VBFH3QCHD8X0
# источник патчей: каталог на диске
# ревизия прогона: worktree 8d6a6cb1b7ef043bc36ae4e0ffad1fe54c387d02
# тесты: tests/test_merge_after_module.py
# рабочих процессов: auto
# патч 44 mutation-044.diff sha256 7ab1f165b056c401c70e2d1ddb6a20161b572f24afca7724f6de997b83bb3295
номер	исход	узлы
44	убита	tests/test_merge_after_module.py::test_ac5_repeated_order_line_refused_without_traces
```

Перед частью №38: `git status --porcelain -- orchestrator/ scripts/` — вывод пуст

```
# mutation-run №38 задачи 01M5RHGRH3YJV8VBFH3QCHD8X0
# источник патчей: каталог на диске
# ревизия прогона: worktree 8d6a6cb1b7ef043bc36ae4e0ffad1fe54c387d02
# тесты: tests/test_merge_after_module.py
# рабочих процессов: auto
# патч 45 mutation-045.diff sha256 3a6b0c6a92d0378c9c69b8d52d97875f2690d9709bb355791515996265aaa5e0
номер	исход	узлы
45	убита	tests/test_merge_after_module.py::test_ac5_repeated_order_line_refused_without_traces
```

Перед частью №39: `git status --porcelain -- orchestrator/ scripts/` — вывод пуст

```
# mutation-run №39 задачи 01M5RHGRH3YJV8VBFH3QCHD8X0
# источник патчей: каталог на диске
# ревизия прогона: worktree 8d6a6cb1b7ef043bc36ae4e0ffad1fe54c387d02
# тесты: tests/test_merge_after_module.py
# рабочих процессов: auto
# патч 46 mutation-046.diff sha256 4f0815c9ecd2a677bd0b75a53b4add824a8ea1fad25623c5eba0a9d3b5c2d148
номер	исход	узлы
46	убита	tests/test_merge_after_module.py::test_ac1_order_line_declares_full_ids_in_line_order,tests/test_merge_after_module.py::test_ac2_list_ends_at_parenthesis_or_dot,tests/test_merge_after_module.py::test_ac6_invalid_dependency_refused_without_traces,tests/test_merge_after_module.py::test_ac8_status_and_show_carry_declared_dependencies
```

Перед частью №40: `git status --porcelain -- orchestrator/ scripts/` — вывод пуст

```
# mutation-run №40 задачи 01M5RHGRH3YJV8VBFH3QCHD8X0
# источник патчей: каталог на диске
# ревизия прогона: worktree 8d6a6cb1b7ef043bc36ae4e0ffad1fe54c387d02
# тесты: tests/test_merge_after_module.py
# рабочих процессов: auto
# патч 47 mutation-047.diff sha256 162393c4d098bfa2062c6becaa3b28d0928948cdf773dac57499ded4f0e50c6d
# патч 48 mutation-048.diff sha256 480e8c23496049703b6fb08a0007a79b9d13ebcf21b08e1f1ec37bd3fe479ea8
# патч 49 mutation-049.diff sha256 4acf5f52f8b9efbdc714599c59390d61be192fcab5e5528e428d39eb14c77a3e
# патч 50 mutation-050.diff sha256 1b7eddad8d45d7f466c10baf9f10120bdb039d840d4b0b7af35096f7aaedd06b
номер	исход	узлы
47	убита	tests/test_merge_after_module.py::test_ac7_path_refusal_and_order_refusal_printed_together
48	убита	tests/test_merge_after_module.py::test_ac7_path_refusal_and_order_refusal_printed_together
49	убита	tests/test_merge_after_module.py::test_ac8_status_and_show_carry_declared_dependencies
50	убита	tests/test_merge_after_module.py::test_ac13_no_suffix_in_other_state,tests/test_merge_after_module.py::test_ac8_status_and_show_carry_declared_dependencies
```

<!-- конец мутаций после -->

## Предложения системе

- `mutation-run`: строка падения (файл:строка утверждения и вызова) по каждому патчу — в таблицу команды; сейчас её добывают разбором логов своим сценарием (`fail_lines.py`, `make_plan.py` волн 3м-2 и 3м-2б).
- Планка волн читает PLAN из ссылки документов, а не с диска: проверить PLAN до автокоммита шага роль может только самодельным `_pult` — не хватает `plank-run --docs-disk`.

## Ответ на эскалацию

ANSWER-2 (25.10): вариант «а» — `amend-tests` (лок c5db3022 → b911bacd), `_same_assertion_line` сводит переименованные по требованию 9 локальные (`journal`, `task`) к прежним; PLAN и код не менялись. `plank-run` после правки планки: 76 passed, код выхода 0.
