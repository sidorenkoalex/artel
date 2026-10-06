---
task: 01M48WR0HKZW8KJCBWDZTFC4ZY
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Тесты не спят в паузе повтора агента (ревизия тестов TR-1, TR-26)

## Подход
Пауза повтора `orchestrator/runner.py::_run_attempts` (`time.sleep(backoff_sec)`)
снимается в тестах тем же приёмом, что `patch_pult_sleep`: ссылка `runner.time`
заменяется заместителем `TimeWithSleep`, у которого `sleep` только записывает
длительность. Код пульта и значения `config` не меняются: тест, ставящий свою
подмену сна `runner` (`tests/test_agent_failure.py`), ложится поверх умолчания
и видит прежние длительности паузы.

- `tests/sandbox.py`: новая `patch_retry_pause(pauses)` (= `patch_sleep(runner,
  pauses.append)`); `TmpRootTest.setUp` накладывает её по умолчанию, пишет паузы
  в `self.retry_pauses`; явный отказ — атрибут класса `REAL_RETRY_PAUSE = True`.
- `patch_pult_sleep` теперь подменяет и модуль, чья ссылка `time` уже
  заместитель `TimeWithSleep`: иначе внутри `TmpRootTest` она пропустила бы
  `runner` (условие было `module.time is time`), и пауза `runner` ушла бы мимо
  счётчика теста (`tests/test_invariants.py:719`, профиль-сторожа
  `tests/test_01m45fjvgqt1k0p8hdexzx6hs7_profile_refusals.py`).
- `tests/test_agent_prompt.py::PromptChannelTest`,
  `tests/test_review_freshness.py::ReviewFreshnessScenarioTest` (голый
  `TestCase`) — точечный `patch_retry_pause` в `setUp`.
- `tests/test_invariants.py::FsmTest` — тот же точечный приём, только
  приложением ниже (защищённый путь).

## Шаги
1. `tests/sandbox.py`: `patch_retry_pause`, умолчание `TmpRootTest` с
   `REAL_RETRY_PAUSE`, `patch_pult_sleep` поверх заместителя.
2. Точечная подмена в `tests/test_agent_prompt.py` и `tests/test_review_freshness.py`.
3. Сторожа `tests/test_sandbox_retry_pause.py` (свойства, не покрытые
   долгоживущим `tests/test_01m48wr0hkzw8kjcbwdztfc4zy_retry_pause.py`):
   умолчание пишет паузу вместо сна; явный отказ флагом оставляет настоящий
   `time`; `patch_pult_sleep` перекрывает умолчание и возвращает его на
   `close()`; оба голых класса после `setUp` держат паузу подменённой.
4. Приложение к `tests/test_invariants.py` (ниже) для `FsmTest`.
5. Регенерация `docs/codebase-map.md`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 (флаг `REAL_RETRY_PAUSE`; своя подмена сна `runner` поверх умолчания) |
| 3 | 2 |
| 4 | 4 |
| 5 | утверждения существующих методов не тронуты (правки только в `setUp`/помощниках) |
| 6 | 3 + таблица замеров ниже (сведения) |
| 7 | 3 + долгоживущий файл задачи |
| 8 | `tests/test_agent_failure.py` не меняется |
| 9 | «Предложения системе» |

### Проверка сторожей временной мутацией (каждая снята после прогона)
Прогон `tests/test_sandbox_retry_pause.py` + долгоживущий файл задачи:
- `REAL_RETRY_PAUSE = True` по умолчанию (подмена снята) — красные
  `test_default_records_pause_instead_of_sleeping`, долгоживущие `test_ac1_*`
  (оба подтеста) и `test_ac7_*`;
- флаг игнорируется (`if True:`) — красный `test_opt_out_keeps_the_real_sleep`;
- `patch_pult_sleep` без ветки заместителя — красный
  `test_pult_sleep_patch_overrides_the_default`;
- подмена убрана из `setUp` `test_agent_prompt.py` / `test_review_freshness.py`
  — красный подтест своего класса в `test_plain_sandboxes_patch_the_retry_pause`.

