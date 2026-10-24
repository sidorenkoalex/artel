---
task: 01M5PT190RWC6984CDQVZ242GN
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Сведение тестов, волна 2б-3 — песочница отчётов исходов в `tests/report_outcome_sandbox.py`, тесты в `tests/test_report_outcome_module.py`

## Подход

Перенос механический и воспроизводимый. Два сценария лежат первым уровнем
каталога документов задачи: `convert_report_outcome.py` (тестовые методы →
функции pytest) и `assemble_report_outcome.py` (шапка `module_head.txt` +
`PytestSpy`/`pytest_output`/`FLAGS` дословно + тело конвертера). Запуск из
корня рабочей копии; исходник сборка читает `git show HEAD:<исходный файл>`.

- Песочница: операторы строк 54–606 исходного файла скопированы побайтно в
  `tests/report_outcome_sandbox.py` под новый однострочный докстринг.
  Сверка `ast.dump` для `report_outcome_sandbox`: 50 операторов исходника
  (строки 54–606) против 50 операторов модуля после докстринга, попарно по
  порядку — все 50 равны (`python3`: `all(ast.dump(a) == ast.dump(b) ...)`
  → `True`).
- Тесты: каждый `test_*` метод → функция модуля `test_*(box)`, фикстура
  `box` — только `yield from _sandbox(ReportSandbox)`. `self` → `box` по
  токенам. `self.assertEqual/NotEqual/In/NotIn/True/False/IsNotNone(a, b,
  msg)` → `assert a <оп> b, msg` с исходными выражениями операндов (литерал
  остаётся литералом, константа — константой). Текст `box.note(...)` —
  вторым операндом `assert`.
- `subTest` (9 мест) — все с общим состоянием песочницы (`box`, `rng`,
  проекты в `targets.yaml`): остаются циклом в одной функции, `with
  self.subTest(k=v)` снят, ярлык дописан в сообщение `assert`:
  `<msg> + "; " + f"k={v!r}"`.
- `with self.assertRaises(SystemExit) as raised` → `pytest.raises(SystemExit)`,
  `raised.exception` → `raised.value` (текст проверяется утверждением по
  `raised.value.code`, `match` не добавлен). `assertRaises(OSError,
  msg=...)` (бывший :1481) → голый `pytest.raises(OSError)`.
- Помощники — функции модуля, первый параметр `box`, тело дословно с
  `self.` → `box.`; тест зовёт их голым именем: `assert_unknown`, `key_case`,
  `main_head`. Переименования с префиксом бывшего класса:
  `VitestReporterTest.full_vitest` → `vitest_reporter_full_vitest`,
  `InstallAndDepsTest.full_vitest` → `install_and_deps_full_vitest`,
  `ArtelUnchangedTest.channels` → `artel_unchanged_channels` (локальная
  `clone, channels = artel_unchanged_channels(box)` сохранена). `commit`
  — метод `ReportSandbox`, остаётся в песочнице. `ArtelUnchangedTest.FLAGS`
  → константа модуля `FLAGS` (выражение дословно).
- Исходный файл сведён к переходному модулю: докстринг + `from
  tests.report_outcome_sandbox import ReportSandbox, junit, vitest_report,
  vitest_test`. `tests/test_component_report_gates.py` — сменён только
  источник импорта.
- Дублей не удаляю: у каждого из 26 тестов своя мутация.

## Шаги

1. Патчи `mutation-001.diff` … `mutation-026.diff` (по одному на заявку,
   каждый проверен одиночным прогоном теста в копии `$TMPDIR`: падает
   утверждение тела теста).
2. Таблица «до»: `mutation-run --ref base` частями 1-13 и 14-26.
3. Вынос песочницы, свод, переходной модуль, импорт, регенерация карты.
4. Таблица «после»: `mutation-run --ref worktree --tests
   tests/test_report_outcome_module.py` теми же частями; сверка sha.
5. Итог CI кодовой ветки — в PLAN.

## Мутации (сопоставление заявкам)

Строка «до» — упавшее утверждение исходного файла базы при одиночном
прогоне теста с патчем.

