---
task: 01M5QG7KXQWJDEWRHAWZFQBXET
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Сведение тестов, волна 2б-4 — тесты гейтов отчётов компонентов в `tests/test_report_outcome_module.py`; тексты сообщений модуля

## Подход

Перенос 13 тестов `tests/test_component_report_gates.py` (далее crg) функциями
pytest в конец `tests/test_report_outcome_module.py` (блок «гейты итога из
отчёта компонента»), crg удалён. Доказательство неослабления — множества
убитых мутаций: 15 патчей `mutation-001…015` к `orchestrator/` прогнаны
`mutation-run` «до» (`--ref base` на crg) и «после» (`--ref worktree` на
модуле) теми же патчами; каждая мутация, убитая «до» тестом T, «после»
убита функцией, в которую перенесён T, тем же по нормальной форме
утверждением (соответствие — раздел «Соответствие мутаций»).

Ключевые решения:
- Имена переносимых определений `profile`, `check`, `UNKNOWN`, `GREEN`,
  `Reached` и помощников `suite`, `approve`, `two_components`, `selected`,
  `check_script`, `checked_case`, `journal`, `merge` не совпадают ни с одним
  именем верхнего уровня модуля базы — переименований с префиксом нет
  (перечень пуст). Локальные `profile`/`outcome` 26 существующих тестов не
  тронуты.
- Импорты: добавлены только недостающие — `dataclasses`, `threading`,
  `types`, `fsm`, `fsm_merge_gate`, `orchestrator.reporters.outcome`,
  `VITEST_REPORT_ARGS`, `block` (из `tests.report_outcome_sandbox`); `json`,
  `unittest`, блок `__main__` не переносились.
- Стенды: фикстура `checks_stand(tmp_dir)` →
  `types.SimpleNamespace(tree=tmp_dir.tdir.resolve())` для бывшего
  `AcceptanceSuiteChecksLocalTest` (помощники `suite`/`approve` с первым
  параметром `stand`); классы на `ReportSandbox` — `box`; `InstallLockTest` —
  `tmp_dir` (ради `addCleanup`); `SuiteRunParseReportedTest` — без фикстуры.
- `subTest`: :81, :96 — `parametrize("actor", ("operator", "fsm"))`; :178,
  :334, :396 — прежний цикл, ярлык (`command=`, `base=`, `actor=`) в тексте
  сообщения каждого `assert` цикла суффиксом `+ "; " + f"<ярлык>={…!r}"`,
  как принято в модуле.
- `self.assertRaises(Reached)` → `pytest.raises(Reached)` без `match` (текст
  не проверялся, `msg=` не было).
- Требование 13: `assert_unknown(box, run, context, case: str = "")`,
  сообщения тела — `box.note(…) + case`; вызовы test_ac1 / test_ac2_empty /
  test_ac4_ac6_sled передают ярлык подслучая; в test_ac16 блок
  `pytest.raises(OSError)` закрыт строкой
  `pytest.fail(box.note("запись в node_modules"))`.

Удалённых дублей нет: все 13 тестов перенесены.

## Шаги

1. Патчи мутаций `mutation-001…015` (каталог документов задачи) и таблица
   «до» одной частью.
2. Свод crg в модуль, правки требования 13, удаление crg, регенерация
   `docs/codebase-map.md`; адресный прогон модуля (`41 passed`).
3. Таблица «после» теми же патчами на рабочей копии; соответствие
   убийц «до»/«после» с файлом:строкой упавших утверждений.

## Патчи мутаций

Каждый патч меняет только файлы под `orchestrator/`; заявка → патч(и):

