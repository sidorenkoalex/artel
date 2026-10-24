---
task: 01M5NNDYGQ8G6VFDEEXYBB0W3D
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Сведение тестов, волна 1а — тесты копилки, бэклога и окна тишины в `tests/test_notes_module.py`

## Подход

Перенос один-к-одному: все 80 тестов четырёх исходных файлов переехали в
`tests/test_notes_module.py` функциями модуля в стиле pytest (80 функций,
99 собранных узлов за счёт `parametrize`), дублей не удалено. Ожидаемые
значения и виды сравнений перенесены дословно (`assertEqual` → `==`,
`assertIn` → `in`, `assertIsNone` → `is None`, `assertLess` → `<`).

- Стенды — фикстуры файла поверх `tests/fixtures.py`: `schema_root`
  (замена `SchemaTmpRootTest`: `tmp_root` + `store.create_schema`),
  `no_role` (пустой `ARTEL_ROLE`, как `mock.patch.dict` в `setUp`),
  `silence_box` (бывший `NoteSilenceSandbox`), `apply_box` (бывший
  `ApplySandbox`), `window_box` (бывший `NoteWindowProjectTest.setUp`);
  все три стенда git — поверх `real_git`. В фикстурах нет утверждений;
  помощники с утверждениями (`origin_backlog`, `refusal`, `inserted_row`,
  `assert_pushed`, `held_reason`) — функции модуля.
- `assertRaises(E) as cm` + `assertIn(X, str(cm.exception))` →
  `pytest.raises(E, match=re.escape(X))` (8 мест из 9 мест проверки
  текста в исходных; девятое — помощник `ApplySandbox.refusal` — стал
  функцией `refusal`, возвращающей текст, на который тесты пишут прежние
  `in`); голый `assertRaises(E)` → `pytest.raises(E)` без `match`.
- `subTest` по литеральным наборам → `parametrize` литералами; перебор
  `config.NOTE_SILENCE_WINDOW_STATES`/`OUTSIDE_WINDOW`, наборы
  `target` с общим состоянием и случайным выбором (стенд окна по
  проекту) — прежним циклом в теле функции.
- Мутации: 72 патча `mutation-001.diff`…`mutation-072.diff` — по одной на
  каждую строку «Ловит мутацию» и на каждый из 26 тестов
  `tests/test_notes.py` без строки; одинаковые по смыслу заявки — общий
  патч (таблица сопоставления ниже). Каждый патч — один хунк в одном
  файле `orchestrator/` (`orchestrator/notes.py`, у 025/026 —
  `orchestrator/doctor/misc_checks.py`), проверен `git apply --check`.
- Прогоны — только `mutation-run` пульта: «до» — `--ref base` на четырёх
  исходных файлах частями 1-24, 25-48, 45-72 (предел команды 900 с);
  «после» — `--ref worktree` на новом файле частями 1-36, 37-72.

## Шаги

1. Патчи мутаций в каталоге документов задачи, прогон «до» частями,
   перенос вывода каждой части в раздел «Мутации до» до старта следующей.
2. Свод `tests/test_notes_module.py`, удаление четырёх исходных файлов,
   регенерация `docs/codebase-map.md`, коммит в ветку задачи.
3. Прогон «после» на том же наборе патчей частями, перенос вывода в
   раздел «Мутации после»; сверка: каждая мутация, убитая «до», убита
   «после».

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 2 |
| 4 | 2 |
| 5 | 2 (дублей не удалено) |
| 6 | 2 |
| 7 | 3 |
| 8 | 1, 3 |
| 9 | 2 |
| 10 | 2 |
| 11 | — (сессия при Операторе) |

## Сопоставление тестов и мутаций

Столбец «Заявка в исходном файле» — была ли у теста строка «Ловит
мутацию» (54 есть, 26 тестов `tests/test_notes.py` — нет; им строка
написана в новом файле под мутацию из этой таблицы). Общие патчи для
одинаковых по смыслу заявок: mutation-005 (дописка затирает ячейку),
mutation-006 (ноль совпадений ключа), mutation-007 (несколько
совпадений), mutation-012 (диапазон 1..4 не сверяется), mutation-028
(окно тишины открыто всегда), mutation-068 (артель по сравнению
`target` с `DEFAULT_TARGET`). mutation-014 — вторая половина заявок
«либо пример формы из текста отказа убран» двух тестов приоритета.

| Исходный тест | Заявка в исходном файле | Мутация | Функция `tests/test_notes_module.py` |
|---|---|---|---|
| `tests/test_notes.py::RowCellsTest::test_strips_outer_pipes_and_whitespace` | нет | mutation-001 | `test_row_cells_strips_outer_pipes_and_whitespace` |
| `tests/test_notes.py::ApplyInsertTest::test_inserts_right_after_separator` | есть | mutation-002 | `test_insert_right_after_separator` |
| `tests/test_notes.py::ApplyInsertTest::test_column_count_mismatch_refuses_naming_expected_count` | нет | mutation-003 | `test_insert_column_count_mismatch_refuses_naming_expected_count` |
| `tests/test_notes.py::ApplyInsertTest::test_unknown_section_heading_refuses` | нет | mutation-004 | `test_insert_unknown_section_heading_refuses` |
| `tests/test_notes.py::ApplyAppendTest::test_unique_key_appends_to_last_column_only` | нет | mutation-005 | `test_append_unique_key_appends_to_last_column_only` |
| `tests/test_notes.py::ApplyAppendTest::test_zero_matches_refuses_without_changing_text` | нет | mutation-006 | `test_append_zero_matches_refuses_without_changing_text` |
| `tests/test_notes.py::ApplyAppendTest::test_multiple_matches_refuses_without_changing_text` | нет | mutation-007 | `test_append_multiple_matches_refuses_without_changing_text` |
| `tests/test_notes.py::ApplyDropTest::test_removes_matched_row_only_neighbours_untouched` | нет | mutation-008 | `test_drop_removes_matched_row_only_neighbours_untouched` |
| `tests/test_notes.py::ApplyDropTest::test_zero_matches_refuses_without_changing_text` | нет | mutation-006 | `test_drop_zero_matches_refuses_without_changing_text` |
| `tests/test_notes.py::ApplyDropTest::test_multiple_matches_refuses_without_changing_text` | нет | mutation-007 | `test_drop_multiple_matches_refuses_without_changing_text` |
| `tests/test_notes.py::ApplySetStateTest::test_replaces_last_column_entirely_not_appends` | нет | mutation-009 | `test_set_state_replaces_last_column_entirely_not_appends` |
| `tests/test_notes.py::ApplySetStateTest::test_multiple_matches_refuses_without_changing_text` | нет | mutation-007 | `test_set_state_multiple_matches_refuses_without_changing_text` |
| `tests/test_notes.py::ApplySetPriorityTest::test_replaces_first_column_with_valid_value` | нет | mutation-010 | `test_set_priority_replaces_first_column_with_valid_value` |
| `tests/test_notes.py::ApplySetPriorityTest::test_value_above_range_refuses_without_changing_text` | нет | mutation-012 | `test_set_priority_value_above_range_refuses_without_changing_text` |
| `tests/test_notes.py::ApplySetPriorityTest::test_value_below_range_refuses_without_changing_text` | нет | mutation-012 | `test_set_priority_value_below_range_refuses_without_changing_text` |
| `tests/test_notes.py::ApplySetPriorityTest::test_non_numeric_value_refuses_without_changing_text` | нет | mutation-013 | `test_set_priority_non_numeric_value_refuses_without_changing_text` |
| `tests/test_notes.py::PendingNotesStorageTest::test_empty_by_default` | нет | mutation-015 | `test_pending_notes_empty_by_default` |
| `tests/test_notes.py::PendingNotesStorageTest::test_hold_then_read_back_round_trips` | нет | mutation-016 | `test_pending_notes_hold_then_read_back_round_trips` |
| `tests/test_notes.py::PendingNotesStorageTest::test_two_holds_are_both_visible` | нет | mutation-017 | `test_pending_notes_two_holds_are_both_visible` |
| `tests/test_notes.py::CmdNoteArgumentValidationTest::test_no_arguments_at_all_refuses` | нет | mutation-018 | `test_cmd_note_no_arguments_at_all_refuses` |
| `tests/test_notes.py::CmdNoteArgumentValidationTest::test_section_without_text_refuses` | нет | mutation-019 | `test_cmd_note_section_without_text_refuses` |
| `tests/test_notes.py::CmdNoteArgumentValidationTest::test_append_without_text_refuses` | нет | mutation-020 | `test_cmd_note_append_without_text_refuses` |
| `tests/test_notes.py::CmdNoteArgumentValidationTest::test_set_state_without_text_refuses` | нет | mutation-021 | `test_cmd_note_set_state_without_text_refuses` |
| `tests/test_notes.py::CmdNoteArgumentValidationTest::test_set_priority_without_text_refuses` | нет | mutation-022 | `test_cmd_note_set_priority_without_text_refuses` |
| `tests/test_notes.py::CmdNoteArgumentValidationTest::test_flush_with_nothing_pending_is_a_noop` | нет | mutation-023 | `test_cmd_note_flush_with_nothing_pending_is_a_noop` |
| `tests/test_notes.py::CmdNoteRoleRefusalTest::test_role_refuses_every_form_before_parsing` | есть | mutation-024 | `test_cmd_note_role_refuses_every_form_before_parsing (5 вариантов parametrize)` |
| `tests/test_notes.py::CheckPendingNotesTest::test_ok_when_nothing_pending` | нет | mutation-025 | `test_check_pending_notes_ok_when_nothing_pending` |
| `tests/test_notes.py::CheckPendingNotesTest::test_warn_when_something_pending` | нет | mutation-026 | `test_check_pending_notes_warn_when_something_pending` |
| `tests/test_notes.py::SilenceWindowReasonTest::test_ac1_live_merge_lock_alone_without_any_task_state_opens_window` | есть | mutation-027 | `test_silence_ac1_live_merge_lock_alone_without_any_task_state_opens_window` |
| `tests/test_notes.py::SilenceWindowReasonTest::test_no_holder_and_no_task_in_set_closes_window` | есть | mutation-028 | `test_silence_no_holder_and_no_task_in_set_closes_window` |
| `tests/test_notes.py::SilenceWindowReasonTest::test_escalated_state_does_not_open_window` | есть | mutation-029 | `test_silence_escalated_state_does_not_open_window` |
| `tests/test_notes.py::SilenceWindowReasonTest::test_dead_merge_lock_holder_does_not_open_window` | есть | mutation-030 | `test_silence_dead_merge_lock_holder_does_not_open_window` |
| `tests/test_notes.py::SilenceWindowReasonTest::test_artel_task_and_holder_not_resolved_through_targets` | есть | mutation-031 | `test_silence_artel_task_and_holder_not_resolved_through_targets` |
| `tests/test_notes.py::WindowHoldsValidNoteTest::test_ac2_all_five_kinds_held_not_pushed_when_task_in_dev` | есть | mutation-032 | `test_window_ac2_all_five_kinds_held_not_pushed_when_task_in_dev` |
| `tests/test_notes.py::WindowHoldsValidNoteTest::test_ac3_hold_message_prefix_and_suffix` | есть | mutation-033 | `test_window_ac3_hold_message_prefix_and_suffix` |
| `tests/test_notes.py::WindowHoldsValidNoteTest::test_ac4_unmatched_key_refuses_before_hold_even_with_window_open` | есть | mutation-034 | `test_window_ac4_unmatched_key_refuses_before_hold_even_with_window_open` |
| `tests/test_notes.py::WindowHoldsValidNoteTest::test_ac9_held_note_uses_existing_pending_json_shape` | есть | mutation-035 | `test_window_ac9_held_note_uses_existing_pending_json_shape` |
| `tests/test_notes.py::WindowBypassAndNoWindowTest::test_ac5_no_window_pushes_immediately_unchanged` | есть | mutation-028 | `test_window_ac5_no_window_pushes_immediately_unchanged` |
| `tests/test_notes.py::WindowBypassAndNoWindowTest::test_ac6_flush_pushes_held_note_while_window_stays_open` | есть | mutation-036 | `test_window_ac6_flush_pushes_held_note_while_window_stays_open` |
| `tests/test_notes.py::WindowBypassAndNoWindowTest::test_ac7_now_pushes_immediately_and_does_not_hold` | есть | mutation-037 | `test_window_ac7_now_pushes_immediately_and_does_not_hold` |
| `tests/test_notes.py::WindowBypassAndNoWindowTest::test_ac8_open_window_leaves_previously_held_note_untouched` | есть | mutation-038 | `test_window_ac8_open_window_leaves_previously_held_note_untouched` |
| `tests/test_notes.py::WindowBypassAndNoWindowTest::test_ac8_closed_window_still_flushes_previously_held_note` | есть | mutation-039 | `test_window_ac8_closed_window_still_flushes_previously_held_note` |
| `tests/test_notes.py::RudimentRemovedTest::test_notes_module_declares_no_rudiment_exception` | есть | mutation-040 | `test_notes_module_declares_no_rudiment_exception` |
| `tests/test_notes_apply.py::ApplySuccessTest::test_draft_becomes_the_document_in_one_commit` | есть | mutation-041 | `test_apply_draft_becomes_the_document_in_one_commit` |
| `tests/test_notes_apply.py::ApplySuccessTest::test_journal_names_dropped_row_count_and_truncated_rows` | есть | mutation-042 | `test_apply_journal_names_dropped_row_count_and_truncated_rows` |
| `tests/test_notes_apply.py::ApplySuccessTest::test_untouched_draft_counts_zero_dropped_rows` | есть | mutation-043 | `test_apply_untouched_draft_counts_zero_dropped_rows` |
| `tests/test_notes_apply.py::ApplyRefusalTest::test_document_changed_in_origin_past_the_base_refuses` | есть | mutation-044 | `test_apply_document_changed_in_origin_past_the_base_refuses` |
| `tests/test_notes_apply.py::ApplyRefusalTest::test_own_note_commit_past_the_pin_does_not_block_apply` | есть | mutation-045 | `test_apply_own_note_commit_past_the_pin_does_not_block_apply` |
| `tests/test_notes_apply.py::ApplyRefusalTest::test_origin_changed_while_the_record_was_held_refuses_on_flush` | есть | mutation-046 | `test_apply_origin_changed_while_the_record_was_held_refuses_on_flush` |
| `tests/test_notes_apply.py::ApplyRefusalTest::test_draft_without_a_section_refuses_before_commit` | есть | mutation-047 | `test_apply_draft_without_a_section_refuses_before_commit` |
| `tests/test_notes_apply.py::ApplyRefusalTest::test_draft_with_section_heading_but_no_table_refuses` | есть | mutation-048 | `test_apply_draft_with_section_heading_but_no_table_refuses` |
| `tests/test_notes_apply.py::ApplyRefusalTest::test_draft_with_widened_header_refuses` | есть | mutation-049 | `test_apply_draft_with_widened_header_refuses` |
| `tests/test_notes_apply.py::ApplyRefusalTest::test_draft_equal_to_origin_refuses_instead_of_hanging_in_pending` | есть | mutation-050 | `test_apply_draft_equal_to_origin_refuses_instead_of_hanging_in_pending` |
| `tests/test_notes_apply.py::ApplyRefusalTest::test_missing_message_and_missing_file_refuse_naming_the_flag` | есть | mutation-051 | `test_apply_missing_message_and_missing_file_refuse_naming_the_flag` |
| `tests/test_notes_apply.py::ApplySilenceWindowTest::test_open_window_holds_apply_until_flush` | есть | mutation-052 | `test_apply_open_window_holds_apply_until_flush` |
| `tests/test_notes_apply.py::ApplySilenceWindowTest::test_held_record_is_self_sufficient_without_the_source_file` | есть | mutation-053 | `test_apply_held_record_is_self_sufficient_without_the_source_file` |
| `tests/test_notes_row_format.py::RowFormsTest::test_framed_and_bare_text_give_the_same_row` | есть | mutation-054 | `test_row_framed_and_bare_text_give_the_same_row` |
| `tests/test_notes_row_format.py::RowFormsTest::test_single_leading_pipe_is_not_treated_as_framing` | есть | mutation-055 | `test_row_single_leading_pipe_is_not_treated_as_framing` |
| `tests/test_notes_row_format.py::RowFormsTest::test_cell_count_is_checked_after_unframing` | есть | mutation-056 | `test_row_cell_count_is_checked_after_unframing` |
| `tests/test_notes_row_format.py::InsertedPriorityTest::test_letter_and_digit_forms_both_give_the_digit` | есть | mutation-057 | `test_row_letter_and_digit_forms_both_give_the_digit (4 варианта)` |
| `tests/test_notes_row_format.py::InsertedPriorityTest::test_unrecognized_priority_refuses_naming_a_valid_form` | есть | mutation-012, mutation-014 | `test_row_unrecognized_priority_refuses_naming_a_valid_form (5 вариантов)` |
| `tests/test_notes_row_format.py::InsertedPriorityTest::test_section_without_priority_column_is_not_normalized` | есть | mutation-058 | `test_row_section_without_priority_column_is_not_normalized` |
| `tests/test_notes_row_format.py::InsertedDateTest::test_year_is_dropped_short_form_and_non_dates_survive` | есть | mutation-059 | `test_row_year_is_dropped_short_form_and_non_dates_survive (4 варианта)` |
| `tests/test_notes_row_format.py::InsertedDateTest::test_date_shaped_cell_of_another_column_is_untouched` | есть | mutation-060 | `test_row_date_shaped_cell_of_another_column_is_untouched` |
| `tests/test_notes_row_format.py::SetPriorityTest::test_both_forms_write_the_digit` | есть | mutation-011 | `test_row_set_priority_both_forms_write_the_digit (2 варианта)` |
| `tests/test_notes_row_format.py::SetPriorityTest::test_range_is_not_widened_by_the_letter_form` | есть | mutation-012, mutation-014 | `test_row_set_priority_range_is_not_widened_by_the_letter_form (4 варианта)` |
| `tests/test_notes_row_format.py::SetPriorityTest::test_section_without_priority_column_refuses_instead_of_cell_zero` | есть | mutation-061 | `test_row_set_priority_section_without_priority_column_refuses_instead_of_cell_zero` |
| `tests/test_notes_row_format.py::StateAppendTest::test_filled_cell_keeps_old_text_and_gets_dated_separator` | есть | mutation-005 | `test_row_filled_cell_keeps_old_text_and_gets_dated_separator` |
| `tests/test_notes_row_format.py::StateAppendTest::test_empty_and_dash_cells_get_no_leading_separator` | есть | mutation-062 | `test_row_empty_and_dash_cells_get_no_leading_separator (2 варианта)` |
| `tests/test_notes_row_format.py::StateAppendTest::test_second_append_keeps_the_first_one_whole` | есть | mutation-063 | `test_row_second_append_keeps_the_first_one_whole` |
| `tests/test_notes_row_format.py::StateFlagAliasTest::test_state_and_append_build_the_same_request` | есть | mutation-064 | `test_row_state_and_append_build_the_same_request` |
| `tests/test_notes_row_format.py::StateFlagAliasTest::test_state_without_text_refuses_naming_the_flag_that_was_used` | есть | mutation-065 | `test_row_state_without_text_refuses_naming_the_flag_that_was_used` |
| `tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac1_external_task_in_every_window_state_does_not_hold` | есть | mutation-066 | `test_project_ac1_external_task_in_every_window_state_does_not_hold` |
| `tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac2_live_holder_with_external_task_does_not_hold` | есть | mutation-067 | `test_project_ac2_live_holder_with_external_task_does_not_hold` |
| `tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac3_artel_task_in_every_window_state_holds_with_old_text` | есть | mutation-068 | `test_project_ac3_artel_task_in_every_window_state_holds_with_old_text` |
| `tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac3_live_holder_with_artel_task_holds_with_old_text` | есть | mutation-068 | `test_project_ac3_live_holder_with_artel_task_holds_with_old_text` |
| `tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac3a_external_holder_does_not_mask_artel_task` | есть | mutation-069 | `test_project_ac3a_external_holder_does_not_mask_artel_task` |
| `tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac3b_earlier_external_task_does_not_mask_artel_task` | есть | mutation-070 | `test_project_ac3b_earlier_external_task_does_not_mask_artel_task` |
| `tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac4_unresolved_project_holds_naming_task_and_reason` | есть | mutation-071 | `test_project_ac4_unresolved_project_holds_naming_task_and_reason` |
| `tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac5_unresolved_project_outside_window_does_not_hold` | есть | mutation-072 | `test_project_ac5_unresolved_project_outside_window_does_not_hold` |

