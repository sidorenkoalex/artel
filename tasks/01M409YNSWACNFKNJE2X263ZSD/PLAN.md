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
`config.ROOT` для артели, клон проекта (`repo_context.resolve(target).path`,
`.artel/projects/<проект>/workspace`) для внешнего target. Клона нет
(каталога `.git` в нём нет) — маркер `_NO_REPO`: git не спрашивается
вовсе, потому что `git -C` в каталоге под `config.ROOT` без своего `.git`
молча ушёл бы вверх и записал/прочитал ссылку в git пульта. Файла БД нет —
задачи нет, репозиторий тот же, что дал бы `store.task_target` (артель),
БД ради чтения не заводится.

Запись, отправка, досылка, сверка с `origin` (гейт мержа, `kill`),
`doctor` — на репозитории задачи (шаги 1–4, сделаны на прошлом шаге).

**Читатели (ANSWER-1 п.1, вариант (а)).** Узел чтения в `artifact_branch`:
`show(task_id, rev, rel)`, `ls_tree(task_id, rev, rel_dir)`,
`rev_sha(task_id, rev)`, `diff_names(task_id, a, b, *paths)`,
`on_foreign_rev(task_id, rev)`, `git(task_id, *args)` (для `git log` по
пути ссылки). Читатель называет задачу и ревизию (имя ссылки или sha её
коммита — `tests_locked_sha`, `materialized_artifact_sha`), репозиторий
выбирает узел. Для артели узел зовёт прежний примитив `gitcmd` байт-в-байт,
без `repo=` (`_repo_kw` отдаёт `{}`): подмены `gitcmd.show`/`git`/
`branch_head_sha` в существующих тестах артели работают как раньше —
это и проверено прогоном (ниже). Переведены все места чтения документов
задачи: бриф (`brief`), ревью-пакет (`review.artifact_text(..., task_id=)`,
`_answer_rels`), гейты `advance`/`approve` (`fsm`, `fsm_advance`,
`fsm_autogate`, `fsm_merge_gate`, `advance_gates/acceptance` — лок планки,
`advance_gates/zones` и `test_integrity` — мандат ANSWER и признак
автокоммита роли), выкладка планки (`acceptance.materialize_from_branch`,
через неё — `pull`), автокоммит шага (`checkpoint`: конфликт-гвард,
кандидаты на удаление, `_same_as_ref`/`_same_as_commit`, перенос
документов рабочей копии кода), `amend-tests --from-branch`, `answer`/
`zones-extend`, `catalog show`, `cleanup` (ТЗ в журнал `kill`), `runner`
(ТЗ для выбора роли), `doctor --fix` (игнорируемые файлы), `canary`
(диагностика). `artifact_source.resolve` по-прежнему отдаёт только имя
ссылки; ретро читает `artifact_branch.read_tree`, фиксация —
`artifact_branch.ref_head` (уже на репозитории задачи). Чтения кодовой
ветки (`t["branch"]`, долгоживущие файлы, `dry_run`) не тронуты — это код
артели в git пульта.

Репозиторий фиксации упразднён: удалены `fixation._fix_external`,
`_read_external`, `projects.init_artifact_repo` (+ `ARTIFACT_GITIGNORE`,
вызов из `cmd_target_init`), `projects.artifact_repo_has_no_remote` с
проверкой `doctor` `remote-empty`; `recovery_check` сверяет только голову
ссылки (подпроверки `recovery-clean`/`recovery-fsck` сняты — ANSWER-1
п.3); `check_target_layout` смотрит на репозиторий ссылок документов.

**Переоценка бюджета ($40 → $80)** — значение во frontmatter с прошлой
сдачи: SPEC оценивал 7–9 модулей, перевод читателей (ANSWER-1 п.1) задел
20 модулей `orchestrator/` и 11 существующих тестовых файлов.

## Шаги
1. `gitcmd`: необязательный `repo=` у `show`, `ls_tree_files`,
   `remote_ref_state`, `commit_exists`, `diff_names`. — сделано.
2. `artifact_branch`: `repo_for_target`/`task_repo`/`_NO_REPO`, запись,
   отправка, досылка, сверка — на репозитории задачи. — сделано.
3. Упразднение репозитория фиксации: `fixation.py`, `projects.py`,
   `doctor/{__init__,cli,misc_checks,recovery,preflight}.py`. — сделано.
4. `doctor/artifact_branches.py`: сверка и `--fix` по репозиторию задачи,
   группами. — сделано.
5. Узел чтения `artifact_branch.{show,ls_tree,rev_sha,diff_names,
   on_foreign_rev,git}` и перевод на него всех читателей (список —
   «Подход»). — сделано.
