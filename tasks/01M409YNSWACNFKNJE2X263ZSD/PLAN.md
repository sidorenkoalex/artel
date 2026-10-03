---
task: 01M409YNSWACNFKNJE2X263ZSD
type: plan
author_role: developer
status: escalate
schema_version: 5
budget_usd: 80
---

# PLAN: ADR-0021, этап 1 (б2) — упразднение репозитория фиксации и ссылка внешнего проекта

## Подход
Один ответ на вопрос «в каком git живёт ссылка документов задачи» —
`artifact_branch.repo_for_target(target)` / `task_repo(task_id)`:
`config.ROOT` для артели, клон проекта (`repo_context.resolve(target).path`)
для внешнего target. Клона нет (каталога `.git` в нём нет) — маркер
`_NO_REPO`: git не спрашивается вовсе, потому что `git -C` в каталоге под
`config.ROOT` без своего `.git` молча ушёл бы вверх и записал ссылку в git
пульта (тот же класс, что прежний `_fix_external` чинил ленивым `git init`).
Все узлы `artifact_branch` (запись `_write`, `ref_head`, `push`/`_send`/
`send_pending`, `origin_sync_refusal`, `read_tree`, `materialize_task_dir`,
`append_passport_line`) работают с репозиторием задачи; для артели вызовы
`gitcmd` идут прежним путём байт-в-байт (без `-C`). Гейт мержа и `kill`
зовут `origin_sync_refusal` — сверка у них переключилась без правки их кода.
`doctor`-сверка ссылок группирует задачи по репозиторию и спрашивает
`ls-remote` у `origin` каждого (для пульта — прежний вызов
`doctor._origin_artifact_refs()`).

Репозиторий фиксации упразднён: удалены `fixation._fix_external`,
`_read_external`, `projects.init_artifact_repo` (+ `ARTIFACT_GITIGNORE`,
вызов из `cmd_target_init`), родственная `projects.artifact_repo_has_no_remote`
с потребителем `doctor.check_remote_empty`; `recovery_check` больше не
пропускается при отсутствии `.artel/projects/<target>/.git` и сверяет только
голову ссылки (подпроверки `recovery-clean`/`recovery-fsck` смотрели в
упразднённый репозиторий — убраны); `check_target_layout` смотрит на
репозиторий ссылок документов. `fixation.external_artifact_sha` читает
голову ссылки в репозитории задачи.

**Переоценка бюджета ($40 → $80).** SPEC оценивал 7–9 модулей; по ходу
реализации выяснилось, что документы внешней задачи после переезда ссылки
нужно и ЧИТАТЬ из репозитория проекта: читатели (`artifact_source.resolve`
— 34 вызова, прямые `gitcmd.show(artifact_branch.branch_name(…))` в
`brief`, `review`, `fsm`, `fsm_advance`, `amend`, `answer`, `catalog`,
`cleanup`, `checkpoint`, `acceptance`, `canary` и др.) живут в пульте, а
существующие тесты внешнего target (≥ 22 метода в 4 модулях, см.
«Эскалация») ведут задачу через эти читатели. Это вопрос 1 эскалации;
поднятый потолок нужен при ответе (а).

## Шаги
1. `gitcmd`: необязательный `repo=` у `show`, `ls_tree_files`,
   `remote_ref_state`, `commit_exists` (по образцу `branch_head_sha`). —
   сделано.
2. `artifact_branch`: `repo_for_target`/`task_repo`/`_NO_REPO`, все узлы
   записи, отправки, досылки, сверки и чтения — на репозитории задачи. —
   сделано.
3. Упразднение репозитория фиксации: `fixation.py`, `projects.py`,
   `doctor/misc_checks.py` (`check_remote_empty`), `doctor/cli.py`,
   `doctor/__init__.py`, `doctor/recovery.py`, `doctor/preflight.py`
   (`check_target_layout`). — сделано.