- mutation-001 — JunitReportOutcomeTest::test_ac1_outcome_follows_report_not_runner_output — `_report_run` берёт итог из кода возврата и строки « failed» вывода раннера, а не из отчёта; утверждение «до»: tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py:652
- mutation-002 — JunitReportOutcomeTest::test_ac2_empty_or_unreadable_report_is_unknown — `outcome.verdict`: неразобранный отчёт судится по коду возврата, пустой — зелёный; утверждение «до» (помощник исхода `assert_unknown`, вызов из теста :686): tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py:475
- mutation-003 — JunitReportOutcomeTest::test_ac2_per_test_record_id_from_repo_root_outcome_kind_reason_time — `parse_junit`: `<error>` схлопнут в `failed`; утверждение «до»: tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py:726
- mutation-004 — JunitReportOutcomeTest::test_ac3_report_path_outside_tree_workdir_and_clean_env — `{path}` отчёта кладётся в `workdir` рабочей копии; утверждение «до»: tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py:770
- mutation-005 — JunitReportOutcomeTest::test_ac4_explicit_report_args_win_over_default — `report_args_of` всегда подставляет умолчание `--junitxml {path}` перед явными; утверждение «до»: tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py:797
- mutation-006 — JunitReportOutcomeTest::test_ac4_ac6_sled_record_default_report_args_outcome_from_report — `project_profile.reported` признаёт итог из отчёта только у компонентов `components:`; утверждение «до»: tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py:837
- mutation-007 — JunitReportOutcomeTest::test_ac5_unknown_outcome_form_and_log — `full_suite` отдаёт «неизвестно» веткой «прогон не начат» без лога; утверждение «до»: tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py:858
- mutation-008 — JunitReportOutcomeTest::test_ac6_pult_pytest_and_no_report_records_by_code_and_text — `reported` смотрит только на поле `report`, запись `pult-pytest` уходит на отчёт; утверждение «до»: tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py:894
- mutation-009 — JunitReportOutcomeTest::test_ac11_unknown_is_never_green_at_any_place — точечные места (`run`, `collect`, `run_repeat`, `run_plank`) судят компонент с отчётом по коду 0; утверждение «до»: tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py:932
- mutation-010 — ResultKeyTest::test_ac18_component_key_follows_tools_lock_command_name_and_artel_key_is_main — из данных ключа `_report_suite_result_key` убраны `component` и `report_args`; утверждение «до»: tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py:1015
- mutation-011 — VitestReporterTest::test_ac6_vitest_component_without_runner_outcome_from_report — `reported` смотрит на `runner == pytest-own`, компонент без `runner` судится по коду; утверждение «до»: tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py:1067
- mutation-012 — VitestReporterTest::test_ac7_failure_kinds_assertion_type_timeout_hook — `_vitest_case`: любое падение без хука и таймаута — `failed`; утверждение «до»: tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py:1106
- mutation-013 — VitestReporterTest::test_ac8_modes_fails_todo_skip_only_and_retries — повторы внутри прогона не учитываются в `verdict`/`summary_line`/`summary_block`; утверждение «до»: tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py:1161
- mutation-014 — VitestReporterTest::test_ac9_run_conditions_argv_env_cache_and_flags — `_vitest_head` не добавляет `--expect.requireAssertions`; утверждение «до»: tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py:1216
- mutation-015 — VitestReporterTest::test_ac9_timeout_kills_group_not_green — по таймауту убивается только главный процесс (`proc.kill()` вместо `_kill_group`); утверждение «до»: tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py:1261
- mutation-016 — VitestReporterTest::test_ac9_version_refusals_require_assertions_and_unconfirmed_cache — `_vitest_head` не сверяет версию с таблицей, флаги по умолчанию; утверждение «до»: tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py:1285
- mutation-017 — VitestReporterTest::test_ac10_preparation_refusals_command_and_report_args — сверка `command` с базовым argv сравнивает только начало; утверждение «до»: tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py:1326
- mutation-018 — VitestReporterTest::test_ac10_subset_by_select_and_refusal_without_select — без `select` `_subset_args` молча отдаёт полный прогон вместо отказа; утверждение «до»: tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py:1370
- mutation-019 — InstallAndDepsTest::test_ac15_install_once_per_lock_content_from_task_branch — каталог установки не привязан к сумме файла блокировки; утверждение «до»: tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py:1413
- mutation-020 — InstallAndDepsTest::test_ac15_install_without_lock_and_failed_install_refuse — без файла блокировки `install` молча пропускается, прогон идёт; утверждение «до»: tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py:1436
- mutation-021 — InstallAndDepsTest::test_ac16_node_modules_read_only_shared_and_substitution_refused — `_link_deps` доверяет `node_modules` дерева; утверждение «до»: tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py:1495
- mutation-022 — HungComponentWatchdogTest::test_ac19_watchdog_knows_component_commands_only — сторож узнаёт только pytest/unittest; утверждение «до»: tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py:1570
- mutation-023 — ArtelUnchangedTest::test_ac4_ac6_pult_pytest_argv_and_outcome_as_main — `reported` признаёт итог из отчёта у любой записи с `report` без различителя; утверждение «до»: tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py:1723
- mutation-024 — ArtelUnchangedTest::test_ac20_constants_and_texts_as_main — текст `FULL_SUITE_NOT_STARTED` заменён; утверждение «до»: tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py:1763
- mutation-025 — ArtelUnchangedTest::test_ac12_suite_run_no_report_non_pytest_refusal_as_main — отказ «не запуск pytest» только при наличии `report`; утверждение «до»: tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py:1821
- mutation-026 — ArtelUnchangedTest::test_ac20_parsing_digest_journal_and_suite_run_lines_as_main — выжимка `full_suite` без итоговой строки pytest; утверждение «до»: tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py:1868

