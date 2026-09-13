---
task: 01M2DC6SQVSANMECXPDZJDP75D
type: plan
author_role: developer
status: ready
schema_version: 5
budget_usd: 90
---

# PLAN: Рефакторинг R8: общая песочница тестов — базовые классы вместо копий setUp и подмножеств PATCHED_ATTRS

## Подход

`budget_usd: 90` (ADR-0014 п.3, однократно, в пределах `ROLE_BUDGET_CAP=100`):
SPEC оценил $25 до анализа факта — фактический объём переноса 49
файлов `tests/*.py` (16 новых базовых классов/примесей + 10 решений по
`PATCHED_ATTRS`) с прогоном всех затронутых модулей на каждой правке
это расходится с оценкой на этой стадии; шаг уже вернулся из
escalated с исчерпанным $25-потолком (см. «Причина возврата» брифа).

Перенос без изменения поведения (класс «рефакторинг», skills/coding-
standards.md): каждое байтово идентичное тело `setUp`/вспомогательной
функции, повторявшееся в ≥2 файлах `tests/*.py` (кроме
`tests/test_invariants.py`, AC-6), переехало дословно в общий базовый
класс/функцию `tests/sandbox.py`; файлы-потребители перешли на
наследование/импорт вместо копии. Каждое подмножество `PATCHED_ATTRS`
без явного обоснования расширено до полного набора
`sandbox.ALL_CONFIG_ATTRS` — override убран, класс наследует его от
`TmpRootTest`.

Один узел потребовал не прямого наследования, а кооперативной примеси:
`SchemaConnTmpRootTest` (цепочка без git) и `ConnRealGitSandbox`
(цепочка с настоящим git) оба сводились к телу `super().setUp();
self.conn = store.db()`, но у разных родителей — прямого общего предка
с этим телом нет. Обнаружено это не на этапе анализа, а планкой AC-1
(`tasks/01M2DC6SQVSANMECXPDZJDP75D/acceptance_tests/
test_ac1_no_duplicate_setup_and_helper_bodies.py`), которая сканирует
И `tests/sandbox.py` в общем пуле источников: после первого прохода
переноса эти две базы остались байтово идентичны ДРУГ ДРУГУ внутри
самого `sandbox.py`. Решение — `_ConnSetupMixin` (`tests/sandbox.py`),
подключённый в `bases` обоих классов; `super().setUp()` внутри примеси
разрешается через MRO каждого потомка в его настоящего родителя
(`SchemaTmpRootTest`/`RealGitSandbox`).

Один класс потребовал НЕ расширения, вопреки общему правилу требования
2: `tests/test_git_fixation.py::_GitFixationTmpRootTest` уже нёс полный
набор `ALL_CONFIG_ATTRS`, только выписанный литералом, а не наследованием.
Уборка литерала (переход на инерцию от `TmpRootTest`) убирает AST-узел
`PATCHED_ATTRS = (...)`, на который по имени класса ссылается ЗАЩИЩЁННЫЙ
`tests/test_invariants.py::SandboxPatchedAttrsCoverWorktreesInvariantTest.
test_git_fixation_sandbox_also_patches_backup_marker` (AC-1 задачи
01M2CN465WEDCF6D77V37FJ82E) — обнаружено прогоном именно этого класса
инвариантов при подготовке PLAN, красный ДО восстановления литерала.
Правка защиты не входит в мандат этой задачи (AC-6 запрещает редактировать
`tests/test_invariants.py`), поэтому литерал возвращён на место с
комментарием-обоснованием (почему он не убран, как остальные 9), а не
исправлен сам инвариант — «Защита не трогается» (skills/coding-standards.md).

## Шаги

1. `tests/sandbox.py`: добавлены `event()`, `TmpDirTest`, `TmpPlanPathTest`,
   `InitializedTmpRootTest`, `TaskSeededTmpRootTest`,
   `BudgetSeededTmpRootTest`, `SchemaTmpRootTest`, `SchemaConnTmpRootTest`
   (+ `_ConnSetupMixin`), `SchemaSeededTmpRootTest`,
   `TaskIdSchemaConnTmpRootTest`, `DeveloperBriefTmpRootTest`,
   `ConnRealGitSandbox`, `SyncedOriginConnSandbox`, `OriginRealGitSandbox`,
   `AutoOriginSandbox`, `GitignoreCommittedRealGitSandbox` + `GITIGNORE_TEXT`.