## Что ломает каждый патч

| Патч | Место | Мутация |
|---|---|---|
| mutation-001 | `_row_cells` | обрамляющие черты не снимаются |
| mutation-002 | `_apply_insert` | вставка от шапки, а не от разделителя |
| mutation-003 | `_apply_insert` | отказ по ширине не называет ожидаемое число |
| mutation-004 | `_apply_insert` | ненайденный раздел — возврат без отказа |
| mutation-005 | `_apply_append` | `cells[-1] = text` (затирание вместо дописки) |
| mutation-006 | `_find_unique_row` | отказ только при `len > 1` |
| mutation-007 | `_find_unique_row` | отказ только при `len == 0` |
| mutation-008 | `_apply_drop` | удаляется соседняя строка |
| mutation-009 | `_apply_set_state` | дописка вместо замены |
| mutation-010 | `_apply_set_priority` | запись в колонку `+ 1` |
| mutation-011 | `_apply_set_priority` | в файл пишется сырой текст |
| mutation-012 | `_PRIORITY_RE` | `[0-9]` вместо `[1-4]` |
| mutation-013 | `_priority_or_refuse` | отказ только для цифр |
| mutation-014 | `_priority_or_refuse` | пример формы убран из отказа |
| mutation-015 | `pending_notes` | пустой перечень → `None` |
| mutation-016 | `_hold_pending` | запись теряет поле `text` |
| mutation-017 | `_hold_pending` | имя файла записи не уникально |
| mutation-018 | `cmd_note` | итоговый отказ → `ValueError` |
| mutation-019 | `cmd_note` | раздел без `--text` → `ValueError` |
| mutation-020 | `cmd_note` | `--append` без `--text` → `ValueError` |
| mutation-021 | `cmd_note` | `--set-state` без `--text` → `ValueError` |
| mutation-022 | `cmd_note` | `--set-priority` без `--text` → `ValueError` |
| mutation-023 | `cmd_note` | пустой `--flush` отказывает |
| mutation-024 | `cmd_note` | проверка роли выключена |
| mutation-025 | `check_pending_notes` | `if pending is None` |
| mutation-026 | `check_pending_notes` | подсказка `note --flush` убрана |
| mutation-027 | `_silence_window_reason` | держатели `merge_locks` не смотрятся |
| mutation-028 | `_silence_window_reason` | итог — открытое окно вместо `None` |
| mutation-029 | `_silence_window_reason` | `escalated` в наборе окна |
| mutation-030 | `_silence_window_reason` | живость держателя не проверяется |
| mutation-031 | `_task_project` | `resolve` зовётся раньше `is_artel` |
| mutation-032 | `_run` | окно только для вида `insert` |
| mutation-033 | `_run` | сообщение удержания не печатается |
| mutation-034 | `_run` | окно проверяется до валидации |
| mutation-035 | `_run` | удержание окном своим видом записи |
| mutation-036 | `cmd_note` | `--flush` уважает окно |
| mutation-037 | `cmd_note` | `--now` без обхода окна |
| mutation-038 | `cmd_note` | попутный флаш безусловен |
| mutation-039 | `cmd_note` | попутный флаш только при открытом окне |
| mutation-040 | модуль | класс-рудимент возвращён |
| mutation-041 | `_ensure_work_repo` | рабочий репозиторий — `config.ROOT` |
| mutation-042 | `_build_apply` | стороны `_dropped_rows` перепутаны |
| mutation-043 | `_apply_journal_detail` | пустой detail без удалённых строк |
| mutation-044 | `_build_apply` | сверка чужой правки пропущена |
| mutation-045 | `_foreign_base_refusal` | пиновая сверка: blob origin ≠ HEAD главной копии — отказ |
| mutation-046 | `_build_apply` | `base_blob` не сверяется при флаше |
| mutation-047 | `_apply_shape_refusal` | отсутствие раздела пропускается |
| mutation-048 | `_apply_shape_refusal` | проверка только заголовка раздела |
| mutation-049 | `_apply_shape_refusal` | ширина шапки не сверяется |
| mutation-050 | `_build_apply` | отказ «совпадает» убран |
| mutation-051 | `cmd_note` | пробельный `--message` проходит |
| mutation-052 | `cmd_note` | `--apply` в обход окна |
| mutation-053 | `cmd_note` | запись несёт путь, а не содержимое |
| mutation-054 | `_apply_insert` | обрамление текста не снимается |
| mutation-055 | `_apply_insert` | `text.lstrip("\|")` |
| mutation-056 | `_apply_insert` | ширина сверяется до снятия обрамления |
| mutation-057 | `_normalized_row` | приоритет вставки не нормализуется |
| mutation-058 | `_normalized_row` | колонка приоритета по номеру 0 |
| mutation-059 | `_normalized_date` | разбор строго `ДД.ММ.ГГГГ` |
| mutation-060 | `_normalized_row` | дата нормализуется в любой колонке |
| mutation-061 | `_apply_set_priority` | без колонки «П» — правка `cells[0]` |
| mutation-062 | `STATE_EMPTY_CELLS` | прочерк не пустой |
| mutation-063 | `_appended_state` | прежний текст режется по `": "` |
| mutation-064 | `_parse_args` | `--state` ведёт в `set_state` |
| mutation-065 | `cmd_note` | имя флага отказа захардкожено `--append` |
| mutation-066 | `_silence_window_reason` | задачи окна не фильтруются по проекту |
| mutation-067 | `_silence_window_reason` | внешний держатель открывает окно |
| mutation-068 | `_task_project` | артель — `target == DEFAULT_TARGET` |
| mutation-069 | `_silence_window_reason` | внешний держатель — досрочный `None` |
| mutation-070 | `_silence_window_reason` | внешняя задача — досрочный `None` |
| mutation-071 | `_task_project` | неразрешённый проект — артель |
| mutation-072 | `_silence_window_reason` | проект проверяется раньше состояния |

## Находки

- Первая редакция mutation-045 (`own = False` в `_foreign_backlog_commits`)
  в прогоне «до» №2 не убита: при собственной заметке blob origin совпадает
  с blob известной клону базы, и `_foreign_base_refusal` выходит раньше
  перебора коммитов. Патч переписан под заявку теста (сверка сведена к
  пиновой) и повторён в части 3 «до» — там убит; в доказательство идёт
  только повтор (у мутации берётся её последняя строка).
- Мутаций, не убитых никем в итоговых строках «до», нет.

## Убитые падением подготовки

Узлы, убитые падением подготовки песочницы (трассировка в `setUp`/
`setUpClass`), по слову роли: таких узлов нет ни у одной мутации набора —
патчи меняют только `orchestrator/notes.py` и
`orchestrator/doctor/misc_checks.py`, которых `setUp` песочниц
(`TmpRootTest`, `SchemaTmpRootTest`, `RealGitSandbox`, стенды файлов)
не вызывает; у каждой мутации убийцы — утверждения тестов.

## Удалённые дубли

Нет: все 80 исходных тестов перенесены, ни один не удалён.

## Число тестов, строк и время

| | Тестов | Строк | Адресный прогон |
|---|---|---|---|
| До (четыре исходных файла) | 80 (55 subTest) | 1728 | 12.58 с |
| После (`tests/test_notes_module.py`) | 80 функций / 99 узлов | 1792 | 11.63 с |

Время — `python3 -m pytest <файлы> -q -p no:cacheprovider -p timeout -o timeout=120` в рабочей копии шага.

## Влияние на систему

- Меняются только тесты: удалены `tests/test_notes.py`,
  `tests/test_notes_apply.py`, `tests/test_notes_row_format.py`,
  `tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py`, добавлен
  `tests/test_notes_module.py`; регенерирована `docs/codebase-map.md`.
  `orchestrator/`, `tests/fixtures.py`, `tests/sandbox.py` не тронуты.
- Удаление и смена вида тестов — по мандату `ANSWER-1.md` (гейты
  неослабления и исходов); ослабления нет: утверждения перенесены
  дословно, `skip`/`xfail` и подъёма пределов нет, все мутации, убитые
  «до», убиты «после».
- Текстовые ссылки на удалённый файл остаются в докстрингах
  `tests/sandbox.py:1815` и `tests/test_doc_commit.py:6` (волна 1б, вне
  зоны) и строковом литерале пути `tests/test_doc_commit.py:94` (путь
  как пример отказа `doc-commit`, существование файла не требуется).
- Откат — revert коммита свода в ветке задачи.

## Риски

- Подлинность таблиц держит независимая проверка (требование 11): вывод
  перенесён дословно из `mutation-run --wait`.

## Предложения системе

- `plank-run` (orchestrator/plank_run.py) читает документы задачи из ссылки `refs/artifacts/<id>`, которую пульт пополняет только после шага: планку на PLAN.md/патчи разработчик внутри шага не прогонит — пришлось сверять ту же логику временным скриптом по файлам каталога документов. Нужен режим «документы с диска».
- `mutation-run --wait` печатает только последний прогон задачи: при делении `--patches` вывод части легко потерять (прогон следующей части стирает доступ к предыдущему); флаг `--run <n>` для печати таблицы прошлого прогона снял бы это ограничение.

## Мутации до

### Часть 1 (патчи 1-24)

