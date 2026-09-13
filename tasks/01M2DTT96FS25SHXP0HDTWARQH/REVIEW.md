---
task: 01M2DTT96FS25SHXP0HDTWARQH
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Модель роли из roles.yaml — флаг --model в команде запуска и модель в журнале шага

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 — необязательное поле `model` в roles.yaml по 4 agent-ролям, правка только unified diff'ом | OK | `tasks/01M2DTT96FS25SHXP0HDTWARQH/roles-yaml.patch` — не применён к рабочему `roles.yaml` этой веткой (подтверждено `git diff … -- roles.yaml` — пусто), `git apply --check` на чистом дереве пройден мной повторно. `developer`/`reviewer` → `claude-opus-5`, `analyst`/`test_author` → `claude-sonnet-5` — соответствует решению Оператора 13.09 (AC-9). |
| 2 — `roles.model(role) -> str \| None` | OK | `orchestrator/roles.py:74-92`: `None` на отсутствии поля, `RolesError` тем же приёмом, что `skills()`, на не-строке/пустой строке (AC-1/AC-2). Покрыто `tests/test_yaml_parsing.py::RolesModelTest` (4 теста, все с докстрингом «Ловит мутацию»). |
| 3 — флаг `--model <id>` в команде шага, если задан; без флага, если нет | OK | `orchestrator/runner.py:1045-1047` — довесок СНАРУЖИ `role_cmd()` (сигнатура залочена AC-7 `tasks/01M2CN3ZCSZ54TFJGTDCXTDHXD`), не переставляет существующие 5 флагов. Подтверждено прогоном локального `test_ac7_locked_public_surface.py` (не тронут) и `tests/test_runner_role_model.py::test_command_carries_the_model_flag_once_in_prior_flag_order`. |
| 4 — предупреждение «модель роли не задана — дефолт CLI» ровно один раз на шаг, не блокирует | OK | `orchestrator/runner.py:390-397` (`_refuse_before_start`, вызывается один раз на шаг, до цикла попыток) — `store.journal(..., "model WARNING", …)`. Покрыто `test_command_has_no_model_flag_and_warns_once_when_unset`: ровно одна запись, шаг не FAILED/SKIPPED/TIMEOUT. |
| 5 — «agent run started» несёт `model=<id>`/`model=дефолт CLI` | OK | `orchestrator/runner.py:1007-1009` (`_prepare_step`). Покрыто `test_run_started_journal_carries_the_model` и `test_run_started_journal_uses_the_default_marker_when_unset`. |
| 6 — «agent cost KNOWN»/«agent cost PARTIAL» несут тот же `model=`, без правки `spend.py` | OK | `_account_step` (`orchestrator/runner.py:1106-1155`) дополняет параметр `numbered`, который `spend.py` дословно вставляет в свою запись, ТОЛЬКО когда локально повторённое условие совпадает с веткой KNOWN (`pump.cost.get("tokens_by_type")`, зеркало `charge_step`) или PARTIAL (`_cost_partial_expected` зовёт `spend.partial_cost_usd` напрямую — не копирует арифметику курса, только ветвление). Прогнал `tests/test_step_cost.py` — 100% зелёный, включая `test_missing_cost_is_warned_but_step_survives` (точная сверка «agent cost UNKNOWN» без `model=`, как и требует SPEC). `spend.py` действительно не тронут (вне diff). |
| 6 (status/report/канарейка) | OK | `git diff --stat` не касается `status.py`/`report.py`. `tests/test_canary.py` зелёный без правки `canary.py` — отсутствие поля `model` у роли не ломает прогон канарейки. |

## Замечания

<Пусто — 0 blocker/major/minor.>

## Реестр замечаний

<Пусто — замечаний в этой итерации не заведено.>

## Вердикт

approved

## Проверено исполнением

- `git apply --check tasks/01M2DTT96FS25SHXP0HDTWARQH/roles-yaml.patch` — применяется на чистом дереве.
- `python3 -m pytest tasks/01M2DTT96FS25SHXP0HDTWARQH/acceptance_tests -q` — 12 passed.
- `python3 -m pytest tests/test_yaml_parsing.py tests/test_runner_role_model.py tests/test_step_cost.py tests/test_agent_prompt.py tests/test_agent_log.py tests/test_agent_failure.py tests/test_dry_run.py -q` — 184 passed, 68 subtests passed.
- `python3 -m pytest tests/test_canary.py tests/test_watch.py tests/test_step_autocommit.py tests/test_timeout_checkpoint.py -q` — 140 passed, 4 subtests passed.
- `python3 -m pytest tests/test_doctor.py -q` — 135 passed, 3 subtests passed.
- `python3 -m pytest tasks/01M2CN3ZCSZ54TFJGTDCXTDHXD/acceptance_tests/test_ac7_locked_public_surface.py -q` — 2 passed, 9 subtests passed (залоченные сигнатуры `role_cmd()`/`run_agent_once()` и 9 других имён не тронуты).
- `python3 scripts/codebase_map.py` (регенерация на месте) — дифф только в `built_at_sha`, содержимое совпадает с закоммиченным (сверено `grep -v '^built_at_sha:'`); откатил регенерацию (`git checkout -- docs/codebase-map.md`) — рабочее дерево оставлено чистым.
- `git diff --stat` ветки против общего предка — совпадает с описью пакета (`docs/codebase-map.md`, `orchestrator/roles.py`, `orchestrator/runner.py`, `tests/test_runner_role_model.py`, `tests/test_yaml_parsing.py`), вне зоны SPEC (`orchestrator/runner.py, orchestrator/roles.py, tests/`) изменений нет; `roles.yaml` этой веткой не тронут.
- CI коммита d04567c7 (текущий HEAD) — зелёный, 7 проверок (по данным пакета).

## Предложения системе

<Пусто.>