- mutation-001 — `orchestrator/acceptance.py::acceptance_suite`: удалён блок `if not run.green: return run._replace(...)` — непрошедшая `checks_local` даёт `FULL_SUITE_RED` при любом итоге; заявки AcceptanceSuiteChecksLocalTest::test_failing_check_keeps_unknown_outcome_on_both_paths и AcceptanceSuiteChecksLocalTest::test_accept_red_refuses_unknown_even_with_failing_check (одна мутация по смыслу — один патч).
- mutation-002 — `orchestrator/acceptance.py::acceptance_suite`: `ok, text = run_checks_local(profile, root)` заменено на `ok, text = True, ""` — `checks_local` не зовётся; заявка AcceptanceSuiteChecksLocalTest::test_check_runs_after_any_source_and_reddens_only_green (альтернатива «не зовёт»).
- mutation-003 — `orchestrator/acceptance.py::acceptance_suite`: `run_checks_local(profile, root) if fresh else (True, "")` — проверка только при свежем прогоне; заявка AcceptanceSuiteChecksLocalTest::test_check_runs_after_any_source_and_reddens_only_green (альтернатива «только при свежем»).
- mutation-004 — `orchestrator/acceptance.py::_report_argv`: `own = _own(profile)` — pytest-аргументы `pytest-own` и у Vitest; заявка ReportArgvTest::test_vitest_component_with_workdir_gets_exact_pult_argv.
- mutation-005 — `orchestrator/acceptance.py::_report_argv`: `own = _own(profile) if not vitest else None` — pytest-аргументы к любой команде `pytest-own`; заявка ReportArgvTest::test_pytest_args_only_for_pytest_command (альтернатива «к любой команде»).
- mutation-006 — `orchestrator/acceptance.py::_report_argv`: `own = None` — pytest-аргументы пропадают и у pytest; заявка ReportArgvTest::test_pytest_args_only_for_pytest_command (альтернатива «пропадают»).
- mutation-007 — `orchestrator/acceptance.py::_install`: удалена строка `fcntl.flock(fh, fcntl.LOCK_EX)` — установка без замка; заявка InstallLockTest::test_parallel_first_installs_run_once_without_refusal.
- mutation-008 — `orchestrator/suite_run.py::parse`: `statuses = _progress(output)` и при `reported` — строки хода читаются; заявка SuiteRunParseReportedTest::test_failures_of_reported_output_come_only_from_report.
- mutation-009 — `orchestrator/fsm_merge_gate.py::_selected_components`: `select_components(ctx.target, changed)` без путей приложений; заявка MergeGateComponentsTest::test_components_chosen_by_branch_diff_and_appendix_paths (альтернатива «без путей приложений»).
- mutation-010 — `orchestrator/fsm_merge_gate.py::_selected_components`: при непрочитанном диффе `component_profiles(ctx.target)[:1]` — выбор молча сужается; заявка MergeGateComponentsTest::test_components_chosen_by_branch_diff_and_appendix_paths (альтернатива «сужение»).
- mutation-011 — `orchestrator/acceptance.py::full_suite`: узел по компонентам берёт `limit = config.FULL_SUITE_TIMEOUT_SEC, "config"` (предел проекта по умолчанию) вместо `component_limit(reported)`; заявка MergeGateComponentsTest::test_each_component_runs_with_its_own_limit.
- mutation-012 — `orchestrator/suite_run.py::_profile_command`: профиль `Profile.from_values(answer.values)` без `with_tools`; заявка SuiteRunKeyTest::test_merge_gate_and_suite_run_keys_match_with_tools.
- mutation-013 — `orchestrator/project_profile.py::_with_component_fields`: `checks_local=()` — поле теряется; заявка ChecksLocalFromRecordTest::test_record_checks_local_runs_in_acceptance_suite.
- mutation-014 — `orchestrator/fsm_merge_gate.py::_cmd_approve_merge_gate`: `if applied and _checks_local_refuse(...)` — вызов только в ветке с применёнными приложениями; заявка ChecksLocalFromRecordTest::test_merge_gate_without_appendices_runs_record_checks_local.
- mutation-015 — `orchestrator/acceptance.py::_install`: `if profile.install is None:` вместо `if not profile.install:`; заявка EmptyInstallTest::test_empty_install_neither_installs_nor_refuses.

Патч 011 переписан один раз: первая редакция (`full_suite_limit(reported.project or target)`) в прогоне №1 убивала тест исключением `TargetsError` в теле узла, не утверждением (ANSWER-1 п. 4); прогон №1 и его копия `mutation-run-1.tsv` — история, доказательство — прогоны №2 («до») и №3 («после»).

## Мутации до

Команда: `mutation-run 01M5QG7KXQWJDEWRHAWZFQBXET --ref base --tests tests/test_component_report_gates.py --workers 4 --copy-table --wait-lock 4` (+ `--wait 5`), вывод таблицы дословно:

