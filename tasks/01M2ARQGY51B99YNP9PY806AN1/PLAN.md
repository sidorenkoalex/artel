---
task: 01M2ARQGY51B99YNP9PY806AN1
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Гонка на FETCH_HEAD — приватная ссылка fetch в трёх местах

## Подход

Новый примитив `gitcmd.fetch_ref_sha(remote, ref, *, repo=None)`:
`git fetch <remote> +refs/heads/<ref>:refs/artel/fetch/<pid>-<uuid>`,
`git rev-parse --verify` приватной ссылки, `git update-ref -d` в
`finally` (убирает и на успех, и на отказ `rev-parse`; отказ самого
`fetch` — убирать нечего, ссылка ещё не создана). `repo` — по образцу
`gitcmd.in_repo`: при `repo is not None` КАЖДЫЙ git-вызов примитива идёт
через `in_repo(repo, ...)`, ни один — через голый `git(...)`.

Три места (`gitcmd.fetch_head_sha`, `fsm._origin_main_sha`,
`fsm_merge_gate._origin_main_sha`) переведены на вызов этого примитива,
имена/сигнатуры не меняются (AC-4): `fetch_head_sha` — тонкая обёртка
`return fetch_ref_sha(remote, ref)`; `fsm._origin_main_sha`/
`fsm_merge_gate._origin_main_sha` берут `(remote, branch)`/`(ctx.base)`
из прежней логики (`_origin_main_source`/`ctx`) и передают их же в
`fetch_ref_sha`, `repo` — тем же значением, что и раньше
(`fsm_merge_gate` — через `repo_context.path_or_none(ctx)`).

Тестовая инфраструктура (`tests/sandbox.py`) несла две заглушки
(`fake_git`, `SpyRun`), захардкоженные на литерал `rev-parse --verify
--quiet FETCH_HEAD` (комментарий явно называл причину — `workspace.
ensure`, заводящий новую ветку задачи, иначе видел бы отказ fetch под
этими песочницами). После перевода трёх мест этот литерал в
`orchestrator/` не звучит вовсе — заглушки заменены на эквивалентный
паттерн `rev-parse ... refs/artel/fetch/*` (тот же фейковый sha), иначе
десятки существующих тестов, реально проходящих через `workspace.
ensure`/`fsm._origin_main_sha` под этими фейками (например,
`tests/test_doctor.py::PreflightBlocksMissingTokenTest`), молча
получали бы «приватная ссылка не разрешилась» и красились.