```text
--- таблица /Users/al.sidorenko/projects/artel/.artel/logs/suite-run/01M5NNDYGQ8G6VFDEEXYBB0W3D/01M5NNDYGQ8G6VFDEEXYBB0W3D-mutation-run-1.mutations.tsv ---
# mutation-run №1 задачи 01M5NNDYGQ8G6VFDEEXYBB0W3D
# источник патчей: каталог на диске
# ревизия прогона: base 549e997ec89bb9b448980d71066a37922b537b9f
# тесты: tests/test_notes.py, tests/test_notes_apply.py, tests/test_notes_row_format.py, tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py
# патч 1 mutation-001.diff sha256 c1f8f6d737ec1908e9eda8b662cf8627cc3cc9f1b182989fa2d70c63be1a6a58
# патч 2 mutation-002.diff sha256 43ba161391b5aadb9c356b5bcc459bed9784807620931bff55b9c25d98bd62de
# патч 3 mutation-003.diff sha256 4f0fd2c40a9e602629c9b45eb3a63f1b8b6b0512bd5ac174d57dd8ddff8b12bd
# патч 4 mutation-004.diff sha256 8b3e2d97fe8770abed7c4aebc13b20762c5b488b9c5562352fbf6d7c2737b8f7
# патч 5 mutation-005.diff sha256 d150e04ea2b3ff43627178a82f0e796b7e9a9a139a7ce2222ba8733af6abd7a1
# патч 6 mutation-006.diff sha256 f5ea290ecddeed7b760b808498b5dcb764f57317453fb4ddcd1e3824ab9887ee
# патч 7 mutation-007.diff sha256 51b937293ea893fc2aec0f769404d15bddc53a0f8770de878aa77c3d4e5b7eb2
# патч 8 mutation-008.diff sha256 a5b85b30c0dc74215a1be362e718b6f52ed9db52515d331a117354118cefc256
# патч 9 mutation-009.diff sha256 406b57fd6533579e69595443f09e00c334ae64c7e7ade310973116223483ccdb
# патч 10 mutation-010.diff sha256 83012fc051bc33f398f81f518212bb103c3c5934359ca2a4597e9ace7acc71f7
# патч 11 mutation-011.diff sha256 bc5f7c9433b8e3ff2639a347809705c8407ceccdf7b2a08f80ce687d3623e6df
# патч 12 mutation-012.diff sha256 277c618cd6b8f24fe377320f20ed62061d5112f273f796c8578fd7261e02d2d2
# патч 13 mutation-013.diff sha256 19c73bd3fb517fe6fd109314bc308ce2901e689beacdc923fba5aa62b9b1f62b
# патч 14 mutation-014.diff sha256 979b4b6dcd56cd09e54f5fe4ce7fb659fe4a60b4f1f9368da5af5efe1de59fa4
# патч 15 mutation-015.diff sha256 b183c501fb9bcc07e3146b0f4f2bf883fe735d65c659482e571a6f10bfc26355
# патч 16 mutation-016.diff sha256 684b27a090f762c9fc827d014566a6cc713490ad59118cfb254b794a16ac7c18
# патч 17 mutation-017.diff sha256 6484ee4d8b578941de8185df2d26d03a445ed2cb3a6794b8dc364692d470d0cf
# патч 18 mutation-018.diff sha256 c800ed5ac99276cf1734dde984c91d328699367c637291d7a24763f7a098c39e
# патч 19 mutation-019.diff sha256 7920a50a58da0396e8319181380bc78862190f88cb3145a360685be33e52d2ae
# патч 20 mutation-020.diff sha256 0c54a2c26c36e92b573325494d647b7d1c6c95fca68f63baa9180f437c66eac5
# патч 21 mutation-021.diff sha256 409bc23a447c1f8a48d483623527a4ec35ade19e134c81474dbfae16f068a2ec
# патч 22 mutation-022.diff sha256 1c2af34f6854d04382247480e6395e4ebf537bcd00d624800e5302ec733192fc
# патч 23 mutation-023.diff sha256 a8abd7ac69e65ecfbffc35be725c8fbf7b5d0a87747f161c4bb84bd7b6c1fe45
# патч 24 mutation-024.diff sha256 99c7323ea0f0f186a8587141bfac135663048886760143be88c3d2bebadfa871
номер	исход	узлы
1	убита	tests/test_notes.py::ApplyInsertTest::test_inserts_right_after_separator,tests/test_notes.py::RowCellsTest::test_strips_outer_pipes_and_whitespace,tests/test_notes.py::ApplySetStateTest::test_replaces_last_column_entirely_not_appends,tests/test_notes.py::ApplySetPriorityTest::test_replaces_first_column_with_valid_value,tests/test_notes.py::WindowHoldsValidNoteTest::test_ac2_all_five_kinds_held_not_pushed_when_task_in_dev,tests/test_notes.py::ApplyInsertTest::test_column_count_mismatch_refuses_naming_expected_count,tests/test_notes.py::WindowBypassAndNoWindowTest::test_ac6_flush_pushes_held_note_while_window_stays_open,tests/test_notes.py::WindowHoldsValidNoteTest::test_ac3_hold_message_prefix_and_suffix,tests/test_notes.py::WindowHoldsValidNoteTest::test_ac9_held_note_uses_existing_pending_json_shape,tests/test_notes.py::WindowBypassAndNoWindowTest::test_ac8_closed_window_still_flushes_previously_held_note,tests/test_notes.py::WindowBypassAndNoWindowTest::test_ac8_open_window_leaves_previously_held_note_untouched,tests/test_notes.py::WindowBypassAndNoWindowTest::test_ac5_no_window_pushes_immediately_unchanged,tests/test_notes.py::WindowBypassAndNoWindowTest::test_ac7_now_pushes_immediately_and_does_not_hold,tests/test_notes_row_format.py::SetPriorityTest::test_both_forms_write_the_digit,tests/test_notes_row_format.py::StateAppendTest::test_filled_cell_keeps_old_text_and_gets_dated_separator,tests/test_notes_row_format.py::StateAppendTest::test_second_append_keeps_the_first_one_whole,tests/test_notes_row_format.py::InsertedPriorityTest::test_letter_and_digit_forms_both_give_the_digit,tests/test_notes_row_format.py::RowFormsTest::test_framed_and_bare_text_give_the_same_row,tests/test_notes_row_format.py::RowFormsTest::test_single_leading_pipe_is_not_treated_as_framing,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac3_live_holder_with_artel_task_holds_with_old_text,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac3_artel_task_in_every_window_state_holds_with_old_text,tests/test_notes_row_format.py::InsertedPriorityTest::test_unrecognized_priority_refuses_naming_a_valid_form,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac1_external_task_in_every_window_state_does_not_hold,tests/test_notes_row_format.py::InsertedPriorityTest::test_section_without_priority_column_is_not_normalized,tests/test_notes_row_format.py::InsertedDateTest::test_date_shaped_cell_of_another_column_is_untouched,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac5_unresolved_project_outside_window_does_not_hold,tests/test_notes_row_format.py::InsertedDateTest::test_year_is_dropped_short_form_and_non_dates_survive,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac3a_external_holder_does_not_mask_artel_task,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac2_live_holder_with_external_task_does_not_hold,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac3b_earlier_external_task_does_not_mask_artel_task,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac4_unresolved_project_holds_naming_task_and_reason
2	убита	tests/test_notes.py::ApplyInsertTest::test_inserts_right_after_separator
3	убита	tests/test_notes.py::ApplyInsertTest::test_column_count_mismatch_refuses_naming_expected_count,tests/test_notes_row_format.py::RowFormsTest::test_single_leading_pipe_is_not_treated_as_framing,tests/test_notes_row_format.py::RowFormsTest::test_cell_count_is_checked_after_unframing
4	убита	tests/test_notes.py::ApplyInsertTest::test_unknown_section_heading_refuses
5	убита	tests/test_notes.py::ApplyAppendTest::test_unique_key_appends_to_last_column_only,tests/test_notes_row_format.py::StateAppendTest::test_empty_and_dash_cells_get_no_leading_separator,tests/test_notes_row_format.py::StateAppendTest::test_filled_cell_keeps_old_text_and_gets_dated_separator,tests/test_notes_row_format.py::StateAppendTest::test_second_append_keeps_the_first_one_whole
6	убита	tests/test_notes.py::ApplyAppendTest::test_zero_matches_refuses_without_changing_text,tests/test_notes.py::ApplyDropTest::test_zero_matches_refuses_without_changing_text,tests/test_notes.py::WindowHoldsValidNoteTest::test_ac4_unmatched_key_refuses_before_hold_even_with_window_open
7	убита	tests/test_notes.py::ApplySetStateTest::test_multiple_matches_refuses_without_changing_text,tests/test_notes.py::ApplyAppendTest::test_multiple_matches_refuses_without_changing_text,tests/test_notes.py::ApplyDropTest::test_multiple_matches_refuses_without_changing_text
8	убита	tests/test_notes.py::ApplyDropTest::test_removes_matched_row_only_neighbours_untouched
9	убита	tests/test_notes.py::ApplySetStateTest::test_replaces_last_column_entirely_not_appends
10	убита	tests/test_notes.py::ApplySetPriorityTest::test_replaces_first_column_with_valid_value,tests/test_notes_row_format.py::SetPriorityTest::test_both_forms_write_the_digit
11	убита	tests/test_notes_row_format.py::SetPriorityTest::test_both_forms_write_the_digit
12	убита	tests/test_notes.py::ApplySetPriorityTest::test_value_above_range_refuses_without_changing_text,tests/test_notes.py::ApplySetPriorityTest::test_value_below_range_refuses_without_changing_text,tests/test_notes_row_format.py::SetPriorityTest::test_range_is_not_widened_by_the_letter_form,tests/test_notes_row_format.py::InsertedPriorityTest::test_unrecognized_priority_refuses_naming_a_valid_form
13	убита	tests/test_notes.py::ApplySetPriorityTest::test_non_numeric_value_refuses_without_changing_text,tests/test_notes_row_format.py::InsertedPriorityTest::test_unrecognized_priority_refuses_naming_a_valid_form,tests/test_notes_row_format.py::SetPriorityTest::test_range_is_not_widened_by_the_letter_form
14	убита	tests/test_notes_row_format.py::InsertedPriorityTest::test_unrecognized_priority_refuses_naming_a_valid_form,tests/test_notes_row_format.py::SetPriorityTest::test_range_is_not_widened_by_the_letter_form
15	убита	tests/test_notes.py::PendingNotesStorageTest::test_empty_by_default,tests/test_notes.py::WindowHoldsValidNoteTest::test_ac4_unmatched_key_refuses_before_hold_even_with_window_open,tests/test_notes_apply.py::ApplyRefusalTest::test_draft_with_widened_header_refuses,tests/test_notes_apply.py::ApplyRefusalTest::test_draft_equal_to_origin_refuses_instead_of_hanging_in_pending,tests/test_notes_apply.py::ApplyRefusalTest::test_document_changed_in_origin_past_the_base_refuses,tests/test_notes_apply.py::ApplyRefusalTest::test_draft_with_section_heading_but_no_table_refuses,tests/test_notes.py::WindowBypassAndNoWindowTest::test_ac6_flush_pushes_held_note_while_window_stays_open,tests/test_notes.py::WindowBypassAndNoWindowTest::test_ac5_no_window_pushes_immediately_unchanged,tests/test_notes.py::WindowBypassAndNoWindowTest::test_ac7_now_pushes_immediately_and_does_not_hold,tests/test_notes_apply.py::ApplySuccessTest::test_draft_becomes_the_document_in_one_commit,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac1_external_task_in_every_window_state_does_not_hold,tests/test_notes.py::WindowBypassAndNoWindowTest::test_ac8_closed_window_still_flushes_previously_held_note,tests/test_notes_apply.py::ApplyRefusalTest::test_draft_without_a_section_refuses_before_commit,tests/test_notes_apply.py::ApplySilenceWindowTest::test_open_window_holds_apply_until_flush,tests/test_notes_apply.py::ApplyRefusalTest::test_missing_message_and_missing_file_refuse_naming_the_flag,tests/test_notes_apply.py::ApplySilenceWindowTest::test_held_record_is_self_sufficient_without_the_source_file,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac5_unresolved_project_outside_window_does_not_hold,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac2_live_holder_with_external_task_does_not_hold
16	убита	tests/test_notes.py::PendingNotesStorageTest::test_hold_then_read_back_round_trips,tests/test_notes.py::WindowBypassAndNoWindowTest::test_ac8_closed_window_still_flushes_previously_held_note,tests/test_notes.py::WindowBypassAndNoWindowTest::test_ac6_flush_pushes_held_note_while_window_stays_open,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac4_unresolved_project_holds_naming_task_and_reason
17	убита	tests/test_notes.py::PendingNotesStorageTest::test_two_holds_are_both_visible,tests/test_notes.py::WindowHoldsValidNoteTest::test_ac2_all_five_kinds_held_not_pushed_when_task_in_dev,tests/test_notes.py::WindowBypassAndNoWindowTest::test_ac8_open_window_leaves_previously_held_note_untouched
18	убита	tests/test_notes.py::CmdNoteArgumentValidationTest::test_no_arguments_at_all_refuses
19	убита	tests/test_notes.py::CmdNoteArgumentValidationTest::test_section_without_text_refuses
20	убита	tests/test_notes.py::CmdNoteArgumentValidationTest::test_append_without_text_refuses,tests/test_notes_row_format.py::StateFlagAliasTest::test_state_without_text_refuses_naming_the_flag_that_was_used
21	убита	tests/test_notes.py::CmdNoteArgumentValidationTest::test_set_state_without_text_refuses
22	убита	tests/test_notes.py::CmdNoteArgumentValidationTest::test_set_priority_without_text_refuses
23	убита	tests/test_notes.py::CmdNoteArgumentValidationTest::test_flush_with_nothing_pending_is_a_noop,tests/test_notes.py::WindowBypassAndNoWindowTest::test_ac6_flush_pushes_held_note_while_window_stays_open,tests/test_notes_apply.py::ApplySilenceWindowTest::test_held_record_is_self_sufficient_without_the_source_file,tests/test_notes_apply.py::ApplySilenceWindowTest::test_open_window_holds_apply_until_flush,tests/test_notes_apply.py::ApplyRefusalTest::test_origin_changed_while_the_record_was_held_refuses_on_flush,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac4_unresolved_project_holds_naming_task_and_reason
24	убита	tests/test_notes.py::CmdNoteRoleRefusalTest::test_role_refuses_every_form_before_parsing
[01M5NNDYGQ8G6VFDEEXYBB0W3D] mutation-run №1: прогнано патчей 24 (убита: 24); таблица: /Users/al.sidorenko/projects/artel/.artel/logs/suite-run/01M5NNDYGQ8G6VFDEEXYBB0W3D/01M5NNDYGQ8G6VFDEEXYBB0W3D-mutation-run-1.mutations.tsv; лог: /Users/al.sidorenko/projects/artel/.artel/logs/suite-run/01M5NNDYGQ8G6VFDEEXYBB0W3D/01M5NNDYGQ8G6VFDEEXYBB0W3D-mutation-run-1.log
```

### Часть 2 (патчи 25-48)

