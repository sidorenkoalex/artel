---
task: 01M2DTT96FS25SHXP0HDTWARQH
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Модель роли из roles.yaml — флаг --model в команде запуска и модель в журнале шага

## Соответствие SPEC

Итерация 2 — переигровка после эскалации: подтяжка main принесла
коммит Оператора `d4e80604` (поле `model` в `roles.yaml`, приложение
патча этой же задачи) РАНЬШЕ мержа ветки, из-за чего помощник планки
`_pipeline.roles_yaml_text` и тестовый помощник `tests/
test_runner_role_model.py::_roles_yaml_text` перестали отличать
сценарий «поле не задано» от боевого. Оператор (`ANSWER-1.md`)
подтвердил: эскалация не по существу, код ветки/PLAN не трогать,
исправить только помощники командой amend-tests. Коммит `36c1bf1f`
это и делает — единственное изменение с момента approve итерации 1.

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 — необязательное поле `model` в roles.yaml по 4 agent-ролям, правка только unified diff'ом | OK | Поле фактически применено к `roles.yaml` коммитом Оператора `d4e80604` (вне этой ветки, приложение того же `tasks/01M2DTT96FS25SHXP0HDTWARQH/roles-yaml.patch`) и подтянуто в ветку `подтяжкой main` (`e5554ccd`). Значения на месте: `developer`/`reviewer` → `claude-opus-5`, `analyst`/`test_author` → `claude-sonnet-5` (roles.yaml:19,24,29,34) — соответствует решению Оператора 13.09 (AC-9). Сама ветка `roles.yaml` не трогает (`git diff origin/main...HEAD -- roles.yaml` — пусто). |
| 2 — `roles.model(role) -> str \| None` | OK | `orchestrator/roles.py:74-92` (диф от origin/main) — без изменений с итерации 1: `None` на отсутствии поля, `RolesError` на не-строке/пустой строке, тем же приёмом, что `skills()` (AC-1/AC-2). `tests/test_yaml_parsing.py::RolesModelTest` (4 теста) прогнаны — зелёные. |
| 3 — флаг `--model <id>` в команде шага, если задан; без флага, если нет | OK | `orchestrator/runner.py:1036-1055` — довесок СНАРУЖИ `role_cmd()` (сигнатура залочена AC-7). `tasks/01M2CN3ZCSZ54TFJGTDCXTDHXD/acceptance_tests/test_ac7_locked_public_surface.py` прогнан — зелёный, залоченные сигнатуры не тронуты. `tests/test_runner_role_model.py::test_command_carries_the_model_flag_once_in_prior_flag_order` — зелёный. |
| 4 — предупреждение «модель роли не задана — дефолт CLI» ровно один раз на шаг, не блокирует | OK | `orchestrator/runner.py:390-397` (`_refuse_before_start`, один раз до цикла попыток). `test_command_has_no_model_flag_and_warns_once_when_unset` — зелёный: ровно одна запись, шаг не FAILED/SKIPPED/TIMEOUT. |
| 5 — «agent run started» несёт `model=<id>`/`model=дефолт CLI` | OK | `orchestrator/runner.py:1007-1009` (`_prepare_step`). `test_run_started_journal_carries_the_model`/`test_run_started_journal_uses_the_default_marker_when_unset` — зелёные. |
| 6 — «agent cost KNOWN»/«agent cost PARTIAL» несут тот же `model=`, без правки `spend.py` | OK | `_account_step` (`orchestrator/runner.py:1126-1155`) дополняет `numbered` меткой `model=` ТОЛЬКО когда локально повторённое условие совпадает с веткой `spend.py`: KNOWN — `pump.cost.get("tokens_by_type")` (сверено дословно с `spend.py:161`); PARTIAL — `_cost_partial_expected` зовёт `spend.partial_cost_usd` напрямую (сверено с `spend.py:273-298`, включая `ValueError`-деградацию). `tests/test_step_cost.py` прогнан целиком — 100% зелёный, включая `test_missing_cost_is_warned_but_step_survives` (точная сверка «agent cost UNKNOWN» БЕЗ `model=`). `spend.py` не тронут (вне diff). |
| 6 (status/report/канарейка) | OK | `git diff --stat origin/main...HEAD` не касается `status.py`/`report.py`. `tests/test_canary.py` прогнан — зелёный без правки `canary.py`. |