Соответствие «до → после» (ANSWER-1, решение 2): тест `<Класс>::<метод>` перенесён в функцию `test_report_outcome_module.py::<метод>` с тем же именем. Строка «после» — убивший узел нового файла и упавшее утверждение по логу патча прогонов №6/№7 (`.artel/logs/suite-run/01M5PT190RWC6984CDQVZ242GN/…-mutation-run-{6,7}-p<nnn>.log`):

- mutation-001 «после» — tests/test_report_outcome_module.py::test_ac1_outcome_follows_report_not_runner_output — утверждение: tests/test_report_outcome_module.py:253
- mutation-002 «после» — tests/test_report_outcome_module.py::test_ac2_empty_or_unreadable_report_is_unknown — утверждение (функция исхода `assert_unknown`, вызов из теста :290): tests/test_report_outcome_module.py:142
- mutation-003 «после» — tests/test_report_outcome_module.py::test_ac2_per_test_record_id_from_repo_root_outcome_kind_reason_time — утверждение: tests/test_report_outcome_module.py:331
- mutation-004 «после» — tests/test_report_outcome_module.py::test_ac3_report_path_outside_tree_workdir_and_clean_env — утверждение: tests/test_report_outcome_module.py:376
- mutation-005 «после» — tests/test_report_outcome_module.py::test_ac4_explicit_report_args_win_over_default — утверждение: tests/test_report_outcome_module.py:404
- mutation-006 «после» — tests/test_report_outcome_module.py::test_ac4_ac6_sled_record_default_report_args_outcome_from_report — утверждение: tests/test_report_outcome_module.py:445
- mutation-007 «после» — tests/test_report_outcome_module.py::test_ac5_unknown_outcome_form_and_log — утверждение: tests/test_report_outcome_module.py:469
- mutation-008 «после» — tests/test_report_outcome_module.py::test_ac6_pult_pytest_and_no_report_records_by_code_and_text — утверждение: tests/test_report_outcome_module.py:505
- mutation-009 «после» — tests/test_report_outcome_module.py::test_ac11_unknown_is_never_green_at_any_place — утверждение: tests/test_report_outcome_module.py:545
- mutation-010 «после» — tests/test_report_outcome_module.py::test_ac18_component_key_follows_tools_lock_command_name_and_artel_key_is_main — утверждение: tests/test_report_outcome_module.py:604
- mutation-011 «после» — tests/test_report_outcome_module.py::test_ac6_vitest_component_without_runner_outcome_from_report — утверждение: tests/test_report_outcome_module.py:644
- mutation-012 «после» — tests/test_report_outcome_module.py::test_ac7_failure_kinds_assertion_type_timeout_hook — утверждение: tests/test_report_outcome_module.py:684
- mutation-013 «после» — tests/test_report_outcome_module.py::test_ac8_modes_fails_todo_skip_only_and_retries — утверждение: tests/test_report_outcome_module.py:740
- mutation-014 «после» — tests/test_report_outcome_module.py::test_ac9_run_conditions_argv_env_cache_and_flags — утверждение: tests/test_report_outcome_module.py:796
- mutation-015 «после» — tests/test_report_outcome_module.py::test_ac9_timeout_kills_group_not_green — утверждение: tests/test_report_outcome_module.py:842
- mutation-016 «после» — tests/test_report_outcome_module.py::test_ac9_version_refusals_require_assertions_and_unconfirmed_cache — утверждение: tests/test_report_outcome_module.py:867
- mutation-017 «после» — tests/test_report_outcome_module.py::test_ac10_preparation_refusals_command_and_report_args — утверждение: tests/test_report_outcome_module.py:908
- mutation-018 «после» — tests/test_report_outcome_module.py::test_ac10_subset_by_select_and_refusal_without_select — утверждение: tests/test_report_outcome_module.py:955
- mutation-019 «после» — tests/test_report_outcome_module.py::test_ac15_install_once_per_lock_content_from_task_branch — утверждение: tests/test_report_outcome_module.py:990
- mutation-020 «после» — tests/test_report_outcome_module.py::test_ac15_install_without_lock_and_failed_install_refuse — утверждение: tests/test_report_outcome_module.py:1013
- mutation-021 «после» — tests/test_report_outcome_module.py::test_ac16_node_modules_read_only_shared_and_substitution_refused — утверждение: tests/test_report_outcome_module.py:1073
- mutation-022 «после» — tests/test_report_outcome_module.py::test_ac19_watchdog_knows_component_commands_only — утверждение: tests/test_report_outcome_module.py:1144
- mutation-023 «после» — tests/test_report_outcome_module.py::test_ac4_ac6_pult_pytest_argv_and_outcome_as_main — утверждение: tests/test_report_outcome_module.py:1177
- mutation-024 «после» — tests/test_report_outcome_module.py::test_ac20_constants_and_texts_as_main — утверждение: tests/test_report_outcome_module.py:1221
- mutation-025 «после» — tests/test_report_outcome_module.py::test_ac12_suite_run_no_report_non_pytest_refusal_as_main — утверждение: tests/test_report_outcome_module.py:1276
- mutation-026 «после» — tests/test_report_outcome_module.py::test_ac20_parsing_digest_journal_and_suite_run_lines_as_main — утверждение: tests/test_report_outcome_module.py:1323