```text
--- таблица /Users/al.sidorenko/projects/artel/.artel/logs/suite-run/01M5NNDYGQ8G6VFDEEXYBB0W3D/01M5NNDYGQ8G6VFDEEXYBB0W3D-mutation-run-2.mutations.tsv ---
# mutation-run №2 задачи 01M5NNDYGQ8G6VFDEEXYBB0W3D
# источник патчей: каталог на диске
# ревизия прогона: base 549e997ec89bb9b448980d71066a37922b537b9f
# тесты: tests/test_notes.py, tests/test_notes_apply.py, tests/test_notes_row_format.py, tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py
# патч 25 mutation-025.diff sha256 c6f8980d3eb06f385df47ba6c194b9c30d76ae3e31ea7137dda3f0594d404890
# патч 26 mutation-026.diff sha256 eae4a1a7af23cf78e7a392b830814415d0a43daee4b0a05ea94c71c32bc18017
# патч 27 mutation-027.diff sha256 3aa6bb9bf0283151a092db83b289f39d6d6e4897d7e5e8381d62cc0fd3d7335a
# патч 28 mutation-028.diff sha256 151efc56032ffa77304cfd66b033636e5cd70683c97895f28063ed8750640738
# патч 29 mutation-029.diff sha256 d0e1864b9fe52ea9bdf121cd56a9b5a33c7a6da9fd5a33b2209b182e6b2cece1
# патч 30 mutation-030.diff sha256 6bd633b014986e997066ee15aee6eb545ceb8e3cf7ceff4bfe7466e31470abf5
# патч 31 mutation-031.diff sha256 80824386da2e8a20887a2a1dac536c222bc55e3fa4c0e11affb09ebce010b1dc
# патч 32 mutation-032.diff sha256 e6fbe9183e4fa96e6aed2aff738c716669265e5dd00dea82d34e8e09a584286e
# патч 33 mutation-033.diff sha256 083a5cc020dad6f1e0d55b85458f3f014ca8cad85395d4ff022f0abb4c12bce0
# патч 34 mutation-034.diff sha256 306a4c892eb725d52a51b02e1141a99ce4729a3eab17d01aa77ecbcfa1565d14
# патч 35 mutation-035.diff sha256 fa9a626f7203a6ce693739dbafd9da4abe4ad3fc3ec761f030166f9328977991
# патч 36 mutation-036.diff sha256 517ab9904fb93af78d0092ddb275326ad74504dc7d00e6e65e46a4eb97977ff3
# патч 37 mutation-037.diff sha256 54d28c679c55e52c6315742808a3eeaffb5ed206f6374b6e8178caed0eaad89f
# патч 38 mutation-038.diff sha256 c12a7b98a1bb44950997c318d60393010ea072b1bc6bde05ade6d35cdffc6b2b
# патч 39 mutation-039.diff sha256 92b8421b66ac6e1e6c509c4003bbb5cb7b61674be3af573fb8f61f2b0615def3
# патч 40 mutation-040.diff sha256 4ff5cc044aee8780db9ebd3c4c58539126a560a3fd7c7d0cdcaefe9a2ebbab33
# патч 41 mutation-041.diff sha256 b376d33a2c97e6dd511809bcc386f6310ba4664dc49cb4e807f857a75ec669e8
# патч 42 mutation-042.diff sha256 0cd73bab43d432353df9eec96afa75cab6563ed2f85b331dfbdefddf2d1f2dd1
# патч 43 mutation-043.diff sha256 0d618a545bc4cc2319f2909ae6630100c4ffbfa90740cec1ebe804a4f73c744a
# патч 44 mutation-044.diff sha256 b84294de901cf3dacc0847fd54e39b646496bc6e761edc839dd6a63b4b8bbdb5
# патч 45 mutation-045.diff sha256 12b70139d7b7a09724721baf12c3aefb511c919085b45d498b8bd14f49cb6d9d
# патч 46 mutation-046.diff sha256 80913e4b0ad154637df9f14564f2c4ad1f7c678f7e47bc3c5987d0a150f7e218
# патч 47 mutation-047.diff sha256 4fa56f68baebb3121bc7acb5c3577b8bd226a7a8043131f9fcf9ecf57ad009e6
# патч 48 mutation-048.diff sha256 f1753b91f6ec65a35f2abea5d257d3a9f3193a3aaf1a088a4a872bf61d76440f
номер	исход	узлы
25	убита	tests/test_notes.py::CheckPendingNotesTest::test_ok_when_nothing_pending
26	убита	tests/test_notes.py::CheckPendingNotesTest::test_warn_when_something_pending
27	убита	tests/test_notes.py::SilenceWindowReasonTest::test_ac1_live_merge_lock_alone_without_any_task_state_opens_window,tests/test_notes.py::SilenceWindowReasonTest::test_artel_task_and_holder_not_resolved_through_targets,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac3_live_holder_with_artel_task_holds_with_old_text,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac4_unresolved_project_holds_naming_task_and_reason
28	убита	tests/test_notes.py::SilenceWindowReasonTest::test_dead_merge_lock_holder_does_not_open_window,tests/test_notes.py::SilenceWindowReasonTest::test_escalated_state_does_not_open_window,tests/test_notes.py::SilenceWindowReasonTest::test_no_holder_and_no_task_in_set_closes_window,tests/test_notes_apply.py::ApplySuccessTest::test_journal_names_dropped_row_count_and_truncated_rows,tests/test_notes_apply.py::ApplySuccessTest::test_untouched_draft_counts_zero_dropped_rows,tests/test_notes.py::WindowBypassAndNoWindowTest::test_ac5_no_window_pushes_immediately_unchanged,tests/test_notes.py::WindowBypassAndNoWindowTest::test_ac8_closed_window_still_flushes_previously_held_note,tests/test_notes_apply.py::ApplySuccessTest::test_draft_becomes_the_document_in_one_commit,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac1_external_task_in_every_window_state_does_not_hold,tests/test_notes_apply.py::ApplyRefusalTest::test_own_note_commit_past_the_pin_does_not_block_apply,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac2_live_holder_with_external_task_does_not_hold,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac5_unresolved_project_outside_window_does_not_hold
29	убита	tests/test_notes.py::SilenceWindowReasonTest::test_escalated_state_does_not_open_window,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac5_unresolved_project_outside_window_does_not_hold
30	убита	tests/test_notes.py::SilenceWindowReasonTest::test_dead_merge_lock_holder_does_not_open_window
31	убита	tests/test_notes.py::SilenceWindowReasonTest::test_artel_task_and_holder_not_resolved_through_targets,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac3_live_holder_with_artel_task_holds_with_old_text,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac3_artel_task_in_every_window_state_holds_with_old_text
32	убита	tests/test_notes.py::WindowHoldsValidNoteTest::test_ac2_all_five_kinds_held_not_pushed_when_task_in_dev,tests/test_notes_apply.py::ApplySilenceWindowTest::test_open_window_holds_apply_until_flush,tests/test_notes_apply.py::ApplyRefusalTest::test_origin_changed_while_the_record_was_held_refuses_on_flush
33	убита	tests/test_notes.py::WindowHoldsValidNoteTest::test_ac3_hold_message_prefix_and_suffix,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac3_artel_task_in_every_window_state_holds_with_old_text,tests/test_notes_apply.py::ApplySilenceWindowTest::test_open_window_holds_apply_until_flush,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac3b_earlier_external_task_does_not_mask_artel_task,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac3a_external_holder_does_not_mask_artel_task,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac4_unresolved_project_holds_naming_task_and_reason,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac3_live_holder_with_artel_task_holds_with_old_text
34	убита	tests/test_notes.py::WindowHoldsValidNoteTest::test_ac3_hold_message_prefix_and_suffix,tests/test_notes.py::WindowHoldsValidNoteTest::test_ac4_unmatched_key_refuses_before_hold_even_with_window_open,tests/test_notes_apply.py::ApplyRefusalTest::test_origin_changed_while_the_record_was_held_refuses_on_flush
35	убита	tests/test_notes.py::WindowHoldsValidNoteTest::test_ac2_all_five_kinds_held_not_pushed_when_task_in_dev,tests/test_notes.py::WindowHoldsValidNoteTest::test_ac9_held_note_uses_existing_pending_json_shape,tests/test_notes.py::WindowBypassAndNoWindowTest::test_ac6_flush_pushes_held_note_while_window_stays_open,tests/test_notes_apply.py::ApplyRefusalTest::test_origin_changed_while_the_record_was_held_refuses_on_flush,tests/test_notes_apply.py::ApplySilenceWindowTest::test_open_window_holds_apply_until_flush,tests/test_notes_apply.py::ApplySilenceWindowTest::test_held_record_is_self_sufficient_without_the_source_file,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac4_unresolved_project_holds_naming_task_and_reason
36	убита	tests/test_notes.py::WindowBypassAndNoWindowTest::test_ac6_flush_pushes_held_note_while_window_stays_open,tests/test_notes_apply.py::ApplySilenceWindowTest::test_held_record_is_self_sufficient_without_the_source_file,tests/test_notes_apply.py::ApplySilenceWindowTest::test_open_window_holds_apply_until_flush,tests/test_notes_apply.py::ApplyRefusalTest::test_origin_changed_while_the_record_was_held_refuses_on_flush
37	убита	tests/test_notes.py::WindowBypassAndNoWindowTest::test_ac7_now_pushes_immediately_and_does_not_hold,tests/test_notes_apply.py::ApplyRefusalTest::test_origin_changed_while_the_record_was_held_refuses_on_flush
38	убита	tests/test_notes.py::WindowHoldsValidNoteTest::test_ac2_all_five_kinds_held_not_pushed_when_task_in_dev,tests/test_notes.py::WindowBypassAndNoWindowTest::test_ac8_open_window_leaves_previously_held_note_untouched,tests/test_notes_apply.py::ApplyRefusalTest::test_origin_changed_while_the_record_was_held_refuses_on_flush
39	убита	tests/test_notes.py::WindowHoldsValidNoteTest::test_ac2_all_five_kinds_held_not_pushed_when_task_in_dev,tests/test_notes.py::WindowBypassAndNoWindowTest::test_ac8_closed_window_still_flushes_previously_held_note,tests/test_notes.py::WindowBypassAndNoWindowTest::test_ac8_open_window_leaves_previously_held_note_untouched,tests/test_notes_apply.py::ApplyRefusalTest::test_origin_changed_while_the_record_was_held_refuses_on_flush
40	убита	tests/test_notes.py::RudimentRemovedTest::test_notes_module_declares_no_rudiment_exception
41	убита	tests/test_notes_apply.py::ApplyRefusalTest::test_document_changed_in_origin_past_the_base_refuses,tests/test_notes_apply.py::ApplySuccessTest::test_draft_becomes_the_document_in_one_commit
42	убита	tests/test_notes_apply.py::ApplySuccessTest::test_journal_names_dropped_row_count_and_truncated_rows,tests/test_notes_apply.py::ApplySuccessTest::test_untouched_draft_counts_zero_dropped_rows,tests/test_notes_apply.py::ApplyRefusalTest::test_own_note_commit_past_the_pin_does_not_block_apply
43	убита	tests/test_notes_apply.py::ApplySuccessTest::test_untouched_draft_counts_zero_dropped_rows,tests/test_notes_apply.py::ApplyRefusalTest::test_own_note_commit_past_the_pin_does_not_block_apply
44	убита	tests/test_notes_apply.py::ApplyRefusalTest::test_document_changed_in_origin_past_the_base_refuses
45	не убита	
46	убита	tests/test_notes_apply.py::ApplyRefusalTest::test_origin_changed_while_the_record_was_held_refuses_on_flush
47	убита	tests/test_notes_apply.py::ApplyRefusalTest::test_draft_with_section_heading_but_no_table_refuses,tests/test_notes_apply.py::ApplyRefusalTest::test_draft_without_a_section_refuses_before_commit
48	убита	tests/test_notes_apply.py::ApplyRefusalTest::test_draft_with_section_heading_but_no_table_refuses
[01M5NNDYGQ8G6VFDEEXYBB0W3D] mutation-run №2: прогнано патчей 24 (убита: 23, не убита: 1); таблица: /Users/al.sidorenko/projects/artel/.artel/logs/suite-run/01M5NNDYGQ8G6VFDEEXYBB0W3D/01M5NNDYGQ8G6VFDEEXYBB0W3D-mutation-run-2.mutations.tsv; лог: /Users/al.sidorenko/projects/artel/.artel/logs/suite-run/01M5NNDYGQ8G6VFDEEXYBB0W3D/01M5NNDYGQ8G6VFDEEXYBB0W3D-mutation-run-2.log
```

### Часть 3 (патчи 45-72; 45 — переписанный патч, повтор)