6. Песочница: `tests/sandbox.make_project_repo(target)` — клон проекта с
   первым коммитом и своим bare-`origin` (запись target'а дописывается в
   `targets.yaml`); `disk_backed_show`/`disk_backed_ls_tree_files`
   принимают и игнорируют `repo=`. Подготовка данных существующих тестов
   внешнего потока — клон проекта (перечень ниже). — сделано.
7. Сторож узла чтения — новый `tests/test_artifact_branch_read_node.py`
   (5 методов, у каждого «Ловит мутацию»; каждая заявка проверена
   временной мутацией — все 4 мутации красят свой тест). — сделано.
8. Приложение к `docs/invariants.md` (инвариант 25) — ниже. — сделано.
9. Карта кодовой базы регенерирована (`python3 scripts/codebase_map.py`). —
   сделано.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 3 (AC-1/AC-2/AC-3 — долгоживущий файл задачи и планка AC-3 зелёные) |
| 2 | 1, 2, 5 (AC-4, AC-5 зелёные; читатели — тот же репозиторий, что запись) |
| 3 | 2, 4 (AC-6, AC-7, AC-8 зелёные) |
| 4 | 2, 5 — гейт мержа, `kill`, лок планки, мандат ANSWER не ослаблены: та же сверка, меняется только репозиторий; AC-9 зелёный |
| 5 | 8 |
| 6 | долгоживущий `tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py` (test_author) — AC-1, AC-2, AC-4–AC-8; узел чтения — шаг 7; изменённые существующие тесты — перечень ниже |

### Изменённые существующие тесты (ADR-0021 п.2–3)
Мандат ANSWER-1 п.2 (группа А):
- `tests/test_git_fixation.py` — удалены классы `ArtifactRepoInitTest`
  (`test_init_creates_a_git_repo_without_a_remote`,
  `test_gitignore_excludes_workspace_and_logs`,
  `test_second_init_does_not_change_state_or_fail`), `NoRemoteCheckTest`
  (`test_freshly_initialized_repo_has_no_remote`,
  `test_repo_with_a_remote_is_detected`), `ExternalTransitionCommitsTest`
  (`test_second_transition_without_changes_reuses_the_head`): репозиторий
  фиксации упразднён (ADR-0021 п.3, требование 1); замена — долгоживущие
  `test_ac1_…`/`test_ac2_…`.
- `tests/test_doctor.py::RecoveryCheckTest::test_dirty_working_copy_raises_an_incident_alert`
  — удалён (подпроверка `recovery-clean` снята, ANSWER-1 п.3);
  `test_healthy_repo_recovery_is_ok`,
  `test_artel_gets_the_same_recovery_sverka_as_any_target` — убрано
  утверждение `recovery-clean`, фикстура — коммит ссылки
  (`artifact_branch.commit_files`, настоящий git, клон проекта для `sled`),
  добавлено `assertTrue(sha)`; докстринги несут «Ловит мутацию».
- `tests/test_doctor_artifact_branch_sync.py::SyncExcludesTerminalAndForeignTargetTest::test_excludes_done_and_external_target`
  — внешняя задача с клоном проекта и его `origin` (утверждения прежние).

Только подготовка данных (ANSWER-1 п.1, утверждения и имена не менялись):
- `tests/test_git_fixation.py` — `setUp` классов
  `ExternalTargetAdvanceIgnoresDirtyCheckTest`,
  `ExternalIntegrityIncidentBlocksRunTest`,
  `ExternalApproveDoesNotCommitOthersWorkInProgressTest` —
  `make_project_repo("sled")`; докстринги модуля и класса без
  `_fix_external`.
- `tests/test_checkpoint_external_step_artifacts.py` — `setUp` обоих
  классов (`make_project_repo`), помощники `artifact_branch_files`/
  `artifact_branch_text` читают клон (`repo=self.project`); в теле
  `CommitExternalStepArtifactsTest::test_second_step_accumulates_onto_the_first_not_replaces_it`
  — `gitcmd.show(..., repo=self.project)`, в
  `CommitExternalStepArtifactsTest::test_binary_file_is_not_lost` —
  `cwd=self.project` у `git show`; утверждения те же.
- `tests/test_artifact_materialization.py::ConflictGuardStateGuardTest` —
  `setUp` и помощник `artifact_branch_files` (клон проекта).
- `tests/test_guard_task_root_subdirectory.py::CheckpointDropsSubdirectoryFileTest`
  — `setUp` и помощник `artifact_branch_files`.
- `tests/test_multitarget_invariants.py::ExternalWorkspaceIsolationTest` —
  помощник `new_task` заводит клон проекта для внешнего target.
- `tests/test_branch_freshness_gate.py::TargetSourcedRemoteTest` — `setUp`:
  клон проекта до `cmd_new`.
- `tests/test_split_assessment_merge_gate.py::SnapshotSplitAssessmentTest::test_external_target_skips_diff_but_still_reads_split_assessment`
  — строка `make_project_repo("sled")` в теле; помощник `_fake_git`
  пропускает ведущее `-C <клон>`.