4. `doctor/artifact_branches.py`: сверка и `--fix` по репозиторию задачи,
   группами. — сделано.
5. Читатели документов внешней задачи — по ответу на вопрос 1. — НЕ
   сделано, ждёт ответа.
6. Правка существующих тестов — по мандату (вопрос 2); сделаны две правки,
   не требующие решения по вопросу 1 (см. перечень). — частично.
7. Приложение к `docs/invariants.md` (инвариант 25) — ниже, `git apply
   --check` пройден. — сделано.
8. Карта кодовой базы регенерирована (`python3 scripts/codebase_map.py`). —
   сделано.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 3 (+ AC-1/AC-2/AC-3 — долгоживущий файл и планка зелёные) |
| 2 | 1, 2 (AC-4, AC-5 зелёные) |
| 3 | 2, 4 (AC-6, AC-7, AC-8 зелёные) |
| 4 | 2 — гейт мержа и `kill` не ослаблены: сверка та же, меняется только репозиторий; AC-9 зелёный |
| 5 | 7 |
| 6 | долгоживущий `tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py` (test_author) покрывает AC-1, AC-2, AC-4–AC-8; перечень изменённых существующих тестов — «Эскалация», вопрос 2 |

Прогоны (передний план, `-p timeout -o timeout=120`):
- `tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py` +
  `acceptance_tests/test_ac3_fixation_repo_code_removed.py` — 15 passed.
- `test_git_fixation`, `test_doctor`, `test_artifact_ref_sync`,
  `test_doctor_artifact_branch_sync`, `test_multitarget_invariants` —
  11 failed / 169 passed (все 11 — в перечне вопроса 2).
- `test_kill_cleanup`, `test_step_autocommit`,
  `test_checkpoint_external_step_artifacts`, `test_artifact_materialization`,
  `test_preflight_step_provider`, `test_retro_artifact_branch_reads`,
  `test_docs_dir_layout`, `test_01m409ykm3qe5kvrgv0g94f5zc_step_docs_dir`,
  `test_fsm_merge_gate_done_snapshot`, `test_doctor_fix_ignored_artifacts`,
  `test_invariants`, `test_gitcmd_branch_reads`, `test_repo_context`,
  `test_multitarget` — 18 failed / 231 passed (все 18 — внешний target,
  вопрос 1).
- `test_artifact_branch_push`, `test_artifact_branch_new_parent`,
  `test_snapshot_closing_outcome` — зелёные.

## Влияние на систему
- Артель: путь записи/отправки/сверки ссылки — прежние вызовы `gitcmd` без
  `-C` (`_git_repo` возвращает `None` для `config.ROOT`); AC-9 и сторожа
  `test_artifact_ref_sync`/`test_doctor_artifact_branch_sync` (кроме
  метода, переписанного под внешний проект) зелёные без правки.
- Гейты мержа и `kill` не ослаблены: та же сверка «локальная ссылка ==
  `origin`» в репозитории задачи. Клона внешнего проекта нет — ссылки
  локально нет, сверять нечего (`None`, как и прежде при отсутствии
  ссылки); причину называет `doctor` (`target-layout` warn).
- `doctor`: сняты `remote-empty`, `recovery-clean`, `recovery-fsck` — они
  проверяли упразднённый репозиторий фиксации (у ссылки нет рабочей копии
  и нет отдельного репозитория). `recovery-sha` теперь не пропускается из-за
  отсутствия того репозитория — сверка стала шире. Решение по снятым
  проверкам — вопрос 3.
- Инвариант 25 — приложением (ниже); правка тестов инвариантов не нужна
  (таблица ссылается на `test_git_fixation.FsmDecidesOnlyOnFixedHashesTest`,
  `IntegrityIncidentBlocksRunTest`, `ApproveByShaTest` — они зелёные).
- Откат — revert одного merge-коммита.