Узлов, убитых только ошибкой сбора, импорта, setup или утверждением подготовки (`profile`, `records_of`, `by_id`, `table`, `accepted_major`, `cache_flag`, `key_case`), в таблицах «до» и «после» нет; находок (мутаций, не убитых «до») нет; исходов предела нет.

Сверка шапок: ревизия «до» — base 579a38199ce682917b9d5e40f15ac95cde4aaddc (прогоны №4, №5), «после» — worktree db7fa348078a0f000453823d20c4ae97daf39378 (прогоны №6, №7); `git diff --quiet 579a38199ce682917b9d5e40f15ac95cde4aaddc db7fa348078a0f000453823d20c4ae97daf39378 -- orchestrator/` — код 0. sha256 каждого из 26 патчей в шапках «до» и «после» совпадает (сверка строк `# патч …` таблиц №4/№6 и №5/№7).

## Мутации до

Прогоны №1–№3 (`--ref base --patches 1-13`, без `--workers`) в доказательство не входят: контроль красный на тесте ac9 с пределом 1 с под xdist (ANSWER-2, п. 4).

Число рабочих процессов — 4 (`--workers 4`, ANSWER-2, п. 1); диапазоны — `--patches 1-13` и `--patches 14-26`.

Часть 1 — `mutation-run 01M5PT190RWC6984CDQVZ242GN --ref base --tests tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py --workers 4 --copy-table --wait-lock 4 --patches 1-13` (прогон №4):

```
# mutation-run №4 задачи 01M5PT190RWC6984CDQVZ242GN
# источник патчей: каталог на диске
# ревизия прогона: base 579a38199ce682917b9d5e40f15ac95cde4aaddc
# тесты: tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py
# рабочих процессов: 4
# патч 1 mutation-001.diff sha256 1880a2452033c88789f3e15b610598e6d74ba9289da5b1f8c262cb4940113666
# патч 2 mutation-002.diff sha256 4e69fd0421fc10889c5931e18aa03cdbd1e159f9362861fb9b3c798918adf570
# патч 3 mutation-003.diff sha256 83a5413d9a208c960ffd593643e35153f1aac3d4407c7a48eb2b60f91b728ddb
# патч 4 mutation-004.diff sha256 2bda985589f1bb841305c0cf1ef0e78ae6acca36f661fcbdf190a0abfa606eba
# патч 5 mutation-005.diff sha256 5d9c759875719c44f235acc82cbdf6aef086b66e7b416a982de370d881972825
# патч 6 mutation-006.diff sha256 497149a6ac34b7fb70d4e90bd2cf41edd60a5a177cb73421e59a97b0fe490db6
# патч 7 mutation-007.diff sha256 66e6b9ea621caf705ee1f3a1446f02a3619386e7b9f40ea4e621a8ad1fb7b224
# патч 8 mutation-008.diff sha256 5b48e3ab752758ee99399b1c99bdd589b359b72544edb9937c1c2aa453dcbfd8
# патч 9 mutation-009.diff sha256 c9aec8ab3480adbd8e5b063d24a95750600f75e63f5b70b55680c2ed27d799f3
# патч 10 mutation-010.diff sha256 c00b576d7ac0187886cd507aca1cbaa90032e45ab6b46e46a2706b37e96ae0f7
# патч 11 mutation-011.diff sha256 9b50c2648425637bdcd6d7ad871cf91073497d3ff3d6ee9b31628d2a09d10319
# патч 12 mutation-012.diff sha256 109651bb2d971f8865fd6876380864c1ddd6a5f77141ad08653d10bed3e8b2e5
# патч 13 mutation-013.diff sha256 59735f8f453c8d33941474b68e61209c709fb6ab98774bb26cc887955e54599d
номер	исход	узлы
1	убита	tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::JunitReportOutcomeTest::test_ac11_unknown_is_never_green_at_any_place,tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::JunitReportOutcomeTest::test_ac2_empty_or_unreadable_report_is_unknown,tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::JunitReportOutcomeTest::test_ac1_outcome_follows_report_not_runner_output,tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::JunitReportOutcomeTest::test_ac4_ac6_sled_record_default_report_args_outcome_from_report,tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::JunitReportOutcomeTest::test_ac5_unknown_outcome_form_and_log,tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::VitestReporterTest::test_ac8_modes_fails_todo_skip_only_and_retries,tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::VitestReporterTest::test_ac6_vitest_component_without_runner_outcome_from_report,tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::VitestReporterTest::test_ac7_failure_kinds_assertion_type_timeout_hook
2	убита	tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::JunitReportOutcomeTest::test_ac2_empty_or_unreadable_report_is_unknown,tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::JunitReportOutcomeTest::test_ac11_unknown_is_never_green_at_any_place,tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::JunitReportOutcomeTest::test_ac1_outcome_follows_report_not_runner_output,tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::JunitReportOutcomeTest::test_ac4_ac6_sled_record_default_report_args_outcome_from_report,tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::JunitReportOutcomeTest::test_ac5_unknown_outcome_form_and_log,tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::VitestReporterTest::test_ac6_vitest_component_without_runner_outcome_from_report
3	убита	tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::JunitReportOutcomeTest::test_ac2_per_test_record_id_from_repo_root_outcome_kind_reason_time
4	убита	tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::JunitReportOutcomeTest::test_ac3_report_path_outside_tree_workdir_and_clean_env,tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::JunitReportOutcomeTest::test_ac4_ac6_sled_record_default_report_args_outcome_from_report,tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::JunitReportOutcomeTest::test_ac1_outcome_follows_report_not_runner_output,tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::VitestReporterTest::test_ac6_vitest_component_without_runner_outcome_from_report
5	убита	tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::JunitReportOutcomeTest::test_ac4_explicit_report_args_win_over_default
6	убита	tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::JunitReportOutcomeTest::test_ac4_ac6_sled_record_default_report_args_outcome_from_report
7	убита	tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::JunitReportOutcomeTest::test_ac5_unknown_outcome_form_and_log
8	убита	tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::JunitReportOutcomeTest::test_ac6_pult_pytest_and_no_report_records_by_code_and_text,tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::ArtelUnchangedTest::test_ac4_ac6_pult_pytest_argv_and_outcome_as_main
9	убита	tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::JunitReportOutcomeTest::test_ac11_unknown_is_never_green_at_any_place
10	убита	tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::ResultKeyTest::test_ac18_component_key_follows_tools_lock_command_name_and_artel_key_is_main
11	убита	tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::JunitReportOutcomeTest::test_ac11_unknown_is_never_green_at_any_place,tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::VitestReporterTest::test_ac6_vitest_component_without_runner_outcome_from_report
12	убита	tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::VitestReporterTest::test_ac7_failure_kinds_assertion_type_timeout_hook
13	убита	tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::VitestReporterTest::test_ac8_modes_fails_todo_skip_only_and_retries
```