```text
--- таблица /Users/al.sidorenko/projects/artel/.artel/logs/suite-run/01M5NNDYGQ8G6VFDEEXYBB0W3D/01M5NNDYGQ8G6VFDEEXYBB0W3D-mutation-run-3.mutations.tsv ---
# mutation-run №3 задачи 01M5NNDYGQ8G6VFDEEXYBB0W3D
# источник патчей: каталог на диске
# ревизия прогона: base 549e997ec89bb9b448980d71066a37922b537b9f
# тесты: tests/test_notes.py, tests/test_notes_apply.py, tests/test_notes_row_format.py, tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py
# патч 45 mutation-045.diff sha256 bc8b6f4fe41841d57c09d197253e2ab02434f2132c5200833d9774a8c7285f4e
# патч 46 mutation-046.diff sha256 80913e4b0ad154637df9f14564f2c4ad1f7c678f7e47bc3c5987d0a150f7e218
# патч 47 mutation-047.diff sha256 4fa56f68baebb3121bc7acb5c3577b8bd226a7a8043131f9fcf9ecf57ad009e6
# патч 48 mutation-048.diff sha256 f1753b91f6ec65a35f2abea5d257d3a9f3193a3aaf1a088a4a872bf61d76440f
# патч 49 mutation-049.diff sha256 3bc6f3ce750f62a462ff874edfa7534828ca81d8894e4fb8cfa8af613d8d2182
# патч 50 mutation-050.diff sha256 9fc40d7614cf3567d47bee33abbaadaa6f5e990b075ba58289d6504c24713142
# патч 51 mutation-051.diff sha256 e5ac39ac4099a799268b09adf2ac2b4070f7691cf0863189ff955e40631c3995
# патч 52 mutation-052.diff sha256 f484151434b4f7ad99c828494420c91173cf814a28b3a24d4cda602d87410374
# патч 53 mutation-053.diff sha256 0657ce9c35f4680cd65d4ada41952509bb040a031643f4f43d977c237bee2654
# патч 54 mutation-054.diff sha256 659134c369b0bbb5c2ffba2cbdc546c55821df072771213784b2075932bebc7b
# патч 55 mutation-055.diff sha256 1bc7487ada2e9c4f732e0c448cb44f72bfd5fc556503294bf9c79a4940b67332
# патч 56 mutation-056.diff sha256 141f897221d8e90349d34ae90043fd30ef90c2444ee3ba346988d399a57ef633
# патч 57 mutation-057.diff sha256 aa1eb9ea9903cbe2514eca9152be254e2e199b9aa3239ad30c89ac6bb063a87c
# патч 58 mutation-058.diff sha256 3c38b60b4df1012ef1fd07f20809003b3779d30015acf96c88d137bf2818ea4e
# патч 59 mutation-059.diff sha256 5e3e40f32d9f220b87a95a2fb75e8da145001491f22892b27f0f5676070f4368
# патч 60 mutation-060.diff sha256 96e4bab21a59dd45f35960d23226ad092720e23e40c133c49f91352357100084
# патч 61 mutation-061.diff sha256 e79a3a415461106d4d67f740eef0abee06b4bf616325a7f0cc182197baadc6a7
# патч 62 mutation-062.diff sha256 806b64658e53dd0b6c14d395c9e473a933ee1c6d296c5c118664881e99996f56
# патч 63 mutation-063.diff sha256 f1c9b607dfc514deb43da16d0bca5df77a22618bd228cf8b03f3fc209929d71a
# патч 64 mutation-064.diff sha256 9bb7914e4d567a14dfedbe46a64d0406299aebc98fb4c37477f5af0ccf3737ca
# патч 65 mutation-065.diff sha256 89c8cd87c040cda3b0463ddaf46922650e48478dc1985d32e8904f4e923a6ba1
# патч 66 mutation-066.diff sha256 04b619336fec0c9d862bc13cd10391a4508bbef20463299a8dc7c3f79ef6199f
# патч 67 mutation-067.diff sha256 45d10f0418ba7cec544fbe18f5dc29e5cf641e793fe54cca9cf0d522b96289b4
# патч 68 mutation-068.diff sha256 d2caa4327f37acdb56b29d96b09fa8176b35d389b98daa16c4487f1158b9366e
# патч 69 mutation-069.diff sha256 90d49f33f0f2633edebca96f396e189329cb81de2d3f87ef6aaefddf6747000c
# патч 70 mutation-070.diff sha256 00fd90bcfd71fbfb416f753a55d328a8a3521610bca23188a01a50836f692a66
# патч 71 mutation-071.diff sha256 d784cc744915f7ba9971be3c6497b97661d0f61f2e09376f2576b4722883a691
# патч 72 mutation-072.diff sha256 ffc9e9bd8abbcd5488c8791107c485450f12d0fa4a09c12633a131f316810c96
номер	исход	узлы
45	убита	tests/test_notes_apply.py::ApplyRefusalTest::test_own_note_commit_past_the_pin_does_not_block_apply
46	убита	tests/test_notes_apply.py::ApplyRefusalTest::test_origin_changed_while_the_record_was_held_refuses_on_flush
47	убита	tests/test_notes_apply.py::ApplyRefusalTest::test_draft_with_section_heading_but_no_table_refuses,tests/test_notes_apply.py::ApplyRefusalTest::test_draft_without_a_section_refuses_before_commit
48	убита	tests/test_notes_apply.py::ApplyRefusalTest::test_draft_with_section_heading_but_no_table_refuses
49	убита	tests/test_notes_apply.py::ApplyRefusalTest::test_draft_with_widened_header_refuses
50	убита	tests/test_notes_apply.py::ApplyRefusalTest::test_draft_equal_to_origin_refuses_instead_of_hanging_in_pending
51	убита	tests/test_notes_apply.py::ApplyRefusalTest::test_missing_message_and_missing_file_refuse_naming_the_flag
52	убита	tests/test_notes_apply.py::ApplyRefusalTest::test_origin_changed_while_the_record_was_held_refuses_on_flush,tests/test_notes_apply.py::ApplySilenceWindowTest::test_open_window_holds_apply_until_flush
53	убита	tests/test_notes_apply.py::ApplySuccessTest::test_journal_names_dropped_row_count_and_truncated_rows,tests/test_notes_apply.py::ApplySuccessTest::test_untouched_draft_counts_zero_dropped_rows,tests/test_notes_apply.py::ApplyRefusalTest::test_draft_without_a_section_refuses_before_commit,tests/test_notes_apply.py::ApplyRefusalTest::test_draft_equal_to_origin_refuses_instead_of_hanging_in_pending,tests/test_notes_apply.py::ApplyRefusalTest::test_draft_with_section_heading_but_no_table_refuses,tests/test_notes_apply.py::ApplySuccessTest::test_draft_becomes_the_document_in_one_commit,tests/test_notes_apply.py::ApplyRefusalTest::test_origin_changed_while_the_record_was_held_refuses_on_flush,tests/test_notes_apply.py::ApplyRefusalTest::test_missing_message_and_missing_file_refuse_naming_the_flag,tests/test_notes_apply.py::ApplySilenceWindowTest::test_held_record_is_self_sufficient_without_the_source_file,tests/test_notes_apply.py::ApplySilenceWindowTest::test_open_window_holds_apply_until_flush,tests/test_notes_apply.py::ApplyRefusalTest::test_own_note_commit_past_the_pin_does_not_block_apply
54	убита	tests/test_notes_apply.py::ApplyRefusalTest::test_origin_changed_while_the_record_was_held_refuses_on_flush,tests/test_notes_row_format.py::RowFormsTest::test_framed_and_bare_text_give_the_same_row,tests/test_notes_row_format.py::RowFormsTest::test_cell_count_is_checked_after_unframing,tests/test_notes_apply.py::ApplyRefusalTest::test_own_note_commit_past_the_pin_does_not_block_apply
55	убита	tests/test_notes_row_format.py::RowFormsTest::test_single_leading_pipe_is_not_treated_as_framing,tests/test_notes_apply.py::ApplyRefusalTest::test_origin_changed_while_the_record_was_held_refuses_on_flush,tests/test_notes_apply.py::ApplyRefusalTest::test_own_note_commit_past_the_pin_does_not_block_apply,tests/test_notes_row_format.py::RowFormsTest::test_framed_and_bare_text_give_the_same_row
56	убита	tests/test_notes_row_format.py::RowFormsTest::test_cell_count_is_checked_after_unframing,tests/test_notes_apply.py::ApplyRefusalTest::test_origin_changed_while_the_record_was_held_refuses_on_flush,tests/test_notes_apply.py::ApplyRefusalTest::test_own_note_commit_past_the_pin_does_not_block_apply,tests/test_notes_row_format.py::RowFormsTest::test_framed_and_bare_text_give_the_same_row
57	убита	tests/test_notes_row_format.py::InsertedPriorityTest::test_unrecognized_priority_refuses_naming_a_valid_form,tests/test_notes_row_format.py::InsertedDateTest::test_date_shaped_cell_of_another_column_is_untouched,tests/test_notes_row_format.py::InsertedPriorityTest::test_letter_and_digit_forms_both_give_the_digit
58	убита	tests/test_notes_row_format.py::InsertedPriorityTest::test_section_without_priority_column_is_not_normalized
59	убита	tests/test_notes.py::ApplyInsertTest::test_inserts_right_after_separator,tests/test_notes.py::WindowHoldsValidNoteTest::test_ac2_all_five_kinds_held_not_pushed_when_task_in_dev,tests/test_notes.py::WindowHoldsValidNoteTest::test_ac3_hold_message_prefix_and_suffix,tests/test_notes.py::WindowBypassAndNoWindowTest::test_ac6_flush_pushes_held_note_while_window_stays_open,tests/test_notes.py::WindowBypassAndNoWindowTest::test_ac5_no_window_pushes_immediately_unchanged,tests/test_notes.py::WindowBypassAndNoWindowTest::test_ac7_now_pushes_immediately_and_does_not_hold,tests/test_notes.py::WindowHoldsValidNoteTest::test_ac9_held_note_uses_existing_pending_json_shape,tests/test_notes.py::WindowBypassAndNoWindowTest::test_ac8_open_window_leaves_previously_held_note_untouched,tests/test_notes.py::WindowBypassAndNoWindowTest::test_ac8_closed_window_still_flushes_previously_held_note,tests/test_notes_row_format.py::RowFormsTest::test_framed_and_bare_text_give_the_same_row,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac1_external_task_in_every_window_state_does_not_hold,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac3_live_holder_with_artel_task_holds_with_old_text,tests/test_notes_row_format.py::InsertedPriorityTest::test_letter_and_digit_forms_both_give_the_digit,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac5_unresolved_project_outside_window_does_not_hold,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac4_unresolved_project_holds_naming_task_and_reason,tests/test_notes_apply.py::ApplyRefusalTest::test_origin_changed_while_the_record_was_held_refuses_on_flush,tests/test_notes_row_format.py::InsertedDateTest::test_year_is_dropped_short_form_and_non_dates_survive,tests/test_notes_apply.py::ApplyRefusalTest::test_own_note_commit_past_the_pin_does_not_block_apply,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac3_artel_task_in_every_window_state_holds_with_old_text,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac3a_external_holder_does_not_mask_artel_task,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac3b_earlier_external_task_does_not_mask_artel_task,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac2_live_holder_with_external_task_does_not_hold
60	убита	tests/test_notes_row_format.py::InsertedDateTest::test_date_shaped_cell_of_another_column_is_untouched
61	убита	tests/test_notes_row_format.py::SetPriorityTest::test_section_without_priority_column_refuses_instead_of_cell_zero
62	убита	tests/test_notes_row_format.py::StateAppendTest::test_empty_and_dash_cells_get_no_leading_separator
63	убита	tests/test_notes_row_format.py::StateAppendTest::test_second_append_keeps_the_first_one_whole
64	убита	tests/test_notes.py::CmdNoteArgumentValidationTest::test_set_state_without_text_refuses,tests/test_notes.py::CmdNoteArgumentValidationTest::test_flush_with_nothing_pending_is_a_noop,tests/test_notes.py::CmdNoteArgumentValidationTest::test_section_without_text_refuses,tests/test_notes.py::WindowHoldsValidNoteTest::test_ac2_all_five_kinds_held_not_pushed_when_task_in_dev,tests/test_notes.py::WindowHoldsValidNoteTest::test_ac3_hold_message_prefix_and_suffix,tests/test_notes.py::CmdNoteArgumentValidationTest::test_no_arguments_at_all_refuses,tests/test_notes_apply.py::ApplySuccessTest::test_untouched_draft_counts_zero_dropped_rows,tests/test_notes_apply.py::ApplySuccessTest::test_journal_names_dropped_row_count_and_truncated_rows,tests/test_notes.py::CmdNoteArgumentValidationTest::test_set_priority_without_text_refuses,tests/test_notes_apply.py::ApplyRefusalTest::test_draft_without_a_section_refuses_before_commit,tests/test_notes_apply.py::ApplyRefusalTest::test_document_changed_in_origin_past_the_base_refuses,tests/test_notes_apply.py::ApplyRefusalTest::test_draft_equal_to_origin_refuses_instead_of_hanging_in_pending,tests/test_notes_apply.py::ApplyRefusalTest::test_missing_message_and_missing_file_refuse_naming_the_flag,tests/test_notes.py::WindowBypassAndNoWindowTest::test_ac8_closed_window_still_flushes_previously_held_note,tests/test_notes.py::WindowBypassAndNoWindowTest::test_ac8_open_window_leaves_previously_held_note_untouched,tests/test_notes.py::WindowBypassAndNoWindowTest::test_ac7_now_pushes_immediately_and_does_not_hold,tests/test_notes.py::WindowBypassAndNoWindowTest::test_ac6_flush_pushes_held_note_while_window_stays_open,tests/test_notes.py::WindowBypassAndNoWindowTest::test_ac5_no_window_pushes_immediately_unchanged,tests/test_notes.py::WindowHoldsValidNoteTest::test_ac9_held_note_uses_existing_pending_json_shape,tests/test_notes_row_format.py::StateFlagAliasTest::test_state_and_append_build_the_same_request,tests/test_notes_apply.py::ApplySuccessTest::test_draft_becomes_the_document_in_one_commit,tests/test_notes_row_format.py::StateFlagAliasTest::test_state_without_text_refuses_naming_the_flag_that_was_used,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac2_live_holder_with_external_task_does_not_hold,tests/test_notes_apply.py::ApplyRefusalTest::test_draft_with_section_heading_but_no_table_refuses,tests/test_notes_apply.py::ApplyRefusalTest::test_draft_with_widened_header_refuses,tests/test_notes_apply.py::ApplyRefusalTest::test_origin_changed_while_the_record_was_held_refuses_on_flush,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac4_unresolved_project_holds_naming_task_and_reason,tests/test_notes_apply.py::ApplySilenceWindowTest::test_held_record_is_self_sufficient_without_the_source_file,tests/test_notes_apply.py::ApplySilenceWindowTest::test_open_window_holds_apply_until_flush,tests/test_notes_apply.py::ApplyRefusalTest::test_own_note_commit_past_the_pin_does_not_block_apply,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac3_artel_task_in_every_window_state_holds_with_old_text,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac1_external_task_in_every_window_state_does_not_hold,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac5_unresolved_project_outside_window_does_not_hold,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac3_live_holder_with_artel_task_holds_with_old_text,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac3a_external_holder_does_not_mask_artel_task,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac3b_earlier_external_task_does_not_mask_artel_task
65	убита	tests/test_notes_row_format.py::StateFlagAliasTest::test_state_without_text_refuses_naming_the_flag_that_was_used
66	убита	tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac1_external_task_in_every_window_state_does_not_hold,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac2_live_holder_with_external_task_does_not_hold,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac3b_earlier_external_task_does_not_mask_artel_task,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac4_unresolved_project_holds_naming_task_and_reason
67	убита	tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac3a_external_holder_does_not_mask_artel_task,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac2_live_holder_with_external_task_does_not_hold
68	убита	tests/test_notes.py::SilenceWindowReasonTest::test_artel_task_and_holder_not_resolved_through_targets,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac3_artel_task_in_every_window_state_holds_with_old_text,tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac3_live_holder_with_artel_task_holds_with_old_text
69	убита	tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac3a_external_holder_does_not_mask_artel_task
70	убита	tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac3b_earlier_external_task_does_not_mask_artel_task
71	убита	tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac4_unresolved_project_holds_naming_task_and_reason
72	убита	tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py::NoteWindowProjectTest::test_ac5_unresolved_project_outside_window_does_not_hold
[01M5NNDYGQ8G6VFDEEXYBB0W3D] mutation-run №3: прогнано патчей 28 (убита: 28); таблица: /Users/al.sidorenko/projects/artel/.artel/logs/suite-run/01M5NNDYGQ8G6VFDEEXYBB0W3D/01M5NNDYGQ8G6VFDEEXYBB0W3D-mutation-run-3.mutations.tsv; лог: /Users/al.sidorenko/projects/artel/.artel/logs/suite-run/01M5NNDYGQ8G6VFDEEXYBB0W3D/01M5NNDYGQ8G6VFDEEXYBB0W3D-mutation-run-3.log
```

## Мутации после

### Часть 1 (патчи 1-36)