`tests/test_branch_freshness_gate.py::TargetSourcedRemoteTest` проверял
имя ветки фетча (`"trunk"`) как ОТДЕЛЬНЫЙ элемент кортежа аргументов —
с этой задачи имя ветки живёт внутри рефспека
(`+refs/heads/trunk:refs/artel/fetch/...`), не отдельным аргументом;
assert переписан на проверку подстроки рефспека, поведенческий смысл
теста (ветка фетча — `base` записи target'а, не `config.MAIN_BRANCH`)
не изменился.

`orchestrator/notes.py` тоже несёт литерал `FETCH_HEAD` (`git checkout
-B <MAIN_BRANCH> FETCH_HEAD` после отдельного `fetch`) — вне зоны
задачи (frontmatter `zones:` называет только `gitcmd.py`/`fsm.py`/
`fsm_merge_gate.py`/`tests/`, «Не входит» и «Оценка объёма» SPEC
подтверждают три файла как реальную зону; локальный acceptance-тест
AC-5 задачи (`test_ac5_no_fetch_head_literal.py`) статически сверяет
только эти три файла) — не тронут; это не гонка «трёх мест одного
приёма» (требование 2), а отдельное, четвёртое использование с иной
формой (последовательный fetch → checkout одним держателем, не три
конкурирующих читателя общего файла).

## Шаги

1. `orchestrator/gitcmd.py`: новый `fetch_ref_sha`, `fetch_head_sha` —
   тонкая обёртка над ним.
2. `orchestrator/fsm.py`: `_origin_main_sha` переведена на
   `gitcmd.fetch_ref_sha`.
3. `orchestrator/fsm_merge_gate.py`: `_origin_main_sha` переведена на
   `gitcmd.fetch_ref_sha`.
4. `tests/sandbox.py`: заглушки `fake_git`/`SpyRun` — литерал
   `FETCH_HEAD` заменён на паттерн `refs/artel/fetch/*`.
5. `tests/test_branch_freshness_gate.py`: assert имени ветки фетча
   переписан под рефспек (та же проверяемая семантика).
6. `tests/test_gitcmd_fetch_ref_sha.py` (новый): AC-6/AC-7/AC-8 +
   `repo`-провод примитива, плюс первый реальный git-прогон
   `fsm._origin_main_sha`/`fsm_merge_gate._origin_main_sha` (существующие
   тесты этих узлов патчат их целиком по имени и никогда не исполняют
   их git-тело).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (примитив, приватная ссылка) | 1, 6 |
| 2 (перевод трёх мест) | 1, 2, 3, 6 |
| 3 (нет литерала FETCH_HEAD в вызовах) | 1, 2, 3 |

## Влияние на систему

Изменена внутренняя механика трёх функций, наблюдаемый контракт
(имена, сигнатуры, форма возврата, семантика для вызывающего кода)
byte-identical — подтверждено локальными acceptance-тестами задачи
(AC-4/AC-9, все зелёные) и прогоном существующих `tests/test_pull.py`,
`tests/test_fsm_merge_gate_*.py`, `tests/test_branch_freshness_gate.py`,
`tests/test_doctor.py`, `tests/test_amend.py`, `tests/test_workspace.py`
и ещё ~25 модулей, использующих `fake_git`/`SpyRun`/`RealGitSandbox`
(список — «Проверено» ниже) — все зелёные. Единственная правка
поведения теста не по существу — `TargetSourcedRemoteTest` (см.
«Подход»): проверяемое свойство (ветка фетча = `base` target'а) не
ослаблено, изменена только форма проверки под новую форму аргумента.

Гейты/лимиты/инварианты не ослабляются — задача добавляет строгость
(приватная ссылка вместо общего файла), не снимает её. Откат — `git
revert` коммита(ов) этой задачи: три места вернутся к прежнему `git
fetch` + `rev-parse ... FETCH_HEAD`, тестовая песочница — к прежнему
литералу.

### Проверено

- `tasks/01M2ARQGY51B99YNP9PY806AN1/acceptance_tests/` — 9/9 зелёных.
- `tests/test_gitcmd_fetch_ref_sha.py` (новый) — 6/6.
- `tests/test_branch_freshness_gate.py`, `tests/test_pull.py`,
  `tests/test_fsm_merge_gate_scratch_worktree_cleanup.py`,
  `tests/test_fsm_merge_gate_done_snapshot.py`,
  `tests/test_gitcmd_branch_reads.py`, `tests/test_gitcmd_carpentry.py`,
  `tests/test_gitcmd_check_ignore.py`,
  `tests/test_fsm_map_conflict_autoresolve.py`,
  `tests/test_fsm_merge_conflict_note.py`, `tests/test_capacity_gate.py`,
  `tests/test_protected_paths_gate.py`, `tests/test_merge_gate_ci_wait.py`,
  `tests/test_ci_status_kind_gate.py` — зелёные.
- `tests/test_doctor.py`, `tests/test_amend.py`, `tests/test_workspace.py`,
  `tests/test_kill_cleanup.py`, `tests/test_timeout_checkpoint.py`,
  `tests/test_doctor_artifact_branch_sync.py`,
  `tests/test_doctor_artifact_branch_ci.py`, `tests/test_notes.py` —
  зелёные (реальный/фейковый git-трафик `workspace.ensure`/
  `artifact_branch`).
- `tests/test_split_assessment_merge_gate.py`, `tests/test_answer_gate.py`,
  `tests/test_advance_guard.py`, `tests/test_spec_budget.py`,
  `tests/test_pin.py`, `tests/test_auto_cycle.py`,
  `tests/test_agent_prompt.py`, `tests/test_acceptance_tests_flow.py`,
  `tests/test_multitarget.py`, `tests/test_fsm_map_regen.py`,
  `tests/test_fsm_retro.py`, `tests/test_multitarget_invariants.py`,
  `tests/test_github_adapter.py`, `tests/test_task_id_prefix_regression.py`,
  `tests/test_agent_log.py`, `tests/test_analyst_role.py`,
  `tests/test_canary.py`, `tests/test_step_cost.py`,
  `tests/test_review_freshness.py`, `tests/test_catalog_new_race.py`,
  `tests/test_fsm_review_rework_gate.py`, `tests/test_review_package.py`,
  `tests/test_fsm_advance_gate_smoke.py`, `tests/test_agent_failure.py`,
  `tests/test_brief.py`, `tests/test_answer_branch_reads.py` — зелёные
  (полный список файлов, использующих `fake_git`/`SpyRun`, кроме уже
  перечисленных выше).

## Риски

`orchestrator/notes.py` несёт четвёртое, не переведённое использование
`FETCH_HEAD` (вне зоны, см. «Подход») — вне зоны инцидента (единоличный
`fetch`+`checkout`, не три конкурирующих места), но если Оператор сочтёт
нужным закрыть и его — отдельная задача.

## Предложения системе