Часть 2 — `mutation-run 01M5PT190RWC6984CDQVZ242GN --ref base --tests tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py --workers 4 --copy-table --wait-lock 4 --patches 14-26` (прогон №5):

```
# mutation-run №5 задачи 01M5PT190RWC6984CDQVZ242GN
# источник патчей: каталог на диске
# ревизия прогона: base 579a38199ce682917b9d5e40f15ac95cde4aaddc
# тесты: tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py
# рабочих процессов: 4
# патч 14 mutation-014.diff sha256 3a6f940677ef497a8192faa5aae9041e412e3915d72431a375f82daa14a57b9e
# патч 15 mutation-015.diff sha256 7026f1825e6a6d8224b21226d11d6919e593e9935ccd1e1d6745cfc45ac57ea3
# патч 16 mutation-016.diff sha256 0408161f68c5aa6e547fa17f0e6160c9bab93637e75bc990a83607c5da4652af
# патч 17 mutation-017.diff sha256 df62c612e09383fadd2018cb20c941f1c33f7549696e508f84527837844d9b96
# патч 18 mutation-018.diff sha256 ca00bc4c21fd4348beeadb00f753902f6e39c886fdd987800625f17710950bf3
# патч 19 mutation-019.diff sha256 473274094dea1bc7f8ea659f88913a9175511cdf2db08dfda39686fdfb69edc7
# патч 20 mutation-020.diff sha256 7bd962fe619821f0d10a7857f797adf6c11d9948279ba90372604e4f9c5302b7
# патч 21 mutation-021.diff sha256 72d47a13e2e350159310b4684b75a9f58063ed33366bf552ca2d18d784f7b48b
# патч 22 mutation-022.diff sha256 f12c6387fb6973486f32e5a7586c772f5a5786b822bb6bdd54cf94d464752622
# патч 23 mutation-023.diff sha256 5ee6aa874342d4f660666109f10061a814f8d82917dcaad742bf205ec79dc703
# патч 24 mutation-024.diff sha256 3e3f60debdd6139893759098b6ba61a5d869cf2ce31c0b3da39aa04e60ac5603
# патч 25 mutation-025.diff sha256 b8839ca7a8ad19f5eb0c94922fcb5a4d1dd3f956fcf4868ad497c8403f18a1b6
# патч 26 mutation-026.diff sha256 1c3da7bd60bc6a567804f0d8923bf5bd2f21c6113bfd8270ce76c0671b864a56
номер	исход	узлы
14	убита	tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::VitestReporterTest::test_ac9_run_conditions_argv_env_cache_and_flags
15	убита	tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::VitestReporterTest::test_ac9_timeout_kills_group_not_green
16	убита	tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::VitestReporterTest::test_ac9_version_refusals_require_assertions_and_unconfirmed_cache
17	убита	tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::VitestReporterTest::test_ac10_preparation_refusals_command_and_report_args
18	убита	tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::VitestReporterTest::test_ac10_subset_by_select_and_refusal_without_select
19	убита	tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::InstallAndDepsTest::test_ac15_install_once_per_lock_content_from_task_branch
20	убита	tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::InstallAndDepsTest::test_ac15_install_without_lock_and_failed_install_refuse
21	убита	tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::InstallAndDepsTest::test_ac16_node_modules_read_only_shared_and_substitution_refused
22	убита	tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::HungComponentWatchdogTest::test_ac19_watchdog_knows_component_commands_only
23	убита	tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::JunitReportOutcomeTest::test_ac6_pult_pytest_and_no_report_records_by_code_and_text,tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::ArtelUnchangedTest::test_ac4_ac6_pult_pytest_argv_and_outcome_as_main
24	убита	tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::ArtelUnchangedTest::test_ac20_constants_and_texts_as_main
25	убита	tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::ArtelUnchangedTest::test_ac12_suite_run_no_report_non_pytest_refusal_as_main,tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::ArtelUnchangedTest::test_ac20_constants_and_texts_as_main
26	убита	tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py::ArtelUnchangedTest::test_ac20_parsing_digest_journal_and_suite_run_lines_as_main
```