```text
--- таблица /Users/al.sidorenko/projects/artel/.artel/logs/suite-run/01M5NNDYGQ8G6VFDEEXYBB0W3D/01M5NNDYGQ8G6VFDEEXYBB0W3D-mutation-run-4.mutations.tsv ---
# mutation-run №4 задачи 01M5NNDYGQ8G6VFDEEXYBB0W3D
# источник патчей: каталог на диске
# ревизия прогона: worktree 7ea8ae4807454acbeecc7221b19079f5766336cf
# тесты: tests/test_notes_module.py
# патч 1 mutation-001.diff sha256 c1f8f6d737ec1908e9eda8b662cf8627cc3cc9f1b182989fa2d70c63be1a6a58
# патч 2 mutation-002.diff sha256 43ba161391b5aadb9c356b5bcc459bed9784807620931bff55b9c25d98bd62de
# патч 3 mutation-003.diff sha256 4f0fd2c40a9e602629c9b45eb3a63f1b8b6b0512bd5ac174d57dd8ddff8b12bd
# патч 4 mutation-004.diff sha256 8b3e2d97fe8770abed7c4aebc13b20762c5b488b9c5562352fbf6d7c2737b8f7
# патч 5 mutation-005.diff sha256 d150e04ea2b3ff43627178a82f0e796b7e9a9a139a7ce2222ba8733af6abd7a1
# патч 6 mutation-006.diff sha256 f5ea290ecddeed7b760b808498b5dcb764f57317453fb4ddcd1e3824ab9887ee
# патч 7 mutation-007.diff sha256 51b937293ea893fc2aec0f769404d15bddc53a0f8770de878aa77c3d4e5b7eb2
# патч 8 mutation-008.diff sha256 a5b85b30c0dc74215a1be362e718b6f52ed9db52515d331a117354118cefc256
# патч 9 mutation-009.diff sha256 406b57fd6533579e69595443f09e00c334ae64c7e7ade310973116223483ccdb
# патч 10 mutation-010.diff sha256 83012fc051bc33f398f81f518212bb103c3c5934359ca2a4597e9ace7acc71f7
# патч 11 mutation-011.diff sha256 bc5f7c9433b8e3ff2639a347809705c8407ceccdf7b2a08f80ce687d3623e6df
# патч 12 mutation-012.diff sha256 277c618cd6b8f24fe377320f20ed62061d5112f273f796c8578fd7261e02d2d2
# патч 13 mutation-013.diff sha256 19c73bd3fb517fe6fd109314bc308ce2901e689beacdc923fba5aa62b9b1f62b
# патч 14 mutation-014.diff sha256 979b4b6dcd56cd09e54f5fe4ce7fb659fe4a60b4f1f9368da5af5efe1de59fa4
# патч 15 mutation-015.diff sha256 b183c501fb9bcc07e3146b0f4f2bf883fe735d65c659482e571a6f10bfc26355
# патч 16 mutation-016.diff sha256 684b27a090f762c9fc827d014566a6cc713490ad59118cfb254b794a16ac7c18
# патч 17 mutation-017.diff sha256 6484ee4d8b578941de8185df2d26d03a445ed2cb3a6794b8dc364692d470d0cf
# патч 18 mutation-018.diff sha256 c800ed5ac99276cf1734dde984c91d328699367c637291d7a24763f7a098c39e
# патч 19 mutation-019.diff sha256 7920a50a58da0396e8319181380bc78862190f88cb3145a360685be33e52d2ae
# патч 20 mutation-020.diff sha256 0c54a2c26c36e92b573325494d647b7d1c6c95fca68f63baa9180f437c66eac5
# патч 21 mutation-021.diff sha256 409bc23a447c1f8a48d483623527a4ec35ade19e134c81474dbfae16f068a2ec
# патч 22 mutation-022.diff sha256 1c2af34f6854d04382247480e6395e4ebf537bcd00d624800e5302ec733192fc
# патч 23 mutation-023.diff sha256 a8abd7ac69e65ecfbffc35be725c8fbf7b5d0a87747f161c4bb84bd7b6c1fe45
# патч 24 mutation-024.diff sha256 99c7323ea0f0f186a8587141bfac135663048886760143be88c3d2bebadfa871
# патч 25 mutation-025.diff sha256 c6f8980d3eb06f385df47ba6c194b9c30d76ae3e31ea7137dda3f0594d404890
# патч 26 mutation-026.diff sha256 eae4a1a7af23cf78e7a392b830814415d0a43daee4b0a05ea94c71c32bc18017
# патч 27 mutation-027.diff sha256 3aa6bb9bf0283151a092db83b289f39d6d6e4897d7e5e8381d62cc0fd3d7335a
# патч 28 mutation-028.diff sha256 151efc56032ffa77304cfd66b033636e5cd70683c97895f28063ed8750640738
# патч 29 mutation-029.diff sha256 d0e1864b9fe52ea9bdf121cd56a9b5a33c7a6da9fd5a33b2209b182e6b2cece1
# патч 30 mutation-030.diff sha256 6bd633b014986e997066ee15aee6eb545ceb8e3cf7ceff4bfe7466e31470abf5
# патч 31 mutation-031.diff sha256 80824386da2e8a20887a2a1dac536c222bc55e3fa4c0e11affb09ebce010b1dc
# патч 32 mutation-032.diff sha256 e6fbe9183e4fa96e6aed2aff738c716669265e5dd00dea82d34e8e09a584286e
# патч 33 mutation-033.diff sha256 083a5cc020dad6f1e0d55b85458f3f014ca8cad85395d4ff022f0abb4c12bce0
# патч 34 mutation-034.diff sha256 306a4c892eb725d52a51b02e1141a99ce4729a3eab17d01aa77ecbcfa1565d14
# патч 35 mutation-035.diff sha256 fa9a626f7203a6ce693739dbafd9da4abe4ad3fc3ec761f030166f9328977991
# патч 36 mutation-036.diff sha256 517ab9904fb93af78d0092ddb275326ad74504dc7d00e6e65e46a4eb97977ff3
номер	исход	узлы
1	убита	tests/test_notes_module.py::test_set_priority_replaces_first_column_with_valid_value,tests/test_notes_module.py::test_set_state_replaces_last_column_entirely_not_appends,tests/test_notes_module.py::test_insert_column_count_mismatch_refuses_naming_expected_count,tests/test_notes_module.py::test_row_cells_strips_outer_pipes_and_whitespace,tests/test_notes_module.py::test_insert_right_after_separator,tests/test_notes_module.py::test_window_ac7_now_pushes_immediately_and_does_not_hold,tests/test_notes_module.py::test_window_ac9_held_note_uses_existing_pending_json_shape,tests/test_notes_module.py::test_window_ac6_flush_pushes_held_note_while_window_stays_open,tests/test_notes_module.py::test_window_ac8_closed_window_still_flushes_previously_held_note,tests/test_notes_module.py::test_row_letter_and_digit_forms_both_give_the_digit[ \u041f 2 ],tests/test_notes_module.py::test_row_unrecognized_priority_refuses_naming_a_valid_form[\u0432\u044b\u0441\u043e\u043a\u0438\u0439],tests/test_notes_module.py::test_row_unrecognized_priority_refuses_naming_a_valid_form[0],tests/test_notes_module.py::test_row_unrecognized_priority_refuses_naming_a_valid_form[\u041f7],tests/test_notes_module.py::test_row_unrecognized_priority_refuses_naming_a_valid_form[],tests/test_notes_module.py::test_row_section_without_priority_column_is_not_normalized,tests/test_notes_module.py::test_row_year_is_dropped_short_form_and_non_dates_survive[22.09.2026-22.09],tests/test_notes_module.py::test_window_ac3_hold_message_prefix_and_suffix,tests/test_notes_module.py::test_row_year_is_dropped_short_form_and_non_dates_survive[27.09-27.09],tests/test_notes_module.py::test_row_year_is_dropped_short_form_and_non_dates_survive[22.9.26-22.9],tests/test_notes_module.py::test_window_ac2_all_five_kinds_held_not_pushed_when_task_in_dev,tests/test_notes_module.py::test_row_date_shaped_cell_of_another_column_is_untouched,tests/test_notes_module.py::test_row_set_priority_both_forms_write_the_digit[\u041f2],tests/test_notes_module.py::test_row_set_priority_both_forms_write_the_digit[2],tests/test_notes_module.py::test_row_filled_cell_keeps_old_text_and_gets_dated_separator,tests/test_notes_module.py::test_row_second_append_keeps_the_first_one_whole,tests/test_notes_module.py::test_window_ac5_no_window_pushes_immediately_unchanged,tests/test_notes_module.py::test_window_ac8_open_window_leaves_previously_held_note_untouched,tests/test_notes_module.py::test_row_framed_and_bare_text_give_the_same_row,tests/test_notes_module.py::test_row_single_leading_pipe_is_not_treated_as_framing,tests/test_notes_module.py::test_row_letter_and_digit_forms_both_give_the_digit[2],tests/test_notes_module.py::test_row_unrecognized_priority_refuses_naming_a_valid_form[5],tests/test_notes_module.py::test_project_ac1_external_task_in_every_window_state_does_not_hold,tests/test_notes_module.py::test_project_ac3_artel_task_in_every_window_state_holds_with_old_text,tests/test_notes_module.py::test_project_ac3a_external_holder_does_not_mask_artel_task,tests/test_notes_module.py::test_row_letter_and_digit_forms_both_give_the_digit[\u041f2],tests/test_notes_module.py::test_project_ac4_unresolved_project_holds_naming_task_and_reason,tests/test_notes_module.py::test_project_ac3_live_holder_with_artel_task_holds_with_old_text,tests/test_notes_module.py::test_project_ac2_live_holder_with_external_task_does_not_hold,tests/test_notes_module.py::test_row_letter_and_digit_forms_both_give_the_digit[\u043f2],tests/test_notes_module.py::test_project_ac3b_earlier_external_task_does_not_mask_artel_task,tests/test_notes_module.py::test_row_year_is_dropped_short_form_and_non_dates_survive[\u0441\u0440\u0430\u0437\u0443-\u0441\u0440\u0430\u0437\u0443],tests/test_notes_module.py::test_project_ac5_unresolved_project_outside_window_does_not_hold
2	убита	tests/test_notes_module.py::test_insert_right_after_separator
3	убита	tests/test_notes_module.py::test_insert_column_count_mismatch_refuses_naming_expected_count,tests/test_notes_module.py::test_row_single_leading_pipe_is_not_treated_as_framing,tests/test_notes_module.py::test_row_cell_count_is_checked_after_unframing
4	убита	tests/test_notes_module.py::test_insert_unknown_section_heading_refuses
5	убита	tests/test_notes_module.py::test_append_unique_key_appends_to_last_column_only,tests/test_notes_module.py::test_row_filled_cell_keeps_old_text_and_gets_dated_separator,tests/test_notes_module.py::test_row_empty_and_dash_cells_get_no_leading_separator[\u0421\u041e\u0421\u0422\u041e\u042f\u041d\u0418\u0415\u041f\u0423\u0421\u0422\u041e],tests/test_notes_module.py::test_row_empty_and_dash_cells_get_no_leading_separator[\u0421\u041e\u0421\u0422\u041e\u042f\u041d\u0418\u0415\u041f\u0420\u041e\u0427\u0415\u0420\u041a],tests/test_notes_module.py::test_row_second_append_keeps_the_first_one_whole
6	убита	tests/test_notes_module.py::test_drop_zero_matches_refuses_without_changing_text,tests/test_notes_module.py::test_append_zero_matches_refuses_without_changing_text,tests/test_notes_module.py::test_window_ac4_unmatched_key_refuses_before_hold_even_with_window_open
7	убита	tests/test_notes_module.py::test_append_multiple_matches_refuses_without_changing_text,tests/test_notes_module.py::test_set_state_multiple_matches_refuses_without_changing_text,tests/test_notes_module.py::test_drop_multiple_matches_refuses_without_changing_text
8	убита	tests/test_notes_module.py::test_drop_removes_matched_row_only_neighbours_untouched
9	убита	tests/test_notes_module.py::test_set_state_replaces_last_column_entirely_not_appends
10	убита	tests/test_notes_module.py::test_set_priority_replaces_first_column_with_valid_value,tests/test_notes_module.py::test_row_set_priority_both_forms_write_the_digit[\u041f2],tests/test_notes_module.py::test_row_set_priority_both_forms_write_the_digit[2]
11	убита	tests/test_notes_module.py::test_row_set_priority_both_forms_write_the_digit[\u041f2]
12	убита	tests/test_notes_module.py::test_set_priority_value_below_range_refuses_without_changing_text,tests/test_notes_module.py::test_set_priority_value_above_range_refuses_without_changing_text,tests/test_notes_module.py::test_row_unrecognized_priority_refuses_naming_a_valid_form[5],tests/test_notes_module.py::test_row_unrecognized_priority_refuses_naming_a_valid_form[0],tests/test_notes_module.py::test_row_unrecognized_priority_refuses_naming_a_valid_form[\u041f7],tests/test_notes_module.py::test_row_set_priority_range_is_not_widened_by_the_letter_form[5],tests/test_notes_module.py::test_row_set_priority_range_is_not_widened_by_the_letter_form[\u041f7],tests/test_notes_module.py::test_row_set_priority_range_is_not_widened_by_the_letter_form[0]
13	убита	tests/test_notes_module.py::test_set_priority_non_numeric_value_refuses_without_changing_text,tests/test_notes_module.py::test_row_unrecognized_priority_refuses_naming_a_valid_form[\u0432\u044b\u0441\u043e\u043a\u0438\u0439],tests/test_notes_module.py::test_row_unrecognized_priority_refuses_naming_a_valid_form[\u041f7],tests/test_notes_module.py::test_row_unrecognized_priority_refuses_naming_a_valid_form[],tests/test_notes_module.py::test_row_set_priority_range_is_not_widened_by_the_letter_form[\u041f7],tests/test_notes_module.py::test_row_set_priority_range_is_not_widened_by_the_letter_form[\u0432\u044b\u0441\u043e\u043a\u0438\u0439]
14	убита	tests/test_notes_module.py::test_row_unrecognized_priority_refuses_naming_a_valid_form[0],tests/test_notes_module.py::test_row_unrecognized_priority_refuses_naming_a_valid_form[5],tests/test_notes_module.py::test_row_unrecognized_priority_refuses_naming_a_valid_form[\u041f7],tests/test_notes_module.py::test_row_unrecognized_priority_refuses_naming_a_valid_form[],tests/test_notes_module.py::test_row_set_priority_range_is_not_widened_by_the_letter_form[5],tests/test_notes_module.py::test_row_set_priority_range_is_not_widened_by_the_letter_form[\u041f7],tests/test_notes_module.py::test_row_set_priority_range_is_not_widened_by_the_letter_form[\u0432\u044b\u0441\u043e\u043a\u0438\u0439],tests/test_notes_module.py::test_row_set_priority_range_is_not_widened_by_the_letter_form[0],tests/test_notes_module.py::test_row_unrecognized_priority_refuses_naming_a_valid_form[\u0432\u044b\u0441\u043e\u043a\u0438\u0439]
15	убита	tests/test_notes_module.py::test_pending_notes_empty_by_default,tests/test_notes_module.py::test_window_ac4_unmatched_key_refuses_before_hold_even_with_window_open,tests/test_notes_module.py::test_window_ac8_closed_window_still_flushes_previously_held_note,tests/test_notes_module.py::test_apply_draft_with_section_heading_but_no_table_refuses,tests/test_notes_module.py::test_window_ac5_no_window_pushes_immediately_unchanged,tests/test_notes_module.py::test_apply_draft_with_widened_header_refuses,tests/test_notes_module.py::test_window_ac7_now_pushes_immediately_and_does_not_hold,tests/test_notes_module.py::test_window_ac6_flush_pushes_held_note_while_window_stays_open,tests/test_notes_module.py::test_apply_draft_becomes_the_document_in_one_commit,tests/test_notes_module.py::test_apply_draft_without_a_section_refuses_before_commit,tests/test_notes_module.py::test_project_ac2_live_holder_with_external_task_does_not_hold,tests/test_notes_module.py::test_project_ac1_external_task_in_every_window_state_does_not_hold,tests/test_notes_module.py::test_project_ac5_unresolved_project_outside_window_does_not_hold,tests/test_notes_module.py::test_apply_held_record_is_self_sufficient_without_the_source_file,tests/test_notes_module.py::test_apply_open_window_holds_apply_until_flush,tests/test_notes_module.py::test_apply_document_changed_in_origin_past_the_base_refuses,tests/test_notes_module.py::test_apply_missing_message_and_missing_file_refuse_naming_the_flag,tests/test_notes_module.py::test_apply_draft_equal_to_origin_refuses_instead_of_hanging_in_pending
16	убита	tests/test_notes_module.py::test_pending_notes_hold_then_read_back_round_trips,tests/test_notes_module.py::test_window_ac6_flush_pushes_held_note_while_window_stays_open,tests/test_notes_module.py::test_window_ac8_closed_window_still_flushes_previously_held_note,tests/test_notes_module.py::test_project_ac4_unresolved_project_holds_naming_task_and_reason
17	убита	tests/test_notes_module.py::test_pending_notes_two_holds_are_both_visible,tests/test_notes_module.py::test_window_ac2_all_five_kinds_held_not_pushed_when_task_in_dev,tests/test_notes_module.py::test_window_ac8_open_window_leaves_previously_held_note_untouched
18	убита	tests/test_notes_module.py::test_cmd_note_no_arguments_at_all_refuses
19	убита	tests/test_notes_module.py::test_cmd_note_section_without_text_refuses
20	убита	tests/test_notes_module.py::test_cmd_note_append_without_text_refuses,tests/test_notes_module.py::test_row_state_without_text_refuses_naming_the_flag_that_was_used
21	убита	tests/test_notes_module.py::test_cmd_note_set_state_without_text_refuses
22	убита	tests/test_notes_module.py::test_cmd_note_set_priority_without_text_refuses
23	убита	tests/test_notes_module.py::test_cmd_note_flush_with_nothing_pending_is_a_noop,tests/test_notes_module.py::test_apply_origin_changed_while_the_record_was_held_refuses_on_flush,tests/test_notes_module.py::test_window_ac6_flush_pushes_held_note_while_window_stays_open,tests/test_notes_module.py::test_apply_open_window_holds_apply_until_flush,tests/test_notes_module.py::test_apply_held_record_is_self_sufficient_without_the_source_file,tests/test_notes_module.py::test_project_ac4_unresolved_project_holds_naming_task_and_reason
24	убита	tests/test_notes_module.py::test_cmd_note_role_refuses_every_form_before_parsing[argv1],tests/test_notes_module.py::test_cmd_note_role_refuses_every_form_before_parsing[argv4],tests/test_notes_module.py::test_cmd_note_role_refuses_every_form_before_parsing[argv3],tests/test_notes_module.py::test_cmd_note_role_refuses_every_form_before_parsing[argv2],tests/test_notes_module.py::test_cmd_note_role_refuses_every_form_before_parsing[argv0]
25	убита	tests/test_notes_module.py::test_check_pending_notes_ok_when_nothing_pending
26	убита	tests/test_notes_module.py::test_check_pending_notes_warn_when_something_pending
27	убита	tests/test_notes_module.py::test_silence_ac1_live_merge_lock_alone_without_any_task_state_opens_window,tests/test_notes_module.py::test_silence_artel_task_and_holder_not_resolved_through_targets,tests/test_notes_module.py::test_project_ac4_unresolved_project_holds_naming_task_and_reason,tests/test_notes_module.py::test_project_ac3_live_holder_with_artel_task_holds_with_old_text
28	убита	tests/test_notes_module.py::test_silence_dead_merge_lock_holder_does_not_open_window,tests/test_notes_module.py::test_silence_escalated_state_does_not_open_window,tests/test_notes_module.py::test_silence_no_holder_and_no_task_in_set_closes_window,tests/test_notes_module.py::test_apply_own_note_commit_past_the_pin_does_not_block_apply,tests/test_notes_module.py::test_apply_journal_names_dropped_row_count_and_truncated_rows,tests/test_notes_module.py::test_apply_untouched_draft_counts_zero_dropped_rows,tests/test_notes_module.py::test_window_ac5_no_window_pushes_immediately_unchanged,tests/test_notes_module.py::test_window_ac8_closed_window_still_flushes_previously_held_note,tests/test_notes_module.py::test_apply_draft_becomes_the_document_in_one_commit,tests/test_notes_module.py::test_project_ac5_unresolved_project_outside_window_does_not_hold,tests/test_notes_module.py::test_project_ac1_external_task_in_every_window_state_does_not_hold,tests/test_notes_module.py::test_project_ac2_live_holder_with_external_task_does_not_hold
29	убита	tests/test_notes_module.py::test_silence_escalated_state_does_not_open_window,tests/test_notes_module.py::test_project_ac5_unresolved_project_outside_window_does_not_hold
30	убита	tests/test_notes_module.py::test_silence_dead_merge_lock_holder_does_not_open_window
31	убита	tests/test_notes_module.py::test_silence_artel_task_and_holder_not_resolved_through_targets,tests/test_notes_module.py::test_project_ac3_artel_task_in_every_window_state_holds_with_old_text,tests/test_notes_module.py::test_project_ac3_live_holder_with_artel_task_holds_with_old_text
32	убита	tests/test_notes_module.py::test_window_ac2_all_five_kinds_held_not_pushed_when_task_in_dev,tests/test_notes_module.py::test_apply_origin_changed_while_the_record_was_held_refuses_on_flush,tests/test_notes_module.py::test_apply_open_window_holds_apply_until_flush
33	убита	tests/test_notes_module.py::test_window_ac3_hold_message_prefix_and_suffix,tests/test_notes_module.py::test_project_ac3b_earlier_external_task_does_not_mask_artel_task,tests/test_notes_module.py::test_project_ac3a_external_holder_does_not_mask_artel_task,tests/test_notes_module.py::test_apply_open_window_holds_apply_until_flush,tests/test_notes_module.py::test_project_ac4_unresolved_project_holds_naming_task_and_reason,tests/test_notes_module.py::test_project_ac3_artel_task_in_every_window_state_holds_with_old_text,tests/test_notes_module.py::test_project_ac3_live_holder_with_artel_task_holds_with_old_text
34	убита	tests/test_notes_module.py::test_window_ac4_unmatched_key_refuses_before_hold_even_with_window_open,tests/test_notes_module.py::test_window_ac3_hold_message_prefix_and_suffix,tests/test_notes_module.py::test_apply_origin_changed_while_the_record_was_held_refuses_on_flush
35	убита	tests/test_notes_module.py::test_window_ac2_all_five_kinds_held_not_pushed_when_task_in_dev,tests/test_notes_module.py::test_window_ac9_held_note_uses_existing_pending_json_shape,tests/test_notes_module.py::test_window_ac6_flush_pushes_held_note_while_window_stays_open,tests/test_notes_module.py::test_apply_origin_changed_while_the_record_was_held_refuses_on_flush,tests/test_notes_module.py::test_project_ac4_unresolved_project_holds_naming_task_and_reason,tests/test_notes_module.py::test_apply_held_record_is_self_sufficient_without_the_source_file,tests/test_notes_module.py::test_apply_open_window_holds_apply_until_flush
36	убита	tests/test_notes_module.py::test_apply_origin_changed_while_the_record_was_held_refuses_on_flush,tests/test_notes_module.py::test_window_ac6_flush_pushes_held_note_while_window_stays_open,tests/test_notes_module.py::test_apply_open_window_holds_apply_until_flush,tests/test_notes_module.py::test_apply_held_record_is_self_sufficient_without_the_source_file
[01M5NNDYGQ8G6VFDEEXYBB0W3D] mutation-run №4: прогнано патчей 36 (убита: 36); таблица: /Users/al.sidorenko/projects/artel/.artel/logs/suite-run/01M5NNDYGQ8G6VFDEEXYBB0W3D/01M5NNDYGQ8G6VFDEEXYBB0W3D-mutation-run-4.mutations.tsv; лог: /Users/al.sidorenko/projects/artel/.artel/logs/suite-run/01M5NNDYGQ8G6VFDEEXYBB0W3D/01M5NNDYGQ8G6VFDEEXYBB0W3D-mutation-run-4.log
```