## Риски
- Внешний target end-to-end до решения вопроса 1 не работает: ссылка
  пишется в клон проекта, а читатели документов ищут её в пульте. Внешних
  задач в базе 0; `new` внешнего target без клона проекта теперь отказывает
  «ссылка документов не создана — git не ответил» (запись в пульт была бы
  нарушением AC-4).
- Пульт не заводит клон проекта (`runner.role_cwd` делает `mkdir`
  `workspace/`, не `clone`) — без клона ссылке внешней задачи негде жить;
  это этап 2 ADR-0021 (`repo/` области проекта).

## Предложения системе
- `orchestrator/artifact_source.py` возвращает только имя ссылки, без
  репозитория: каждый читатель документов неявно читает `config.ROOT`.
  Любой перенос ссылки (этот этап, этап 2) упирается в ~35 мест —
  читателю нужен один узел «прочитать файл документов задачи» в
  `artifact_branch`, а не пара `resolve` + `gitcmd.show`.
- Комментарии в `checkpoint.py:176/203`, `fsm_advance.py:430`,
  `fsm.py:319`, `store.py:736-760` ещё описывают `_fix_external` как
  живой механизм — устаревшие пояснения; AST-планка их не видит.

## Приложение 1: docs/invariants.md — инвариант 25

Применимость проверена `git apply --check` на чистом дереве рабочей копии
ветки задачи (HEAD d203d46a + правки кода этой задачи; `docs/invariants.md`
веткой не менялся) — проходит.

