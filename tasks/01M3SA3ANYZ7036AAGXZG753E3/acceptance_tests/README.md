# Планка задачи 01M3SA3ANYZ7036AAGXZG753E3

Все критерии AC-1…AC-5 проверяют свойства кода и документа, которые
обязаны держаться и после мержа, поэтому планка целиком — долгоживущий
файл кодовой ветки:

`tests/test_01m3sa3anyz7036aagxzg753e3_models_roles.py`

| AC | метод |
|----|-------|
| AC-1 | `RolesColumnTest::test_ac1_roles_column_follows_role_models_with_source` |
| AC-2 | `SummaryLinesTest::test_ac2_summary_line_per_role_matches_resolve_role` |
| AC-3 | `SummaryLinesTest::test_ac3_resolution_error_is_printed_and_the_rest_survives` |
| AC-4 | `ReadOnlyAndReasonsTest::test_ac4_unreadable_layers_named_above_table_nothing_written` |
| AC-5 | `StackDocTest::test_ac5_stack_doc_describes_roles_source_and_summary_lines` |

Валидация стабом: временная реализация `cmd_models` (столбец по
`resolve_role` с источником, итоговые строки, отказ роли строкой) и правка
пункта `docs/stack.md` — все пять тестов зелёные на шести случайных
зёрнах; стаб откатан. До реализации красны AC-1, AC-2, AC-3, AC-5; AC-4
зелёный — держит прежнее поведение (строки-причины, только чтение).