## Мутации после

Число рабочих процессов — 4, диапазоны — те же: `--patches 1-13` и `--patches 14-26`.

Перед частью 1 — `git status --porcelain -- orchestrator/` рабочей копии: вывод пустой.

Часть 1 — `mutation-run 01M5PT190RWC6984CDQVZ242GN --ref worktree --tests tests/test_report_outcome_module.py --workers 4 --copy-table --wait-lock 4 --patches 1-13`:

```
# mutation-run №6 задачи 01M5PT190RWC6984CDQVZ242GN
# источник патчей: каталог на диске
# ревизия прогона: worktree db7fa348078a0f000453823d20c4ae97daf39378
# тесты: tests/test_report_outcome_module.py
# рабочих процессов: 4
# патч 1 mutation-001.diff sha256 1880a2452033c88789f3e15b610598e6d74ba9289da5b1f8c262cb4940113666
# патч 2 mutation-002.diff sha256 4e69fd0421fc10889c5931e18aa03cdbd1e159f9362861fb9b3c798918adf570
# патч 3 mutation-003.diff sha256 83a5413d9a208c960ffd593643e35153f1aac3d4407c7a48eb2b60f91b728ddb
# патч 4 mutation-004.diff sha256 2bda985589f1bb841305c0cf1ef0e78ae6acca36f661fcbdf190a0abfa606eba
# патч 5 mutation-005.diff sha256 5d9c759875719c44f235acc82cbdf6aef086b66e7b416a982de370d881972825
# патч 6 mutation-006.diff sha256 497149a6ac34b7fb70d4e90bd2cf41edd60a5a177cb73421e59a97b0fe490db6
# патч 7 mutation-007.diff sha256 66e6b9ea621caf705ee1f3a1446f02a3619386e7b9f40ea4e621a8ad1fb7b224
# патч 8 mutation-008.diff sha256 5b48e3ab752758ee99399b1c99bdd589b359b72544edb9937c1c2aa453dcbfd8
# патч 9 mutation-009.diff sha256 c9aec8ab3480adbd8e5b063d24a95750600f75e63f5b70b55680c2ed27d799f3
# патч 10 mutation-010.diff sha256 c00b576d7ac0187886cd507aca1cbaa90032e45ab6b46e46a2706b37e96ae0f7
# патч 11 mutation-011.diff sha256 9b50c2648425637bdcd6d7ad871cf91073497d3ff3d6ee9b31628d2a09d10319
# патч 12 mutation-012.diff sha256 109651bb2d971f8865fd6876380864c1ddd6a5f77141ad08653d10bed3e8b2e5
# патч 13 mutation-013.diff sha256 59735f8f453c8d33941474b68e61209c709fb6ab98774bb26cc887955e54599d
номер	исход	узлы
1	убита	tests/test_report_outcome_module.py::test_ac1_outcome_follows_report_not_runner_output,tests/test_report_outcome_module.py::test_ac5_unknown_outcome_form_and_log,tests/test_report_outcome_module.py::test_ac4_ac6_sled_record_default_report_args_outcome_from_report,tests/test_report_outcome_module.py::test_ac2_empty_or_unreadable_report_is_unknown,tests/test_report_outcome_module.py::test_ac11_unknown_is_never_green_at_any_place,tests/test_report_outcome_module.py::test_ac6_vitest_component_without_runner_outcome_from_report,tests/test_report_outcome_module.py::test_ac8_modes_fails_todo_skip_only_and_retries,tests/test_report_outcome_module.py::test_ac7_failure_kinds_assertion_type_timeout_hook
2	убита	tests/test_report_outcome_module.py::test_ac5_unknown_outcome_form_and_log,tests/test_report_outcome_module.py::test_ac1_outcome_follows_report_not_runner_output,tests/test_report_outcome_module.py::test_ac4_ac6_sled_record_default_report_args_outcome_from_report,tests/test_report_outcome_module.py::test_ac2_empty_or_unreadable_report_is_unknown,tests/test_report_outcome_module.py::test_ac6_vitest_component_without_runner_outcome_from_report,tests/test_report_outcome_module.py::test_ac11_unknown_is_never_green_at_any_place
3	убита	tests/test_report_outcome_module.py::test_ac2_per_test_record_id_from_repo_root_outcome_kind_reason_time
4	убита	tests/test_report_outcome_module.py::test_ac1_outcome_follows_report_not_runner_output,tests/test_report_outcome_module.py::test_ac3_report_path_outside_tree_workdir_and_clean_env,tests/test_report_outcome_module.py::test_ac4_ac6_sled_record_default_report_args_outcome_from_report,tests/test_report_outcome_module.py::test_ac6_vitest_component_without_runner_outcome_from_report
5	убита	tests/test_report_outcome_module.py::test_ac4_explicit_report_args_win_over_default
6	убита	tests/test_report_outcome_module.py::test_ac4_ac6_sled_record_default_report_args_outcome_from_report
7	убита	tests/test_report_outcome_module.py::test_ac5_unknown_outcome_form_and_log
8	убита	tests/test_report_outcome_module.py::test_ac6_pult_pytest_and_no_report_records_by_code_and_text,tests/test_report_outcome_module.py::test_ac4_ac6_pult_pytest_argv_and_outcome_as_main
9	убита	tests/test_report_outcome_module.py::test_ac11_unknown_is_never_green_at_any_place
10	убита	tests/test_report_outcome_module.py::test_ac18_component_key_follows_tools_lock_command_name_and_artel_key_is_main
11	убита	tests/test_report_outcome_module.py::test_ac11_unknown_is_never_green_at_any_place,tests/test_report_outcome_module.py::test_ac6_vitest_component_without_runner_outcome_from_report
12	убита	tests/test_report_outcome_module.py::test_ac7_failure_kinds_assertion_type_timeout_hook
13	убита	tests/test_report_outcome_module.py::test_ac8_modes_fails_todo_skip_only_and_retries
```

