---
task: 01M48WR0HKZW8KJCBWDZTFC4ZY
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Тесты не спят в паузе повтора агента (ревизия тестов TR-1)

# ТЗ: тесты не спят в паузе повтора агента (ревизия тестов 05.10, TR-1, TR-26)

Источник: ревизия тестов 05.10 (`docs/audits/tests-revision-2026-10-05.md`,
TR-1, TR-26, план п. 1); строка бэклога «Тесты: подмена паузы повтора
агента в песочнице». Решение Оператора 06.10: завести первой из задач
ускорения набора.

Факты (пин 73ce3329, сверка кода 06.10):
- `orchestrator/runner.py::_run_attempts` (~780) — `time.sleep(backoff_sec)`
  между попытками агента; пауза — `config.RETRY_BACKOFF_SEC * 2 ** (attempt
  - 1)` (`config.RETRY_BACKOFF_SEC = 5`, ~223) либо
  `config.TRANSIENT_SYSTEM_BACKOFF_SEC` (120, ~230) для системных классов
  сбоя. При `AGENT_ATTEMPTS = 3` неуспешный шаг в песочнице ждёт 5 + 10 с.
- Профиль ревизии: 12 самых медленных тестов набора (≈ 244 с работы
  процессов из ~1 065, два по 45 с и десять по 15 с) почти целиком спят в
  этой паузе, например
  `tests/test_agent_prompt.py::PromptChannelTest::test_the_prompt_is_not_echoed_to_the_terminal`
  (15,57 с, из них `time.sleep` — 15,004 с) и
  `tests/test_invariants.py::MergeOnlyFromMergeGateTest::test_no_other_state_and_no_other_command_merges`
  (46,88 с, из них сна 45,01 с).
- `tests/sandbox.py::patch_pult_sleep` (~481) уже подменяет `time.sleep`
  пульта; `TmpRootTest` (~1302) — основание 5 из 12 тестов; 2 стоят на
  голом `unittest.TestCase` (`tests/test_agent_prompt.py::PromptChannelTest`,
  `tests/test_review_freshness.py::ReviewFreshnessScenarioTest`); 3 — в
  защищённом `tests/test_invariants.py` (`FsmTest`, ~147).
- Сами паузы проверяет `tests/test_agent_failure.py` (явная подмена
  `RETRY_BACKOFF_SEC`) — эти тесты не меняются.

Требуется:
1. В песочнице `tests/sandbox.py` пауза повтора агента по умолчанию не
   спит (подмена тем же приёмом, что `patch_pult_sleep`): тест, который
   проходит шаг роли с неуспешной попыткой, не ждёт `RETRY_BACKOFF_SEC` и
   `TRANSIENT_SYSTEM_BACKOFF_SEC`. Тест, которому нужна настоящая пауза или
   её длительность, получает её явным отказом от подмены.
2. Точечная подмена в `tests/test_agent_prompt.py` и
   `tests/test_review_freshness.py` (классы на голом `unittest.TestCase`).
3. Три теста `FsmTest` в `tests/test_invariants.py` — приложением к PLAN
   (защищённый путь, правит только Оператор): разработчик пишет точный дифф
   в PLAN.
4. Утверждения существующих тестов не меняются; каждый из 12 тестов ревизии
   после правки идёт не дольше 3 с (замер в PLAN: имя, было, стало).
5. Сторож — тест в `tests/` с заявкой «Ловит мутацию»: шаг роли в песочнице
   с неуспешной попыткой не вызывает настоящий `time.sleep` пульта на паузу
   повтора (мутация: подмена в песочнице снята — тест красный).
6. Строки бэклога 05.10 о дроблении перебора инвариантов и о «слепке
   окружения» (неверная причина медленных тестов, ревизия TR-1) — назвать в
   PLAN, раздел «Предложения системе», для снятия Оператором.

Зоны: tests/sandbox.py, tests/test_agent_prompt.py,
tests/test_review_freshness.py, tests/, docs/codebase-map.md.

Приложением: tests/test_invariants.py

Только чтение (не менять): docs/audits/tests-revision-2026-10-05.md,
orchestrator/runner.py, orchestrator/config.py,
conftest.py, docs/invariants.md, docs/adr/, docs/roadmap.md,
docs/backlog.md, docs/operator-session.md, templates/, skills/, CLAUDE.md,
models.yaml, roles.yaml, targets.yaml, .github/workflows/ci.yml.

Не входит: изменение значений `RETRY_BACKOFF_SEC`,
`TRANSIENT_SYSTEM_BACKOFF_SEC`, `AGENT_ATTEMPTS` и поведения пульта;
вынос прочей подготовки песочницы (отдельная задача TR-23..25); сведение
методов.

Рамка: $30.
