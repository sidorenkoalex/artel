---
task: 01M48WR0HKZW8KJCBWDZTFC4ZY
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: tests/sandbox.py, tests/test_agent_prompt.py, tests/test_review_freshness.py, tests/, docs/codebase-map.md
budget_usd: 30
---

# SPEC: Тесты не спят в паузе повтора агента (ревизия тестов TR-1, TR-26)

## Контекст
`orchestrator/runner.py::_run_attempts` между попытками агента вызывает
`time.sleep(backoff_sec)`: пауза — `config.RETRY_BACKOFF_SEC * 2 ** (attempt - 1)`
(`RETRY_BACKOFF_SEC = 5`) либо `config.TRANSIENT_SYSTEM_BACKOFF_SEC` (120) для
системных классов сбоя; при `AGENT_ATTEMPTS = 3` неуспешный шаг в песочнице
ждёт 5 + 10 с. Ревизия тестов 05.10 (`docs/audits/tests-revision-2026-10-05.md`,
TR-1, TR-26, план п. 1) показала профилем: 12 самых медленных тестов набора
(≈ 244 с работы процессов из ~1 065) почти целиком спят в этой паузе.
`tests/sandbox.py::patch_pult_sleep` уже подменяет `time.sleep` пульта, но
пауза повтора в умолчании песочницы не снята. Из 12 тестов 5 стоят на
`TmpRootTest`, 2 — на голом `unittest.TestCase`
(`tests/test_agent_prompt.py::PromptChannelTest`,
`tests/test_review_freshness.py::ReviewFreshnessScenarioTest`), 3 — в
защищённом `tests/test_invariants.py` (`FsmTest`).

Двенадцать тестов ревизии (таблица мест 1–12 ревизии):
1. `tests/test_invariants.py::MergeOnlyFromMergeGateTest::test_no_other_state_and_no_other_command_merges`
2. `tests/test_invariants.py::AgentRunsOnlyFromRunTest::test_run_starts_the_agent_only_in_working_states`
3. `tests/test_multitarget_invariants.py::ExternalWorkspaceIsolationTest::test_external_target_cwd_is_its_workspace`
4. `tests/test_multitarget_invariants.py::ExternalWorkspaceIsolationTest::test_pult_root_marker_is_unreachable_from_external_workspace_cwd`
5. `tests/test_multitarget.py::RoleEnvTest::test_agent_process_gets_that_environment`
6. `tests/test_multitarget.py::ProgramSpendTest::test_a_step_run_is_what_moves_the_program_counter`
7. `tests/test_review_freshness.py::ReviewFreshnessScenarioTest::test_reviewer_prompt_asks_for_next_iteration`
8. `tests/test_multitarget_invariants.py::ExternalWorkspaceIsolationTest::test_dogfood_cwd_is_its_worktree`
9. `tests/test_invariants.py::FreshVerdictGuardsAcceptanceTest::test_stale_verdict_is_not_passed_by_any_command`
10. `tests/test_agent_log.py::CmdRunLoggingTest::test_second_run_writes_new_file`
11. `tests/test_analyst_role.py::RunAnalystTest::test_run_starts_analyst_when_tz_present`
12. `tests/test_agent_prompt.py::PromptChannelTest::test_the_prompt_is_not_echoed_to_the_terminal`

## Требования

1. В песочнице `tests/sandbox.py` пауза повтора агента по умолчанию не спит —
   подмена тем же приёмом, что `patch_pult_sleep`: тест, который проходит шаг
   роли с неуспешной попыткой, не ждёт ни `RETRY_BACKOFF_SEC`, ни
   `TRANSIENT_SYSTEM_BACKOFF_SEC`.
2. Тест, которому нужна настоящая пауза повтора или её длительность,
   получает её явным отказом от подмены песочницы.
3. В `tests/test_agent_prompt.py` (`PromptChannelTest`) и
   `tests/test_review_freshness.py` (`ReviewFreshnessScenarioTest`) — классах
   на голом `unittest.TestCase` — пауза повтора снята точечной подменой в
   файле.
4. Три теста `FsmTest` в `tests/test_invariants.py` (места 1, 2, 9 перечня:
   классы `MergeOnlyFromMergeGateTest`, `AgentRunsOnlyFromRunTest`,
   `FreshVerdictGuardsAcceptanceTest` — наследники `FsmTest`) снимают паузу
   только приложением к PLAN: защищённый путь правит только Оператор,
   разработчик пишет в PLAN точный дифф к `tests/test_invariants.py`. Рубеж
   `in_dev -> verifying` гоняет планку и долгоживущие файлы без приложений
   PLAN (`orchestrator/advance_gates/acceptance.py::_acceptance_run_body`),
   поэтому приложение проверяется статически, не исполнением
   `tests/test_invariants.py` с наложенным диффом (решение Оператора 06.10).
5. Утверждения существующих тестов не меняются.
6. Время прогона тестами не утверждается (решение Оператора 06.10: под
   параллельной нагрузкой тесты идут в 4–5 раз дольше, утверждение времени
   даёт ложные красные планки). Снятие паузы проверяется детерминированным
   признаком: тест проходит без вызова настоящего `time.sleep` пульта на паузу
   повтора (подмена фиксирует вызовы сна, длительность паузы не ждётся).
   Замер «имя, было, стало» по 12 тестам ревизии — в PLAN таблицей как
   сведения, не как критерий приёмки.
