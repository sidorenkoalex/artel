# Записка developer

## Выяснено
- Планка — acceptance_tests/ (test_places_*.py, test_pin_etalon.py, test_layers_and_prior_test.py); долгоживущие tests/test_01m5jgsaanr1nzyqd4fcsve48y_{task_component,outcome_components,mandate_components,role_outputs}.py.
- `repo_context.profile_of` — «только чтение»: проверка обязательных подполей компонента продублирована в `project_profile._by_zones`.
- Помощники в project_profile: `decide_task`, `for_task`, `for_task_target(target, task_id, conn=None)` (decide как раньше, строку задачи читает только у multi), `for_row(row)`, `is_multi(target)`, `task_components` (зона-каталог — `git ls-tree` базы в клоне, сбой → ZoneListingError → отказ).
- Гейт исходов multi: `outcome_integrity._components_gate` (select_components диффа, запись на компонент, строки «вне границы» в каждой записи, запись пропуска `journal_skip(CHECK_OUTCOME)` с «голова <sha>»), `_components_review_lines`.
- Планка чужого компонента: `tests_writing._tests_writing_foreign_plank_gate` первым в списке гейтов выхода из tests_writing.
- Мандат: `_record_outcome_profiles`, `_record_test_id_refusal`, покрытие матрицы по компонентам в границе.

## Не сработало
- Длинный python-heredoc в Bash — «Parser aborted»: правки большими кусками — Edit.
- `cat`, `ls`, `sed -i` в Bash недоступны/требуют подтверждения.

## Где остановился
- Шаг завершён: все места таблицы переведены (кроме недостижимых fsm_merge_gate :858/:912/:1093); PLAN.md status: ready; карта регенерирована.
- Прогоны: долгоживущие 4 файла — 46 passed; plank-run — 69 passed; тесты затронутых модулей (≈75 файлов тремя пачками) — зелёные; свой tests/test_profile_layers_declared.py (мутация layers_of проверена).

## Чего не хватило
- Дольше всего — опись мест: где `t` — dict без `id`/зон (amend._group_line_errors, fsm_autogate._plank_rule_refusal в старых тестах) — отсюда `for_task_target`/`for_row` с ленивым чтением зон только у multi.
