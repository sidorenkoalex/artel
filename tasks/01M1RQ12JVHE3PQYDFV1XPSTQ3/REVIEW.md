---
task: 01M1RQ12JVHE3PQYDFV1XPSTQ3
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 4
---

# REVIEW: бриф роли называет артефакты путём от рабочего каталога роли, не от корня пульта

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (AC-1) | OK | `review.py::artifact_text` больше не отдаёт `str(FileNotFoundError)` наружу; AC-1 приёмочный тест зелёный. |
| 2 (AC-2) | OK | `role_cwd_path()` + правка `role_prompt.mission_brief_package` дописывают буквальную строку рабочего каталога во все четыре миссии; AC-2 приёмочный тест зелёный, `role_cwd()` корректно рефакторен на ту же формулу (`workspace.ensure` для self/артели всегда возвращает `workspace.path(task_id)` — та же величина, что и `role_cwd_path`). |
| 3/4 (AC-3..AC-7) | OK по приёмочной планке, НО регрессия существующего набора (см. блокер ниже) | `_missing_required_artifact` + её вызов в `run_agent_once` реализованы верно: проверка на РЕАЛЬНОМ `cwd`, до `commit_step_artifacts` (иначе `shutil.rmtree` уже стёр бы каталог), `or` для analyst (SPEC.md ИЛИ QUESTIONS.md), проверка каталога (не файла) для test_author. Все 5 приёмочных тестов (AC-3..AC-7) зелёные. Но штатная правка сломала непричастные части существующего набора — требование 8/AC-8 нарушено шире заявленного. |
| 8 (AC-8, регрессия) | НЕ выполнено | PLAN заявляет «все зелёные» по списку из ~24 файлов, включая `test_agent_failure`, `test_agent_log`, `test_doctor`, `test_git_fixation`, `test_invariants`, `test_multitarget`, `test_step_cost` — при реальном прогоне все 7 файлов дают 26 упавших тестов (см. блокер ниже). |

## Замечания

- blocker — `orchestrator/runner.py:883` (`_missing_required_artifact`, вызов в `run_agent_once`) — новая проверка обязательного артефакта ломает 26 тестов в 7 файлах существующего набора, не входящих в список из двух файлов, которые developer поправил (`tests/test_agent_prompt.py`, `tests/test_review_package.py`). Причина: эти тесты мокают `spawn_agent`/`FakeProc` с rc=0 для шага developer/reviewer, не сажая на диск `PLAN.md`/`REVIEW.md` — с новой проверкой шаг теперь честно ретраит (`AGENT_ATTEMPTS` раз) вместо одной попытки, и там, где мок настроен как одноразовый `side_effect`-итератор, тест падает `StopIteration`; там, где мок допускает несколько вызовов — падает на `assertEqual(len(claude_calls), 1, …)`. PLAN.md, раздел «Влияние на систему», утверждает: «прогнаны точечно все файлы, реально пересекающиеся с правкой… все зелёные» — этот список ПОИМЁННО включает все 7 файлов ниже, то есть заявленная проверка либо не проводилась, либо проводилась до внесения финальной версии диффа. Полный список упавших тестов (прогнано `python3 -m pytest <файл> -q` на HEAD ветки, каждый воспроизведён и в одиночном прогоне, и в общем; на merge-base `a9ab7291` те же тесты зелёные — регрессия подтверждена, не флейк):
  - `tests/test_agent_failure.py::CmdRunFailureTest::test_retry_succeeds_on_second_attempt`
  - `tests/test_agent_failure.py::CmdRunFailureTest::test_successful_run_behaves_as_before`
  - `tests/test_agent_log.py::CmdRunLoggingTest::test_agent_output_still_printed`
  - `tests/test_agent_log.py::CmdRunLoggingTest::test_broken_log_is_journaled_not_silent`
  - `tests/test_agent_log.py::CmdRunLoggingTest::test_environment_fingerprint_is_journaled_on_start_and_finish`
  - `tests/test_agent_log.py::CmdRunLoggingTest::test_log_path_journaled_at_start`
  - `tests/test_agent_log.py::CmdRunLoggingTest::test_missing_git_during_fingerprint_does_not_change_the_step_outcome`
  - `tests/test_agent_log.py::CmdRunLoggingTest::test_second_run_writes_new_file`
  - `tests/test_agent_log.py::CmdRunLoggingTest::test_stuck_pump_does_not_hang_run`
  - `tests/test_doctor.py::PreflightBlocksMissingTokenTest::test_broken_identity_warns_but_does_not_block_the_step`
  - `tests/test_doctor.py::PreflightBlocksMissingTokenTest::test_token_present_lets_the_step_start`
  - `tests/test_git_fixation.py::ExternalIntegrityIncidentBlocksRunTest::test_clean_state_runs_normally`
  - `tests/test_git_fixation.py::IntegrityIncidentBlocksRunTest::test_clean_unchanged_state_runs_normally`
  - `tests/test_git_fixation.py::FsmDecidesOnlyOnFixedHashesTest::test_mutation_without_the_check_would_run_on_tampered_state`
  - `tests/test_invariants.py::ExhaustedBudgetIsNotBypassableTest::test_only_the_operator_ceiling_unblocks_the_run`
  - `tests/test_invariants.py::ParallelTaskLimitIsNotBypassableTest::test_below_the_ceiling_run_starts`
  - `tests/test_multitarget.py::RoleEnvTest::test_absent_identity_is_journalled_before_the_step`
  - `tests/test_step_cost.py::CmdRunCostTest::test_costs_accumulate_over_steps`
  - `tests/test_step_cost.py::CmdRunCostTest::test_missing_cost_is_warned_but_step_survives`
  - `tests/test_step_cost.py::CmdRunCostTest::test_no_warning_below_the_threshold`
  - `tests/test_step_cost.py::CmdRunCostTest::test_status_and_log_show_the_money`
  - `tests/test_step_cost.py::CmdRunCostTest::test_step_cost_lands_in_spent_and_journal`
  - `tests/test_step_cost.py::CmdRunCostTest::test_step_friction_is_journaled_even_for_a_clean_step`
  - `tests/test_step_cost.py::CmdRunCostTest::test_step_friction_lands_in_journal_from_the_live_stream`
  - `tests/test_step_cost.py::CmdRunCostTest::test_task_without_budget_is_not_blocked`
  - `tests/test_step_cost.py::CmdRunCostTest::test_warning_at_seventy_percent`

  Предложение: применить тот же приём, что уже применён в `tests/test_agent_prompt.py`/`tests/test_review_package.py` (сидировать обязательный артефакт роли на диске рабочего каталога перед `cmd_run`/`spawn_agent`-моком), ко всем перечисленным файлам/тестам — либо завести общий helper в `tests/sandbox.py`, если список разрастётся дальше, чтобы не чинить один и тот же класс россыпью по файлам семь раз подряд.