7. Сторож — тест в `tests/` с заявкой «Ловит мутацию»: шаг роли в песочнице с
   неуспешной попыткой не вызывает настоящий `time.sleep` пульта на паузу
   повтора; мутация — подмена в песочнице снята, тест красный.
8. Тесты, проверяющие саму паузу (`tests/test_agent_failure.py`, явная
   подмена `RETRY_BACKOFF_SEC`), не меняются.
9. Строки бэклога 05.10 о дроблении перебора инвариантов и о «слепке
   окружения» (неверная причина медленных тестов, ревизия TR-1) названы в
   PLAN, раздел «Предложения системе», для снятия Оператором.

## Критерии приёмки

AC-1. Тест на `TmpRootTest` без явного отказа от подмены, проходящий шаг роли
с неуспешной попыткой агента, не вызывает настоящий `time.sleep` на паузу
повтора длительностью `RETRY_BACKOFF_SEC * 2 ** (attempt - 1)` или
`TRANSIENT_SYSTEM_BACKOFF_SEC`.

AC-2. Тест песочницы, явно отказавшийся от подмены, получает паузу повтора
настоящей длительности (вызов сна пульта с прежним значением паузы).

AC-3. `tests/test_agent_prompt.py::PromptChannelTest::test_the_prompt_is_not_echoed_to_the_terminal`
и `tests/test_review_freshness.py::ReviewFreshnessScenarioTest::test_reviewer_prompt_asks_for_next_iteration`
проходят зелёными без вызова настоящего `time.sleep` пульта на паузу повтора
агента: подмена фиксирует вызовы сна, длительность паузы не ждётся. Время
прогона не утверждается.

AC-4. PLAN несёт приложение — точный дифф к `tests/test_invariants.py`;
проверка статическая, без исполнения `tests/test_invariants.py` с наложенным
приложением: (а) приложение применяется к дереву ветки (`git apply --check`);
(б) разбор текста приложения показывает, что дифф снимает паузу повтора в
`FsmTest` либо в каждом из классов `MergeOnlyFromMergeGateTest`,
`AgentRunsOnlyFromRunTest`, `FreshVerdictGuardsAcceptanceTest`.

AC-5. Тесты мест 3, 4, 5, 6, 8, 10, 11 перечня «Контекста» (вне
`tests/test_invariants.py`) проходят зелёными без вызова настоящего
`time.sleep` пульта на паузу повтора агента: подмена фиксирует вызовы сна,
длительность паузы не ждётся. Время прогона не утверждается.

AC-6. Утверждения существующих тестовых методов `tests/` не изменены, файл
`tests/test_agent_failure.py` в диффе ветки не изменён.

AC-7. В `tests/` есть тест-сторож с заявкой «Ловит мутацию» в докстринге:
шаг роли в песочнице с неуспешной попыткой не вызывает настоящий
`time.sleep` пульта на паузу повтора; при снятой подмене в песочнице он
красный.

AC-8. Раздел «Предложения системе» PLAN называет строку бэклога 05.10 о
дроблении перебора инвариантов и строку о «слепке окружения» как неверную
причину медленных тестов (ревизия TR-1) — для снятия Оператором.

## Не входит

- Изменение значений `RETRY_BACKOFF_SEC`, `TRANSIENT_SYSTEM_BACKOFF_SEC`,
  `AGENT_ATTEMPTS` и поведения пульта (`orchestrator/runner.py`,
  `orchestrator/config.py` — только чтение); правка рубежа приёмки
  `orchestrator/advance_gates/acceptance.py` (только чтение).
- Прямая правка `tests/test_invariants.py` в ветке — только приложением к PLAN;
  исполнение `tests/test_invariants.py` с наложенным приложением тестами
  планки и долгоживущими файлами (рубеж `in_dev -> verifying` идёт без
  приложений PLAN).
- Утверждение времени прогона тестов (порог «не дольше N с») — ни в
  критериях, ни в тестах; замер «имя, было, стало» в PLAN — сведения.
- Вынос прочей подготовки песочницы (отдельная задача TR-23..25).
- Сведение методов.
- Правка `docs/backlog.md` — строки бэклога только называются в PLAN, снимает
  их Оператор.
- Только чтение: `docs/audits/tests-revision-2026-10-05.md`, `conftest.py`,
  `docs/invariants.md`, `docs/adr/`, `docs/roadmap.md`,
  `docs/operator-session.md`, `templates/`, `skills/`, `CLAUDE.md`,
  `models.yaml`, `roles.yaml`, `targets.yaml`, `.github/workflows/ci.yml`.

## Материалы

- `docs/audits/tests-revision-2026-10-05.md` — TR-1 (профиль, таблица мест
  1–12), TR-26, план п. 1.
- `tests/sandbox.py::patch_pult_sleep`, `tests/sandbox.py::TmpRootTest`.
- `orchestrator/runner.py::_run_attempts`.