Перед частью 2 — `git status --porcelain -- orchestrator/` рабочей копии: вывод пустой.

Часть 2 — `mutation-run 01M5PT190RWC6984CDQVZ242GN --ref worktree --tests tests/test_report_outcome_module.py --workers 4 --copy-table --wait-lock 4 --patches 14-26`:

```
# mutation-run №7 задачи 01M5PT190RWC6984CDQVZ242GN
# источник патчей: каталог на диске
# ревизия прогона: worktree db7fa348078a0f000453823d20c4ae97daf39378
# тесты: tests/test_report_outcome_module.py
# рабочих процессов: 4
# патч 14 mutation-014.diff sha256 3a6f940677ef497a8192faa5aae9041e412e3915d72431a375f82daa14a57b9e
# патч 15 mutation-015.diff sha256 7026f1825e6a6d8224b21226d11d6919e593e9935ccd1e1d6745cfc45ac57ea3
# патч 16 mutation-016.diff sha256 0408161f68c5aa6e547fa17f0e6160c9bab93637e75bc990a83607c5da4652af
# патч 17 mutation-017.diff sha256 df62c612e09383fadd2018cb20c941f1c33f7549696e508f84527837844d9b96
# патч 18 mutation-018.diff sha256 ca00bc4c21fd4348beeadb00f753902f6e39c886fdd987800625f17710950bf3
# патч 19 mutation-019.diff sha256 473274094dea1bc7f8ea659f88913a9175511cdf2db08dfda39686fdfb69edc7
# патч 20 mutation-020.diff sha256 7bd962fe619821f0d10a7857f797adf6c11d9948279ba90372604e4f9c5302b7
# патч 21 mutation-021.diff sha256 72d47a13e2e350159310b4684b75a9f58063ed33366bf552ca2d18d784f7b48b
# патч 22 mutation-022.diff sha256 f12c6387fb6973486f32e5a7586c772f5a5786b822bb6bdd54cf94d464752622
# патч 23 mutation-023.diff sha256 5ee6aa874342d4f660666109f10061a814f8d82917dcaad742bf205ec79dc703
# патч 24 mutation-024.diff sha256 3e3f60debdd6139893759098b6ba61a5d869cf2ce31c0b3da39aa04e60ac5603
# патч 25 mutation-025.diff sha256 b8839ca7a8ad19f5eb0c94922fcb5a4d1dd3f956fcf4868ad497c8403f18a1b6
# патч 26 mutation-026.diff sha256 1c3da7bd60bc6a567804f0d8923bf5bd2f21c6113bfd8270ce76c0671b864a56
номер	исход	узлы
14	убита	tests/test_report_outcome_module.py::test_ac9_run_conditions_argv_env_cache_and_flags
15	убита	tests/test_report_outcome_module.py::test_ac9_timeout_kills_group_not_green
16	убита	tests/test_report_outcome_module.py::test_ac9_version_refusals_require_assertions_and_unconfirmed_cache
17	убита	tests/test_report_outcome_module.py::test_ac10_preparation_refusals_command_and_report_args
18	убита	tests/test_report_outcome_module.py::test_ac10_subset_by_select_and_refusal_without_select
19	убита	tests/test_report_outcome_module.py::test_ac15_install_once_per_lock_content_from_task_branch
20	убита	tests/test_report_outcome_module.py::test_ac15_install_without_lock_and_failed_install_refuse
21	убита	tests/test_report_outcome_module.py::test_ac16_node_modules_read_only_shared_and_substitution_refused
22	убита	tests/test_report_outcome_module.py::test_ac19_watchdog_knows_component_commands_only
23	убита	tests/test_report_outcome_module.py::test_ac6_pult_pytest_and_no_report_records_by_code_and_text,tests/test_report_outcome_module.py::test_ac4_ac6_pult_pytest_argv_and_outcome_as_main
24	убита	tests/test_report_outcome_module.py::test_ac20_constants_and_texts_as_main
25	убита	tests/test_report_outcome_module.py::test_ac20_constants_and_texts_as_main,tests/test_report_outcome_module.py::test_ac12_suite_run_no_report_non_pytest_refusal_as_main
26	убита	tests/test_report_outcome_module.py::test_ac20_parsing_digest_journal_and_suite_run_lines_as_main
```