- major — `docs/codebase-map.md` не регенерирована после добавления публичной функции `role_cwd_path` в `orchestrator/runner.py` (conventions-core: «правишь `*.py` в orchestrator/… — регенерируй карту тем же коммитом»). Прогон `python3 scripts/codebase_map.py` на ветке реально меняет файл (не только `built_at_sha` — сверено `grep -v '^built_at_sha:'` до/после): добавляется строка `role_cwd_path` в перечень `orchestrator/runner.py`. CI-джоb `codebase-map` (`.github/workflows/ci.yml:213-246`) сравнивает содержимое без `built_at_sha` и покраснеет на этом диффе. Предложение: `python3 scripts/codebase_map.py` и закоммитить результат тем же MR.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | fixed | orchestrator/runner.py:883 (+ 7 файлов tests/, список выше) | Новая проверка обязательного артефакта ломает 26 тестов существующего набора вне двух починенных файлов | AC-8 нарушено шире заявленного, PLAN содержит недостоверное «все зелёные» по этим файлам | Во всех 7 файлах на диск рабочего каталога роли теперь сидируется обязательный артефакт роли ПЕРЕД прогоном шага (тем же приёмом, что уже несут `test_agent_prompt.py`/`test_review_package.py`): `test_agent_failure.py` (`_STEP_ARTIFACT` по текущему состоянию задачи в `run_agent()`), `test_agent_log.py`/`test_doctor.py`/`test_step_cost.py` (сидирование PLAN.md один раз в `setUp` — класс всегда в `in_dev`), `test_multitarget.py::RoleEnvTest` (маркер в `config.TASKS/<id>/` — этот класс подменяет `workspace.ensure` на `self.root`, не на `config.WORKTREES`), `test_invariants.py` (новый общий хелпер `FsmTest.seed_worktree_plan()` — маркер в `config.WORKTREES/<id>/tasks/<id>/`, отдельно от `self.tdir`, откуда читает FSM/бриф), `test_git_fixation.py` (PLAN.md добавлен в СОДЕРЖИМОЕ коммита артефактной ветки — `make_task`/`enter_in_dev`, а не только на диск репо фиксации: у этих двух классов `runner.role_cwd` — настоящий git, `materialize_task_dir` стирает с диска любой файл, которого нет в ветке, поэтому сидирование мимо ветки не пережило бы материализацию). По ходу правки `test_agent_log.py::test_environment_fingerprint_is_journaled_on_start_and_finish` вскрыла отдельный латентный дефект теста (не продакшн-кода): её собственный `mock.patch.object(agent_log.subprocess, "run", ...)` патчит АТРИБУТ ОБЩЕГО модуля `subprocess`, попадая и под `gitcmd.check_ignore` — раньше это было незаметно (коммитить было нечего, `check_ignore` не вызывался), с сидированным PLAN.md автокоммит шага стал реально коммитить файл и звать `check_ignore`, получая от чужого мока текстовый `CompletedProcess` вместо байтового и падая `TypeError`; сузил `fake_run` теста до точного совпадения `["git", "--version"]`/`["claude", "--version"]`, всё остальное делегируется в `self.git_spy` (тот же `SpyRun`, что уже стоит в `TmpRootTest.setUp`). Полный перечень из замечания прогнан заново — все 26 тестов и весь набор из 19 файлов, что и в первой итерации, зелёные (см. «Проверено исполнением») |
| R1-F2 | fixed | docs/codebase-map.md | Карта не регенерирована после добавления `role_cwd_path` в orchestrator/runner.py | CI-джоб codebase-map покраснеет на этом диффе (свежесть карты — гейт) | `python3 scripts/codebase_map.py` прогнан и закоммичен — `role_cwd_path` теперь в перечне публичных функций `orchestrator/runner.py`, `built_at_sha` обновлён на голову ветки |