## Замечания

<Пусто — 0 blocker/major/minor.>

## Реестр замечаний

<Пусто — в итерации 1 замечаний не заведено, в итерации 2 новых не найдено.>

## Вердикт

approved

## Проверено исполнением

- `git diff --stat origin/main...HEAD` (после `git fetch origin main`, т.к. локальный `main` отстаёт от актуального origin/main на коммиты `0357f54c`/`d4e80604`, слитые в ветку раньше, чем обновился локальный ref) — затронуты ровно `orchestrator/roles.py`, `orchestrator/runner.py`, `tests/test_runner_role_model.py`, `tests/test_yaml_parsing.py`, `docs/codebase-map.md`; `roles.yaml`/`docs/backlog.md` веткой не тронуты (пришли уже смёрженными из origin/main).
- `git apply --check tasks/01M2DTT96FS25SHXP0HDTWARQH/roles-yaml.patch` на текущем HEAD — НЕ проходит (`patch failed: roles.yaml:16`), ожидаемо: поле `model` в рабочем `roles.yaml` уже присутствует (применено коммитом Оператора `d4e80604` до мержа ветки, объяснено в `ANSWER-1.md`), патч писан против состояния без поля. Значения в файле сверены построчно с патчем — совпадают. Не замечание: AC-9 «проходит на чистом дереве» относится к моменту приложения патча (пройдено итерацией 1 до применения), не к текущему состоянию, где применение уже свершившийся факт.
- `git show 36c1bf1f -- tests/test_runner_role_model.py` — единственное изменение с итерации 1: `_roles_yaml_text` снимает существующую строку `model:` перед вставкой/пропуском новой; ни одна существующая строка `assert`/докстринг не тронуты.
- `python3 -m pytest tasks/01M2DTT96FS25SHXP0HDTWARQH/acceptance_tests -q` — 12 passed.
- `python3 -m pytest tests/test_yaml_parsing.py tests/test_runner_role_model.py tests/test_step_cost.py -q` — 94 passed, 55 subtests passed.
- `python3 -m pytest tests/test_agent_prompt.py tests/test_agent_log.py tests/test_agent_failure.py tests/test_dry_run.py tests/test_canary.py -q` — 175 passed, 17 subtests passed.
- `python3 -m pytest tasks/01M2CN3ZCSZ54TFJGTDCXTDHXD/acceptance_tests/test_ac7_locked_public_surface.py -q` — 2 passed, 9 subtests passed (залоченные `role_cmd()`/`run_agent_once()` и 9 других имён не тронуты).
- `python3 scripts/codebase_map.py` (регенерация на месте) — дифф с закоммиченным только в `built_at_sha` и уже присутствующих в дифе ветки записях (новая функция `model`, новые импортёры `test_runner_role_model.py`); откатил регенерацию (`git checkout -- docs/codebase-map.md`) — рабочее дерево оставлено чистым.
- Сверка ветвления `_cost_partial_expected`/KNOWN-условия в `orchestrator/runner.py` против `orchestrator/spend.py::charge_step`/`charge_missing_result` построчным чтением обоих файлов — условия дублируют друг друга корректно.
- CI коммита `36c1bf1f` (текущий HEAD ветки, подтверждено `git rev-parse HEAD`) — зелёный, 14 проверок (по данным пакета ревью).
- Полный набор `tests/` не прогонялся (решение Оператора 05.09) — его гоняет CI на каждый пуш, зелёный статус подтверждён отдельно.

## Предложения системе

<Пусто.>
