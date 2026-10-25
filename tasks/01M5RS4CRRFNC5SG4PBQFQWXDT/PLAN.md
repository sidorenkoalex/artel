---
task: 01M5RS4CRRFNC5SG4PBQFQWXDT
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Сведение тестов, волна 2а-2в-1 — песочницы G3б-2 в `tests/prior_outcome_sandbox.py`, 22 теста на `PriorSandbox` в `tests/test_outcome_prior_module.py`

## Подход

Свод механический и сверяется по AST помощниками планки
(`acceptance_tests/_plan.py`); доказательство неослабления — один набор из
37 патчей мутаций `orchestrator/advance_gates/outcome_integrity.py` против
долгоживущего файла («до», `--ref base`) и нового модуля («после», `--ref
worktree`) при неизменном дереве `orchestrator/`.

- `tests/prior_outcome_sandbox.py` — докстринг одной строкой, строки 41–95
  исходного файла (импорты и константы от `import contextlib` до `CLAIM`)
  и классы `Moved`, `Link`, `PriorSandbox`, `ReplacementSandbox`,
  `StrictSandbox` вырезкой строк без единой правки (строки-комментарии
  разделов не перенесены).
- `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py` — удалены пять
  классов песочниц и 14 тестовых классов задачи со строками-комментариями
  разделов `AC-3` … `AC-13`, `AC-32`, `AC-33`, `AC-30`; разделы
  «заменяемые тесты» и «строгий режим» остались над своими оставшимися
  классами; сразу после импорта `MergeOutcomeSandbox` — один оператор
  `from tests.prior_outcome_sandbox import (Moved, ReplacementSandbox,
  StrictSandbox)`. Прочее — без изменений, включая ставшие ненужными
  импорты.
- `tests/test_outcome_prior_module.py` — фикстура `box`
  (`yield from _sandbox(PriorSandbox)`), помощники `refusal`,
  `no_gate_refusal` (копия функций `tests/test_outcome_gate_module.py`
  с докстрингами), `passed`, `grant`, `conftest_case` и 22 тестовые
  функции с прежними именами в порядке файла.
- Карта регенерирована `python3 scripts/codebase_map.py`.

Бюджет SPEC ($50) не пересматривается: файлов и шагов столько, сколько
оценивал SPEC.

## Шаги

1. Перенос песочниц, сокращение долгоживущего файла, свод 22 тестов,
   карта — коммит 53dfb8c0. Проверка: сверка AST (раздел «Сверка по
   AST»); адресно `python3 -m pytest tests/test_outcome_prior_module.py`
   — 22 passed за 144,01 с, `python3 -m pytest
   tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py` — 22 passed,
   18 subtests passed за 204,90 с (оба — под нагрузкой параллельного
   `mutation-run`); `pytest --collect-only` сокращённого файла — 22 теста.
2. Патчи `mutation-001.diff` … `mutation-037.diff` по заявкам (раздел
   «Мутации и заявки»); каждый проверен `git apply --check` на базе
   a8e57874 и компилируется.
3. Таблица «до» частями 1-15, 16-30, 31-37 (раздел «Мутации до»).
4. Таблица «после» теми же диапазонами (раздел «Мутации после»),
   соответствие строк падения — в описании каждой мутации.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 2 (раздел «Мутации и заявки») |
| 2 | 3 |
| 3 | 3, 4 |
| 4 | 3, 4 (раздел «Находки») |
| 5 | 3, 4 |
| 6 | 3, 4 |
| 7 | 3, 4 (контроль зелёный во всех прогонах) |
| 8 | 3, 4 (`--wait-lock 4`) |
| 9 | 1–4 (раздел «Влияние на систему») |
| 10 | 1 |
| 11 | 1 |
| 12 | 1 |
| 13 | 1 |
| 14 | 1 |
| 15 | 3, 4 |
| 16 | 1 |
| 17 | 1 |
| 18 | 1, 3 (раздел «Удалённые дубли», «Находки») |
| 19 | 4 |
| 20 | 4 |
| 21 | 1, 4 (раздел «Числа и время») |
| 22 | 1 |
| 23 | 1 |
| 24 | вне роли (сессия при Операторе) |

## Соответствие имён «до → после»

Каждый тест перенесён функцией с тем же именем, стенд — фикстура `box`.

| Исходный тест | Функция |
|---|---|
| `Ac3GreenPriorTest::test_ac3_green_prior_version_passes_with_prior_line` | `tests/test_outcome_prior_module.py::test_ac3_green_prior_version_passes_with_prior_line` |
| `Ac10EmptyPriorSetTest::test_ac10_empty_set_no_third_checkout` | `tests/test_outcome_prior_module.py::test_ac10_empty_set_no_third_checkout` |
| `Ac4PriorRedTest::test_ac4_prior_red_thrice_refuses_outcome` | `tests/test_outcome_prior_module.py::test_ac4_prior_red_thrice_refuses_outcome` |
| `Ac5PriorUnstableTest::test_ac5_prior_mixed_is_unstable_finding` | `tests/test_outcome_prior_module.py::test_ac5_prior_mixed_is_unstable_finding` |
| `Ac5PriorUnstableTest::test_ac5_red_base_rerun_is_flaky_line_not_finding` | `tests/test_outcome_prior_module.py::test_ac5_red_base_rerun_is_flaky_line_not_finding` |
| `Ac6OneFindingPerIdTest::test_ac6_old_kind_finding_wins_single_line` | `tests/test_outcome_prior_module.py::test_ac6_old_kind_finding_wins_single_line` |
| `Ac7RunScopeTest::test_ac7_test_support_change_runs_full_suite` | `tests/test_outcome_prior_module.py::test_ac7_test_support_change_runs_full_suite` |
| `Ac7RunScopeTest::test_ac7_tests_change_runs_only_changed_files` | `tests/test_outcome_prior_module.py::test_ac7_tests_change_runs_only_changed_files` |
| `Ac8RestoredPathsTest::test_ac8_deleted_file_restored_and_judged` | `tests/test_outcome_prior_module.py::test_ac8_deleted_file_restored_and_judged` |
| `Ac8RestoredPathsTest::test_ac8_renamed_file_old_path_restored_new_stays` | `tests/test_outcome_prior_module.py::test_ac8_renamed_file_old_path_restored_new_stays` |
| `Ac8RestoredPathsTest::test_ac8_type_changed_file_in_set` | `tests/test_outcome_prior_module.py::test_ac8_type_changed_file_in_set` |
| `Ac9NoTestsFieldTest::test_ac9_code_only_and_new_file_no_third_checkout` | `tests/test_outcome_prior_module.py::test_ac9_code_only_and_new_file_no_third_checkout` |
| `Ac9NoTestsFieldTest::test_ac9_changed_base_file_and_file_level_record_in_set` | `tests/test_outcome_prior_module.py::test_ac9_changed_base_file_and_file_level_record_in_set` |
| `Ac11PrepareTest::test_ac11_third_checkout_failure_refuses_prepare` | `tests/test_outcome_prior_module.py::test_ac11_third_checkout_failure_refuses_prepare` |
| `Ac11PrepareTest::test_ac11_third_run_failure_refuses_prepare` | `tests/test_outcome_prior_module.py::test_ac11_third_run_failure_refuses_prepare` |
| `Ac12DiffFailureTest::test_ac12_diff_failures_refuse_prepare` | `tests/test_outcome_prior_module.py::test_ac12_diff_failures_refuse_prepare` |
| `Ac13OwnerMarkerTest::test_ac13_third_checkout_in_scratch_with_marker_and_removed` | `tests/test_outcome_prior_module.py::test_ac13_third_checkout_in_scratch_with_marker_and_removed` |
| `Ac32AddedFilesRemovedTest::test_ac32_added_conftest_under_test_support_removed` | `tests/test_outcome_prior_module.py::test_ac32_added_conftest_under_test_support_removed` |
| `Ac32AddedFilesRemovedTest::test_ac32_added_conftest_under_tests_masks_removed` | `tests/test_outcome_prior_module.py::test_ac32_added_conftest_under_tests_masks_removed` |
| `Ac32AddedFilesRemovedTest::test_ac32_added_conftest_under_scope_without_tests_removed` | `tests/test_outcome_prior_module.py::test_ac32_added_conftest_under_scope_without_tests_removed` |
| `Ac33SkippedMissingRedTest::test_ac33_prior_skipped_or_missing_is_red` | `tests/test_outcome_prior_module.py::test_ac33_prior_skipped_or_missing_is_red` |
| `Ac30OutOfBoundsTest::test_ac30_test_profile_no_outcome_gate` | `tests/test_outcome_prior_module.py::test_ac30_test_profile_no_outcome_gate` |

Помощники: `PriorSandbox.passed` → `passed(box, rows, output, case="")`,
`PriorSandbox.grant` → `grant(box, t, …, case="")`,
`Ac32AddedFilesRemovedTest.conftest_case` → `conftest_case(box, extra,
conftest)`; `refusal`/`no_gate_refusal` — копия одноимённых функций
`tests/test_outcome_gate_module.py` (методы песочницы
`OutcomeGateSandbox.refusal`/`no_gate_refusal` «до»).

Переименованных локальных имён нет: ни одно локальное имя 22 исходных
тестов не совпало с функцией или фикстурой модуля (`box`, `refusal`,
`no_gate_refusal`, `passed`, `grant`, `conftest_case`, имена тестов) и с
фикстурами `tests/fixtures.py`.

Заявки «Ловит мутацию» перенесены дословно, ни одна не переписана.

## Сверка по AST

Сверка — помощниками планки `_plan.py` на базе a8e57874 против рабочей
копии (тот же код, что у планки):

- `sandbox_statements(старый файл)` против операторов
  `tests/prior_outcome_sandbox.py` без докстринга: 48 операторов, все 48
  `ast.dump` равны, порядок тот же.
- Сокращённый долгоживущий файл: оператор сразу после импорта
  `MergeOutcomeSandbox` по `ast.dump` равен `from tests.prior_outcome_sandbox
  import (Moved, ReplacementSandbox, StrictSandbox)`; прочие 62 оператора
  верхнего уровня равны 62 оставшимся операторам базы в том же порядке
  (докстринг, импорты, константы, `env_lines`, 16 классов,
  `unittest.main()`).
- Тела 22 тестовых функций: `actual_test_body(функция) ==
  expected_test_body(метод)` — равны у всех 22 (подслучаи бывших `subTest`
  — строка `case = f"{label}, зерно {box.seed}: "`, у двух блоков `Ac9` —
  литералы «правка файла», «ошибка уровня файла»; прежние циклы `Ac9`,
  `Ac12`, `Ac33` остались циклами); присваивания атрибутам стенда
  (`box.cases[…]`, `box.watch_old`, `box.git_fail`, `box.timeout_when`) —
  та же последовательность, что у `self.…` метода.
- Помощники: `refusal`, `no_gate_refusal` — `ast.dump` равен функциям
  `tests/test_outcome_gate_module.py`; `passed`, `grant`, `conftest_case`
  — `actual_helper_body == expected_helper_body(метод, "box", case)`,
  сигнатуры дословны (у `grant` сообщение — `case + box.note(f"answer
  отказала: {output}")`, ANSWER-1 п. 1).

## Мутации и заявки

Номера — в порядке тестов исходного файла; каждый патч меняет одну
функцию `orchestrator/advance_gates/outcome_integrity.py`. «Строка
падения» — файл:строка упавшего утверждения из лога прогона патча
(`<id>-mutation-run-<n>-p<nnn>.log`): «до» — прогоны №1–№3, «после» —
№4–№6. Строки `tests/outcome_gate_sandbox.py:824`/`:837` «до» —
утверждения методов `OutcomeGateSandbox.refusal`/`no_gate_refusal`,
«после» им соответствуют функции модуля `refusal`
(`tests/test_outcome_prior_module.py:73`) и `no_gate_refusal` (`:83`).

### mutation-001