### Прогоны
- `python3 -m pytest tests/test_01m48wr0hkzw8kjcbwdztfc4zy_retry_pause.py
  tests/test_sandbox_time_with_sleep.py tests/test_agent_prompt.py
  tests/test_review_freshness.py tests/test_agent_failure.py
  tests/test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard.py tests/test_sandbox.py
  tests/test_sandbox_retry_pause.py` — зелёные.
- `tests/test_invariants.py` с наложенным локально приложением (затем снято
  `git checkout`) — 74 passed, 215 subtests passed (сведения; рубеж его не
  исполняет).
- `artel.py suite-run 01M48WR0HKZW8KJCBWDZTFC4ZY` №1 (без приложений): прошло
  4541, упало 1, пропущено 2; база не посчитана (прогон базы красный).
  Упавший — `tests/test_liveness.py::TerminateProcessGroupTest::test_kills_the_leader_and_returns_a_positive_count`
  (`0 not greater than or equal to 1`): `tests/sandbox.py` он не импортирует
  и падает так же с базовой `tests/sandbox.py` (проверено локально) —
  окружение шага роли, не эта правка. `--failed` отказал: замок полного
  прогона держала другая задача.
- `plank-run`: AC-4 и AC-8 красные только из-за `PLAN.md`, которого ещё нет в
  ссылке документов (его переносит автокоммит после шага); тексты проверок с
  этим PLAN сверены вручную, приложение разобрано `guard.plan_appendices`
  (1 приложение, 0 ошибок) и `git apply --check` — rc 0.

### Замер 12 тестов ревизии (сведения, не критерий приёмки)
`pytest --durations`, один процесс, локально 06.10; «было» — `tests/sandbox.py`,
`test_agent_prompt.py`, `test_review_freshness.py` из базы ветки и
`test_invariants.py` без приложения; «стало» — ветка + приложение.

| № | Тест | было, с | стало, с |
|---|---|---|---|
| 1 | test_invariants.py::MergeOnlyFromMergeGateTest::test_no_other_state_and_no_other_command_merges | 45.71 | 0.59 |
| 2 | test_invariants.py::AgentRunsOnlyFromRunTest::test_run_starts_the_agent_only_in_working_states | 45.29 | 0.21 |
| 3 | test_multitarget_invariants.py::ExternalWorkspaceIsolationTest::test_external_target_cwd_is_its_workspace | 16.08 | 1.28 |
| 4 | test_multitarget_invariants.py::ExternalWorkspaceIsolationTest::test_pult_root_marker_is_unreachable_from_external_workspace_cwd | 15.37 | 0.33 |
| 5 | test_multitarget.py::RoleEnvTest::test_agent_process_gets_that_environment | 15.17 | 0.12 |
| 6 | test_multitarget.py::ProgramSpendTest::test_a_step_run_is_what_moves_the_program_counter | 15.14 | 0.11 |
| 7 | test_review_freshness.py::ReviewFreshnessScenarioTest::test_reviewer_prompt_asks_for_next_iteration | 15.19 | 0.16 |
| 8 | test_multitarget_invariants.py::ExternalWorkspaceIsolationTest::test_dogfood_cwd_is_its_worktree | 15.12 | 0.11 |
| 9 | test_invariants.py::FreshVerdictGuardsAcceptanceTest::test_stale_verdict_is_not_passed_by_any_command | 15.29 | 0.15 |
| 10 | test_agent_log.py::CmdRunLoggingTest::test_second_run_writes_new_file | 15.18 | 0.15 |
| 11 | test_analyst_role.py::RunAnalystTest::test_run_starts_analyst_when_tz_present | 15.13 | 0.10 |
| 12 | test_agent_prompt.py::PromptChannelTest::test_the_prompt_is_not_echoed_to_the_terminal | 15.16 | 0.09 |

Итого 12 тестов: 244.06 с → 3.67 с.