```diff
diff --git a/docs/invariants.md b/docs/invariants.md
--- a/docs/invariants.md
+++ b/docs/invariants.md
@@ -52,7 +52,7 @@
 | 22 | Нумерация задач независима per-target; операции по `task_id` (журнал, spend, kill) одного target не читают и не меняют строки другого | `test_multitarget_invariants.CrossTargetDbIsolationTest` | ADR-0003 3ж; tasks/T020/SPEC.md, требование 3 |
 | 23 | Пороги суммарного расхода программы (70%/90%) считаются суммой `spent_usd` по всем задачам ВСЕХ target, не одного | `test_multitarget_invariants.ProgramSpendAcrossTargetsTest` | roadmap §5; ADR-0003 3ж; tasks/T020/SPEC.md, требование 4 |
 | 24 | Счётчик номеров задач target не переиспользует номер архивированной (не удалённой) строки при пересеве после reconnect | `test_multitarget_invariants.CounterSurvivesArchivalOnReconnectTest` | ADR-0003 3ж («архивация строк, никогда DELETE»); tasks/T020/SPEC.md, требование 5 |
-| 25 | FSM принимает решения только по артефактам, чьи хэши зафиксированы его журналом (для документов задачи зафиксированное состояние — коммит ссылки `refs/artifacts/<id>`, ADR-0021 п.3): расхождение живого sha (или грязная копия) с зафиксированным на последнем переходе — инцидент целостности, агент не запускается; `approve` без явного sha сам сверяет живой sha и чистоту копии/ссылки документов с зафиксированными на последнем переходе тем же источником, которым печатается подсказка — совпало, гейт проходит без ручного набора и журналирует согласованный sha, расхождение/грязная копия отклоняют его именованным отказом с обоими sha так же, как и явный неверный sha | `test_git_fixation.FsmDecidesOnlyOnFixedHashesTest`; `test_git_fixation.IntegrityIncidentBlocksRunTest`; `test_git_fixation.ApproveByShaTest`; `tasks/01M1SHJX22EMEP4AJ9FFJJ09DC/acceptance_tests/test_ac1_*.py`, `test_ac2_matching_fixation_auto_confirms.py`, `test_ac3_diverged_or_dirty_refuses_named.py` | ADR-0003 п.15, п.17; tasks/T021/SPEC.md, требования 4–6; tasks/01M1SHJX22EMEP4AJ9FFJJ09DC/SPEC.md, требования 1–2; ADR-0021 п.3, п.12; SPEC 01M3Z2DMQRD0BD7AARFVTCVVG8, требование 4 |
+| 25 | FSM принимает решения только по артефактам, чьи хэши зафиксированы его журналом (для документов задачи зафиксированное состояние — коммит ссылки `refs/artifacts/<id>` в репозитории задачи: git проекта для внешнего проекта, git главной копии пульта для артели, ADR-0021 п.3; репозиторий фиксации области проекта упразднён, ADR-0021 п.2): расхождение живого sha с зафиксированным на последнем переходе — инцидент целостности, агент не запускается; `approve` без явного sha сам сверяет живой sha ссылки документов с зафиксированным на последнем переходе тем же источником, которым печатается подсказка — совпало, гейт проходит без ручного набора и журналирует согласованный sha, расхождение отклоняет его именованным отказом с обоими sha так же, как и явный неверный sha | `test_git_fixation.FsmDecidesOnlyOnFixedHashesTest`; `test_git_fixation.IntegrityIncidentBlocksRunTest`; `test_git_fixation.ApproveByShaTest`; `tasks/01M1SHJX22EMEP4AJ9FFJJ09DC/acceptance_tests/test_ac1_*.py`, `test_ac2_matching_fixation_auto_confirms.py`, `test_ac3_diverged_or_dirty_refuses_named.py` | ADR-0003 п.15, п.17; tasks/T021/SPEC.md, требования 4–6; tasks/01M1SHJX22EMEP4AJ9FFJJ09DC/SPEC.md, требования 1–2; ADR-0021 п.3, п.12; SPEC 01M3Z2DMQRD0BD7AARFVTCVVG8, требование 4; SPEC 01M409YNSWACNFKNJE2X263ZSD, требование 1 |
 | 26 | Выход из `tests_writing`: критерий приёмки (AC-n) без теста и без пометки manual/skip/escalate — невалидный выход, переход отказывает с именем критерия | `test_acceptance_tests_flow.TraceabilityTest` | tasks/T023/SPEC.md, требование 4 |
 | 27 | Каталог `acceptance_tests/` залочен фиксацией T021 после выхода из `tests_writing` — коммитом ссылки документов `refs/artifacts/<id>` (`tests_locked_sha`, ADR-0021 п.3): расхождение с зафиксированным на выходе sha — отказ перехода `in_dev → verifying` и гейта мержа после подтяжки main, код чинится под тест, не наоборот. Лок распространяется на перечень долгоживущих файлов задачи `acceptance_tests/long_lived.sha256.txt` (суммы `tests/test_<id задачи в нижнем регистре>_*.py` кодовой ветки): сверка сумм с головой кодовой ветки — на переходах `in_dev → verifying`, `verifying → review`, `review → acceptance`, `approve` из `acceptance` и на гейте мержа после подтяжки main; изменённый или удалённый файл, сбой git — отказ | `test_acceptance_tests_flow.LockTest`; `test_long_lived_manifest.ManifestCheckNodeTest`; `test_long_lived_transitions.ManifestBoundariesTest`, `test_long_lived_transitions.MergeGatePlankLockTest`, `test_long_lived_transitions.TestsWritingManifestTest` | tasks/T023/SPEC.md, требование 5; ADR-0015 (переезд рубежа с `in_dev → review`); ADR-0020, п. 3; SPEC 01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ, требования 6-8; ADR-0021 п.12 |
 | 28 | Чтение артефактов задачи оркестратором (маршрутизация `spec_gate`, бриф роли developer, трассируемость AC, лок `acceptance_tests/`, sha догфуд-фиксации, статус SPEC.md и батч QUESTIONS.md на переходе `spec_writing → spec_gate`, вердикт REVIEW.md — status и iteration — на переходе `review → acceptance/in_dev`) не зависит от того, какая ветка сейчас выписана в рабочем дереве пульта: источник истины — ссылка документов задачи `refs/artifacts/<id>` (ADR-0021 п.3; до неё — ветка задачи), читаемая `git show`/`git ls-tree`, чужой чекаут её не подменяет; ветка ещё не создана ролью — прежнее поведение (рабочая копия), не именованный отказ | `test_gitcmd_branch_reads.OnForeignBranchTest`; end-to-end по каждому месту чтения — `tasks/T031/acceptance_tests/test_branch_correct_reads.py` (`SpecGateBranchRoutingTest`, `BriefBuildBranchTest`, `TraceabilityBranchTest`, `LockBranchTest`, `FixationBranchTest`, `NoUnhandledExceptionOnMissingBranchTest`); `tasks/T047/acceptance_tests/test_branch_correct_status_reads.py` (`SpecWritingBranchRoutingTest`, `ReviewBranchRoutingTest`, `NoTaskBranchDegradationTest`, `NoGitDegradationTest`) | tasks/T031/SPEC.md, требования 1–2; tasks/T030 (класс-дефект «артефакто-чтения ветко-зависимы», журнал ~17:35 25.08.2026); tasks/T047/SPEC.md, требования 1–4 (инциденты T046 27.08.2026, T045 27.08.2026) |
```