### Часть 2 (патчи 37-72)

```text
--- таблица /Users/al.sidorenko/projects/artel/.artel/logs/suite-run/01M5NNDYGQ8G6VFDEEXYBB0W3D/01M5NNDYGQ8G6VFDEEXYBB0W3D-mutation-run-5.mutations.tsv ---
# mutation-run №5 задачи 01M5NNDYGQ8G6VFDEEXYBB0W3D
# источник патчей: каталог на диске
# ревизия прогона: worktree 7ea8ae4807454acbeecc7221b19079f5766336cf
# тесты: tests/test_notes_module.py
# патч 37 mutation-037.diff sha256 54d28c679c55e52c6315742808a3eeaffb5ed206f6374b6e8178caed0eaad89f
# патч 38 mutation-038.diff sha256 c12a7b98a1bb44950997c318d60393010ea072b1bc6bde05ade6d35cdffc6b2b
# патч 39 mutation-039.diff sha256 92b8421b66ac6e1e6c509c4003bbb5cb7b61674be3af573fb8f61f2b0615def3
# патч 40 mutation-040.diff sha256 4ff5cc044aee8780db9ebd3c4c58539126a560a3fd7c7d0cdcaefe9a2ebbab33
# патч 41 mutation-041.diff sha256 b376d33a2c97e6dd511809bcc386f6310ba4664dc49cb4e807f857a75ec669e8
# патч 42 mutation-042.diff sha256 0cd73bab43d432353df9eec96afa75cab6563ed2f85b331dfbdefddf2d1f2dd1
# патч 43 mutation-043.diff sha256 0d618a545bc4cc2319f2909ae6630100c4ffbfa90740cec1ebe804a4f73c744a
# патч 44 mutation-044.diff sha256 b84294de901cf3dacc0847fd54e39b646496bc6e761edc839dd6a63b4b8bbdb5
# патч 45 mutation-045.diff sha256 bc8b6f4fe41841d57c09d197253e2ab02434f2132c5200833d9774a8c7285f4e
# патч 46 mutation-046.diff sha256 80913e4b0ad154637df9f14564f2c4ad1f7c678f7e47bc3c5987d0a150f7e218
# патч 47 mutation-047.diff sha256 4fa56f68baebb3121bc7acb5c3577b8bd226a7a8043131f9fcf9ecf57ad009e6
# патч 48 mutation-048.diff sha256 f1753b91f6ec65a35f2abea5d257d3a9f3193a3aaf1a088a4a872bf61d76440f
# патч 49 mutation-049.diff sha256 3bc6f3ce750f62a462ff874edfa7534828ca81d8894e4fb8cfa8af613d8d2182
# патч 50 mutation-050.diff sha256 9fc40d7614cf3567d47bee33abbaadaa6f5e990b075ba58289d6504c24713142
# патч 51 mutation-051.diff sha256 e5ac39ac4099a799268b09adf2ac2b4070f7691cf0863189ff955e40631c3995
# патч 52 mutation-052.diff sha256 f484151434b4f7ad99c828494420c91173cf814a28b3a24d4cda602d87410374
# патч 53 mutation-053.diff sha256 0657ce9c35f4680cd65d4ada41952509bb040a031643f4f43d977c237bee2654
# патч 54 mutation-054.diff sha256 659134c369b0bbb5c2ffba2cbdc546c55821df072771213784b2075932bebc7b
# патч 55 mutation-055.diff sha256 1bc7487ada2e9c4f732e0c448cb44f72bfd5fc556503294bf9c79a4940b67332
# патч 56 mutation-056.diff sha256 141f897221d8e90349d34ae90043fd30ef90c2444ee3ba346988d399a57ef633
# патч 57 mutation-057.diff sha256 aa1eb9ea9903cbe2514eca9152be254e2e199b9aa3239ad30c89ac6bb063a87c
# патч 58 mutation-058.diff sha256 3c38b60b4df1012ef1fd07f20809003b3779d30015acf96c88d137bf2818ea4e
# патч 59 mutation-059.diff sha256 5e3e40f32d9f220b87a95a2fb75e8da145001491f22892b27f0f5676070f4368
# патч 60 mutation-060.diff sha256 96e4bab21a59dd45f35960d23226ad092720e23e40c133c49f91352357100084
# патч 61 mutation-061.diff sha256 e79a3a415461106d4d67f740eef0abee06b4bf616325a7f0cc182197baadc6a7
# патч 62 mutation-062.diff sha256 806b64658e53dd0b6c14d395c9e473a933ee1c6d296c5c118664881e99996f56
# патч 63 mutation-063.diff sha256 f1c9b607dfc514deb43da16d0bca5df77a22618bd228cf8b03f3fc209929d71a
# патч 64 mutation-064.diff sha256 9bb7914e4d567a14dfedbe46a64d0406299aebc98fb4c37477f5af0ccf3737ca
# патч 65 mutation-065.diff sha256 89c8cd87c040cda3b0463ddaf46922650e48478dc1985d32e8904f4e923a6ba1
# патч 66 mutation-066.diff sha256 04b619336fec0c9d862bc13cd10391a4508bbef20463299a8dc7c3f79ef6199f
# патч 67 mutation-067.diff sha256 45d10f0418ba7cec544fbe18f5dc29e5cf641e793fe54cca9cf0d522b96289b4
# патч 68 mutation-068.diff sha256 d2caa4327f37acdb56b29d96b09fa8176b35d389b98daa16c4487f1158b9366e
# патч 69 mutation-069.diff sha256 90d49f33f0f2633edebca96f396e189329cb81de2d3f87ef6aaefddf6747000c
# патч 70 mutation-070.diff sha256 00fd90bcfd71fbfb416f753a55d328a8a3521610bca23188a01a50836f692a66
# патч 71 mutation-071.diff sha256 d784cc744915f7ba9971be3c6497b97661d0f61f2e09376f2576b4722883a691
# патч 72 mutation-072.diff sha256 ffc9e9bd8abbcd5488c8791107c485450f12d0fa4a09c12633a131f316810c96
номер	исход	узлы
37	убита	tests/test_notes_module.py::test_window_ac7_now_pushes_immediately_and_does_not_hold,tests/test_notes_module.py::test_apply_origin_changed_while_the_record_was_held_refuses_on_flush
38	убита	tests/test_notes_module.py::test_window_ac2_all_five_kinds_held_not_pushed_when_task_in_dev,tests/test_notes_module.py::test_window_ac8_open_window_leaves_previously_held_note_untouched,tests/test_notes_module.py::test_apply_origin_changed_while_the_record_was_held_refuses_on_flush
39	убита	tests/test_notes_module.py::test_window_ac2_all_five_kinds_held_not_pushed_when_task_in_dev,tests/test_notes_module.py::test_window_ac8_open_window_leaves_previously_held_note_untouched,tests/test_notes_module.py::test_apply_origin_changed_while_the_record_was_held_refuses_on_flush,tests/test_notes_module.py::test_window_ac8_closed_window_still_flushes_previously_held_note
40	убита	tests/test_notes_module.py::test_notes_module_declares_no_rudiment_exception
41	убита	tests/test_notes_module.py::test_apply_document_changed_in_origin_past_the_base_refuses,tests/test_notes_module.py::test_apply_draft_becomes_the_document_in_one_commit
42	убита	tests/test_notes_module.py::test_apply_journal_names_dropped_row_count_and_truncated_rows,tests/test_notes_module.py::test_apply_untouched_draft_counts_zero_dropped_rows,tests/test_notes_module.py::test_apply_own_note_commit_past_the_pin_does_not_block_apply
43	убита	tests/test_notes_module.py::test_apply_untouched_draft_counts_zero_dropped_rows,tests/test_notes_module.py::test_apply_own_note_commit_past_the_pin_does_not_block_apply
44	убита	tests/test_notes_module.py::test_apply_document_changed_in_origin_past_the_base_refuses
45	убита	tests/test_notes_module.py::test_apply_own_note_commit_past_the_pin_does_not_block_apply
46	убита	tests/test_notes_module.py::test_apply_origin_changed_while_the_record_was_held_refuses_on_flush
47	убита	tests/test_notes_module.py::test_apply_draft_with_section_heading_but_no_table_refuses,tests/test_notes_module.py::test_apply_draft_without_a_section_refuses_before_commit
48	убита	tests/test_notes_module.py::test_apply_draft_with_section_heading_but_no_table_refuses
49	убита	tests/test_notes_module.py::test_apply_draft_with_widened_header_refuses
50	убита	tests/test_notes_module.py::test_apply_draft_equal_to_origin_refuses_instead_of_hanging_in_pending
51	убита	tests/test_notes_module.py::test_apply_missing_message_and_missing_file_refuse_naming_the_flag
52	убита	tests/test_notes_module.py::test_apply_origin_changed_while_the_record_was_held_refuses_on_flush,tests/test_notes_module.py::test_apply_open_window_holds_apply_until_flush
53	убита	tests/test_notes_module.py::test_apply_journal_names_dropped_row_count_and_truncated_rows,tests/test_notes_module.py::test_apply_untouched_draft_counts_zero_dropped_rows,tests/test_notes_module.py::test_apply_draft_with_section_heading_but_no_table_refuses,tests/test_notes_module.py::test_apply_draft_becomes_the_document_in_one_commit,tests/test_notes_module.py::test_apply_origin_changed_while_the_record_was_held_refuses_on_flush,tests/test_notes_module.py::test_apply_draft_without_a_section_refuses_before_commit,tests/test_notes_module.py::test_apply_missing_message_and_missing_file_refuse_naming_the_flag,tests/test_notes_module.py::test_apply_draft_equal_to_origin_refuses_instead_of_hanging_in_pending,tests/test_notes_module.py::test_apply_open_window_holds_apply_until_flush,tests/test_notes_module.py::test_apply_held_record_is_self_sufficient_without_the_source_file,tests/test_notes_module.py::test_apply_own_note_commit_past_the_pin_does_not_block_apply
54	убита	tests/test_notes_module.py::test_apply_own_note_commit_past_the_pin_does_not_block_apply,tests/test_notes_module.py::test_row_framed_and_bare_text_give_the_same_row,tests/test_notes_module.py::test_row_cell_count_is_checked_after_unframing,tests/test_notes_module.py::test_apply_origin_changed_while_the_record_was_held_refuses_on_flush
55	убита	tests/test_notes_module.py::test_apply_origin_changed_while_the_record_was_held_refuses_on_flush,tests/test_notes_module.py::test_apply_own_note_commit_past_the_pin_does_not_block_apply,tests/test_notes_module.py::test_row_single_leading_pipe_is_not_treated_as_framing,tests/test_notes_module.py::test_row_framed_and_bare_text_give_the_same_row
56	убита	tests/test_notes_module.py::test_apply_own_note_commit_past_the_pin_does_not_block_apply,tests/test_notes_module.py::test_apply_origin_changed_while_the_record_was_held_refuses_on_flush,tests/test_notes_module.py::test_row_framed_and_bare_text_give_the_same_row,tests/test_notes_module.py::test_row_cell_count_is_checked_after_unframing
57	убита	tests/test_notes_module.py::test_row_letter_and_digit_forms_both_give_the_digit[ \u041f 2 ],tests/test_notes_module.py::test_row_unrecognized_priority_refuses_naming_a_valid_form[\u0432\u044b\u0441\u043e\u043a\u0438\u0439],tests/test_notes_module.py::test_row_unrecognized_priority_refuses_naming_a_valid_form[5],tests/test_notes_module.py::test_row_unrecognized_priority_refuses_naming_a_valid_form[0],tests/test_notes_module.py::test_row_unrecognized_priority_refuses_naming_a_valid_form[\u041f7],tests/test_notes_module.py::test_row_date_shaped_cell_of_another_column_is_untouched,tests/test_notes_module.py::test_row_letter_and_digit_forms_both_give_the_digit[\u043f2],tests/test_notes_module.py::test_row_letter_and_digit_forms_both_give_the_digit[\u041f2],tests/test_notes_module.py::test_row_unrecognized_priority_refuses_naming_a_valid_form[]
58	убита	tests/test_notes_module.py::test_row_section_without_priority_column_is_not_normalized
59	убита	tests/test_notes_module.py::test_insert_right_after_separator,tests/test_notes_module.py::test_window_ac3_hold_message_prefix_and_suffix,tests/test_notes_module.py::test_window_ac2_all_five_kinds_held_not_pushed_when_task_in_dev,tests/test_notes_module.py::test_window_ac9_held_note_uses_existing_pending_json_shape,tests/test_notes_module.py::test_row_letter_and_digit_forms_both_give_the_digit[2],tests/test_notes_module.py::test_row_year_is_dropped_short_form_and_non_dates_survive[27.09-27.09],tests/test_notes_module.py::test_row_year_is_dropped_short_form_and_non_dates_survive[\u0441\u0440\u0430\u0437\u0443-\u0441\u0440\u0430\u0437\u0443],tests/test_notes_module.py::test_window_ac5_no_window_pushes_immediately_unchanged,tests/test_notes_module.py::test_window_ac8_open_window_leaves_previously_held_note_untouched,tests/test_notes_module.py::test_window_ac7_now_pushes_immediately_and_does_not_hold,tests/test_notes_module.py::test_window_ac6_flush_pushes_held_note_while_window_stays_open,tests/test_notes_module.py::test_window_ac8_closed_window_still_flushes_previously_held_note,tests/test_notes_module.py::test_row_framed_and_bare_text_give_the_same_row,tests/test_notes_module.py::test_row_letter_and_digit_forms_both_give_the_digit[\u043f2],tests/test_notes_module.py::test_row_letter_and_digit_forms_both_give_the_digit[ \u041f 2 ],tests/test_notes_module.py::test_apply_origin_changed_while_the_record_was_held_refuses_on_flush,tests/test_notes_module.py::test_project_ac2_live_holder_with_external_task_does_not_hold,tests/test_notes_module.py::test_project_ac1_external_task_in_every_window_state_does_not_hold,tests/test_notes_module.py::test_project_ac3b_earlier_external_task_does_not_mask_artel_task,tests/test_notes_module.py::test_project_ac3a_external_holder_does_not_mask_artel_task,tests/test_notes_module.py::test_project_ac5_unresolved_project_outside_window_does_not_hold,tests/test_notes_module.py::test_row_letter_and_digit_forms_both_give_the_digit[\u041f2],tests/test_notes_module.py::test_apply_own_note_commit_past_the_pin_does_not_block_apply,tests/test_notes_module.py::test_project_ac3_live_holder_with_artel_task_holds_with_old_text,tests/test_notes_module.py::test_project_ac3_artel_task_in_every_window_state_holds_with_old_text,tests/test_notes_module.py::test_project_ac4_unresolved_project_holds_naming_task_and_reason
60	убита	tests/test_notes_module.py::test_row_date_shaped_cell_of_another_column_is_untouched
61	убита	tests/test_notes_module.py::test_row_set_priority_section_without_priority_column_refuses_instead_of_cell_zero
62	убита	tests/test_notes_module.py::test_row_empty_and_dash_cells_get_no_leading_separator[\u0421\u041e\u0421\u0422\u041e\u042f\u041d\u0418\u0415\u041f\u0420\u041e\u0427\u0415\u0420\u041a]
63	убита	tests/test_notes_module.py::test_row_second_append_keeps_the_first_one_whole
64	убита	tests/test_notes_module.py::test_cmd_note_section_without_text_refuses,tests/test_notes_module.py::test_cmd_note_flush_with_nothing_pending_is_a_noop,tests/test_notes_module.py::test_cmd_note_set_state_without_text_refuses,tests/test_notes_module.py::test_cmd_note_no_arguments_at_all_refuses,tests/test_notes_module.py::test_cmd_note_set_priority_without_text_refuses,tests/test_notes_module.py::test_window_ac2_all_five_kinds_held_not_pushed_when_task_in_dev,tests/test_notes_module.py::test_window_ac3_hold_message_prefix_and_suffix,tests/test_notes_module.py::test_window_ac9_held_note_uses_existing_pending_json_shape,tests/test_notes_module.py::test_row_state_and_append_build_the_same_request,tests/test_notes_module.py::test_row_state_without_text_refuses_naming_the_flag_that_was_used,tests/test_notes_module.py::test_window_ac6_flush_pushes_held_note_while_window_stays_open,tests/test_notes_module.py::test_window_ac8_open_window_leaves_previously_held_note_untouched,tests/test_notes_module.py::test_window_ac7_now_pushes_immediately_and_does_not_hold,tests/test_notes_module.py::test_window_ac8_closed_window_still_flushes_previously_held_note,tests/test_notes_module.py::test_apply_untouched_draft_counts_zero_dropped_rows,tests/test_notes_module.py::test_apply_origin_changed_while_the_record_was_held_refuses_on_flush,tests/test_notes_module.py::test_window_ac5_no_window_pushes_immediately_unchanged,tests/test_notes_module.py::test_apply_journal_names_dropped_row_count_and_truncated_rows,tests/test_notes_module.py::test_apply_draft_with_widened_header_refuses,tests/test_notes_module.py::test_apply_draft_equal_to_origin_refuses_instead_of_hanging_in_pending,tests/test_notes_module.py::test_project_ac3_live_holder_with_artel_task_holds_with_old_text,tests/test_notes_module.py::test_apply_draft_becomes_the_document_in_one_commit,tests/test_notes_module.py::test_apply_document_changed_in_origin_past_the_base_refuses,tests/test_notes_module.py::test_apply_own_note_commit_past_the_pin_does_not_block_apply,tests/test_notes_module.py::test_project_ac3b_earlier_external_task_does_not_mask_artel_task,tests/test_notes_module.py::test_project_ac5_unresolved_project_outside_window_does_not_hold,tests/test_notes_module.py::test_apply_missing_message_and_missing_file_refuse_naming_the_flag,tests/test_notes_module.py::test_apply_draft_with_section_heading_but_no_table_refuses,tests/test_notes_module.py::test_apply_draft_without_a_section_refuses_before_commit,tests/test_notes_module.py::test_project_ac1_external_task_in_every_window_state_does_not_hold,tests/test_notes_module.py::test_apply_open_window_holds_apply_until_flush,tests/test_notes_module.py::test_apply_held_record_is_self_sufficient_without_the_source_file,tests/test_notes_module.py::test_project_ac3a_external_holder_does_not_mask_artel_task,tests/test_notes_module.py::test_project_ac2_live_holder_with_external_task_does_not_hold,tests/test_notes_module.py::test_project_ac4_unresolved_project_holds_naming_task_and_reason,tests/test_notes_module.py::test_project_ac3_artel_task_in_every_window_state_holds_with_old_text
65	убита	tests/test_notes_module.py::test_row_state_without_text_refuses_naming_the_flag_that_was_used
66	убита	tests/test_notes_module.py::test_project_ac2_live_holder_with_external_task_does_not_hold,tests/test_notes_module.py::test_project_ac1_external_task_in_every_window_state_does_not_hold,tests/test_notes_module.py::test_project_ac3b_earlier_external_task_does_not_mask_artel_task,tests/test_notes_module.py::test_project_ac4_unresolved_project_holds_naming_task_and_reason
67	убита	tests/test_notes_module.py::test_project_ac3a_external_holder_does_not_mask_artel_task,tests/test_notes_module.py::test_project_ac2_live_holder_with_external_task_does_not_hold
68	убита	tests/test_notes_module.py::test_silence_artel_task_and_holder_not_resolved_through_targets,tests/test_notes_module.py::test_project_ac3_artel_task_in_every_window_state_holds_with_old_text,tests/test_notes_module.py::test_project_ac3_live_holder_with_artel_task_holds_with_old_text
69	убита	tests/test_notes_module.py::test_project_ac3a_external_holder_does_not_mask_artel_task
70	убита	tests/test_notes_module.py::test_project_ac3b_earlier_external_task_does_not_mask_artel_task
71	убита	tests/test_notes_module.py::test_project_ac4_unresolved_project_holds_naming_task_and_reason
72	убита	tests/test_notes_module.py::test_project_ac5_unresolved_project_outside_window_does_not_hold
[01M5NNDYGQ8G6VFDEEXYBB0W3D] mutation-run №5: прогнано патчей 36 (убита: 36); таблица: /Users/al.sidorenko/projects/artel/.artel/logs/suite-run/01M5NNDYGQ8G6VFDEEXYBB0W3D/01M5NNDYGQ8G6VFDEEXYBB0W3D-mutation-run-5.mutations.tsv; лог: /Users/al.sidorenko/projects/artel/.artel/logs/suite-run/01M5NNDYGQ8G6VFDEEXYBB0W3D/01M5NNDYGQ8G6VFDEEXYBB0W3D-mutation-run-5.log
```