## Влияние на систему
- Код пульта (`orchestrator/`) не меняется; значения `RETRY_BACKOFF_SEC`,
  `TRANSIENT_SYSTEM_BACKOFF_SEC`, `AGENT_ATTEMPTS` прежние. Тесты самой паузы
  (`tests/test_agent_failure.py`, своя `patch_sleep(runner, …)`) не меняются и
  видят прежние длительности — подмена теста ложится поверх умолчания.
- Подмена — заместитель ссылки `runner.time`, не `time.sleep` процесса:
  сторож `tests/test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard.py` зелёный.
- `patch_pult_sleep` расширена, не сужена: модули с настоящим `time` она
  подменяет как прежде, плюс модули с заместителем песочницы.
- Утверждения существующих методов не тронуты; новых методов-удалений нет.
- Откат — revert коммита ветки; приложение Оператор просто не накладывает.

## Риски
- Тест на `TmpRootTest`, которому нужна настоящая пауза повтора, теперь
  должен заявить `REAL_RETRY_PAUSE = True`; в наборе такого не нашлось
  (`grep` по `runner.time`/`patch_sleep(runner` — все прочие подменяют сон
  сами). Полный набор — `suite-run`, итог в «Прогоны» выше.

## Приложение: tests/test_invariants.py — пауза повтора в FsmTest
Снимает паузу повтора в `FsmTest.setUp` — общей песочнице
`MergeOnlyFromMergeGateTest`, `AgentRunsOnlyFromRunTest`,
`FreshVerdictGuardsAcceptanceTest` (места 1, 2, 9). `git apply --check` на
чистом дереве ветки — проходит.

```diff
diff --git a/tests/test_invariants.py b/tests/test_invariants.py
index 160eee73..ec0f457d 100644
--- a/tests/test_invariants.py
+++ b/tests/test_invariants.py
@@ -42,7 +42,7 @@ from scripts import guard  # noqa: E402
 from tests.sandbox import (FakeProc, SpyRun, TmpRootTest, _stub_check_stack,  # noqa: E402
                            capture, capture_new_task_id,
                            disk_backed_ls_tree_files, disk_backed_show,
-                           patch_pult_sleep, patch_sleep,
+                           patch_pult_sleep, patch_retry_pause, patch_sleep,
                            resilient_tmp_cleanup, seed_artel_targets)
 
 REPO_ROOT = Path(__file__).resolve().parent.parent
@@ -278,6 +278,13 @@ class FsmTest(unittest.TestCase):
             lambda role, target: [])
         pf_patcher.start()
         self.addCleanup(pf_patcher.stop)
+        # Пауза повтора агента без сна — тот же приём, что умолчание
+        # `tests.sandbox.TmpRootTest.setUp` (SPEC 01M48WR0HKZW8KJCBWDZTFC4ZY):
+        # класс на голом `TestCase` его не наследует.
+        self.retry_pauses = []
+        pause_patcher = patch_retry_pause(self.retry_pauses)
+        pause_patcher.start()
+        self.addCleanup(pause_patcher.stop)
 
         self.set_ci(GREEN_CI)
 
```

## Предложения системе
- Снять Оператором две строки бэклога (ревизия тестов TR-1; в аудите они
  названы `docs/backlog.md:235`/`:236`, на базе ветки — строки 274 и 275):
  «Два теста инвариантов по 45 с — перебор на подтесты для xdist» (дробление
  перебора лечит не причину: после снятия паузы тесты идут 0.2–0.6 с) и
  «Десять тестов по 15 с: слепок окружения шага в песочнице» (неверная
  причина — время уходило в паузу повтора `runner`, не в слепок окружения).
- Адресация строк бэклога номером строки (`docs/backlog.md:235`) в аудите
  устаревает за неделю — строки сместились на 39; ссылаться на заголовок строки.
- `tests/test_liveness.py::TerminateProcessGroupTest::test_kills_the_leader_and_returns_a_positive_count`
  красный в окружении шага роли и на базе (`terminate_process_group` вернул 0)
  — `suite-run` без посчитанной базы не отделяет такое падение от регресса ветки.