```
# mutation-run №2 задачи 01M5QG7KXQWJDEWRHAWZFQBXET
# источник патчей: каталог на диске
# ревизия прогона: base ec948ea430e262436fbedcd59c35c6f472764af9
# тесты: tests/test_component_report_gates.py
# рабочих процессов: 4
# патч 1 mutation-001.diff sha256 39299f609200d63d3d4b76dfd255132d0d5bf9ce3e331aee967e8db5e0076dc1
# патч 2 mutation-002.diff sha256 abe604f874f6707ab64da60c67d09390d389d79f61b80b8b116a9327cdb97a25
# патч 3 mutation-003.diff sha256 d3c585a42cca8a49484e4b844c7a425f68b93ac366e5d65064c7e6048573de52
# патч 4 mutation-004.diff sha256 e8da90353c6615b0b475de86410ba2d308ffdb169101d4d2aa95dbb6b4d0db55
# патч 5 mutation-005.diff sha256 c1af1e73ba248c87f86c33199f83328b1ef465a27db13650d19deea303240c83
# патч 6 mutation-006.diff sha256 79c8981ec79d244ffe3e32ae508530b0cbdd0f70f12a3f4e7b86cfa1d0c65534
# патч 7 mutation-007.diff sha256 91ce8fd39483d670ef7c3dfdc5851fba5adb20664edd44e658b4912fc3ab5a1d
# патч 8 mutation-008.diff sha256 b69e87fc7270c722df53911d2dbb3d36962792e4286c60e8f3343410b2456147
# патч 9 mutation-009.diff sha256 fbb4b5ead8059374a1b7f58b3a490ebe5651a1c610a4c0dadb0fef1406de30c4
# патч 10 mutation-010.diff sha256 7224d3b6dad71ed8203e0828ea3dfdf0a28f6d968db1c6cacf14b79b92309ea4
# патч 11 mutation-011.diff sha256 050065d6ad78cbd578e24f296ea5b2fa4d1cc7797ee9dcfa410a688134c746c0
# патч 12 mutation-012.diff sha256 d057910f85ce4bf29330c4c5d82e3a232d0d0d87da5dc1375cf2c5cd029f9e3b
# патч 13 mutation-013.diff sha256 71dc62b491cc9239101af14b6c22d75766462450babc1bdf70d59aa50ec94ef2
# патч 14 mutation-014.diff sha256 85029fc59c71d071042127829f651e43260fe1fe34efdcbc61dc4ea5b6dfcce9
# патч 15 mutation-015.diff sha256 44c7c15d45366ec01db7fff1729234cfa331d60c8ea4f21dc378231a38572632
номер	исход	узлы
1	убита	tests/test_component_report_gates.py::AcceptanceSuiteChecksLocalTest::test_failing_check_keeps_unknown_outcome_on_both_paths,tests/test_component_report_gates.py::AcceptanceSuiteChecksLocalTest::test_accept_red_refuses_unknown_even_with_failing_check
2	убита	tests/test_component_report_gates.py::AcceptanceSuiteChecksLocalTest::test_accept_red_refuses_unknown_even_with_failing_check,tests/test_component_report_gates.py::AcceptanceSuiteChecksLocalTest::test_failing_check_keeps_unknown_outcome_on_both_paths,tests/test_component_report_gates.py::AcceptanceSuiteChecksLocalTest::test_check_runs_after_any_source_and_reddens_only_green,tests/test_component_report_gates.py::ChecksLocalFromRecordTest::test_record_checks_local_runs_in_acceptance_suite
3	убита	tests/test_component_report_gates.py::AcceptanceSuiteChecksLocalTest::test_accept_red_refuses_unknown_even_with_failing_check,tests/test_component_report_gates.py::AcceptanceSuiteChecksLocalTest::test_failing_check_keeps_unknown_outcome_on_both_paths,tests/test_component_report_gates.py::AcceptanceSuiteChecksLocalTest::test_check_runs_after_any_source_and_reddens_only_green
4	убита	tests/test_component_report_gates.py::ReportArgvTest::test_vitest_component_with_workdir_gets_exact_pult_argv,tests/test_component_report_gates.py::ReportArgvTest::test_pytest_args_only_for_pytest_command
5	убита	tests/test_component_report_gates.py::ReportArgvTest::test_pytest_args_only_for_pytest_command
6	убита	tests/test_component_report_gates.py::ReportArgvTest::test_pytest_args_only_for_pytest_command
7	убита	tests/test_component_report_gates.py::InstallLockTest::test_parallel_first_installs_run_once_without_refusal
8	убита	tests/test_component_report_gates.py::SuiteRunParseReportedTest::test_failures_of_reported_output_come_only_from_report
9	убита	tests/test_component_report_gates.py::MergeGateComponentsTest::test_components_chosen_by_branch_diff_and_appendix_paths
10	убита	tests/test_component_report_gates.py::MergeGateComponentsTest::test_components_chosen_by_branch_diff_and_appendix_paths
11	убита	tests/test_component_report_gates.py::MergeGateComponentsTest::test_each_component_runs_with_its_own_limit
12	убита	tests/test_component_report_gates.py::SuiteRunKeyTest::test_merge_gate_and_suite_run_keys_match_with_tools
13	убита	tests/test_component_report_gates.py::ChecksLocalFromRecordTest::test_merge_gate_without_appendices_runs_record_checks_local,tests/test_component_report_gates.py::ChecksLocalFromRecordTest::test_record_checks_local_runs_in_acceptance_suite
14	убита	tests/test_component_report_gates.py::ChecksLocalFromRecordTest::test_merge_gate_without_appendices_runs_record_checks_local
15	убита	tests/test_component_report_gates.py::AcceptanceSuiteChecksLocalTest::test_check_runs_after_any_source_and_reddens_only_green,tests/test_component_report_gates.py::ChecksLocalFromRecordTest::test_merge_gate_without_appendices_runs_record_checks_local,tests/test_component_report_gates.py::EmptyInstallTest::test_empty_install_neither_installs_nor_refuses,tests/test_component_report_gates.py::ChecksLocalFromRecordTest::test_record_checks_local_runs_in_acceptance_suite
```