2. 46 файлов `tests/*.py` переведены на наследование/импорт из шага 1
   вместо собственной копии тела (список — «Покрытие требований» и
   таблица переносов ниже).
3. 10 файлов с собственным `PATCHED_ATTRS` разобраны по AC-2: 9
   расширены до полного набора (override убран), 1
   (`tests/test_doctor.py::_RoleHomeReferenceTmpRootTest`) оставлен
   подмножеством с комментарием-обоснованием.
4. `tests/test_git_fixation.py::_GitFixationTmpRootTest` — литерал
   `PATCHED_ATTRS` восстановлен (исключение из шага 3, см. «Подход»).
5. Уборка рабочих файлов анализа предыдущей итерации шага
   (`tasks/01M2DC6SQVSANMECXPDZJDP75D/_*.py`, `_dups_*.txt`) — не часть
   контракта артефактов задачи (skills/conventions-core.md).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (перенос дублей setUp/помощников в базовые классы) | 1, 2 |
| 2 (PATCHED_ATTRS: обоснование или расширение) | 3, 4 |
| 3 (ассерты/сценарии не меняются, tests/ зелёный) | 1–4 |
| 4 (AC-4: сохранение критерия «нет утечки worktrees») | — (не тронуто; `tests/test_invariants.py` не редактируется, AC-6) |
| 5 (таблица переносов + откат) | этот PLAN.md |
| 6 (test_invariants.py не редактируется) | 4 (литерал восстановлен, а не защита) |

### Таблица переносов

| Откуда (файл:строка/класс, было) | Куда (`tests/sandbox.py`) |
|---|---|
| `test_agent_log.py`, `test_step_cost.py` — функция `event(**fields)` | `event()` |
| `test_acceptance_collect.py`, `test_acceptance_tests_flow.py` (×2), `test_id_format_guard.py` — `setUp`: временный каталог, только `self.tdir` | `TmpDirTest` |
| `test_guard_schema.py`, `test_yaml_parsing.py` — `setUp`: временный каталог + `self.path` будущего PLAN.md | `TmpPlanPathTest` |
| `test_doctor.py` (`BranchFreshnessCheckTest`, `TaskCounterCheckTest`), `test_prune.py` (3 класса) — `setUp`: `TmpRootTest` + `catalog.cmd_init` | `InitializedTmpRootTest` |
| `test_detached_cycle.py` (×4), `test_doctor.py`, `test_lease.py` (×6), `test_parallel_limit.py`, `test_zone_lock.py`, `test_catalog_status_log.py` (×2), `test_store_journal.py` — `setUp`: + заведённая задача `TASK="T001"` | `TaskSeededTmpRootTest` |
| `test_catalog_wave_breaker_status.py`, `test_pause.py`, `test_release.py` — как выше, но бюджет `config.DEFAULT_BUDGET_USD` | `BudgetSeededTmpRootTest` |
| `test_alerts_wave_breaker.py`, `test_diff_not_collected_alerts.py` (×2), `test_doctor_wave_breaker.py`, `test_notes.py`, `test_runner_wave_breaker.py`, `test_stall_alerts.py` (×2) — `setUp`: схема БД, без задачи | `SchemaTmpRootTest` |
| `test_auto_escalated_return_rework_gate.py`, `test_fsm_review_rework_gate.py`, `test_fsm_review_rework_sha_gate.py`, `test_program_spend_reseed.py`, `test_spent_estimate_store.py` — `setUp`: + `self.conn` | `SchemaConnTmpRootTest` (через `_ConnSetupMixin`) |
| `test_budget_live_lease_and_escalation.py` (×2), `test_cas_set_state.py`, `test_stall_alerts.py` — `setUp`: схема + задача, без `cmd_init` | `SchemaSeededTmpRootTest` |
| `test_mutation_claim_gate.py::MutationClaimGateGitFailureTest`, `test_protected_paths_gate.py::ZonesGateProtectedPathPriorityTest` — `setUp`: схема + `self.conn` + `self.task_id`, задача НЕ заведена | `TaskIdSchemaConnTmpRootTest` |
| `test_agent_failure.py`, `test_agent_log.py`, `test_step_cost.py` — локальные `_*TmpRootTest`: `templates/`+`skills/` + фикстуры брифа | `DeveloperBriefTmpRootTest` |
| `test_canary.py::MergesSinceLastGreenRunTest`, `test_dry_run.py`, `test_pin.py` (×2) — `setUp`: `RealGitSandbox` + `self.conn` | `ConnRealGitSandbox` (через `_ConnSetupMixin`) |
| `test_doctor.py::CanaryTriggerCheckTest`, `test_pin.py::PinUpdateRefusalMessageTest` — `setUp`: + `self.conn` + синхронный origin | `SyncedOriginConnSandbox` |
| `test_artifact_branch_push.py::PushJournalSandbox`, `test_doctor_artifact_branch_sync.py::ArtifactBranchSyncSandbox` — метод `add_origin()` | `OriginRealGitSandbox.add_origin` |
| `test_artifact_branch_push.py::PushSuccessTest`, `test_doctor_artifact_branch_sync.py::ArtifactBranchSyncSandbox` — `setUp`: origin сразу | `AutoOriginSandbox` |
| `test_doctor_fix_ignored_artifacts.py`, `test_gitcmd_check_ignore.py` — `setUp` + константа `GITIGNORE_TEXT`: закоммиченный `.gitignore` | `GitignoreCommittedRealGitSandbox` + `GITIGNORE_TEXT` |
| `test_acceptance_tests_flow.py`, `test_agent_failure.py`, `test_agent_log.py`, `test_analyst_role.py`, `test_catalog_new_race.py`, `test_multitarget.py`, `test_multitarget_invariants.py`, `test_step_cost.py` — собственный `PATCHED_ATTRS` (подмножество без обоснования) | override убран, наследуют `TmpRootTest.PATCHED_ATTRS` (= `ALL_CONFIG_ATTRS`) |
| `test_doctor.py::_RoleHomeReferenceTmpRootTest` — `PATCHED_ATTRS` без `ROOT`/`TASKS`/… | оставлено подмножеством + комментарий-обоснование (читает настоящий `config.ROOT`) |
| `test_git_fixation.py::_GitFixationTmpRootTest` — `PATCHED_ATTRS`, литерально равный `ALL_CONFIG_ATTRS` | литерал сохранён (не убран) + комментарий: убрать нельзя — защищённый `test_invariants.py` ссылается на этот AST-узел по имени класса |