- Заявка: `Ac3GreenPriorTest::test_ac3_green_prior_version_passes_with_prior_line` — альтернатива «третья выписка не делается — прогонов на стороне прежних версий нет и строки нет».
- Заявка: `Ac4PriorRedTest::test_ac4_prior_red_thrice_refuses_outcome` — альтернатива «прежние версии не гоняются — переход в `verifying`».
- Патч: `orchestrator/advance_gates/outcome_integrity.py`, функция `_judge` — условие шага прежних версий `if prior_paths:` → `if prior_paths and False:` — шаг не исполняется никогда.
- Независимость от случайности: ветвь отключена при любом непустом C, а случайные имена, число и выбор файлов меняют только состав C; строки «прежние версии: …» и отказа прежней версии нет при любом зерне.
- Падение: `test_ac3_green_prior_version_passes_with_prior_line` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:413` → после `tests/test_outcome_prior_module.py:157` (`test_outcome_prior_module.py::test_ac3_green_prior_version_passes_with_prior_line`).
- Падение: `test_ac5_red_base_rerun_is_flaky_line_not_finding` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:543` → после `tests/test_outcome_prior_module.py:274` (`test_outcome_prior_module.py::test_ac5_red_base_rerun_is_flaky_line_not_finding`).
- Падение: `test_ac8_deleted_file_restored_and_judged` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:652` → после `tests/test_outcome_prior_module.py:368` (`test_outcome_prior_module.py::test_ac8_deleted_file_restored_and_judged`).
- Падение: `test_ac11_third_run_failure_refuses_prepare` — до `tests/outcome_gate_sandbox.py:824` → после `tests/test_outcome_prior_module.py:73` (`test_outcome_prior_module.py::test_ac11_third_run_failure_refuses_prepare`).
- Падение: `test_ac4_prior_red_thrice_refuses_outcome` — до `tests/outcome_gate_sandbox.py:824` → после `tests/test_outcome_prior_module.py:73` (`test_outcome_prior_module.py::test_ac4_prior_red_thrice_refuses_outcome`).
- Падение: `test_ac7_test_support_change_runs_full_suite` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:600` → после `tests/test_outcome_prior_module.py:321` (`test_outcome_prior_module.py::test_ac7_test_support_change_runs_full_suite`).
- Падение: `test_ac8_type_changed_file_in_set` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:699` → после `tests/test_outcome_prior_module.py:417` (`test_outcome_prior_module.py::test_ac8_type_changed_file_in_set`).
- Падение: `test_ac13_third_checkout_in_scratch_with_marker_and_removed` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:869` → после `tests/test_outcome_prior_module.py:573` (`test_outcome_prior_module.py::test_ac13_third_checkout_in_scratch_with_marker_and_removed`).
- Падение: `test_ac7_tests_change_runs_only_changed_files` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:622` → после `tests/test_outcome_prior_module.py:343` (`test_outcome_prior_module.py::test_ac7_tests_change_runs_only_changed_files`).
- Падение: `test_ac5_prior_mixed_is_unstable_finding` — до `tests/outcome_gate_sandbox.py:824` → после `tests/test_outcome_prior_module.py:73` (`test_outcome_prior_module.py::test_ac5_prior_mixed_is_unstable_finding`).
- Падение: `test_ac8_renamed_file_old_path_restored_new_stays` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:676` → после `tests/test_outcome_prior_module.py:393` (`test_outcome_prior_module.py::test_ac8_renamed_file_old_path_restored_new_stays`).
- Падение: `test_ac9_changed_base_file_and_file_level_record_in_set` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:751` → после `tests/test_outcome_prior_module.py:466` (`test_outcome_prior_module.py::test_ac9_changed_base_file_and_file_level_record_in_set`).
- Падение: `test_ac11_third_checkout_failure_refuses_prepare` — до `tests/outcome_gate_sandbox.py:824` → после `tests/test_outcome_prior_module.py:73` (`test_outcome_prior_module.py::test_ac11_third_checkout_failure_refuses_prepare`).
- Падение: `test_ac32_added_conftest_under_scope_without_tests_removed` — до `tests/outcome_gate_sandbox.py:824` → после `tests/test_outcome_prior_module.py:73` (`test_outcome_prior_module.py::test_ac32_added_conftest_under_scope_without_tests_removed`).
- Падение: `test_ac32_added_conftest_under_test_support_removed` — до `tests/outcome_gate_sandbox.py:824` → после `tests/test_outcome_prior_module.py:73` (`test_outcome_prior_module.py::test_ac32_added_conftest_under_test_support_removed`).
- Падение: `test_ac32_added_conftest_under_tests_masks_removed` — до `tests/outcome_gate_sandbox.py:824` → после `tests/test_outcome_prior_module.py:73` (`test_outcome_prior_module.py::test_ac32_added_conftest_under_tests_masks_removed`).
- Падение: `test_ac33_prior_skipped_or_missing_is_red` — до `tests/outcome_gate_sandbox.py:824` → после `tests/test_outcome_prior_module.py:73` (`test_outcome_prior_module.py::test_ac33_prior_skipped_or_missing_is_red`).

### mutation-002

- Заявка: `Ac3GreenPriorTest::test_ac3_green_prior_version_passes_with_prior_line` — альтернатива «строка пишется без чисел».
- Патч: `orchestrator/advance_gates/outcome_integrity.py`, функция `_judge` — строка `prior_line` — текст без чисел `f"{PRIOR}: файлов; прогонов"`.
- Независимость от случайности: строка без чисел не совпадает с `PRIOR_LINE` при любом случайном числе файлов и прогонов.
- Падение: `test_ac8_deleted_file_restored_and_judged` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:654` → после `tests/test_outcome_prior_module.py:370` (`test_outcome_prior_module.py::test_ac8_deleted_file_restored_and_judged`).
- Падение: `test_ac3_green_prior_version_passes_with_prior_line` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:413` → после `tests/test_outcome_prior_module.py:157` (`test_outcome_prior_module.py::test_ac3_green_prior_version_passes_with_prior_line`).

### mutation-003

- Заявка: `Ac3GreenPriorTest::test_ac3_green_prior_version_passes_with_prior_line` — альтернатива «строка считает файлы набора C вместе с неизменённым файлом — `n` не тот».
- Патч: `orchestrator/advance_gates/outcome_integrity.py`, функция `_judge` — в `PRIOR_LINE.format` число файлов — `len(files.base_paths)` (все файлы отчёта базы) вместо `len(paths)`.
- Независимость от случайности: неизменённый файл тестов есть в базе при любом зерне, поэтому `n` больше случайного числа изменённых файлов (1 или 2) всегда.
- Падение: `test_ac3_green_prior_version_passes_with_prior_line` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:415` → после `tests/test_outcome_prior_module.py:159` (`test_outcome_prior_module.py::test_ac3_green_prior_version_passes_with_prior_line`).
- Падение: `test_ac8_deleted_file_restored_and_judged` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:654` → после `tests/test_outcome_prior_module.py:370` (`test_outcome_prior_module.py::test_ac8_deleted_file_restored_and_judged`).

### mutation-004

- Заявка: `Ac3GreenPriorTest::test_ac3_green_prior_version_passes_with_prior_line` — альтернатива «гоняется весь набор вместо файлов C».
- Заявка: `Ac7RunScopeTest::test_ac7_tests_change_runs_only_changed_files` — альтернатива «на третьей выписке всегда гоняется полный набор».
- Патч: `orchestrator/advance_gates/outcome_integrity.py`, функция `_prior_versions` — условие полного набора `if any(files.is_support(p) for p in paths):` → `if True:` (альтернативы одинаковы по смыслу — одна мутация).
- Независимость от случайности: полный набор гоняется при любом составе C; случайный выбор изменённых файлов не влияет — на стороне прежних версий всегда есть вызов полного набора и неизменённые файлы.
- Падение: `test_ac3_green_prior_version_passes_with_prior_line` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:418` → после `tests/test_outcome_prior_module.py:162` (`test_outcome_prior_module.py::test_ac3_green_prior_version_passes_with_prior_line`).
- Падение: `test_ac7_tests_change_runs_only_changed_files` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:623` → после `tests/test_outcome_prior_module.py:344` (`test_outcome_prior_module.py::test_ac7_tests_change_runs_only_changed_files`).
- Падение: `test_ac9_changed_base_file_and_file_level_record_in_set` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:751` → после `tests/test_outcome_prior_module.py:466` (`test_outcome_prior_module.py::test_ac9_changed_base_file_and_file_level_record_in_set`).

### mutation-005

- Заявка: `Ac10EmptyPriorSetTest::test_ac10_empty_set_no_third_checkout` — альтернатива «шаг прежних версий исполняется и при пустом C».
- Патч: `orchestrator/advance_gates/outcome_integrity.py`, функция `_judge` — условие `if prior_paths:` → `if True:`.
- Независимость от случайности: при пустом C (правка только кода, случайное имя модуля) третья выписка делается всегда; от случайных имён это не зависит.
- Падение: `test_ac9_code_only_and_new_file_no_third_checkout` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:728` → после `tests/test_outcome_prior_module.py:442` (`test_outcome_prior_module.py::test_ac9_code_only_and_new_file_no_third_checkout`).
- Падение: `test_ac10_empty_set_no_third_checkout` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:444` → после `tests/test_outcome_prior_module.py:184` (`test_outcome_prior_module.py::test_ac10_empty_set_no_third_checkout`).

### mutation-006

- Заявка: `Ac4PriorRedTest::test_ac4_prior_red_thrice_refuses_outcome` — альтернатива «красная прежняя версия отнесена к «сломан правкой»».
- Патч: `orchestrator/advance_gates/outcome_integrity.py`, функция `_prior_redness` — строка вида `PRIOR_RED` записывается видом `BROKEN`.
- Независимость от случайности: прежняя версия красна во всех прогонах при любом зерне, поэтому действие отказа всегда «сломан правкой».
- Падение: `test_ac4_prior_red_thrice_refuses_outcome` — до `tests/outcome_gate_sandbox.py:824` → после `tests/test_outcome_prior_module.py:73` (`test_outcome_prior_module.py::test_ac4_prior_red_thrice_refuses_outcome`).
- Падение: `test_ac32_added_conftest_under_scope_without_tests_removed` — до `tests/outcome_gate_sandbox.py:824` → после `tests/test_outcome_prior_module.py:73` (`test_outcome_prior_module.py::test_ac32_added_conftest_under_scope_without_tests_removed`).
- Падение: `test_ac32_added_conftest_under_test_support_removed` — до `tests/outcome_gate_sandbox.py:824` → после `tests/test_outcome_prior_module.py:73` (`test_outcome_prior_module.py::test_ac32_added_conftest_under_test_support_removed`).
- Падение: `test_ac32_added_conftest_under_tests_masks_removed` — до `tests/outcome_gate_sandbox.py:824` → после `tests/test_outcome_prior_module.py:73` (`test_outcome_prior_module.py::test_ac32_added_conftest_under_tests_masks_removed`).
- Падение: `test_ac33_prior_skipped_or_missing_is_red` — до `tests/outcome_gate_sandbox.py:824` → после `tests/test_outcome_prior_module.py:73` (`test_outcome_prior_module.py::test_ac33_prior_skipped_or_missing_is_red`).

### mutation-007

- Заявка: `Ac4PriorRedTest::test_ac4_prior_red_thrice_refuses_outcome` — альтернатива «исходы строки без «прежняя версия: »».
- Патч: `orchestrator/advance_gates/outcome_integrity.py`, функция `_prior_redness` — текст `runs` — без префикса «прежняя версия: ».
- Независимость от случайности: префикс выпадает в каждой строке отказа; случайный идентификатор теста в начало строки не влияет на её хвост.
- Падение: `test_ac4_prior_red_thrice_refuses_outcome` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:481` → после `tests/test_outcome_prior_module.py:217` (`test_outcome_prior_module.py::test_ac4_prior_red_thrice_refuses_outcome`).
- Падение: `test_ac5_prior_mixed_is_unstable_finding` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:514` → после `tests/test_outcome_prior_module.py:245` (`test_outcome_prior_module.py::test_ac5_prior_mixed_is_unstable_finding`).