## Эскалация

**Вопросы** (по блокирующести):

1. **Читатели документов внешней задачи** (блокирует шаг 5 и судьбу 22+
   существующих тестов). SPEC требует, чтобы ссылка внешней задачи жила в
   git проекта (AC-4), но не говорит, откуда её ЧИТАЮТ бриф, ревью-пакет,
   гейты `advance`/`approve`, автокоммит шага, `amend-tests`, `answer`,
   ретро. Сейчас все они читают `config.ROOT`.
   - (а) перевести всех читателей на репозиторий задачи в этой задаче
     (узел чтения в `artifact_branch`, ~35 мест, ~15 модулей; потолок $80
     из frontmatter); существующие тесты внешнего target меняются только
     фикстурой — у песочницы появляется клон проекта со своим `origin`;
   - (б) читатели остаются на пульте до этапов 2–3 (ADR-0021 п.8, этап 3 —
     «проверки смотрят на репозиторий проекта»); внешний target
     end-to-end не работает до них, тесты внешнего потока из вопроса 2
     (группа Б) удаляются/переписываются под мандат;
   - (в) зеркало: после каждой записи пульт подтягивает ссылку проекта в
     свой git под служебным именем, `artifact_source.resolve` отдаёт его —
     второй источник истины, против духа ADR-0021 п.1.
   Дефолт при молчании: (а).

