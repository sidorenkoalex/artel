---
task: 01M5PT190RWC6984CDQVZ242GN
type: plan
author_role: developer
status: escalate
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

## Мутации до

Прогоны №1, №2 и №3 (`--ref base --patches 1-13`) отказали до патчей:
контрольный прогон без мутаций красный —
`VitestReporterTest::test_ac9_timeout_kills_group_not_green`, утверждение
:1249 «раннер не запускался» (`full_suite_timeout_sec: 1`, под xdist в копии
`mutation-run` раннер не успевает записать пробу за 1 с). Одиночный прогон
того же теста зелёный.

## Мутации после

Не прогнаны: ждут таблицы «до».

## Удалённые дубли

Нет: все 26 тестов перенесены.

## Числа адресного прогона

- До: исходный файл — 26 тестов, 1894 строки; контрольный прогон
  `mutation-run` №2 под xdist: «1 failed, 25 passed, 35 subtests passed in
  10.24s» — 10.24 с.
- После: `tests/test_report_outcome_module.py` — 26 тестовых функций, 1344
  строки; `python3 -m pytest tests/test_report_outcome_module.py -p
  no:cacheprovider -p timeout -o timeout=120` — «26 passed in 23.58s»,
  23.58 с (без xdist).

## Итог CI

- CI кодовой ветки для `tests/test_invariants.py::ReportedOutcomeNotGreenInvariantTest` — ещё не получен (код ветки не запушен на этом шаге).
- CI кодовой ветки для `tests/test_component_report_gates.py` — ещё не получен.

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

- `test_ac9_timeout_kills_group_not_green` с пределом компонента 1 с
  неустойчив под xdist в копии `mutation-run` (см. «Мутации до»).

## Предложения системе

- `mutation-run` отказывает целиком при одном красном контрольном тесте с
  жёстким пределом времени — нет ни повтора контроля, ни способа задать
  число исполнителей xdist; для тестов с пределом 1 с
  (`test_ac9_timeout_kills_group_not_green`) это блокирует таблицу «до».

## Эскалация

**Вопросы** (по блокирующести):

1. Таблицу «до» получить нельзя: `mutation-run --ref base --tests
   tests/test_01m590gjaf0edv4nbc4c99mfvh_report_outcome.py --patches 1-13`
   три раза подряд (прогоны №1–№3) отказал до патчей — контрольный прогон
   базы a426605f красный на `VitestReporterTest::test_ac9_timeout_kills_group_not_green`,
   утверждение :1249 «раннер не запускался» (`full_suite_timeout_sec: 1`;
   под xdist в копии `mutation-run` поддельный раннер не успевает записать
   пробу за 1 с). Одиночный прогон того же теста и прогон всего сведённого
   файла без xdist — зелёные. Нагрузка машины низкая (loadavg 4.3 на 14
   ядрах). Код базы и `orchestrator/mutation_run.py` роль менять не вправе.
   Варианты:
   а) повторить `mutation-run` в следующем шаге без изменений (если флак
      — пройдёт);
   б) Оператор прогоняет «до» сам при другой нагрузке / с иным числом
      исполнителей и кладёт вывод, роль переносит его в PLAN;
   в) отдельная задача: `mutation-run` повторяет красный контроль или
      принимает число исполнителей xdist; волна ждёт её;
   г) иное решение Оператора.
   Дефолт при молчании: а), при повторном отказе — б).

**Контекст.** Сделано и зелёно: 26 патчей `mutation-001.diff` …
`mutation-026.diff` (каждый проверен одиночным прогоном теста с патчем в
копии `$TMPDIR` — падает утверждение тела теста, строки — в разделе
«Мутации»); `tests/report_outcome_sandbox.py` (ast.dump 50/50);
`tests/test_report_outcome_module.py` (26 функций, «26 passed in 23.58s»);
переходной модуль; импорт `tests/test_component_report_gates.py`; карта
перегенерирована. Логи контроля:
`.artel/logs/suite-run/01M5PT190RWC6984CDQVZ242GN/01M5PT190RWC6984CDQVZ242GN-mutation-run-{1,2,3}-control.log`.

**Блокирует.** Таблицы «до» и «после» (требования 2, 14), доказательство
мутациями и строки «после» с упавшими утверждениями нового файла.