Итог: убиты все 15; ни одна не «итог неизвестен», «патч не применяется», «патч трогает тесты», «не прогнана».

## Находки

Нет: мутаций, не убитых «до» никем, нет.

## Удалённые дубли

Нет: все 13 тестов перенесены функциями модуля с теми же именами.

## Мутации после

Перед прогоном — пустой вывод `git status --porcelain -- orchestrator/` (между командой и строкой-маркером ничего нет):

```
$ git status --porcelain -- orchestrator/
--- конец вывода git status
```

Команда: `mutation-run 01M5QG7KXQWJDEWRHAWZFQBXET --ref worktree --tests tests/test_report_outcome_module.py --workers 4 --copy-table --wait-lock 4` (+ `--wait 5`), вывод таблицы дословно:

```
# mutation-run №3 задачи 01M5QG7KXQWJDEWRHAWZFQBXET
# источник патчей: каталог на диске
# ревизия прогона: worktree 8c0dc33714a457677752748ce06325ecea5f2c34
# тесты: tests/test_report_outcome_module.py
# рабочих процессов: 4
# патч 1 mutation-001.diff sha256 39299f609200d63d3d4b76dfd255132d0d5bf9ce3e331aee967e8db5e0076dc1
# патч 2 mutation-002.diff sha256 abe604f874f6707ab64da60c67d09390d389d79f61b80b8b116a9327cdb97a25
# патч 3 mutation-003.diff sha256 d3c585a42cca8a49484e4b844c7a425f68b93ac366e5d65064c7e6048573de52
# патч 4 mutation-004.diff sha256 e8da90353c6615b0b475de86410ba2d308ffdb169101d4d2aa95dbb6b4d0db55
# патч 5 mutation-005.diff sha256 c1af1e73ba248c87f86c33199f83328b1ef465a27db13650d19deea303240c83
# патч 6 mutation-006.diff sha256 79c8981ec79d244ffe3e32ae508530b0cbdd0f70f12a3f4e7b86cfa1d0c65534
# патч 7 mutation-007.diff sha256 91ce8fd39483d670ef7c3dfdc5851fba5adb20664edd44e658b4912fc3ab5a1d
# патч 8 mutation-008.diff sha256 b69e87fc7270c722df53911d2dbb3d36962792e4286c60e8f3343410b2456147
# патч 9 mutation-009.diff sha256 fbb4b5ead8059374a1b7f58b3a490ebe5651a1c610a4c0dadb0fef1406de30c4
# патч 10 mutation-010.diff sha256 7224d3b6dad71ed8203e0828ea3dfdf0a28f6d968db1c6cacf14b79b92309ea4
# патч 11 mutation-011.diff sha256 050065d6ad78cbd578e24f296ea5b2fa4d1cc7797ee9dcfa410a688134c746c0
# патч 12 mutation-012.diff sha256 d057910f85ce4bf29330c4c5d82e3a232d0d0d87da5dc1375cf2c5cd029f9e3b
# патч 13 mutation-013.diff sha256 71dc62b491cc9239101af14b6c22d75766462450babc1bdf70d59aa50ec94ef2
# патч 14 mutation-014.diff sha256 85029fc59c71d071042127829f651e43260fe1fe34efdcbc61dc4ea5b6dfcce9
# патч 15 mutation-015.diff sha256 44c7c15d45366ec01db7fff1729234cfa331d60c8ea4f21dc378231a38572632
номер	исход	узлы
1	убита	tests/test_report_outcome_module.py::test_failing_check_keeps_unknown_outcome_on_both_paths[operator],tests/test_report_outcome_module.py::test_accept_red_refuses_unknown_even_with_failing_check,tests/test_report_outcome_module.py::test_failing_check_keeps_unknown_outcome_on_both_paths[fsm]
2	убита	tests/test_report_outcome_module.py::test_failing_check_keeps_unknown_outcome_on_both_paths[operator],tests/test_report_outcome_module.py::test_check_runs_after_any_source_and_reddens_only_green[operator],tests/test_report_outcome_module.py::test_check_runs_after_any_source_and_reddens_only_green[fsm],tests/test_report_outcome_module.py::test_accept_red_refuses_unknown_even_with_failing_check,tests/test_report_outcome_module.py::test_failing_check_keeps_unknown_outcome_on_both_paths[fsm],tests/test_report_outcome_module.py::test_record_checks_local_runs_in_acceptance_suite
3	убита	tests/test_report_outcome_module.py::test_failing_check_keeps_unknown_outcome_on_both_paths[operator],tests/test_report_outcome_module.py::test_accept_red_refuses_unknown_even_with_failing_check,tests/test_report_outcome_module.py::test_check_runs_after_any_source_and_reddens_only_green[operator],tests/test_report_outcome_module.py::test_check_runs_after_any_source_and_reddens_only_green[fsm],tests/test_report_outcome_module.py::test_failing_check_keeps_unknown_outcome_on_both_paths[fsm]
4	убита	tests/test_report_outcome_module.py::test_vitest_component_with_workdir_gets_exact_pult_argv,tests/test_report_outcome_module.py::test_pytest_args_only_for_pytest_command
5	убита	tests/test_report_outcome_module.py::test_pytest_args_only_for_pytest_command
6	убита	tests/test_report_outcome_module.py::test_pytest_args_only_for_pytest_command
7	убита	tests/test_report_outcome_module.py::test_parallel_first_installs_run_once_without_refusal
8	убита	tests/test_report_outcome_module.py::test_failures_of_reported_output_come_only_from_report
9	убита	tests/test_report_outcome_module.py::test_components_chosen_by_branch_diff_and_appendix_paths
10	убита	tests/test_report_outcome_module.py::test_components_chosen_by_branch_diff_and_appendix_paths
11	убита	tests/test_report_outcome_module.py::test_each_component_runs_with_its_own_limit
12	убита	tests/test_report_outcome_module.py::test_merge_gate_and_suite_run_keys_match_with_tools
13	убита	tests/test_report_outcome_module.py::test_record_checks_local_runs_in_acceptance_suite,tests/test_report_outcome_module.py::test_merge_gate_without_appendices_runs_record_checks_local
14	убита	tests/test_report_outcome_module.py::test_merge_gate_without_appendices_runs_record_checks_local
15	убита	tests/test_report_outcome_module.py::test_ac1_outcome_follows_report_not_runner_output,tests/test_report_outcome_module.py::test_ac5_unknown_outcome_form_and_log,tests/test_report_outcome_module.py::test_ac2_per_test_record_id_from_repo_root_outcome_kind_reason_time,tests/test_report_outcome_module.py::test_ac4_explicit_report_args_win_over_default,tests/test_report_outcome_module.py::test_ac2_empty_or_unreadable_report_is_unknown,tests/test_report_outcome_module.py::test_ac4_ac6_sled_record_default_report_args_outcome_from_report,tests/test_report_outcome_module.py::test_ac3_report_path_outside_tree_workdir_and_clean_env,tests/test_report_outcome_module.py::test_check_runs_after_any_source_and_reddens_only_green[operator],tests/test_report_outcome_module.py::test_check_runs_after_any_source_and_reddens_only_green[fsm],tests/test_report_outcome_module.py::test_merge_gate_without_appendices_runs_record_checks_local,tests/test_report_outcome_module.py::test_empty_install_neither_installs_nor_refuses,tests/test_report_outcome_module.py::test_record_checks_local_runs_in_acceptance_suite
```