## Удалённые дубли

Нет: все 26 тестов перенесены.

## Числа адресного прогона

- До: исходный файл `tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py` — 26 тестов, 1894 строки; контрольный прогон `mutation-run` №4 (`--workers 4`): «26 passed, 35 subtests passed in 9.66s» — 9.66 с.
- После: `tests/test_report_outcome_module.py` — 26 тестовых функций, 1344 строки; контрольный прогон `mutation-run` №6 (`--workers 4`): «26 passed in 9.29s» — 9.29 с.
- Адресный прогон этого шага — один файл, импортёр: `python3 -m pytest tests/test_component_report_gates.py -p no:cacheprovider -p timeout -o timeout=120` — «13 passed, 10 subtests passed in 4.53s».

## Итог CI

- CI кодовой ветки для `tests/test_invariants.py::ReportedOutcomeNotGreenInvariantTest`: роли в шаге не виден — `gh run list` по ветке требует подтверждения, которого в шаге нет; код ветки запушен (origin на 20943324, после него только подтяжка main). Итог сверяет гейт `verifying` по CI ветки.
- CI кодовой ветки для `tests/test_component_report_gates.py`: то же, CI роли не виден; локально адресным прогоном — «13 passed, 10 subtests passed in 4.53s».

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2, 3, 4 | 2 |
| 5 | все (временные сценарии — файлы первого уровня каталога документов) |
| 6, 7, 8, 9, 10, 11, 12, 13 | 3 |
| 14 | 4 |
| 15 | 3 (раздел «Числа адресного прогона») |
| 16 | 3 (утверждения перенесены без ослабления) |
| 17 | 3 |
| 18 | вне ролей |

## Влияние на систему

Код `orchestrator/` не меняется. Защищённые пути (`tests/test_invariants.py`,
`docs/invariants.md`) не меняются: имена для инварианта отдаёт переходной
модуль. Утверждения перенесены без ослабления. Откат — revert merge-коммита.

## Риски

- `test_ac9_timeout_kills_group_not_green` с пределом компонента 1 с был неустойчив под xdist с числом процессов по умолчанию (прогоны №1–№3); с `--workers 4` контроль зелёный во всех четырёх прогонах №4–№7.

## Предложения системе

- `mutation-run --copy-table` кладёт копию `mutation-run-<n>.tsv` первым уровнем каталога документов, а планка волны (AC-5, `test_branch_diff.py::test_ac5_docs_dir_has_no_subdirs_and_no_test_or_mutation_named_files`) запрещает там файлы `mutation-*`, кроме патчей: роль переносит таблицу в PLAN и удаляет копию. Имя копии без префикса `mutation-` (или подкаталог) сняло бы конфликт.
- Шапка `mutation-run` с 01M5PWFGJQNV8YSAN5MF0CKHVW несёт строку `# рабочих процессов: <n>` между `# тесты:` и `# патч …`; разбор таблиц планок волн, написанных до этого (`acceptance_tests/_plan.py::tables`, `_TABLE_LINE`), этой строки не знает.