- `tests/test_artifact_ref_sync.py::RecoveryRewrittenRefTest.setUp` —
  `git init` старого репозитория фиксации самой фикстурой.
- `tests/test_fsm_merge_gate_done_snapshot.py::DonePathSnapshotTest.setUp`
  — коммит PLAN.md после заведения клона проекта.

Замена утверждений — вопрос 1 «Эскалации»:
`tests/test_fsm_merge_gate_done_snapshot.py::DonePathSnapshotTest::test_done_transition_publishes_a_snapshot_like_killed_does`,
`::test_done_snapshot_retro_names_the_done_outcome_and_the_ref`,
`::test_done_snapshot_removes_the_pult_artifact_branch`.

### Прогоны (передний план, `-p timeout -o timeout=120`)
- Планка AC-3 + долгоживущий файл задачи + `test_artifact_branch_read_node`
  + все изменённые тестовые модули + `test_codebase_map` — 280 passed.
- По модулям, все затронутые (ANSWER-1 п.4), включая `amend*`, `answer*`,
  `canary*`, `brief`, `review*`, `fsm*`, `checkpoint*`, `doctor*`,
  `multitarget*`, `pull*`, `long_lived*`: пакеты 259 / 414 / 388 / 395 /
  366 / 174 и остаток набора тремя пакетами 492 / 699 / 710 тестов — все
  зелёные, кроме не связанных с задачей отказов окружения роли:
  `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py` (16) и
  `tests/test_main_ci_line.py::FixesMainArgTest` (2) — «artel.py
  approve/pin: команда недоступна процессу роли developer» (рубеж роли,
  в CI его нет); `tests/test_liveness.py::TerminateProcessGroupTest::test_kills_the_leader_and_returns_a_positive_count`
  — убийство группы процессов в песочнице шага (модуль задачей не тронут).
- Объём diff против `main` без карты — 206 537 байт (потолок гейта
  ёмкости 262 144, ANSWER-1 п.1).

## Влияние на систему
- Артель: запись, отправка, сверка и чтение — прежние вызовы `gitcmd` без
  `-C` и без `repo=`; сторожа `test_artifact_ref_sync`,
  `test_doctor_artifact_branch_sync` и весь набор артели зелёные без
  правки (AC-9).
- Гейты мержа, `kill`, лок планки, мандаты ANSWER, гейт заявки мутации не
  ослаблены: та же сверка в репозитории задачи. Клона внешнего проекта нет
  — ссылки нет, чтение отдаёт «git не ответил» (`NO_REPO_REASON`) и
  читатели отказывают так же, как при отсутствии ссылки; причину называет
  `doctor` (`target-layout`).
- `doctor`: сняты `remote-empty`, `recovery-clean`, `recovery-fsck`
  (ANSWER-1 п.3); `recovery-sha` теперь не пропускается из-за отсутствия
  репозитория фиксации — сверка шире.
- Инвариант 25 — приложением (ниже); `tests/test_invariants.py` правка не
  нужна (таблица ссылается на `FsmDecidesOnlyOnFixedHashesTest`,
  `IntegrityIncidentBlocksRunTest`, `ApproveByShaTest` — зелёные).
- Откат — revert одного merge-коммита.

## Риски
- Пульт не заводит клон проекта (`runner.role_cwd` делает `mkdir`
  `workspace/`, не `clone`) — без клона ссылке внешней задачи негде жить,
  `new` внешнего target отказывает «ссылка документов не создана». Это
  этап 2 ADR-0021 (`repo/` области проекта); внешних задач в базе 0.
- `checkpoint`/лок планки фильтруют пути внешней задачи `.gitignore`
  пульта (`gitcmd.check_ignore` в `config.ROOT`), не проекта — прежнее
  поведение, задачей не менялось.

## Предложения системе
- `orchestrator/artifact_source.py::resolve` отдаёт только имя ссылки — без
  узла чтения каждый читатель неявно читал `config.ROOT`; новым читателям
  — только `artifact_branch.show/ls_tree/rev_sha`, `gitcmd.show(<ссылка>,
  …)` напрямую стоит ловить guard'ом (класс «чтение ссылки мимо узла»).
- `store.record_fixation` (комментарии `store.py:733-750`) и докстринги
  тестов (`test_capacity_gate.py:201`, `test_step_autocommit.py:20`,
  `test_multitarget_invariants.py:438`, `test_git_fixation.py:585/770`) ещё
  описывают `_fix_external` как живой механизм — устаревшие пояснения.
- Шаг роли: скилы требуют «полный набор не запускать», а ANSWER просит
  «все затронутые модули» — при перекрёстной правке это ~200 файлов
  пакетами; команды пульта «прогнать набор по пакетам» нет.