Итог: убиты все 15. Дерево `orchestrator/` ревизий шапок (`ec948ea4` и `8c0dc337`) одно — коммит ветки меняет только `tests/` и `docs/codebase-map.md`; sha256 каждого патча в шапках совпадает.

## Соответствие мутаций

Строка: мутация, убийца «до» (тест crg) и файл:строка упавшего утверждения из лога прогона патча №2, убийца «после» (функция модуля) и файл:строка из лога прогона №3.

- mutation-001: AcceptanceSuiteChecksLocalTest::test_failing_check_keeps_unknown_outcome_on_both_paths — до `tests/test_component_report_gates.py:84`; после `test_report_outcome_module.py::test_failing_check_keeps_unknown_outcome_on_both_paths` — `tests/test_report_outcome_module.py:1415`
- mutation-001: AcceptanceSuiteChecksLocalTest::test_accept_red_refuses_unknown_even_with_failing_check — до `tests/test_component_report_gates.py:133`; после `test_report_outcome_module.py::test_accept_red_refuses_unknown_even_with_failing_check` — `tests/test_report_outcome_module.py:1466`
- mutation-002: AcceptanceSuiteChecksLocalTest::test_failing_check_keeps_unknown_outcome_on_both_paths — до `tests/test_component_report_gates.py:86`; после `test_report_outcome_module.py::test_failing_check_keeps_unknown_outcome_on_both_paths` — `tests/test_report_outcome_module.py:1417`
- mutation-002: AcceptanceSuiteChecksLocalTest::test_check_runs_after_any_source_and_reddens_only_green — до `tests/test_component_report_gates.py:99`; после `test_report_outcome_module.py::test_check_runs_after_any_source_and_reddens_only_green` — `tests/test_report_outcome_module.py:1430`
- mutation-002: AcceptanceSuiteChecksLocalTest::test_accept_red_refuses_unknown_even_with_failing_check — до `tests/test_component_report_gates.py:135`; после `test_report_outcome_module.py::test_accept_red_refuses_unknown_even_with_failing_check` — `tests/test_report_outcome_module.py:1468`
- mutation-002: ChecksLocalFromRecordTest::test_record_checks_local_runs_in_acceptance_suite — до `tests/test_component_report_gates.py:408`; после `test_report_outcome_module.py::test_record_checks_local_runs_in_acceptance_suite` — `tests/test_report_outcome_module.py:1731`
- mutation-003: AcceptanceSuiteChecksLocalTest::test_failing_check_keeps_unknown_outcome_on_both_paths — до `tests/test_component_report_gates.py:86`; после `test_report_outcome_module.py::test_failing_check_keeps_unknown_outcome_on_both_paths` — `tests/test_report_outcome_module.py:1417`
- mutation-003: AcceptanceSuiteChecksLocalTest::test_check_runs_after_any_source_and_reddens_only_green — до `tests/test_component_report_gates.py:99`; после `test_report_outcome_module.py::test_check_runs_after_any_source_and_reddens_only_green` — `tests/test_report_outcome_module.py:1430`
- mutation-003: AcceptanceSuiteChecksLocalTest::test_accept_red_refuses_unknown_even_with_failing_check — до `tests/test_component_report_gates.py:135`; после `test_report_outcome_module.py::test_accept_red_refuses_unknown_even_with_failing_check` — `tests/test_report_outcome_module.py:1468`
- mutation-004: ReportArgvTest::test_vitest_component_with_workdir_gets_exact_pult_argv — до `tests/test_component_report_gates.py:159`; после `test_report_outcome_module.py::test_vitest_component_with_workdir_gets_exact_pult_argv` — `tests/test_report_outcome_module.py:1489`
- mutation-004: ReportArgvTest::test_pytest_args_only_for_pytest_command — до `tests/test_component_report_gates.py:185`; после `test_report_outcome_module.py::test_pytest_args_only_for_pytest_command` — `tests/test_report_outcome_module.py:1514`
- mutation-005: ReportArgvTest::test_pytest_args_only_for_pytest_command — до `tests/test_component_report_gates.py:185`; после `test_report_outcome_module.py::test_pytest_args_only_for_pytest_command` — `tests/test_report_outcome_module.py:1514`
- mutation-006: ReportArgvTest::test_pytest_args_only_for_pytest_command — до `tests/test_component_report_gates.py:185`; после `test_report_outcome_module.py::test_pytest_args_only_for_pytest_command` — `tests/test_report_outcome_module.py:1514`
- mutation-007: InstallLockTest::test_parallel_first_installs_run_once_without_refusal — до `tests/test_component_report_gates.py:219`; после `test_report_outcome_module.py::test_parallel_first_installs_run_once_without_refusal` — `tests/test_report_outcome_module.py:1549`
- mutation-008: SuiteRunParseReportedTest::test_failures_of_reported_output_come_only_from_report — до `tests/test_component_report_gates.py:242`; после `test_report_outcome_module.py::test_failures_of_reported_output_come_only_from_report` — `tests/test_report_outcome_module.py:1570`
- mutation-009: MergeGateComponentsTest::test_components_chosen_by_branch_diff_and_appendix_paths — до `tests/test_component_report_gates.py:289`; после `test_report_outcome_module.py::test_components_chosen_by_branch_diff_and_appendix_paths` — `tests/test_report_outcome_module.py:1616`
- mutation-010: MergeGateComponentsTest::test_components_chosen_by_branch_diff_and_appendix_paths — до `tests/test_component_report_gates.py:291`; после `test_report_outcome_module.py::test_components_chosen_by_branch_diff_and_appendix_paths` — `tests/test_report_outcome_module.py:1617`
- mutation-011: MergeGateComponentsTest::test_each_component_runs_with_its_own_limit — до `tests/test_component_report_gates.py:313`; после `test_report_outcome_module.py::test_each_component_runs_with_its_own_limit` — `tests/test_report_outcome_module.py:1640`
- mutation-012: SuiteRunKeyTest::test_merge_gate_and_suite_run_keys_match_with_tools — до `tests/test_component_report_gates.py:331`; после `test_report_outcome_module.py::test_merge_gate_and_suite_run_keys_match_with_tools` — `tests/test_report_outcome_module.py:1656`
- mutation-013: ChecksLocalFromRecordTest::test_record_checks_local_runs_in_acceptance_suite — до `tests/test_component_report_gates.py:392`; после `test_report_outcome_module.py::test_record_checks_local_runs_in_acceptance_suite` — `tests/test_report_outcome_module.py:1716`
- mutation-013: ChecksLocalFromRecordTest::test_merge_gate_without_appendices_runs_record_checks_local — до `tests/test_component_report_gates.py:464`; после `test_report_outcome_module.py::test_merge_gate_without_appendices_runs_record_checks_local` — `tests/test_report_outcome_module.py:1791` (сигнал `Reached` из операнда утверждения, см. «Риски»)
- mutation-014: ChecksLocalFromRecordTest::test_merge_gate_without_appendices_runs_record_checks_local — до `tests/test_component_report_gates.py:464`; после `test_report_outcome_module.py::test_merge_gate_without_appendices_runs_record_checks_local` — `tests/test_report_outcome_module.py:1791` (сигнал `Reached` из операнда утверждения, см. «Риски»)
- mutation-015: AcceptanceSuiteChecksLocalTest::test_check_runs_after_any_source_and_reddens_only_green — до `tests/test_component_report_gates.py:99`; после `test_report_outcome_module.py::test_check_runs_after_any_source_and_reddens_only_green` — `tests/test_report_outcome_module.py:1430`
- mutation-015: ChecksLocalFromRecordTest::test_record_checks_local_runs_in_acceptance_suite — до `tests/test_component_report_gates.py:402`; после `test_report_outcome_module.py::test_record_checks_local_runs_in_acceptance_suite` — `tests/test_report_outcome_module.py:1725`
- mutation-015: ChecksLocalFromRecordTest::test_merge_gate_without_appendices_runs_record_checks_local — до `tests/test_component_report_gates.py:467`; после `test_report_outcome_module.py::test_merge_gate_without_appendices_runs_record_checks_local` — `tests/test_report_outcome_module.py:1794`
- mutation-015: EmptyInstallTest::test_empty_install_neither_installs_nor_refuses — до `tests/test_component_report_gates.py:499`; после `test_report_outcome_module.py::test_empty_install_neither_installs_nor_refuses` — `tests/test_report_outcome_module.py:1824`