### mutation-008

- Заявка: `Ac4PriorRedTest::test_ac4_prior_red_thrice_refuses_outcome` — альтернатива «исходы строки без базы».
- Патч: `orchestrator/advance_gates/outcome_integrity.py`, функция `_prior_redness` — текст `runs` — без «; база: …».
- Независимость от случайности: «; база: » выпадает в каждой строке отказа при любых случайных именах.
- Падение: `test_ac4_prior_red_thrice_refuses_outcome` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:483` → после `tests/test_outcome_prior_module.py:218` (`test_outcome_prior_module.py::test_ac4_prior_red_thrice_refuses_outcome`).

### mutation-009

- Заявка: `Ac5PriorUnstableTest::test_ac5_prior_mixed_is_unstable_finding` — альтернатива «смесь исходов отнесена к «красной»».
- Патч: `orchestrator/advance_gates/outcome_integrity.py`, функция `_prior_redness` — условие красной прежней версии `all(...)` → `any(...)`.
- Независимость от случайности: во всех трёх случайных порядках смеси первый прогон `failed`, поэтому `any` даёт «красную» при любом зерне.
- Падение: `test_ac5_prior_mixed_is_unstable_finding` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:514` → после `tests/test_outcome_prior_module.py:245` (`test_outcome_prior_module.py::test_ac5_prior_mixed_is_unstable_finding`).

### mutation-010

- Заявка: `Ac5PriorUnstableTest::test_ac5_prior_mixed_is_unstable_finding` — альтернатива «перепрогонов на третьей выписке нет».
- Патч: `orchestrator/advance_gates/outcome_integrity.py`, функция `_prior_versions` — `reruns = 0` — перепрогоны прежних версий и базы не делаются.
- Независимость от случайности: первый прогон прежней версии `failed` во всех случайных вариантах; без перепрогонов смеси не видно никогда.
- Падение: `test_ac5_red_base_rerun_is_flaky_line_not_finding` — до `tests/outcome_gate_sandbox.py:837` → после `tests/test_outcome_prior_module.py:83` (`test_outcome_prior_module.py::test_ac5_red_base_rerun_is_flaky_line_not_finding`).
- Падение: `test_ac5_prior_mixed_is_unstable_finding` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:514` → после `tests/test_outcome_prior_module.py:245` (`test_outcome_prior_module.py::test_ac5_prior_mixed_is_unstable_finding`).

### mutation-011

- Заявка: `Ac5PriorUnstableTest::test_ac5_red_base_rerun_is_flaky_line_not_finding` — альтернатива «база в перепрогонах прежних версий не гоняется».
- Патч: `orchestrator/advance_gates/outcome_integrity.py`, функция `_prior_versions` — в `_rerun` сторона базы выброшена (`sides=(PRIOR,)`).
- Независимость от случайности: красный перепрогон базы (случайно 1-й или 2-й, `failed` или `error`) не делается вовсе, поэтому отказ «прежняя версия красная» остаётся при любом зерне.
- Падение: `test_ac5_red_base_rerun_is_flaky_line_not_finding` — до `tests/outcome_gate_sandbox.py:837` → после `tests/test_outcome_prior_module.py:83` (`test_outcome_prior_module.py::test_ac5_red_base_rerun_is_flaky_line_not_finding`).

### mutation-012

- Заявка: `Ac5PriorUnstableTest::test_ac5_red_base_rerun_is_flaky_line_not_finding` — альтернатива «краснота базы в перепрогонах не читается».
- Патч: `orchestrator/advance_gates/outcome_integrity.py`, функция `_prior_redness` — условие красноты базы `if any(... sides[BASE])` → `if False:`.
- Независимость от случайности: краснота базы игнорируется при любом случайном номере и виде красного перепрогона.
- Падение: `test_ac5_red_base_rerun_is_flaky_line_not_finding` — до `tests/outcome_gate_sandbox.py:837` → после `tests/test_outcome_prior_module.py:83` (`test_outcome_prior_module.py::test_ac5_red_base_rerun_is_flaky_line_not_finding`).

### mutation-013

- Заявка: `Ac5PriorUnstableTest::test_ac5_red_base_rerun_is_flaky_line_not_finding` — альтернатива «строка о базе не пишется».
- Патч: `orchestrator/advance_gates/outcome_integrity.py`, функция `_judge` — `flaky += []` — строки «нестабилен и на базе» прежних версий не добавляются.
- Независимость от случайности: строка не пишется при любом случайном номере и виде красного перепрогона базы.
- Падение: `test_ac5_red_base_rerun_is_flaky_line_not_finding` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:543` → после `tests/test_outcome_prior_module.py:274` (`test_outcome_prior_module.py::test_ac5_red_base_rerun_is_flaky_line_not_finding`).

### mutation-014