## Вердикт

changes_requested — R1-F1 (регрессия существующего набора тестов, 26 упавших) и R1-F2 (не регенерирована карта кодовой базы). Сама логика трёх требований SPEC (AC-1..AC-7) реализована верно и подтверждена приёмочной планкой — доработка точечная, не архитектурная.

## Проверено исполнением

- `python3 -m pytest tasks/01M1RQ12JVHE3PQYDFV1XPSTQ3/acceptance_tests/test_role_cwd_in_prompt.py tasks/01M1RQ12JVHE3PQYDFV1XPSTQ3/acceptance_tests/test_step_finishes_without_artifact.py -v` — 7 тестов (12 subtests), все зелёные.
- `python3 -m pytest tests/test_brief.py tests/test_agent_prompt.py tests/test_review_package.py tests/test_review_freshness.py tests/test_acceptance_tests_flow.py -q` — 200 passed, 6 subtests passed.
- `python3 -m pytest tests/test_advance_refusal_history.py tests/test_agent_failure.py tests/test_agent_log.py tests/test_analyst_role.py tests/test_auto_cycle.py tests/test_canary.py tests/test_checkpoint_external_step_artifacts.py tests/test_diff_not_collected_alerts.py tests/test_doctor.py tests/test_failure_classification.py tests/test_git_fixation.py tests/test_invariants.py tests/test_lease_pgid_store.py tests/test_multitarget.py tests/test_multitarget_invariants.py tests/test_step_autocommit.py tests/test_step_cost.py tests/test_step_refixation.py tests/test_timeout_checkpoint.py -q` — 26 failed, 564 passed, 294 subtests passed (полный список упавших — в замечании R1-F1).
- `python3 -m pytest tests/test_agent_failure.py -q` и `tests/test_doctor.py::PreflightBlocksMissingTokenTest -q` — повторно в одиночном прогоне на этой ветке (то же падение) и на merge-base `a9ab7291e2fc8108a59bccba6a402aae338ebd25` через временный `git worktree add /tmp/artel-mainbase-check` (28 passed, чисто) — регрессия подтверждена диффом этой задачи, не флейк/пересечением тестов; временный worktree удалён (`git worktree remove --force`).
- `python3 scripts/guard.py tasks/01M1RQ12JVHE3PQYDFV1XPSTQ3/SPEC.md tasks/01M1RQ12JVHE3PQYDFV1XPSTQ3/PLAN.md` — «GUARD: ок (2 файлов)».
- `python3 scripts/codebase_map.py` — воспроизвёл дефект R1-F2 (файл реально меняется за пределами `built_at_sha`); после проверки `docs/codebase-map.md` возвращён в состояние ветки (`git checkout -- docs/codebase-map.md`), рабочее дерево ревью не изменено.
- Чтение кода вне пакета: `orchestrator/review.py`, `orchestrator/role_prompt.py`, `orchestrator/runner.py` (все три — предмет диффа, точечно проверены места из PLAN), `orchestrator/workspace.py::path/ensure` (проверка совпадения `role_cwd_path` и `role_cwd` для self/артели), `orchestrator/brief.py` (проверка, что зона `brief.py` из `zones:` действительно не несёт того же класса утечки — вне рамок этой задачи, отдельно не заведено замечанием).

## Предложения системе

- Класс «тест гоняет агентский шаг через `FakeProc` без сидирования обязательного артефакта роли» задел не 2, а минимум 9 файлов теста (developer сам предупредил об этом классе в PLAN «Предложения системе», но обнаружил и починил не весь периметр) — стоит завести общий helper в `tests/sandbox.py` для сидирования артефакта по роли/состоянию, если задача, вводящая обязательные проверки такого рода, повторится ещё раз.