«После» патч 015 убивает ещё 7 существующих тестов модуля (test_ac1, test_ac2_*, test_ac3, test_ac4_*, test_ac5) — сверх «до», на доказательство не влияет.

## Числа до и после

- До: crg — 13 тестов, 507 строк; контрольный прогон `mutation-run` №2 — `13 passed, 10 subtests passed in 3.20s` (3,20 с).
- После: модуль — 39 тестовых функций (26 + 13), 41 узел сбора, 1827 строк (было 1344); контрольный прогон `mutation-run` №3 — `41 passed in 10.95s` (10,95 с).
- Под ролью адресно — только `python3 -m pytest tests/test_report_outcome_module.py` (`41 passed in 40.20s`, без xdist).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 (раздел «Патчи мутаций») |
| 2 | 1 (раздел «Мутации до») |
| 3 | 3 (раздел «Соответствие мутаций») |
| 4 | 1, 3 (патч 011 переписан; раздел «Находки»; «Риски» про 014) |
| 5 | 1, 3 (красного контроля не было; ожидание замка — только `--wait-lock`) |
| 6 | 1–3 (временные файлы — только в каталоге документов, удалены) |
| 7 | 2 |
| 8 | 2 (переименований нет) |
| 9 | 2 |
| 10 | 2 |
| 11 | 2 |
| 12 | 2 (дублей нет, «Ловит мутацию:» у всех 13) |
| 13 | 2 |
| 14 | 3 (раздел «Мутации после») |
| 15 | 3 |
| 16 | 2, 3 (раздел «Числа до и после») |
| 17 | 2 |
| 18 | 2 |
| 19 | — (сессия при Операторе) |