- Заявка: `Ac6OneFindingPerIdTest::test_ac6_old_kind_finding_wins_single_line` — альтернатива «строка прежней версии добавляется к строке прежнего вида — две строки с идентификатором».
- Патч: `orchestrator/advance_gates/outcome_integrity.py`, функция `_judge` — `findings += prior_found` — без отбора уже занятых идентификаторов.
- Независимость от случайности: у теста всегда есть и «стал пропуском», и красная прежняя версия; случайные имена не меняют число строк с идентификатором.
- Падение: `test_ac6_old_kind_finding_wins_single_line` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:572` → после `tests/test_outcome_prior_module.py:298` (`test_outcome_prior_module.py::test_ac6_old_kind_finding_wins_single_line`).

### mutation-015

- Заявка: `Ac7RunScopeTest::test_ac7_test_support_change_runs_full_suite` — альтернатива «путь `test_support` не входит в C».
- Патч: `orchestrator/advance_gates/outcome_integrity.py`, функция `_judge` — в отборе C `(files.is_test(path) or files.is_support(path))` → `files.is_test(path)`.
- Независимость от случайности: случайное имя файла под `support/**` всегда вне `tests`, поэтому C пуст при любом зерне.
- Падение: `test_ac7_test_support_change_runs_full_suite` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:600` → после `tests/test_outcome_prior_module.py:321` (`test_outcome_prior_module.py::test_ac7_test_support_change_runs_full_suite`).

### mutation-016

- Заявка: `Ac7RunScopeTest::test_ac7_test_support_change_runs_full_suite` — альтернатива «при пути `test_support` гоняются только файлы C».
- Патч: `orchestrator/advance_gates/outcome_integrity.py`, функция `_prior_versions` — условие полного набора `if any(files.is_support(p) ...)` → `if False:`.
- Независимость от случайности: полного набора на стороне прежних версий нет при любом случайном имени файла.
- Падение: `test_ac7_test_support_change_runs_full_suite` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:600` → после `tests/test_outcome_prior_module.py:321` (`test_outcome_prior_module.py::test_ac7_test_support_change_runs_full_suite`).

### mutation-017

- Заявка: `Ac7RunScopeTest::test_ac7_tests_change_runs_only_changed_files` — альтернатива «гоняются и неизменённые файлы отчёта базы».
- Патч: `orchestrator/advance_gates/outcome_integrity.py`, функция `_prior_versions` — прогон прежних версий по `sorted(files.base_paths)` вместо `list(paths)`.
- Независимость от случайности: из трёх файлов базы меняются два (случайный выбор), третий всегда лишний.
- Падение: `test_ac3_green_prior_version_passes_with_prior_line` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:418` → после `tests/test_outcome_prior_module.py:162` (`test_outcome_prior_module.py::test_ac3_green_prior_version_passes_with_prior_line`).
- Падение: `test_ac7_tests_change_runs_only_changed_files` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:626` → после `tests/test_outcome_prior_module.py:346` (`test_outcome_prior_module.py::test_ac7_tests_change_runs_only_changed_files`).
- Падение: `test_ac9_changed_base_file_and_file_level_record_in_set` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:751` → после `tests/test_outcome_prior_module.py:466` (`test_outcome_prior_module.py::test_ac9_changed_base_file_and_file_level_record_in_set`).

### mutation-018

- Заявка: `Ac8RestoredPathsTest::test_ac8_deleted_file_restored_and_judged` — альтернатива «записи `D` выброшены из C».
- Патч: `orchestrator/advance_gates/outcome_integrity.py`, функция `_judge` — в отборе C статус `D` исключён вместе с `A`/`C`.
- Независимость от случайности: удаляется один файл со случайным именем; без `D` C пуст при любом зерне.
- Падение: `test_ac8_deleted_file_restored_and_judged` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:652` → после `tests/test_outcome_prior_module.py:368` (`test_outcome_prior_module.py::test_ac8_deleted_file_restored_and_judged`).

### mutation-019

- Заявка: `Ac8RestoredPathsTest::test_ac8_deleted_file_restored_and_judged` — альтернатива «удалённый путь не восстанавливается командой `git checkout <база> -- <пути>`».
- Патч: `orchestrator/advance_gates/outcome_integrity.py`, функция `_prior_checkout` — `git checkout` прежних версий — только по путям, уже существующим в дереве.
- Независимость от случайности: удалённый путь не существует в дереве головы при любом случайном имени.
- Падение: `test_ac8_deleted_file_restored_and_judged` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:652` → после `tests/test_outcome_prior_module.py:368` (`test_outcome_prior_module.py::test_ac8_deleted_file_restored_and_judged`).
- Падение: `test_ac8_renamed_file_old_path_restored_new_stays` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:676` → после `tests/test_outcome_prior_module.py:393` (`test_outcome_prior_module.py::test_ac8_renamed_file_old_path_restored_new_stays`).

### mutation-020

- Заявка: `Ac8RestoredPathsTest::test_ac8_renamed_file_old_path_restored_new_stays` — альтернатива «у `R` берётся новый путь».
- Патч: `orchestrator/advance_gates/outcome_integrity.py`, функция `_judge` — в C у записи `R` берётся новый путь вместо прежнего.
- Независимость от случайности: переименование `R100` со случайными путями — прежний путь не гоняется при любом зерне.
- Падение: `test_ac8_renamed_file_old_path_restored_new_stays` — до `tests/outcome_gate_sandbox.py:837` → после `tests/test_outcome_prior_module.py:83` (`test_outcome_prior_module.py::test_ac8_renamed_file_old_path_restored_new_stays`).

### mutation-021

- Заявка: `Ac8RestoredPathsTest::test_ac8_renamed_file_old_path_restored_new_stays` — альтернатива «новый путь удалён с третьей выписки».
- Патч: `orchestrator/advance_gates/outcome_integrity.py`, функция `_prior_checkout` — после восстановления путей новый путь записи `R` удаляется из третьей выписки.
- Независимость от случайности: новый путь удаляется всегда, имена путей случайны и на это не влияют.
- Падение: `test_ac8_renamed_file_old_path_restored_new_stays` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:677` → после `tests/test_outcome_prior_module.py:394` (`test_outcome_prior_module.py::test_ac8_renamed_file_old_path_restored_new_stays`).

### mutation-022

- Заявка: `Ac8RestoredPathsTest::test_ac8_type_changed_file_in_set` — альтернатива «в C берутся только статусы `M`/`D`/`R`».
- Патч: `orchestrator/advance_gates/outcome_integrity.py`, функция `_judge` — отбор C — `status.startswith(("M", "D", "R"))`.
- Независимость от случайности: запись `T` выпадает при любом случайном имени файла и данных.
- Падение: `test_ac8_type_changed_file_in_set` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:699` → после `tests/test_outcome_prior_module.py:417` (`test_outcome_prior_module.py::test_ac8_type_changed_file_in_set`).

### mutation-023

- Заявка: `Ac9NoTestsFieldTest::test_ac9_code_only_and_new_file_no_third_checkout` — альтернатива «у компонента без `tests` C — все файлы отчёта базы (третья выписка при правке кода)».
- Заявка: `Ac9NoTestsFieldTest::test_ac9_changed_base_file_and_file_level_record_in_set` — альтернатива «C — все файлы отчёта базы (гоняются и неизменённые файлы)».
- Патч: `orchestrator/advance_gates/outcome_integrity.py`, функция `_judge` — у компонента без `tests` C дополняется `files.base_paths` (альтернативы одинаковы по смыслу — одна мутация).
- Независимость от случайности: файлы отчёта базы есть при любом зерне, поэтому C непуст при правке кода и содержит неизменённые файлы при любом случайном выборе.
- Падение: `test_ac3_green_prior_version_passes_with_prior_line` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:415` → после `tests/test_outcome_prior_module.py:159` (`test_outcome_prior_module.py::test_ac3_green_prior_version_passes_with_prior_line`).
- Падение: `test_ac9_code_only_and_new_file_no_third_checkout` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:728` → после `tests/test_outcome_prior_module.py:442` (`test_outcome_prior_module.py::test_ac9_code_only_and_new_file_no_third_checkout`).
- Падение: `test_ac8_deleted_file_restored_and_judged` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:654` → после `tests/test_outcome_prior_module.py:370` (`test_outcome_prior_module.py::test_ac8_deleted_file_restored_and_judged`).
- Падение: `test_ac10_empty_set_no_third_checkout` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:444` → после `tests/test_outcome_prior_module.py:184` (`test_outcome_prior_module.py::test_ac10_empty_set_no_third_checkout`).
- Падение: `test_ac7_tests_change_runs_only_changed_files` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:626` → после `tests/test_outcome_prior_module.py:346` (`test_outcome_prior_module.py::test_ac7_tests_change_runs_only_changed_files`).
- Падение: `test_ac9_changed_base_file_and_file_level_record_in_set` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:751` → после `tests/test_outcome_prior_module.py:466` (`test_outcome_prior_module.py::test_ac9_changed_base_file_and_file_level_record_in_set`).

### mutation-024

- Заявка: `Ac9NoTestsFieldTest::test_ac9_code_only_and_new_file_no_third_checkout` — альтернатива «файлы `A` входят в C».
- Патч: `orchestrator/advance_gates/outcome_integrity.py`, функция `_judge` — в C добавлены пути `A`, присутствующие в голове.
- Независимость от случайности: новый файл тестов со случайным именем всегда `A`, третья выписка делается при любом зерне.
- Падение: `test_ac9_code_only_and_new_file_no_third_checkout` — до `tests/outcome_gate_sandbox.py:837` → после `tests/test_outcome_prior_module.py:83` (`test_outcome_prior_module.py::test_ac9_code_only_and_new_file_no_third_checkout`).

### mutation-025

- Заявка: `Ac9NoTestsFieldTest::test_ac9_changed_base_file_and_file_level_record_in_set` — альтернатива «файлы записей ошибок уровня файла не входят в перечень отчёта базы».
- Патч: `orchestrator/advance_gates/outcome_integrity.py`, функция `_record_paths` — в разборе записей базы записи `file_level` пропускаются.
- Независимость от случайности: у файла (г) в отчёте базы только запись уровня файла при любом случайном имени — он выпадает всегда.
- Падение: `test_ac9_changed_base_file_and_file_level_record_in_set` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:759` → после `tests/test_outcome_prior_module.py:474` (`test_outcome_prior_module.py::test_ac9_changed_base_file_and_file_level_record_in_set`).

### mutation-026

- Заявка: `Ac11PrepareTest::test_ac11_third_checkout_failure_refuses_prepare` — альтернатива «сбой выписки проглочен как пустой C».
- Патч: `orchestrator/advance_gates/outcome_integrity.py`, функция `_judge` — `_Prepare` из `_prior_checkout` перехвачен — пустой C и ноль прогонов.
- Независимость от случайности: сбой `worktree add` третьей выписки наступает при любом случайном имени файла.
- Падение: `test_ac11_third_checkout_failure_refuses_prepare` — до `tests/outcome_gate_sandbox.py:824` → после `tests/test_outcome_prior_module.py:73` (`test_outcome_prior_module.py::test_ac11_third_checkout_failure_refuses_prepare`).

### mutation-027

- Заявка: `Ac11PrepareTest::test_ac11_third_run_failure_refuses_prepare` — альтернатива «таймаут прогона прежних версий считается красным исходом».
- Патч: `orchestrator/advance_gates/outcome_integrity.py`, функция `_prior_versions` — при `run.timed_out` — пустой список записей вместо `_Prepare` (все тесты прогона без записи).
- Независимость от случайности: таймаут — на каждом прогоне стороны прежних версий при любом зерне; исход от случайных имён не зависит.
- «До» — не убита, «после» — не убита: строки падения нет (раздел «Находки»).

### mutation-028

- Заявка: `Ac11PrepareTest::test_ac11_third_run_failure_refuses_prepare` — альтернатива «таймаут прогона прежних версий считается пропуском».
- Патч: `orchestrator/advance_gates/outcome_integrity.py`, функция `_prior_versions` — при `run.timed_out` — возврат пустой истории (`return {}, [], 1`).
- Независимость от случайности: таймаут наступает при любом случайном имени файла, гейт проходит всегда.
- Падение: `test_ac11_third_run_failure_refuses_prepare` — до `tests/outcome_gate_sandbox.py:824` → после `tests/test_outcome_prior_module.py:73` (`test_outcome_prior_module.py::test_ac11_third_run_failure_refuses_prepare`).

### mutation-029

- Заявка: `Ac11PrepareTest::test_ac11_third_run_failure_refuses_prepare` — альтернатива «уборка третьей выписки не в `finally`».
- Патч: `orchestrator/advance_gates/outcome_integrity.py`, функция `_gate` — уборка `trees`/`scratch` перенесена из `finally` в ветку успеха `_judge`.
- Независимость от случайности: при отказе подготовки (таймаут при любом зерне) уборка не выполняется никогда.
- Падение: `test_ac11_third_run_failure_refuses_prepare` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:813` → после `tests/test_outcome_prior_module.py:525` (`test_outcome_prior_module.py::test_ac11_third_run_failure_refuses_prepare`).

### mutation-030

- Заявка: `Ac12DiffFailureTest::test_ac12_diff_failures_refuse_prepare` — альтернатива «`None` диффа имён — пустой C и пустой строгий режим, гейт идёт дальше».
- Патч: `orchestrator/advance_gates/outcome_integrity.py`, функция `_name_status` — `if entries is None: return []` вместо `_Prepare`.
- Независимость от случайности: сбой `diff --name-status` подстроен для каждого вызова при любом зерне.
- Падение: `test_ac12_diff_failures_refuse_prepare` — до `tests/outcome_gate_sandbox.py:824` → после `tests/test_outcome_prior_module.py:73` (`test_outcome_prior_module.py::test_ac12_diff_failures_refuse_prepare`).

### mutation-031

- Заявка: `Ac12DiffFailureTest::test_ac12_diff_failures_refuse_prepare` — альтернатива «сбой `diff -U0` — пустое «исключение в коде», отказ общего действия либо проход».
- Патч: `orchestrator/advance_gates/outcome_integrity.py`, функция `_added_lines` — при ненулевом коде `diff -U0` — `return {}` вместо `_Prepare`.
- Независимость от случайности: сбой `diff -U0` подстроен для каждого вызова при любом зерне.
- Падение: `test_ac12_diff_failures_refuse_prepare` — до `tests/outcome_gate_sandbox.py:824` → после `tests/test_outcome_prior_module.py:73` (`test_outcome_prior_module.py::test_ac12_diff_failures_refuse_prepare`).

### mutation-032

- Заявка: `Ac13OwnerMarkerTest::test_ac13_third_checkout_in_scratch_with_marker_and_removed` — альтернатива «третья выписка — во временном каталоге вне `scratch` (без маркера владельца)».
- Патч: `orchestrator/advance_gates/outcome_integrity.py`, функция `_prior_checkout` — каталог третьей выписки — `tempfile.mkdtemp` вне `scratch`.
- Независимость от случайности: родитель выписки другой при любом случайном имени файла.
- Падение: `test_ac4_prior_red_thrice_refuses_outcome` — до `tests/outcome_gate_sandbox.py:824` → после `tests/test_outcome_prior_module.py:73` (`test_outcome_prior_module.py::test_ac4_prior_red_thrice_refuses_outcome`).
- Падение: `test_ac5_red_base_rerun_is_flaky_line_not_finding` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:543` → после `tests/test_outcome_prior_module.py:274` (`test_outcome_prior_module.py::test_ac5_red_base_rerun_is_flaky_line_not_finding`).
- Падение: `test_ac3_green_prior_version_passes_with_prior_line` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:417` → после `tests/test_outcome_prior_module.py:161` (`test_outcome_prior_module.py::test_ac3_green_prior_version_passes_with_prior_line`).
- Падение: `test_ac8_type_changed_file_in_set` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:699` → после `tests/test_outcome_prior_module.py:417` (`test_outcome_prior_module.py::test_ac8_type_changed_file_in_set`).
- Падение: `test_ac13_third_checkout_in_scratch_with_marker_and_removed` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:872` → после `tests/test_outcome_prior_module.py:576` (`test_outcome_prior_module.py::test_ac13_third_checkout_in_scratch_with_marker_and_removed`).
- Падение: `test_ac8_deleted_file_restored_and_judged` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:652` → после `tests/test_outcome_prior_module.py:368` (`test_outcome_prior_module.py::test_ac8_deleted_file_restored_and_judged`).
- Падение: `test_ac11_third_run_failure_refuses_prepare` — до `tests/outcome_gate_sandbox.py:824` → после `tests/test_outcome_prior_module.py:73` (`test_outcome_prior_module.py::test_ac11_third_run_failure_refuses_prepare`).
- Падение: `test_ac7_test_support_change_runs_full_suite` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:600` → после `tests/test_outcome_prior_module.py:321` (`test_outcome_prior_module.py::test_ac7_test_support_change_runs_full_suite`).
- Падение: `test_ac5_prior_mixed_is_unstable_finding` — до `tests/outcome_gate_sandbox.py:824` → после `tests/test_outcome_prior_module.py:73` (`test_outcome_prior_module.py::test_ac5_prior_mixed_is_unstable_finding`).
- Падение: `test_ac7_tests_change_runs_only_changed_files` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:622` → после `tests/test_outcome_prior_module.py:343` (`test_outcome_prior_module.py::test_ac7_tests_change_runs_only_changed_files`).
- Падение: `test_ac9_changed_base_file_and_file_level_record_in_set` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:751` → после `tests/test_outcome_prior_module.py:466` (`test_outcome_prior_module.py::test_ac9_changed_base_file_and_file_level_record_in_set`).
- Падение: `test_ac8_renamed_file_old_path_restored_new_stays` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:676` → после `tests/test_outcome_prior_module.py:393` (`test_outcome_prior_module.py::test_ac8_renamed_file_old_path_restored_new_stays`).
- Падение: `test_ac32_added_conftest_under_scope_without_tests_removed` — до `tests/outcome_gate_sandbox.py:824` → после `tests/test_outcome_prior_module.py:73` (`test_outcome_prior_module.py::test_ac32_added_conftest_under_scope_without_tests_removed`).
- Падение: `test_ac32_added_conftest_under_tests_masks_removed` — до `tests/outcome_gate_sandbox.py:824` → после `tests/test_outcome_prior_module.py:73` (`test_outcome_prior_module.py::test_ac32_added_conftest_under_tests_masks_removed`).
- Падение: `test_ac32_added_conftest_under_test_support_removed` — до `tests/outcome_gate_sandbox.py:824` → после `tests/test_outcome_prior_module.py:73` (`test_outcome_prior_module.py::test_ac32_added_conftest_under_test_support_removed`).
- Падение: `test_ac33_prior_skipped_or_missing_is_red` — до `tests/outcome_gate_sandbox.py:824` → после `tests/test_outcome_prior_module.py:73` (`test_outcome_prior_module.py::test_ac33_prior_skipped_or_missing_is_red`).

### mutation-033

- Заявка: `Ac13OwnerMarkerTest::test_ac13_third_checkout_in_scratch_with_marker_and_removed` — альтернатива «выписка не попадает в `trees` и не убирается».
- Патч: `orchestrator/advance_gates/outcome_integrity.py`, функция `_prior_checkout` — строка `trees[PRIOR] = tree` удалена.
- Независимость от случайности: без записи в `trees` третья выписка не судится и не убирается при любом зерне.
- Падение: `test_ac5_red_base_rerun_is_flaky_line_not_finding` — до `tests/outcome_gate_sandbox.py:837` → после `tests/test_outcome_prior_module.py:83` (`test_outcome_prior_module.py::test_ac5_red_base_rerun_is_flaky_line_not_finding`).
- Падение: `test_ac4_prior_red_thrice_refuses_outcome` — до `tests/outcome_gate_sandbox.py:824` → после `tests/test_outcome_prior_module.py:73` (`test_outcome_prior_module.py::test_ac4_prior_red_thrice_refuses_outcome`).
- Падение: `test_ac5_prior_mixed_is_unstable_finding` — до `tests/outcome_gate_sandbox.py:824` → после `tests/test_outcome_prior_module.py:73` (`test_outcome_prior_module.py::test_ac5_prior_mixed_is_unstable_finding`).
- Падение: `test_ac6_old_kind_finding_wins_single_line` — до `tests/outcome_gate_sandbox.py:824` → после `tests/test_outcome_prior_module.py:73` (`test_outcome_prior_module.py::test_ac6_old_kind_finding_wins_single_line`).
- Падение: `test_ac32_added_conftest_under_scope_without_tests_removed` — до `tests/outcome_gate_sandbox.py:824` → после `tests/test_outcome_prior_module.py:73` (`test_outcome_prior_module.py::test_ac32_added_conftest_under_scope_without_tests_removed`).
- Падение: `test_ac32_added_conftest_under_test_support_removed` — до `tests/outcome_gate_sandbox.py:824` → после `tests/test_outcome_prior_module.py:73` (`test_outcome_prior_module.py::test_ac32_added_conftest_under_test_support_removed`).
- Падение: `test_ac32_added_conftest_under_tests_masks_removed` — до `tests/outcome_gate_sandbox.py:824` → после `tests/test_outcome_prior_module.py:73` (`test_outcome_prior_module.py::test_ac32_added_conftest_under_tests_masks_removed`).
- Падение: `test_ac33_prior_skipped_or_missing_is_red` — до `tests/outcome_gate_sandbox.py:824` → после `tests/test_outcome_prior_module.py:73` (`test_outcome_prior_module.py::test_ac33_prior_skipped_or_missing_is_red`).

### mutation-034

- Заявка: `Ac32AddedFilesRemovedTest::test_ac32_added_conftest_under_test_support_removed` — альтернатива «файлы `A` под `test_support` на третьей выписке остаются».
- Патч: `orchestrator/advance_gates/outcome_integrity.py`, функция `_Files.dropped_on_prior` — в `_Files.added_removable` (проверка `is_support`) ветвь `test_support` удалена.
- Независимость от случайности: `conftest.py` под `support/` со случайным именем теста остаётся всегда.
- Падение: `test_ac32_added_conftest_under_test_support_removed` — до `tests/outcome_gate_sandbox.py:824` → после `tests/test_outcome_prior_module.py:73` (`test_outcome_prior_module.py::test_ac32_added_conftest_under_test_support_removed`).

### mutation-035

- Заявка: `Ac32AddedFilesRemovedTest::test_ac32_added_conftest_under_tests_masks_removed` — альтернатива «удаляются только файлы `A` с записями в отчёте».
- Заявка: `Ac32AddedFilesRemovedTest::test_ac32_added_conftest_under_scope_without_tests_removed` — альтернатива «у компонента без `tests` удаляются только файлы `A` с записями в отчёте головы».
- Патч: `orchestrator/advance_gates/outcome_integrity.py`, функция `_Files.dropped_on_prior` — удаляемые файлы `A` ограничены путями с записями отчёта головы (`head_paths`) (альтернативы одинаковы по смыслу — одна мутация).
- Независимость от случайности: `conftest.py` без записей в отчёте не удаляется при любом случайном имени.
- Падение: `test_ac32_added_conftest_under_scope_without_tests_removed` — до `tests/outcome_gate_sandbox.py:824` → после `tests/test_outcome_prior_module.py:73` (`test_outcome_prior_module.py::test_ac32_added_conftest_under_scope_without_tests_removed`).
- Падение: `test_ac32_added_conftest_under_tests_masks_removed` — до `tests/outcome_gate_sandbox.py:824` → после `tests/test_outcome_prior_module.py:73` (`test_outcome_prior_module.py::test_ac32_added_conftest_under_tests_masks_removed`).

### mutation-036

- Заявка: `Ac33SkippedMissingRedTest::test_ac33_prior_skipped_or_missing_is_red` — альтернатива «зелёным считается всё, кроме `failed`/`error`».
- Патч: `orchestrator/advance_gates/outcome_integrity.py`, функция `_prior_versions` — зелёная прежняя версия — `case is None or case.outcome not in (FAILED, ERROR)`.
- Независимость от случайности: оба подслучая (`skipped` и отсутствие записи) зелены при любом случайном имени.
- Падение: `test_ac33_prior_skipped_or_missing_is_red` — до `tests/outcome_gate_sandbox.py:824` → после `tests/test_outcome_prior_module.py:73` (`test_outcome_prior_module.py::test_ac33_prior_skipped_or_missing_is_red`).

### mutation-037

- Заявка: `Ac30OutOfBoundsTest::test_ac30_test_profile_no_outcome_gate` — альтернатива «строгий режим, исключения в коде или прежние версии исполняются вне границы `in_outcome_bounds`».
- Патч: `orchestrator/advance_gates/outcome_integrity.py`, функция `_bounds` — граница гейта `in_outcome_bounds(decision.profile)` → `project_profile.reported(decision.profile)` — все три шага исполняются у `test_profile` (три альтернативы — одно решение кода: одна проверка границы открывает все три шага).
- Независимость от случайности: у `test_profile` граница пропускает шаги при любом случайном имени файла.
- Падение: `test_ac30_test_profile_no_outcome_gate` — до `tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py:1729` → после `tests/test_outcome_prior_module.py:664` (`test_outcome_prior_module.py::test_ac30_test_profile_no_outcome_gate`).

## Мутации до

Части `--patches 1-15`, `16-30`, `31-37`, рабочих процессов auto
(умолчание узла прогона), `--wait-lock 4`; контрольный прогон каждой
части зелёный. Таблица части 1-15 перенесена в PLAN после старта части
16-30: вызов второй части ушёл в одном пакете с записью PLAN, запись
отказала, вторая часть стартовала — нарушение порядка требования 2 SPEC
признаю; на исход и таблицы оно не влияет.

```
# mutation-run №1 задачи 01M5RS4CRRFNC5SG4PBQFQWXDT
# источник патчей: каталог на диске
# ревизия прогона: base a8e578743f79554d0590c07f17a9ade06f539639
# тесты: tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py
# рабочих процессов: auto
# патч 1 mutation-001.diff sha256 9f8b0340b675f44dd418afab8b53697d413ce635608e0f53b9ba2a05885262f1
# патч 2 mutation-002.diff sha256 c35bcf5b49ee9494bf544b48fc705c4203a70bf3b7e29ffbaaa60b0cda6c3886
# патч 3 mutation-003.diff sha256 6529b8e8be0858ca14a029aabca87e003d51abea20881f5f6b2aa4ed23e012a1
# патч 4 mutation-004.diff sha256 bf22fefdf6ec1198143f74295829ea033bf4e79dbc9524079de1a39bc44f208f
# патч 5 mutation-005.diff sha256 5f090575ae91abf8f5c446f4270bfecf4c4d7f0201aedaec23f42e31b94805b9
# патч 6 mutation-006.diff sha256 d7ffce340818753e21b6da3b638631f15d2fffac87084fe18929043ca893056e
# патч 7 mutation-007.diff sha256 8171ea9949ecd7950c9ef24c27d0c6416f8c773476801f042ae03cf9538db3a2
# патч 8 mutation-008.diff sha256 1d7a64dbf967e716ff6f5927819ebaba3e1947fe4b865eb7874c3121bda51c70
# патч 9 mutation-009.diff sha256 b3e049593c14e82b4b4e9327b18111548a9e18cdda9c67327895b3133986ee3f
# патч 10 mutation-010.diff sha256 b119a6c53964c7e47381da5b1162497a5943263eeb9a27cc8884543b81d18991
# патч 11 mutation-011.diff sha256 99fe1aedc1c29b8f61267c67310dd8ea2455225cbe4ddbddee959c542241c780
# патч 12 mutation-012.diff sha256 1691ebfa9193b17868c260acdb60ccfe34c38734e7833469890fb208b7e959e2
# патч 13 mutation-013.diff sha256 f8761c424dab6d321c10a456429cfe1f94aaee7ba6babca5786733b7da7a20b0
# патч 14 mutation-014.diff sha256 5b8343411120d94ae890f5c0b2d539d7767e97345424c677cd69373e9cedf39b
# патч 15 mutation-015.diff sha256 4d317dbd5c59bd1147d36accf2bff39605631f0be540e0886b6644abd831ce36
номер	исход	узлы
1	убита	tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac3GreenPriorTest::test_ac3_green_prior_version_passes_with_prior_line,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac5PriorUnstableTest::test_ac5_red_base_rerun_is_flaky_line_not_finding,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac26RecordOrderTest::test_ac26_passed_record_line_order,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac15ReplacementNotGreenTest::test_ac15_replacement_red_on_base_or_base_rerun,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac8RestoredPathsTest::test_ac8_deleted_file_restored_and_judged,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac11PrepareTest::test_ac11_third_run_failure_refuses_prepare,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac4PriorRedTest::test_ac4_prior_red_thrice_refuses_outcome,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac7RunScopeTest::test_ac7_test_support_change_runs_full_suite,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac8RestoredPathsTest::test_ac8_type_changed_file_in_set,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac13OwnerMarkerTest::test_ac13_third_checkout_in_scratch_with_marker_and_removed,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac18ReplacementLimitsTest::test_ac18_replacement_does_not_cover_skipped,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac17ReplacementCoversTest::test_ac17_gone_replaced_test_passes_covered_by_replacement,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac17ReplacementCoversTest::test_ac17_present_replaced_test_prior_red_covered,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac18ReplacementLimitsTest::test_ac18_undeclared_prior_red_covered_only_by_operator,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac34NeedlessWithGoneTest::test_ac34_needless_added_despite_gone,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac7RunScopeTest::test_ac7_tests_change_runs_only_changed_files,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac5PriorUnstableTest::test_ac5_prior_mixed_is_unstable_finding,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac8RestoredPathsTest::test_ac8_renamed_file_old_path_restored_new_stays,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac9NoTestsFieldTest::test_ac9_changed_base_file_and_file_level_record_in_set,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac16ReplacementNeedlessTest::test_ac16_prior_green_once_is_needless_finding,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac20StrictReplacementTest::test_ac20_replacement_file_strict_without_path_mandate,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac11PrepareTest::test_ac11_third_checkout_failure_refuses_prepare,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac32AddedFilesRemovedTest::test_ac32_added_conftest_under_scope_without_tests_removed,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac25RefusalActionTest::test_ac25_broken_only_vs_new_kind_action_and_hint,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac32AddedFilesRemovedTest::test_ac32_added_conftest_under_test_support_removed,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac27MergeProofTest::test_ac27_proof_with_new_kinds_skips_run,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac32AddedFilesRemovedTest::test_ac32_added_conftest_under_tests_masks_removed,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac33SkippedMissingRedTest::test_ac33_prior_skipped_or_missing_is_red,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac27MergeProofTest::test_ac27_changed_replacements_rerun_gate,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac27MergeProofTest::test_ac27_same_replacements_reapproved_no_run
2	убита	tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac8RestoredPathsTest::test_ac8_deleted_file_restored_and_judged,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac3GreenPriorTest::test_ac3_green_prior_version_passes_with_prior_line,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac26RecordOrderTest::test_ac26_passed_record_line_order
3	убита	tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac3GreenPriorTest::test_ac3_green_prior_version_passes_with_prior_line,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac8RestoredPathsTest::test_ac8_deleted_file_restored_and_judged
4	убита	tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac3GreenPriorTest::test_ac3_green_prior_version_passes_with_prior_line,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac7RunScopeTest::test_ac7_tests_change_runs_only_changed_files,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac9NoTestsFieldTest::test_ac9_changed_base_file_and_file_level_record_in_set
5	убита	tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac9NoTestsFieldTest::test_ac9_code_only_and_new_file_no_third_checkout,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac10EmptyPriorSetTest::test_ac10_empty_set_no_third_checkout
6	убита	tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac4PriorRedTest::test_ac4_prior_red_thrice_refuses_outcome,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac18ReplacementLimitsTest::test_ac18_undeclared_prior_red_covered_only_by_operator,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac17ReplacementCoversTest::test_ac17_present_replaced_test_prior_red_covered,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac25RefusalActionTest::test_ac25_broken_only_vs_new_kind_action_and_hint,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac32AddedFilesRemovedTest::test_ac32_added_conftest_under_scope_without_tests_removed,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac32AddedFilesRemovedTest::test_ac32_added_conftest_under_test_support_removed,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac32AddedFilesRemovedTest::test_ac32_added_conftest_under_tests_masks_removed,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac33SkippedMissingRedTest::test_ac33_prior_skipped_or_missing_is_red
7	убита	tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac4PriorRedTest::test_ac4_prior_red_thrice_refuses_outcome,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac5PriorUnstableTest::test_ac5_prior_mixed_is_unstable_finding
8	убита	tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac4PriorRedTest::test_ac4_prior_red_thrice_refuses_outcome
9	убита	tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac5PriorUnstableTest::test_ac5_prior_mixed_is_unstable_finding
10	убита	tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac26RecordOrderTest::test_ac26_passed_record_line_order,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac5PriorUnstableTest::test_ac5_red_base_rerun_is_flaky_line_not_finding,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac15ReplacementNotGreenTest::test_ac15_replacement_red_on_base_or_base_rerun,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac5PriorUnstableTest::test_ac5_prior_mixed_is_unstable_finding,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac16ReplacementNeedlessTest::test_ac16_prior_green_once_is_needless_finding
11	убита	tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac26RecordOrderTest::test_ac26_passed_record_line_order,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac5PriorUnstableTest::test_ac5_red_base_rerun_is_flaky_line_not_finding,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac15ReplacementNotGreenTest::test_ac15_replacement_red_on_base_or_base_rerun
12	убита	tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac5PriorUnstableTest::test_ac5_red_base_rerun_is_flaky_line_not_finding,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac26RecordOrderTest::test_ac26_passed_record_line_order
13	убита	tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac26RecordOrderTest::test_ac26_passed_record_line_order,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac5PriorUnstableTest::test_ac5_red_base_rerun_is_flaky_line_not_finding
14	убита	tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac17ReplacementCoversTest::test_ac17_gone_replaced_test_passes_covered_by_replacement,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac6OneFindingPerIdTest::test_ac6_old_kind_finding_wins_single_line
15	убита	tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac7RunScopeTest::test_ac7_test_support_change_runs_full_suite
```

```
# mutation-run №2 задачи 01M5RS4CRRFNC5SG4PBQFQWXDT
# источник патчей: каталог на диске
# ревизия прогона: base a8e578743f79554d0590c07f17a9ade06f539639
# тесты: tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py
# рабочих процессов: auto
# патч 16 mutation-016.diff sha256 556e272f70fde04e057e7d593eaae1843706e0873489a2471d54bae93b5d540c
# патч 17 mutation-017.diff sha256 5476459d8f7797d263a8cc44b128abab6deb941e7517c05537c149d0515f8d62
# патч 18 mutation-018.diff sha256 f6d0d60691905e1b1f6ed3e8533882db7094cebf89a729a3d7783d36bfc8709c
# патч 19 mutation-019.diff sha256 641d0cad00b88fe3e536b0f2b515647c7ec2a1bf2f539e309a5963320c257887
# патч 20 mutation-020.diff sha256 a6b73149fb6276df30d1060befd898c36454e4a91c34610044103876a13304b2
# патч 21 mutation-021.diff sha256 03bf43e9677b425a20137466db57871c378b402052f5e12ca01e1aa3010a6977
# патч 22 mutation-022.diff sha256 28b8d63994b2a42c99532e530be7a7db42b1f12683d870f27c18461e6c96d830
# патч 23 mutation-023.diff sha256 cf727c3e8b5bfcc8eef4bbd1904279b8248e9eb96658b025a07ec895d4b119a2
# патч 24 mutation-024.diff sha256 4372614e2d9ddb5b18a95a8e4e34a51ddbbd104a73c455d43c499fbe1e4568de
# патч 25 mutation-025.diff sha256 596e5d7639838b3b53d9a21750bc344d3bfb0412db96bfdeb0cfceb39b018647
# патч 26 mutation-026.diff sha256 727c9c98bdfb71264aae3d3e40fc6526d73ef0a383c8029a7327ae9a1ea05c84
# патч 27 mutation-027.diff sha256 a91707fb10cfad71e205a050b7996031a34b0c29666d7a7a5ea6e6dc5418d738
# патч 28 mutation-028.diff sha256 6d8008b893e0c33b7bccdfbf4a17ee5280d0500e6f500d11a9893a471d3f7dc7
# патч 29 mutation-029.diff sha256 0a3d2b0282d6ee23b0579dee1816c32a4500eae324b37652bad5d4772cf38974
# патч 30 mutation-030.diff sha256 05805294bcf3768847ca1a8a52b6360432c0103d012936612a830f390237bc38
номер	исход	узлы
16	убита	tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac7RunScopeTest::test_ac7_test_support_change_runs_full_suite
17	убита	tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac3GreenPriorTest::test_ac3_green_prior_version_passes_with_prior_line,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac7RunScopeTest::test_ac7_tests_change_runs_only_changed_files,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac9NoTestsFieldTest::test_ac9_changed_base_file_and_file_level_record_in_set
18	убита	tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac8RestoredPathsTest::test_ac8_deleted_file_restored_and_judged
19	убита	tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac8RestoredPathsTest::test_ac8_deleted_file_restored_and_judged,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac8RestoredPathsTest::test_ac8_renamed_file_old_path_restored_new_stays
20	убита	tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac19StrictModeTest::test_ac19_strict_deleted_and_renamed,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac8RestoredPathsTest::test_ac8_renamed_file_old_path_restored_new_stays
21	убита	tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac8RestoredPathsTest::test_ac8_renamed_file_old_path_restored_new_stays
22	убита	tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac8RestoredPathsTest::test_ac8_type_changed_file_in_set
23	убита	tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac3GreenPriorTest::test_ac3_green_prior_version_passes_with_prior_line,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac9NoTestsFieldTest::test_ac9_code_only_and_new_file_no_third_checkout,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac8RestoredPathsTest::test_ac8_deleted_file_restored_and_judged,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac10EmptyPriorSetTest::test_ac10_empty_set_no_third_checkout,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac7RunScopeTest::test_ac7_tests_change_runs_only_changed_files,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac9NoTestsFieldTest::test_ac9_changed_base_file_and_file_level_record_in_set
24	убита	tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac9NoTestsFieldTest::test_ac9_code_only_and_new_file_no_third_checkout,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac31NoTestsFieldExceptionsTest::test_ac31_new_and_unreported_files_under_scope
25	убита	tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac9NoTestsFieldTest::test_ac9_changed_base_file_and_file_level_record_in_set
26	убита	tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac11PrepareTest::test_ac11_third_checkout_failure_refuses_prepare
27	не убита	
28	убита	tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac11PrepareTest::test_ac11_third_run_failure_refuses_prepare
29	убита	tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac11PrepareTest::test_ac11_third_run_failure_refuses_prepare
30	убита	tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac12DiffFailureTest::test_ac12_diff_failures_refuse_prepare
```

```
# mutation-run №3 задачи 01M5RS4CRRFNC5SG4PBQFQWXDT
# источник патчей: каталог на диске
# ревизия прогона: base 2bf85f6219a9c2bc1477ede626760c93e48d08a6
# тесты: tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py
# рабочих процессов: auto
# патч 31 mutation-031.diff sha256 76ca17ed6b09a5f890ce51b2de268d4297b44c93988150ef01f727b5221fcb54
# патч 32 mutation-032.diff sha256 16564527fad48ce1ed4123024d9c85b42554780c28e1197b40f66e9f4a07cc18
# патч 33 mutation-033.diff sha256 93789684ff28b366557d997f652adada58f1f75af080fdba8bbe6b922cf8cb43
# патч 34 mutation-034.diff sha256 9373c32802eb329cbbc80aedfa2867360e2ac13f208b9585d8c28f90e88fb955
# патч 35 mutation-035.diff sha256 ce32607b261b22504201475f2004567a8916fe2cdd0da7bde23f0f791af7b2b1
# патч 36 mutation-036.diff sha256 d9690d4736df6d6271444c6d3be681180b386c2df5c507e1e971be9917f15cde
# патч 37 mutation-037.diff sha256 e5b643ac1e5d0a4d8f9767da17847ff5433f9bc153b3407d585e98e5afd5b9ae
номер	исход	узлы
31	убита	tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac12DiffFailureTest::test_ac12_diff_failures_refuse_prepare
32	убита	tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac4PriorRedTest::test_ac4_prior_red_thrice_refuses_outcome,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac5PriorUnstableTest::test_ac5_red_base_rerun_is_flaky_line_not_finding,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac3GreenPriorTest::test_ac3_green_prior_version_passes_with_prior_line,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac26RecordOrderTest::test_ac26_passed_record_line_order,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac8RestoredPathsTest::test_ac8_type_changed_file_in_set,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac13OwnerMarkerTest::test_ac13_third_checkout_in_scratch_with_marker_and_removed,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac8RestoredPathsTest::test_ac8_deleted_file_restored_and_judged,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac11PrepareTest::test_ac11_third_run_failure_refuses_prepare,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac7RunScopeTest::test_ac7_test_support_change_runs_full_suite,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac18ReplacementLimitsTest::test_ac18_undeclared_prior_red_covered_only_by_operator,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac5PriorUnstableTest::test_ac5_prior_mixed_is_unstable_finding,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac17ReplacementCoversTest::test_ac17_present_replaced_test_prior_red_covered,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac34NeedlessWithGoneTest::test_ac34_needless_added_despite_gone,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac7RunScopeTest::test_ac7_tests_change_runs_only_changed_files,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac9NoTestsFieldTest::test_ac9_changed_base_file_and_file_level_record_in_set,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac8RestoredPathsTest::test_ac8_renamed_file_old_path_restored_new_stays,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac16ReplacementNeedlessTest::test_ac16_prior_green_once_is_needless_finding,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac25RefusalActionTest::test_ac25_broken_only_vs_new_kind_action_and_hint,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac32AddedFilesRemovedTest::test_ac32_added_conftest_under_scope_without_tests_removed,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac32AddedFilesRemovedTest::test_ac32_added_conftest_under_tests_masks_removed,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac32AddedFilesRemovedTest::test_ac32_added_conftest_under_test_support_removed,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac33SkippedMissingRedTest::test_ac33_prior_skipped_or_missing_is_red
33	убита	tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac26RecordOrderTest::test_ac26_passed_record_line_order,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac5PriorUnstableTest::test_ac5_red_base_rerun_is_flaky_line_not_finding,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac15ReplacementNotGreenTest::test_ac15_replacement_red_on_base_or_base_rerun,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac4PriorRedTest::test_ac4_prior_red_thrice_refuses_outcome,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac18ReplacementLimitsTest::test_ac18_replacement_does_not_cover_skipped,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac17ReplacementCoversTest::test_ac17_gone_replaced_test_passes_covered_by_replacement,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac18ReplacementLimitsTest::test_ac18_undeclared_prior_red_covered_only_by_operator,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac17ReplacementCoversTest::test_ac17_present_replaced_test_prior_red_covered,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac5PriorUnstableTest::test_ac5_prior_mixed_is_unstable_finding,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac6OneFindingPerIdTest::test_ac6_old_kind_finding_wins_single_line,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac16ReplacementNeedlessTest::test_ac16_prior_green_once_is_needless_finding,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac25RefusalActionTest::test_ac25_broken_only_vs_new_kind_action_and_hint,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac32AddedFilesRemovedTest::test_ac32_added_conftest_under_scope_without_tests_removed,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac32AddedFilesRemovedTest::test_ac32_added_conftest_under_test_support_removed,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac20StrictReplacementTest::test_ac20_replacement_file_strict_without_path_mandate,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac27MergeProofTest::test_ac27_changed_replacements_rerun_gate,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac32AddedFilesRemovedTest::test_ac32_added_conftest_under_tests_masks_removed,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac33SkippedMissingRedTest::test_ac33_prior_skipped_or_missing_is_red,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac27MergeProofTest::test_ac27_same_replacements_reapproved_no_run,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac27MergeProofTest::test_ac27_proof_with_new_kinds_skips_run
34	убита	tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac32AddedFilesRemovedTest::test_ac32_added_conftest_under_test_support_removed
35	убита	tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac32AddedFilesRemovedTest::test_ac32_added_conftest_under_scope_without_tests_removed,tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac32AddedFilesRemovedTest::test_ac32_added_conftest_under_tests_masks_removed
36	убита	tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac33SkippedMissingRedTest::test_ac33_prior_skipped_or_missing_is_red
37	убита	tests/test_01m5j0jyw3gzsshhk3tycytq3j_outcome_prior.py::Ac30OutOfBoundsTest::test_ac30_test_profile_no_outcome_gate
```

## Мутации после

Те же части `--patches 1-15`, `16-30`, `31-37`, рабочих процессов auto,
`--ref worktree --tests tests/test_outcome_prior_module.py --copy-table
--wait-lock 4`. Перед каждой частью — вывод `git status --porcelain --
orchestrator/` рабочей копии (пустой).

Перед частью 1-15: `git status --porcelain -- orchestrator/`

```
```

```
# mutation-run №4 задачи 01M5RS4CRRFNC5SG4PBQFQWXDT
# источник патчей: каталог на диске
# ревизия прогона: worktree ab8d6df2eb5352d64e34b05e9b2bc794a3f51772
# тесты: tests/test_outcome_prior_module.py
# рабочих процессов: auto
# патч 1 mutation-001.diff sha256 9f8b0340b675f44dd418afab8b53697d413ce635608e0f53b9ba2a05885262f1
# патч 2 mutation-002.diff sha256 c35bcf5b49ee9494bf544b48fc705c4203a70bf3b7e29ffbaaa60b0cda6c3886
# патч 3 mutation-003.diff sha256 6529b8e8be0858ca14a029aabca87e003d51abea20881f5f6b2aa4ed23e012a1
# патч 4 mutation-004.diff sha256 bf22fefdf6ec1198143f74295829ea033bf4e79dbc9524079de1a39bc44f208f
# патч 5 mutation-005.diff sha256 5f090575ae91abf8f5c446f4270bfecf4c4d7f0201aedaec23f42e31b94805b9
# патч 6 mutation-006.diff sha256 d7ffce340818753e21b6da3b638631f15d2fffac87084fe18929043ca893056e
# патч 7 mutation-007.diff sha256 8171ea9949ecd7950c9ef24c27d0c6416f8c773476801f042ae03cf9538db3a2
# патч 8 mutation-008.diff sha256 1d7a64dbf967e716ff6f5927819ebaba3e1947fe4b865eb7874c3121bda51c70
# патч 9 mutation-009.diff sha256 b3e049593c14e82b4b4e9327b18111548a9e18cdda9c67327895b3133986ee3f
# патч 10 mutation-010.diff sha256 b119a6c53964c7e47381da5b1162497a5943263eeb9a27cc8884543b81d18991
# патч 11 mutation-011.diff sha256 99fe1aedc1c29b8f61267c67310dd8ea2455225cbe4ddbddee959c542241c780
# патч 12 mutation-012.diff sha256 1691ebfa9193b17868c260acdb60ccfe34c38734e7833469890fb208b7e959e2
# патч 13 mutation-013.diff sha256 f8761c424dab6d321c10a456429cfe1f94aaee7ba6babca5786733b7da7a20b0
# патч 14 mutation-014.diff sha256 5b8343411120d94ae890f5c0b2d539d7767e97345424c677cd69373e9cedf39b
# патч 15 mutation-015.diff sha256 4d317dbd5c59bd1147d36accf2bff39605631f0be540e0886b6644abd831ce36
номер	исход	узлы
1	убита	tests/test_outcome_prior_module.py::test_ac4_prior_red_thrice_refuses_outcome,tests/test_outcome_prior_module.py::test_ac9_changed_base_file_and_file_level_record_in_set,tests/test_outcome_prior_module.py::test_ac5_prior_mixed_is_unstable_finding,tests/test_outcome_prior_module.py::test_ac7_test_support_change_runs_full_suite,tests/test_outcome_prior_module.py::test_ac11_third_checkout_failure_refuses_prepare,tests/test_outcome_prior_module.py::test_ac8_type_changed_file_in_set,tests/test_outcome_prior_module.py::test_ac5_red_base_rerun_is_flaky_line_not_finding,tests/test_outcome_prior_module.py::test_ac8_deleted_file_restored_and_judged,tests/test_outcome_prior_module.py::test_ac3_green_prior_version_passes_with_prior_line,tests/test_outcome_prior_module.py::test_ac8_renamed_file_old_path_restored_new_stays,tests/test_outcome_prior_module.py::test_ac7_tests_change_runs_only_changed_files,tests/test_outcome_prior_module.py::test_ac32_added_conftest_under_scope_without_tests_removed,tests/test_outcome_prior_module.py::test_ac33_prior_skipped_or_missing_is_red,tests/test_outcome_prior_module.py::test_ac32_added_conftest_under_tests_masks_removed,tests/test_outcome_prior_module.py::test_ac32_added_conftest_under_test_support_removed,tests/test_outcome_prior_module.py::test_ac13_third_checkout_in_scratch_with_marker_and_removed,tests/test_outcome_prior_module.py::test_ac11_third_run_failure_refuses_prepare
2	убита	tests/test_outcome_prior_module.py::test_ac3_green_prior_version_passes_with_prior_line,tests/test_outcome_prior_module.py::test_ac8_deleted_file_restored_and_judged
3	убита	tests/test_outcome_prior_module.py::test_ac3_green_prior_version_passes_with_prior_line,tests/test_outcome_prior_module.py::test_ac8_deleted_file_restored_and_judged
4	убита	tests/test_outcome_prior_module.py::test_ac9_changed_base_file_and_file_level_record_in_set,tests/test_outcome_prior_module.py::test_ac3_green_prior_version_passes_with_prior_line,tests/test_outcome_prior_module.py::test_ac7_tests_change_runs_only_changed_files
5	убита	tests/test_outcome_prior_module.py::test_ac10_empty_set_no_third_checkout,tests/test_outcome_prior_module.py::test_ac9_code_only_and_new_file_no_third_checkout
6	убита	tests/test_outcome_prior_module.py::test_ac4_prior_red_thrice_refuses_outcome,tests/test_outcome_prior_module.py::test_ac32_added_conftest_under_test_support_removed,tests/test_outcome_prior_module.py::test_ac32_added_conftest_under_scope_without_tests_removed,tests/test_outcome_prior_module.py::test_ac33_prior_skipped_or_missing_is_red,tests/test_outcome_prior_module.py::test_ac32_added_conftest_under_tests_masks_removed
7	убита	tests/test_outcome_prior_module.py::test_ac4_prior_red_thrice_refuses_outcome,tests/test_outcome_prior_module.py::test_ac5_prior_mixed_is_unstable_finding
8	убита	tests/test_outcome_prior_module.py::test_ac4_prior_red_thrice_refuses_outcome
9	убита	tests/test_outcome_prior_module.py::test_ac5_prior_mixed_is_unstable_finding
10	убита	tests/test_outcome_prior_module.py::test_ac5_red_base_rerun_is_flaky_line_not_finding,tests/test_outcome_prior_module.py::test_ac5_prior_mixed_is_unstable_finding
11	убита	tests/test_outcome_prior_module.py::test_ac5_red_base_rerun_is_flaky_line_not_finding
12	убита	tests/test_outcome_prior_module.py::test_ac5_red_base_rerun_is_flaky_line_not_finding
13	убита	tests/test_outcome_prior_module.py::test_ac5_red_base_rerun_is_flaky_line_not_finding
14	убита	tests/test_outcome_prior_module.py::test_ac6_old_kind_finding_wins_single_line
15	убита	tests/test_outcome_prior_module.py::test_ac7_test_support_change_runs_full_suite
```

Перед частью 16-30: `git status --porcelain -- orchestrator/`

```
```

```
# mutation-run №5 задачи 01M5RS4CRRFNC5SG4PBQFQWXDT
# источник патчей: каталог на диске
# ревизия прогона: worktree ab8d6df2eb5352d64e34b05e9b2bc794a3f51772
# тесты: tests/test_outcome_prior_module.py
# рабочих процессов: auto
# патч 16 mutation-016.diff sha256 556e272f70fde04e057e7d593eaae1843706e0873489a2471d54bae93b5d540c
# патч 17 mutation-017.diff sha256 5476459d8f7797d263a8cc44b128abab6deb941e7517c05537c149d0515f8d62
# патч 18 mutation-018.diff sha256 f6d0d60691905e1b1f6ed3e8533882db7094cebf89a729a3d7783d36bfc8709c
# патч 19 mutation-019.diff sha256 641d0cad00b88fe3e536b0f2b515647c7ec2a1bf2f539e309a5963320c257887
# патч 20 mutation-020.diff sha256 a6b73149fb6276df30d1060befd898c36454e4a91c34610044103876a13304b2
# патч 21 mutation-021.diff sha256 03bf43e9677b425a20137466db57871c378b402052f5e12ca01e1aa3010a6977
# патч 22 mutation-022.diff sha256 28b8d63994b2a42c99532e530be7a7db42b1f12683d870f27c18461e6c96d830
# патч 23 mutation-023.diff sha256 cf727c3e8b5bfcc8eef4bbd1904279b8248e9eb96658b025a07ec895d4b119a2
# патч 24 mutation-024.diff sha256 4372614e2d9ddb5b18a95a8e4e34a51ddbbd104a73c455d43c499fbe1e4568de
# патч 25 mutation-025.diff sha256 596e5d7639838b3b53d9a21750bc344d3bfb0412db96bfdeb0cfceb39b018647
# патч 26 mutation-026.diff sha256 727c9c98bdfb71264aae3d3e40fc6526d73ef0a383c8029a7327ae9a1ea05c84
# патч 27 mutation-027.diff sha256 a91707fb10cfad71e205a050b7996031a34b0c29666d7a7a5ea6e6dc5418d738
# патч 28 mutation-028.diff sha256 6d8008b893e0c33b7bccdfbf4a17ee5280d0500e6f500d11a9893a471d3f7dc7
# патч 29 mutation-029.diff sha256 0a3d2b0282d6ee23b0579dee1816c32a4500eae324b37652bad5d4772cf38974
# патч 30 mutation-030.diff sha256 05805294bcf3768847ca1a8a52b6360432c0103d012936612a830f390237bc38
номер	исход	узлы
16	убита	tests/test_outcome_prior_module.py::test_ac7_test_support_change_runs_full_suite
17	убита	tests/test_outcome_prior_module.py::test_ac3_green_prior_version_passes_with_prior_line,tests/test_outcome_prior_module.py::test_ac7_tests_change_runs_only_changed_files,tests/test_outcome_prior_module.py::test_ac9_changed_base_file_and_file_level_record_in_set
18	убита	tests/test_outcome_prior_module.py::test_ac8_deleted_file_restored_and_judged
19	убита	tests/test_outcome_prior_module.py::test_ac8_renamed_file_old_path_restored_new_stays,tests/test_outcome_prior_module.py::test_ac8_deleted_file_restored_and_judged
20	убита	tests/test_outcome_prior_module.py::test_ac8_renamed_file_old_path_restored_new_stays
21	убита	tests/test_outcome_prior_module.py::test_ac8_renamed_file_old_path_restored_new_stays
22	убита	tests/test_outcome_prior_module.py::test_ac8_type_changed_file_in_set
23	убита	tests/test_outcome_prior_module.py::test_ac8_deleted_file_restored_and_judged,tests/test_outcome_prior_module.py::test_ac7_tests_change_runs_only_changed_files,tests/test_outcome_prior_module.py::test_ac9_code_only_and_new_file_no_third_checkout,tests/test_outcome_prior_module.py::test_ac10_empty_set_no_third_checkout,tests/test_outcome_prior_module.py::test_ac9_changed_base_file_and_file_level_record_in_set,tests/test_outcome_prior_module.py::test_ac3_green_prior_version_passes_with_prior_line
24	убита	tests/test_outcome_prior_module.py::test_ac9_code_only_and_new_file_no_third_checkout
25	убита	tests/test_outcome_prior_module.py::test_ac9_changed_base_file_and_file_level_record_in_set
26	убита	tests/test_outcome_prior_module.py::test_ac11_third_checkout_failure_refuses_prepare
27	не убита	
28	убита	tests/test_outcome_prior_module.py::test_ac11_third_run_failure_refuses_prepare
29	убита	tests/test_outcome_prior_module.py::test_ac11_third_run_failure_refuses_prepare
30	убита	tests/test_outcome_prior_module.py::test_ac12_diff_failures_refuse_prepare
```

Перед частью 31-37: `git status --porcelain -- orchestrator/`

```
```

```
# mutation-run №6 задачи 01M5RS4CRRFNC5SG4PBQFQWXDT
# источник патчей: каталог на диске
# ревизия прогона: worktree ab8d6df2eb5352d64e34b05e9b2bc794a3f51772
# тесты: tests/test_outcome_prior_module.py
# рабочих процессов: auto
# патч 31 mutation-031.diff sha256 76ca17ed6b09a5f890ce51b2de268d4297b44c93988150ef01f727b5221fcb54
# патч 32 mutation-032.diff sha256 16564527fad48ce1ed4123024d9c85b42554780c28e1197b40f66e9f4a07cc18
# патч 33 mutation-033.diff sha256 93789684ff28b366557d997f652adada58f1f75af080fdba8bbe6b922cf8cb43
# патч 34 mutation-034.diff sha256 9373c32802eb329cbbc80aedfa2867360e2ac13f208b9585d8c28f90e88fb955
# патч 35 mutation-035.diff sha256 ce32607b261b22504201475f2004567a8916fe2cdd0da7bde23f0f791af7b2b1
# патч 36 mutation-036.diff sha256 d9690d4736df6d6271444c6d3be681180b386c2df5c507e1e971be9917f15cde
# патч 37 mutation-037.diff sha256 e5b643ac1e5d0a4d8f9767da17847ff5433f9bc153b3407d585e98e5afd5b9ae
номер	исход	узлы
31	убита	tests/test_outcome_prior_module.py::test_ac12_diff_failures_refuse_prepare
32	убита	tests/test_outcome_prior_module.py::test_ac5_red_base_rerun_is_flaky_line_not_finding,tests/test_outcome_prior_module.py::test_ac8_renamed_file_old_path_restored_new_stays,tests/test_outcome_prior_module.py::test_ac9_changed_base_file_and_file_level_record_in_set,tests/test_outcome_prior_module.py::test_ac5_prior_mixed_is_unstable_finding,tests/test_outcome_prior_module.py::test_ac7_test_support_change_runs_full_suite,tests/test_outcome_prior_module.py::test_ac7_tests_change_runs_only_changed_files,tests/test_outcome_prior_module.py::test_ac4_prior_red_thrice_refuses_outcome,tests/test_outcome_prior_module.py::test_ac8_deleted_file_restored_and_judged,tests/test_outcome_prior_module.py::test_ac8_type_changed_file_in_set,tests/test_outcome_prior_module.py::test_ac3_green_prior_version_passes_with_prior_line,tests/test_outcome_prior_module.py::test_ac32_added_conftest_under_scope_without_tests_removed,tests/test_outcome_prior_module.py::test_ac32_added_conftest_under_tests_masks_removed,tests/test_outcome_prior_module.py::test_ac32_added_conftest_under_test_support_removed,tests/test_outcome_prior_module.py::test_ac33_prior_skipped_or_missing_is_red,tests/test_outcome_prior_module.py::test_ac13_third_checkout_in_scratch_with_marker_and_removed,tests/test_outcome_prior_module.py::test_ac11_third_run_failure_refuses_prepare
33	убита	tests/test_outcome_prior_module.py::test_ac6_old_kind_finding_wins_single_line,tests/test_outcome_prior_module.py::test_ac4_prior_red_thrice_refuses_outcome,tests/test_outcome_prior_module.py::test_ac5_red_base_rerun_is_flaky_line_not_finding,tests/test_outcome_prior_module.py::test_ac5_prior_mixed_is_unstable_finding,tests/test_outcome_prior_module.py::test_ac32_added_conftest_under_scope_without_tests_removed,tests/test_outcome_prior_module.py::test_ac32_added_conftest_under_tests_masks_removed,tests/test_outcome_prior_module.py::test_ac32_added_conftest_under_test_support_removed,tests/test_outcome_prior_module.py::test_ac33_prior_skipped_or_missing_is_red
34	убита	tests/test_outcome_prior_module.py::test_ac32_added_conftest_under_test_support_removed
35	убита	tests/test_outcome_prior_module.py::test_ac32_added_conftest_under_scope_without_tests_removed,tests/test_outcome_prior_module.py::test_ac32_added_conftest_under_tests_masks_removed
36	убита	tests/test_outcome_prior_module.py::test_ac33_prior_skipped_or_missing_is_red
37	убита	tests/test_outcome_prior_module.py::test_ac30_test_profile_no_outcome_gate
```

## Находки

- mutation-027 (заявка бывшего `test_ac11_third_run_failure_refuses_prepare`,
  альтернатива «таймаут прогона прежних версий считается красным
  исходом») — не убита ни «до», ни «после». Причина: при таймауте патч
  делает все тесты прогона красными, красные идут в перепрогон на той же
  стороне прежних версий (`_rerun`), а стенд (`timeout_when` по стороне
  прежних версий) роняет таймаутом и перепрогон — `_Prepare` из `_rerun`
  даёт тот же отказ подготовки, что и без мутации. Альтернатива на этом
  стенде не наблюдаема: тест её не различает при любом зерне. Тест не
  удалён, заявка и ожидания не менялись; две другие альтернативы той же
  заявки (пропуск; уборка не в `finally`) тест убивает «до» и «после».
- mutation-033 (вторая альтернатива заявки бывшего
  `test_ac13_third_checkout_in_scratch_with_marker_and_removed`) убита и
  «до», и «после», но не самим заявившим тестом, а другими тестами задачи
  (бывшие `test_ac4_…`, `test_ac5_…`, `test_ac6_…`, `test_ac32_…`,
  `test_ac33_…`): без записи в `trees` третья выписка не судится вовсе.
  Свод на неё не влияет; записано для независимой проверки.

## Удалённые дубли

Нет: перенесены все 22 теста.

## Числа и время

- Тестов: «до» — 22 теста задачи в долгоживущем файле (1736 строк, 44
  теста); «после» — 22 тестовые функции в
  `tests/test_outcome_prior_module.py` (667 строк), в
  сокращённом долгоживущем файле — 22 теста (810 строк); песочницы
  `tests/prior_outcome_sandbox.py` — 365 строк.
- Подслучаев: 8 «до» (по два у четырёх бывших `subTest`) и 8 «после»
  (строки `case`).
- Контрольные прогоны `mutation-run` (весь целевой файл, рабочих
  процессов auto): «до» (долгоживущий файл, 44 теста) — 49,27 с (№1),
  42,16 с (№2), 32,91 с (№3); «после» (новый модуль, 22 теста) —
  14,29 с (№4), 14,55 с (№5), 14,83 с (№6). Все шесть контрольных
  прогонов зелёные; ни в одном логе патча нет `Timeout`.
- Исходы: «до» — 36 убиты, 1 не убита (мутация 27); «после» — те же 36
  убиты, та же 27 не убита; расхождений «до/после» нет, повторов не
  было.

## Влияние на систему

- Код пульта (`orchestrator/`) не меняется; мутации живут только во
  временной копии `mutation-run`; дерево `orchestrator/` ревизий шапок
  «до» (a8e57874) и «после» (53dfb8c0 и рабочая копия) совпадает.
- Гейт неослабления тестов увидит исчезновение 22 методов по пути
  долгоживущего файла и, возможно, убыль храповика — покрыто мандатом
  ANSWER-1 на этот путь; новые пути в мандат не вносятся. Утверждения не
  удалены без переноса, сравнения не ослаблены, `skip`/`xfail` и пределов
  нет.
- `tests/outcome_gate_sandbox.py`, `tests/merge_outcome_sandbox.py`,
  `tests/components_outcome_sandbox.py`, `tests/test_outcome_gate_module.py`,
  `tests/fixtures.py`, `tests/sandbox.py`, `tests/test_invariants.py` не
  менялись.
- Временные файлы шага (генераторы патчей, свода и PLAN, сверка AST) жили в
  каталоге документов под именами не `test_*`/`mutation-*`/`.md` и удалены
  до конца шага; в рабочей копии временных файлов не было.
- Откат — revert одного merge-коммита задачи.

## Риски

- Строки сообщений многострочных `assert` выровнены генератором свода не
  идеально (продолжение строки внутри скобок) — на AST и поведение не
  влияет.

## Предложения системе

- `mutation-run` не отличает в логе кадр утверждения песочницы от
  итоговой строки исключения: строку падения в методе песочницы
  (`tests/outcome_gate_sandbox.py:824: in refusal`) приходится выбирать по
  трассе руками — разбор лога в строку «файл:строка утверждения» сэкономил
  бы каждой волне ручную работу.
- Смещения `col_offset` AST в байтах UTF-8: генератор свода по смещениям
  на кириллических тестах ломается без перевода в байты — стоит карточки
  знаний для волн сведения.
- `plank-run` выкладывает планку с ревизией ссылки документов, поэтому
  разработчик в шаге не может прогнать проверки PLAN планки на своём
  новом PLAN (видит PLAN прошлого шага): сверка 23 тестов `test_mutation_*`
  шла через временный репозиторий в `$TMPDIR` — не хватает флага
  `plank-run --docs-from-disk` (`orchestrator/plank_run.py`).