## Влияние на систему

Изменение — только `tests/*.py`, продовый код (`orchestrator/`,
`scripts/`) не тронут. Риск — случайное изменение поведения теста при
переносе тела (другой конструктор, другой порядок вызовов); закрыт
прогоном всех 48 изменённых файлов (кроме `sandbox.py`) — 438 + 454 +
230 + 140 (частично пересекающихся) тестов зелёные — и планкой приёмки
задачи (AC-1/AC-2/AC-3/AC-6 зелёные; AC-4 — `manual`, операционный
прогон вне шага, см. её файл; AC-5 — этот документ).

Единственный инвариант рядом — `tests/test_invariants.py::
SandboxPatchedAttrsCoverWorktreesInvariantTest` (не редактируется,
AC-6) — сверен отдельным прогоном, зелёный после восстановления
литерала `_GitFixationTmpRootTest.PATCHED_ATTRS` (см. «Подход»).

Откат: revert одного merge-коммита ветки задачи в `main` — правка не
трогает схему БД, миграции, внешние контракты и продовый код, откат
безопасен и не требует сопутствующих действий.

## Риски

- Таблица переносов не воспроизводит номера строк ИСХОДНОГО (до
  рефакторинга) файла — они были собраны предыдущей итерацией шага
  (WIP-чекпоинт после таймаута) через одноразовый скрипт-сканер,
  который эта итерация убрала как рабочий мусор (шаг 5); привязка
  «файл:класс» в таблице выше достаточна для проверки полноты по
  дифу — точные строки до правки восстановимы из `git show
  0b9b7b57:tests/<file>.py` при необходимости ревью.

## Предложения системе

- `tests/sandbox.py` — при добавлении нового `TmpRootTest`-потомка,
  дублирующего тело `setUp` УЖЕ существующего несмежного класса (не
  прямого предка), планка AC-1 такого класса задачи 01M2DC6SQVSANMECXPDZJDP75D
  ловит это только если сама планка ещё жива в дереве; стоит перенести
  сам сканер (`_collect_setup_bodies`/`_collect_module_helper_bodies` из
  `tasks/01M2DC6SQVSANMECXPDZJDP75D/acceptance_tests/
  test_ac1_no_duplicate_setup_and_helper_bodies.py`) в постоянный
  `tests/test_invariants.py` — иначе следующий рефакторинг песочницы
  рискует тем же классом регрессии (кросс-иерархийный дубль внутри
  `sandbox.py`), что нашёлся в этой задаче только благодаря собственной
  планке.