## Влияние на систему

Меняются только `tests/test_report_outcome_module.py` (перенос 13 тестов,
тексты сообщений `assert_unknown` и test_ac16), удаление
`tests/test_component_report_gates.py` (мандат ANSWER-1) и вывод генератора
`docs/codebase-map.md`. `orchestrator/`, песочница
`tests/report_outcome_sandbox.py`, переходной модуль и файлы требования 18 не
тронуты. Утверждения перенесены дословно в форме `assert` (ADR-0027),
пределов и `skip`/`xfail` не добавлено; множество убитых мутаций «после»
не меньше «до». Откат — revert merge-коммита задачи.

## Риски

- Мутация 014 (и второй убийца мутации 013): тест
  `test_merge_gate_without_appendices_runs_record_checks_local` ловит её
  так, как устроен с самого crg, — подменённая публикация мержа бросает
  сигнальное исключение теста `Reached` («гейт дошёл до публикации»), и оно
  выходит из операнда первого утверждения `merge(box, case) == ("stopped",)`
  (crg :464 → модуль :1791). Иной формы падения у этой заявки нет: любое
  её воплощение (вызов `_checks_local_refuse` в ветке с приложениями или
  внутри `_full_suite_or_refuse`) доводит гейт до публикации. Это не сбой
  кода пульта (как `TargetsError` первой редакции патча 011), а ожидаемый
  тестом сигнал; поведение «до» и «после» одинаково. Отмечено для
  независимой проверки (требование 19) как оговорка к ANSWER-1 п. 4.

## Предложения системе

- `mutation-run`: в логе прогона патча под xdist заголовки FAILURES не
  всегда связываются с узлом, а строки файл:строка приходится выбирать из
  трассировок руками (сценарий во временном файле) — команде не хватает
  колонки «файл:строка упавшего утверждения» в таблице.
- Замок машины держала параллельная волна 2а-1б: `--wait-lock 4` истёк
  трижды подряд; `mutation-run` с `--wait-lock` до 9 минут при пустом
  `--wait` сэкономил бы повторы.