2. **Мандат на правку существующих тестов** (ADR-0021 п.2–3).
   Группа А — от вопроса 1 не зависит:
   - `tests/test_git_fixation.py::ArtifactRepoInitTest::test_init_creates_a_git_repo_without_a_remote`,
     `::test_gitignore_excludes_workspace_and_logs`,
     `::test_second_init_does_not_change_state_or_fail` — удалить: проверяют
     заведение репозитория фиксации `target-init`ом; замена — долгоживущий
     `test_ac1_no_path_creates_fixation_repo_of_project`.
   - `tests/test_git_fixation.py::NoRemoteCheckTest::test_freshly_initialized_repo_has_no_remote`,
     `::test_repo_with_a_remote_is_detected` — удалить: функция
     `projects.artifact_repo_has_no_remote` и проверка `doctor`
     `remote-empty` упразднены вместе с репозиторием.
   - `tests/test_git_fixation.py::ExternalTransitionCommitsTest::test_second_transition_without_changes_reuses_the_head`
     — удалить: зелёный, но пустой (сравнивает HEAD несуществующего
     репозитория фиксации, `"" == ""`); замена —
     `test_ac2_fixed_sha_is_ref_head_not_fixation_repo`.
   - `tests/test_doctor.py::RecoveryCheckTest::test_dirty_working_copy_raises_an_incident_alert`
     — удалить: подпроверка `recovery-clean` снята (вопрос 3).
   - `tests/test_doctor.py::RecoveryCheckTest::test_healthy_repo_recovery_is_ok`,
     `::test_artel_gets_the_same_recovery_sverka_as_any_target` — убрать
     утверждение `statuses["recovery-clean"] == "ok"`, фикстуру
     перевести с коммита репозитория фиксации на коммит ссылки
     (`artifact_branch.commit_files`); утверждения `recovery-sha == "ok"` и
     «нет инцидентов» остаются.
   - `tests/test_doctor_artifact_branch_sync.py::SyncExcludesTerminalAndForeignTargetTest::test_excludes_done_and_external_target`
     — ПЕРЕПИСАН в worktree: внешняя задача теперь получает клон проекта со
     своим `origin` (метод `external_project`), «коммит мимо пульта» уходит в
     `origin` проекта; утверждения прежние (закрытая без коммита закрытия не
     сверяется, расхождение внешней — одна строка `warn`). Старое тело
     утверждало ссылку внешней задачи в git пульта — прямо против AC-8.
   - `tests/test_artifact_ref_sync.py::RecoveryRewrittenRefTest.setUp` —
     ИЗМЕНЁН в worktree (методы не тронуты): вместо удалённого
     `projects.init_artifact_repo` фикстура сама делает `git init` старого
     репозитория фиксации.
   Группа Б — внешний поток, читающий документы из пульта (зависит от
   вопроса 1; при (а) меняется только фикстура — клон проекта, при (б)
   методы удаляются):
   - `tests/test_git_fixation.py::ExternalTargetAdvanceIgnoresDirtyCheckTest::test_uncommitted_plan_still_advances_for_external_target`,
     `::ExternalIntegrityIncidentBlocksRunTest::test_clean_state_runs_normally`,
     `::ExternalApproveDoesNotCommitOthersWorkInProgressTest::test_approve_with_matching_sha_still_transitions`;
   - `tests/test_checkpoint_external_step_artifacts.py` — все 14 методов
     `CommitExternalStepArtifactsTest` и
     `CommitExternalStepArtifactsGitignoreFilterTest`;
   - `tests/test_artifact_materialization.py::ConflictGuardStateGuardTest::test_deletion_after_state_left_tests_writing_is_not_carried_over`;
   - `tests/test_fsm_merge_gate_done_snapshot.py::DonePathSnapshotTest::test_done_snapshot_removes_the_pult_artifact_branch`,
     `::test_done_snapshot_retro_names_the_done_outcome_and_the_ref`,
     `::test_done_transition_publishes_a_snapshot_like_killed_does`;
   - модули, не прогнанные в шаге (`amend`, `answer`, `canary`, `brief`,
     `review` и др. с внешним target), — перечень дополню после ответа
     прогоном по модулям.
   Дефолт при молчании: мандат на группу А как описано; группа Б — по
   дефолту вопроса 1.

3. **Снятые проверки `doctor`** (`remote-empty`, `recovery-clean`,
   `recovery-fsck`): (а) снять — они проверяли упразднённый репозиторий
   (сделано в worktree); (б) оставить их для репозитория фиксации,
   оставшегося на диске от прежнего устройства, пока его не уберут. Дефолт:
   (а).

**Контекст.** Код шагов 1–4, 7, 8 в worktree (незакоммичен):
`orchestrator/gitcmd.py`, `artifact_branch.py`, `fixation.py`,
`projects.py`, `doctor/{__init__,cli,misc_checks,recovery,preflight,artifact_branches}.py`,
карта. Долгоживущий файл задачи (11 методов) и планка AC-3 — зелёные;
AC-10 — приложение выше; AC-11 зелёный до правки существующих тестов, после
неё перечень — вопрос 2. Ссылки на код: `artifact_source.py:24`
(читатель без репозитория), `runner.py:1039` (`workspace/` — `mkdir`, не
клон).

**Блокирует.** Шаг 5 (читатели) и правку тестов группы Б; без мандата на
группу А гейт неослабления тестов не пропустит выход из `in_dev`.