## Приложение 1: docs/invariants.md — инвариант 25

Применимость проверена `git apply --check` на чистом дереве рабочей копии
ветки задачи (HEAD a58738bf + правки кода этой задачи; `docs/invariants.md`
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

1. **Замена утверждений в `tests/test_fsm_merge_gate_done_snapshot.py`**
   (блокирует сдачу `ready`: правило skills/coding-standards.md «замена
   утверждения существующего метода — эскалация до сдачи шага»; ANSWER-1
   п.1 разрешил внешнему потоку только подготовку данных, а эти три метода
   утверждают прямо противоположное AC-5 — ссылку внешней задачи в
   `origin` ПУЛЬТА). Требование SPEC — 2 и AC-5 (отправка ссылки внешней
   задачи — в `origin` проекта, не пульта). Сделано в worktree:
   - `DonePathSnapshotTest::test_done_transition_publishes_a_snapshot_like_killed_does`:
     было `_snapshot_ref_exists(self.pult_origin, TASK)`,
     `_snapshot_files(self.pult_origin, …)`, `_snapshot_file_text(self.pult_origin, …)`
     — стало то же с `self.target_origin` (bare-`origin` клона проекта);
     текст сообщения «origin пульта» → «origin проекта».
   - `DonePathSnapshotTest::test_done_snapshot_retro_names_the_done_outcome_and_the_ref`:
     `_snapshot_file_text(self.pult_origin, …)` и
     `_snapshot_commit_subject(self.pult_origin, …)` → `self.target_origin`;
     проверяемые строки RETRO и сообщения коммита те же.
   - `DonePathSnapshotTest::test_done_snapshot_removes_the_pult_artifact_branch`:
     было `assertTrue(gitcmd.is_ancestor(before, head))` (git пульта) —
     стало `assertEqual(git merge-base --is-ancestor before head в клоне
     проекта .returncode, 0)`; `assertNotEqual(head, before)` и
     `assertFalse(branch_exists(artifact/<id>))` прежние.
   Варианты: (а) мандат на эти три метода как сделано; (б) оставить
   методы на артели (задача `artel` вместо `extproj`) — путь внешнего
   `done` тогда без сторожа, кроме долгоживущего AC-5; (в) удалить методы
   — против принципа целостности. Дефолт при молчании: (а).
   Строка мандата для гейта неослабления (если он требует её и для
   изменённых без удаления методов внешнего потока — включены и они):
   `Ослабление тестов разрешено: tests/test_fsm_merge_gate_done_snapshot.py::DonePathSnapshotTest::test_done_transition_publishes_a_snapshot_like_killed_does, tests/test_fsm_merge_gate_done_snapshot.py::DonePathSnapshotTest::test_done_snapshot_retro_names_the_done_outcome_and_the_ref, tests/test_fsm_merge_gate_done_snapshot.py::DonePathSnapshotTest::test_done_snapshot_removes_the_pult_artifact_branch, tests/test_checkpoint_external_step_artifacts.py::CommitExternalStepArtifactsTest::test_second_step_accumulates_onto_the_first_not_replaces_it, tests/test_checkpoint_external_step_artifacts.py::CommitExternalStepArtifactsTest::test_binary_file_is_not_lost, tests/test_split_assessment_merge_gate.py::SnapshotSplitAssessmentTest::test_external_target_skips_diff_but_still_reads_split_assessment`

2. **`tests/test_multitarget_invariants.py::ExternalWorkspaceIsolationTest::test_external_target_cwd_is_its_workspace`**
   (не блокирует; метод не менялся, менялся помощник `new_task`).
   Утверждение `expected.is_dir()` («каталог workspace заводит пульт, а не
   CLI на ходу») после подготовки данных выполняется всегда: каталог
   `workspace` теперь — клон проекта, где живёт ссылка документов, и
   фикстура заводит его до шага (без клона бриф внешней задачи не
   собирается). Варианты: (а) принять — заведение клона пультом — этап 2
   ADR-0021, до него утверждение сторожит только `mkdir` в
   `runner.role_cwd`; (б) отдельной задачей переписать метод под этап 2.
   Дефолт: (а).

**Контекст.** Ответ ANSWER-1 выполнен целиком: читатели переведены на узел
чтения (п.1, вариант (а)), группа А по мандату (п.2), проверки `doctor`
сняты (п.3), прогон по модулям — «Покрытие требований» (п.4). Код —
20 модулей `orchestrator/`, `tests/sandbox.py`, новый
`tests/test_artifact_branch_read_node.py`, 11 существующих тестовых
файлов, карта; всё в worktree, зелёное. Гейт ёмкости: 206 537 байт из
262 144.

**Блокирует.** Только сдачу `ready` до мандата по вопросу 1; правки кода
не требуется ни при одном варианте, кроме (б)/(в) вопроса 1.
