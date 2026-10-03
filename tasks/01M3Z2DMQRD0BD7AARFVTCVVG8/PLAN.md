---
task: 01M3Z2DMQRD0BD7AARFVTCVVG8
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: ADR-0021, этап 1 (а) — документы задачи в одной ссылке refs/artifacts/<id>

## Подход
Одна ссылка `refs/artifacts/<id>` на всю жизнь задачи; ветки
`artifact/<id>` и снимка закрытия больше нет. Решения:

- **Один узел записи** — `artifact_branch.commit_files` (и его вариант
  `commit_change`, не пишущий пустой коммит): плотницкий `commit-tree`
  поверх головы ссылки (нет ссылки — первый коммит без родителя), затем
  `update-ref <ref> <new> <old>` со сверкой прежнего значения (для первой
  записи — нулевой oid). Проигрыш сверки — перечитать голову и пересобрать
  коммит, до `_CAS_ATTEMPTS` раз: обе правки остаются, история линейна
  (AC-2). Через этот узел пишут все места требования 2: автокоммит шага
  (`checkpoint`), `new` (`catalog`), `amend-tests` (`amend`), `answer` и
  `zones-extend` (`answer`), паспорт на `set_state` (`store` →
  `append_passport_line`), перечень долгоживущих тестов и
  `tests_locked_sha` (`advance_gates/tests_writing`, `fsm_advance`),
  `doctor --fix` (`doctor/ignored_artifacts`).
- **Отправка** — после каждого коммита `_send` пушит `ref:ref` в `origin`
  без `--force`; отказ журналируется классифицированной причиной (прежний
  `_journal_push_outcome`), коммит остаётся. Повтор — `send_pending` на
  каждом `store.set_state` (AC-3). `branch_name` возвращает полное имя
  ссылки; `gitcmd.qualified_ref` даёт `branch_exists`/`branch_head_sha`/
  `remote_branch_sha` принимать и имя ветки, и полное имя ссылки — чтение
  `gitcmd.show(<ссылка>, …)` не меняется (AC-1, AC-9).
- **Закрытие без снимка** — `snapshot.commit_closing` (модуль сохранил имя):
  коммит `tasks/<id>/RETRO.md` поверх головы ссылки, запись журнала
  «коммит закрытия» с sha, перефиксация. Зовут оба пути закрытия через
  `cleanup._commit_closing` (`kill` и `fsm_merge_gate`); исход — из БД
  (`_closing_outcome`). `publish_and_cleanup`/`pending`/`drop`/
  `snapshot_pending`/`store.closed_external_tasks` удалены (AC-5).
- **Сверка с origin перед закрытием** — `artifact_branch.origin_sync_refusal`
  (сначала досылка, потом `ls-remote`): гейт мержа (`_docs_ref_unsynced`,
  первым шагом тела гейта) и `kill` (`_refuse_unsynced_docs`, до смены
  состояния) отказывают именованно, если локальная ссылка не равна ссылке в
  `origin`, её там нет или `origin` не ответил (AC-6).
- **Фиксация** — `fixation.fix`/`read` = голова ссылки (инвариант 25,
  часть «для документов»); `set_state` пишет паспорт ДО `record_fixation`,
  иначе собственная строка паспорта читалась бы расхождением;
  `tests_locked_sha` — коммит ссылки на выходе `tests_writing` (AC-8).
  Репозиторий фиксации `.artel/projects/<target>/` больше не коммитится
  фиксацией (код `_fix_external` остаётся до части (б)).
- **doctor** — `doctor/artifact_branches.py` заменён на
  `check_artifact_ref_sync`: живая задача — локальная ссылка ≠ `origin`;
  закрытая — голова (локально/в `origin`) ≠ коммиту закрытия журнала;
  задачи без записи о коммите закрытия (исторические снимки) не сверяются
  (AC-7, AC-10). Сироты `artifact/*` (`doctor/orphan_branches.py`),
  CI артефактной ветки и отложенные снимки (`misc_checks`) сняты;
  recovery-сверка смотрит голову ссылки, если зафиксированный sha — коммит
  её истории.

Бюджет SPEC ($85) не переоцениваю.

## Шаги
1. Узел записи ссылки со сверкой и отправкой, перевод всех пишущих мест
   (WIP прошлого шага, коммит `aa7cd419`).
2. Закрытие коммитом RETRO, сверка с origin в гейте мержа и `kill`
   (`aa7cd419`).
3. Фиксация и `tests_locked_sha` на коммитах ссылки, doctor на ссылке
   (`aa7cd419`).
4. Тесты прежнего устройства в `tests/`: перевод на ссылку, удаление
   тестов снятой механики (коммит `b7edb0c8`, перечень — раздел
   «Тесты прежнего устройства»), регенерация карты.
5. Приложение к `docs/invariants.md` (раздел «Приложение»).
6. Возврат из verifying: фикстура `MergeSandbox.make_task` долгоживущего
   `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py` кладёт документы в
   `refs/artifacts/<id>` узлом записи части (а); прогон затронутых тестов
   без `ARTEL_ROLE`; регенерация карты.
7. Возврат из ревью (итерация 1, R1-F1…R1-F3): сторожа в `tests/` на
   AC-2/AC-3/AC-6 (`tests/test_artifact_ref_sync.py`), досылка коммита
   закрытия в `doctor --fix`, recovery-сверка по наличию объекта;
   регенерация карты.
8. Отказ гейта ёмкости diff (262 678 > 262 144 байт): докстринги нового
   кода сокращены без смены поведения — раздел «Отказ гейта ёмкости».

## Покрытие требований
| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1, 7 |
| 3 | 2, 7 |
| 4 | 3 |
| 5 | 3, 7 |
| 6 | 1, 3 (исторические снимки не трогаются, канарейка идёт тем же потоком) |
| 7 | 5 |
| 8 | 4 |

Тесты в `tests/` на поведение AC (требование 8): AC-2, AC-3, AC-6 —
`tests/test_artifact_ref_sync.py` (итерация 2, R1-F1; прежняя сдача
ошибочно называла здесь `test_artifact_branch_push.py`, который проверяет
только явный `push()`, и `test_merge_gate_ci_wait.py`, где сверка
подменена): `CompareAndSwapRaceTest` — гонка двух записей от одной головы;
`SendAfterCommitTest` — ссылка в origin после каждого коммита, отказ →
запись журнала и коммит цел, следующий `set_state` досылает;
`OriginSyncRefusalTest`, `MergeGateDocsRefTest`, `KillDocsRefTest` — отказ
при локальной впереди, при отсутствии в origin и недоступном origin
(журнал `MERGE_UNSYNCED_JOURNAL_ACTION`/`KILL_UNSYNCED_JOURNAL_ACTION`,
состояние и ссылка не меняются), проход при совпадении; там же
`DoctorFixResendsClosingCommitTest` (R1-F2) и `RecoveryRewrittenRefTest`
(R1-F3). AC-5 — `test_snapshot_closing_outcome.py`,
`test_fsm_merge_gate_done_snapshot.py` (коммит закрытия — потомок прежней
головы, ссылка не удаляется, канарейка тем же потоком); AC-7/AC-10 —
`test_doctor_artifact_branch_sync.py` (живая — в обе стороны и разошедшаяся;
закрытая, изменённая после коммита закрытия, — новый
`ClosedRefMovedAfterClosingTest`, проверен временной мутацией; закрытая без
записи о коммите закрытия не сверяется); AC-8/инвариант 25 —
`test_git_fixation.py` (подмена мимо гейта — посторонним коммитом в ссылку),
`test_doctor.py::RecoveryCheckTest`; AC-1/AC-4/AC-9 — переведённые на ссылку
`test_acceptance_tests_flow.py`, `test_amend.py`, `test_answer*.py`,
`test_checkpoint_external_step_artifacts.py`, `test_review_package.py`.

Прогоны в шаге: планка задачи — AC-1…AC-10 зелёные (39 passed); AC-11 по
голове не прогоняется до автокоммита PLAN (читает PLAN из git) — вручную:
приложение накладывается на дерево ветки, `tests/test_invariants.py` с ним
— 66 passed, 215 subtests passed.

Прежняя сдача ошибочно списала красноту `tests/test_main_ci_line.py` и
`tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py` на `ARTEL_ROLE` целиком;
CI ветки (прогон 37083080729) показал, что два метода
`MergeGuardAfterSnapshotTest` красные и без него — см. раздел «Возврат из
verifying». Прогоны этой итерации — все без `ARTEL_ROLE` (признак снят из
окружения процесса pytest), чтобы краснота окружения больше не маскировала
краснота задачи: 140 файлов `tests/` (все изменённые веткой + все,
упоминающие ссылку/ветку документов, снимок, фиксацию, гейт мержа, уборку
или `artel.main`), четырьмя порциями — 2824 passed, 2 skipped, 1 failed.
Единственный красный —
`tests/test_liveness.py::TerminateProcessGroupTest::test_kills_the_leader_and_returns_a_positive_count`
(`terminate_process_group` вернул 0): `orchestrator/liveness.py` и тест
веткой не тронуты (`git diff main` пуст), красный и с `ARTEL_ROLE`, и без —
`killpg` недоступен песочнице процесса шага; задача к нему отношения не
имеет, в CI ветки он зелёный.

## Влияние на систему
- Инварианты 25, 27, 28, 33, 34, 38 — смена источника на ссылку (таблица
  ADR-0021 п.12), суть та же; правка текста — приложением ниже, одним
  мержем с кодом. Гейт неослабления не трогается — удаления тестов идут
  только по мандату (раздел «Эскалация»).
- Гейт мержа и `kill` получают новый отказ (ссылка ≠ origin) — это
  усиление: закрыть задачу с историей документов только в одном месте
  больше нельзя. Пульт без `origin` (лёгкие песочницы) — сверять не с чем,
  отказа нет; об этом говорит `doctor`.
- Мандат зон/тестов (34, 38) читается по истории ссылки
  (`advance_gates/zones._answer_commit_is_role_step_autocommit` получает
  ссылку от `artifact_source.resolve`) — проверка прежняя.
- Не переносится: живые задачи (вливание при пустом конвейере, п.13),
  исторические снимки читаются как раньше, `doctor` их не сверяет.
- Откат — revert merge-коммита + `pin --to` предыдущего пина (ADR-0013); при
  пустом конвейере живых задач в новом устройстве нет.

## Риски
- Ссылки `refs/artifacts/*` не подтягиваются обычным `git fetch` — чтение
  документа задачи с другой машины требует явного fetch (команда — часть
  (в)).
- Задача, у которой `origin` долго недоступен, не закроется (отказ
  гейта/`kill`) — осознанно (ADR-0021 п.3), отказ называет причину.

## Предложения системе
- `skills/coding-standards.md` (раздел «Тесты»): тесты, запускающие CLI
  пульта отдельным процессом (`tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`,
  `tests/test_main_ci_line.py`), краснеют в шаге роли из-за унаследованного
  `ARTEL_ROLE` — разработчик не может отличить такую красноту от своей без
  ручного разбора; песочнице стоит снимать признак шага роли с окружения
  дочернего CLI. Цена урока подтверждена возвратом из verifying этой
  задачи: под общей «ARTEL_ROLE-краснотой» 16 методов спрятались два
  настоящих провала фикстуры. До такой правки песочницы
  `skills/coding-standards.md` стоит требовать прогона затронутых тестов
  с признаком, снятым из окружения pytest (`os.environ.pop('ARTEL_ROLE')`
  в процессе pytest — `env -u` в шаге требует подтверждения).
- Шаг developer задачи-монолита (25 модулей + до 62 файлов тестов) не
  уложился в один таймаут (WIP-чекпоинт `aa7cd419`); `pytest -n` в шаге
  роли не работает (воркеры xdist падают «node down»), и порционный прогон
  затронутых модулей — единственный способ уложиться.

## Тесты прежнего устройства
Удалены (находки гейта неослабления, нужен мандат — «Эскалация», вопрос 1):

| Что удалено | Почему | Чем покрыто |
|---|---|---|
| `tests/test_doctor_artifact_branch_ci.py` (5 методов) | проверка CI ветки `artifact/<id>` снята (AC-7) | `test_doctor_artifact_branch_sync.py` — сверка ссылки |
| `tests/test_doctor.py`: `OrphanArtifactBranchSweepTest`, `RemoteArtifactBranchNamesTest`, `OrphanArtifactBranchOriginFilterTest`, `SweepOrphanArtifactBranchesOriginGateTest`, `PrintOrphanBranchCandidatesTest`, `CmdDoctorOriginUnavailableTest` (21 метод) | уборка сирот `artifact/*` снята вместе с `doctor/orphan_branches.py` (требование 5, AC-7) | ветки `artifact/*` пульт больше не заводит; разовая уборка в `origin` — часть (в) |
| `tests/test_git_fixation.py::ExternalTransitionCommitsTest::test_transition_commits_the_artifact_repo`, `::test_sha_lands_in_the_journal` | фиксация больше не коммитит репозиторий фиксации — зафиксированное состояние = голова ссылки (инвариант 25) | `DogfoodTransitionJournalsShaTest::test_journal_gets_head_sha_and_cleanliness` (sha ссылки в журнале) |
| `tests/test_git_fixation.py::ExternalIntegrityIncidentBlocksRunTest` (3 метода), `ExternalApproveDoesNotCommitOthersWorkInProgressTest` (2 метода) | подмена/WIP на диске репозитория фиксации больше не источник решений FSM | `IntegrityIncidentBlocksRunTest::test_committed_change_after_approve_also_blocks_the_run`, `FsmDecidesOnlyOnFixedHashesTest` (подмена коммитом в ссылку) |
| `tests/test_git_fixation.py::DogfoodTransitionJournalsShaTest::test_uncommitted_artifact_is_journaled_as_dirty`, `ApproveByShaTest::test_approve_without_sha_on_dirty_copy_is_refused_and_state_unchanged`, `IntegrityIncidentBlocksRunTest::test_uncommitted_change_after_approve_blocks_the_run` | у ссылки нет рабочей копии — «грязной копии» документов не бывает | `ApproveByShaTest::test_approve_without_sha_on_diverged_fixation_is_refused_and_names_both_shas`, `IntegrityIncidentBlocksRunTest::test_committed_change_after_approve_also_blocks_the_run` |

Изменены утверждения (наблюдение гейта, имена методов сохранены —
«Эскалация», вопрос 2):

| Метод | Было | Стало | Основание |
|---|---|---|---|
| `tests/test_snapshot_closing_outcome.py::ClosingSnapshotOutcomeTest::test_merged_task_snapshot_commit_message_names_done` | тема `снапшот закрытия (done)` | `закрытие (done) — RETRO` | требование 3 |
| `…::test_killed_task_snapshot_keeps_reason_and_old_address` | тема `снапшот закрытия (killed)`, «опубликован» в выводе | `закрытие (killed) — RETRO`, «коммит закрытия» без «не записан» | требование 3 |
| `…::test_canary_run_publishes_no_snapshot` | ссылки в origin нет, ветка на месте | ссылка в origin есть, RETRO с «Итог: done» | ADR-0021 п.13, требование 6 (канарейка тем же потоком) |
| `…::test_published_snapshot_removes_the_artifact_branch` | ветки нет | коммит закрытия — потомок прежней головы, ссылка = origin | требование 3, AC-5 |
| `tests/test_fsm_merge_gate_done_snapshot.py::DonePathSnapshotTest::test_done_transition_publishes_a_snapshot_like_killed_does` | ссылка в origin целевого | ссылка в origin пульта | требование 1 (ссылка в репозитории пульта для любого target) |
| `…::test_done_snapshot_retro_names_the_done_outcome_and_the_ref` | тема `снапшот закрытия (done)` в origin целевого | `закрытие (done) — RETRO` в origin пульта | требования 1, 3 |
| `…::test_done_snapshot_removes_the_pult_artifact_branch` | ветки `artifact/<id>` нет | коммит закрытия — потомок прежней головы, ветки нет | AC-5 |
| `tests/test_doctor_artifact_branch_sync.py::SyncOriginAheadTest::test_warn_local_behind`, `SyncLocalAheadTest::test_warn_origin_behind`, `SyncDivergedTest::test_warn_diverged` | тексты «локальный отстаёт»/«origin отстаёт»/«разошлись» | «расходится с origin» с sha | требование 5, AC-7 (одно условие «не совпадает с origin») |
| `…::SyncExcludesTerminalAndForeignTargetTest::test_excludes_done_and_external_target` | внешний target исключён | внешний target сверяется, закрытая без записи о коммите закрытия — нет | требование 1 (ссылка для любого target), AC-10 |
| `tests/test_multitarget_invariants.py::PultArtifactIsolationTest::test_external_artifacts_never_appear_in_git_status` | ветка документов удалена после `kill` | коммит закрытия записан в журнал | AC-5, AC-7 |
| `tests/test_retro_artifact_branch_reads.py::RetroWithoutBranchTest::test_generation_degrades_to_zeros_and_bare_title` | предпосылка `snapshot_pending` ложна | ссылки документов нет (`ref_head` пуст) | удалён `snapshot_pending` |
| `tests/test_review_package.py::CmdRunReviewPackageTest::test_developer_step_has_no_package` | git-вызовы по `artifact/<id>` | те же вызовы по `refs/artifacts/<id>` | требование 1 |

Утверждения сохранены, менялась только подготовка: `test_doctor.py::
RecoveryCheckTest::test_sha_mismatch_raises_an_incident_alert` (голова
ссылки вместо репозитория фиксации; итерация 2 — подмена
`gitcmd.is_ancestor` заменена подменой `gitcmd.commit_exists`, R1-F3), `test_git_fixation.py::ApproveByShaTest::
test_approve_on_escalated_with_matching_sha_returns_to_escalated_from` и
`RunnerEscalationHintsIncludeShaTest::test_integrity_incident_hint_includes_full_fixed_sha`
(подмена — коммитом в ссылку), `test_merge_gate_ci_wait.py` (подмена
новых узлов гейта вместо `_publish_closing_snapshot_or_wait`),
`tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py::MergeSandbox.make_task`
(документы — в `refs/artifacts/<id>`, возврат из verifying) и остальные
файлы WIP `aa7cd419` (импорты, песочница `tests/sandbox.py`).

## Приложение: docs/invariants.md — инварианты 25, 27, 28, 33, 34, 38 (ADR-0021 п.12)
Проверено: `git apply --check` на чистом дереве ветки — применяется;
`tests/test_invariants.py` с наложенным приложением — 66 passed.
`tests/test_invariants.py` правки не требует: ни один его узел не
утверждает ветку `artifact/<id>` или снимок закрытия.

```diff
diff --git a/docs/invariants.md b/docs/invariants.md
index cb1233a0..b674ca24 100644
--- a/docs/invariants.md
+++ b/docs/invariants.md
@@ -52,21 +52,21 @@ docs/adr/0002-integrity-principle.md, CLAUDE.md.
 | 22 | Нумерация задач независима per-target; операции по `task_id` (журнал, spend, kill) одного target не читают и не меняют строки другого | `test_multitarget_invariants.CrossTargetDbIsolationTest` | ADR-0003 3ж; tasks/T020/SPEC.md, требование 3 |
 | 23 | Пороги суммарного расхода программы (70%/90%) считаются суммой `spent_usd` по всем задачам ВСЕХ target, не одного | `test_multitarget_invariants.ProgramSpendAcrossTargetsTest` | roadmap §5; ADR-0003 3ж; tasks/T020/SPEC.md, требование 4 |
 | 24 | Счётчик номеров задач target не переиспользует номер архивированной (не удалённой) строки при пересеве после reconnect | `test_multitarget_invariants.CounterSurvivesArchivalOnReconnectTest` | ADR-0003 3ж («архивация строк, никогда DELETE»); tasks/T020/SPEC.md, требование 5 |
-| 25 | FSM принимает решения только по артефактам, чьи хэши зафиксированы его журналом: расхождение живого sha (или грязная копия) с зафиксированным на последнем переходе — инцидент целостности, агент не запускается; `approve` без явного sha сам сверяет живой sha и чистоту копии/артефактной ветки с зафиксированными на последнем переходе тем же источником, которым печатается подсказка — совпало, гейт проходит без ручного набора и журналирует согласованный sha, расхождение/грязная копия отклоняют его именованным отказом с обоими sha так же, как и явный неверный sha | `test_git_fixation.FsmDecidesOnlyOnFixedHashesTest`; `test_git_fixation.IntegrityIncidentBlocksRunTest`; `test_git_fixation.ApproveByShaTest`; `tasks/01M1SHJX22EMEP4AJ9FFJJ09DC/acceptance_tests/test_ac1_*.py`, `test_ac2_matching_fixation_auto_confirms.py`, `test_ac3_diverged_or_dirty_refuses_named.py` | ADR-0003 п.15, п.17; tasks/T021/SPEC.md, требования 4–6; tasks/01M1SHJX22EMEP4AJ9FFJJ09DC/SPEC.md, требования 1–2 |
+| 25 | FSM принимает решения только по артефактам, чьи хэши зафиксированы его журналом (для документов задачи зафиксированное состояние — коммит ссылки `refs/artifacts/<id>`, ADR-0021 п.3): расхождение живого sha (или грязная копия) с зафиксированным на последнем переходе — инцидент целостности, агент не запускается; `approve` без явного sha сам сверяет живой sha и чистоту копии/ссылки документов с зафиксированными на последнем переходе тем же источником, которым печатается подсказка — совпало, гейт проходит без ручного набора и журналирует согласованный sha, расхождение/грязная копия отклоняют его именованным отказом с обоими sha так же, как и явный неверный sha | `test_git_fixation.FsmDecidesOnlyOnFixedHashesTest`; `test_git_fixation.IntegrityIncidentBlocksRunTest`; `test_git_fixation.ApproveByShaTest`; `tasks/01M1SHJX22EMEP4AJ9FFJJ09DC/acceptance_tests/test_ac1_*.py`, `test_ac2_matching_fixation_auto_confirms.py`, `test_ac3_diverged_or_dirty_refuses_named.py` | ADR-0003 п.15, п.17; tasks/T021/SPEC.md, требования 4–6; tasks/01M1SHJX22EMEP4AJ9FFJJ09DC/SPEC.md, требования 1–2; ADR-0021 п.3, п.12; SPEC 01M3Z2DMQRD0BD7AARFVTCVVG8, требование 4 |
 | 26 | Выход из `tests_writing`: критерий приёмки (AC-n) без теста и без пометки manual/skip/escalate — невалидный выход, переход отказывает с именем критерия | `test_acceptance_tests_flow.TraceabilityTest` | tasks/T023/SPEC.md, требование 4 |
-| 27 | Каталог `acceptance_tests/` залочен фиксацией T021 после выхода из `tests_writing`: расхождение с зафиксированным на выходе sha — отказ перехода `in_dev → verifying` и гейта мержа после подтяжки main, код чинится под тест, не наоборот. Лок распространяется на перечень долгоживущих файлов задачи `acceptance_tests/long_lived.sha256.txt` (суммы `tests/test_<id задачи в нижнем регистре>_*.py` кодовой ветки): сверка сумм с головой кодовой ветки — на переходах `in_dev → verifying`, `verifying → review`, `review → acceptance`, `approve` из `acceptance` и на гейте мержа после подтяжки main; изменённый или удалённый файл, сбой git — отказ | `test_acceptance_tests_flow.LockTest`; `test_long_lived_manifest.ManifestCheckNodeTest`; `test_long_lived_transitions.ManifestBoundariesTest`, `test_long_lived_transitions.MergeGatePlankLockTest`, `test_long_lived_transitions.TestsWritingManifestTest` | tasks/T023/SPEC.md, требование 5; ADR-0015 (переезд рубежа с `in_dev → review`); ADR-0020, п. 3; SPEC 01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ, требования 6-8 |
-| 28 | Чтение артефактов задачи оркестратором (маршрутизация `spec_gate`, бриф роли developer, трассируемость AC, лок `acceptance_tests/`, sha догфуд-фиксации, статус SPEC.md и батч QUESTIONS.md на переходе `spec_writing → spec_gate`, вердикт REVIEW.md — status и iteration — на переходе `review → acceptance/in_dev`) не зависит от того, какая ветка сейчас выписана в рабочем дереве пульта: источник истины — ВЕТКА задачи (`git show`/`git ls-tree`), чужой чекаут её не подменяет; ветка ещё не создана ролью — прежнее поведение (рабочая копия), не именованный отказ | `test_gitcmd_branch_reads.OnForeignBranchTest`; end-to-end по каждому месту чтения — `tasks/T031/acceptance_tests/test_branch_correct_reads.py` (`SpecGateBranchRoutingTest`, `BriefBuildBranchTest`, `TraceabilityBranchTest`, `LockBranchTest`, `FixationBranchTest`, `NoUnhandledExceptionOnMissingBranchTest`); `tasks/T047/acceptance_tests/test_branch_correct_status_reads.py` (`SpecWritingBranchRoutingTest`, `ReviewBranchRoutingTest`, `NoTaskBranchDegradationTest`, `NoGitDegradationTest`) | tasks/T031/SPEC.md, требования 1–2; tasks/T030 (класс-дефект «артефакто-чтения ветко-зависимы», журнал ~17:35 25.08.2026); tasks/T047/SPEC.md, требования 1–4 (инциденты T046 27.08.2026, T045 27.08.2026) |
+| 27 | Каталог `acceptance_tests/` залочен фиксацией T021 после выхода из `tests_writing` — коммитом ссылки документов `refs/artifacts/<id>` (`tests_locked_sha`, ADR-0021 п.3): расхождение с зафиксированным на выходе sha — отказ перехода `in_dev → verifying` и гейта мержа после подтяжки main, код чинится под тест, не наоборот. Лок распространяется на перечень долгоживущих файлов задачи `acceptance_tests/long_lived.sha256.txt` (суммы `tests/test_<id задачи в нижнем регистре>_*.py` кодовой ветки): сверка сумм с головой кодовой ветки — на переходах `in_dev → verifying`, `verifying → review`, `review → acceptance`, `approve` из `acceptance` и на гейте мержа после подтяжки main; изменённый или удалённый файл, сбой git — отказ | `test_acceptance_tests_flow.LockTest`; `test_long_lived_manifest.ManifestCheckNodeTest`; `test_long_lived_transitions.ManifestBoundariesTest`, `test_long_lived_transitions.MergeGatePlankLockTest`, `test_long_lived_transitions.TestsWritingManifestTest` | tasks/T023/SPEC.md, требование 5; ADR-0015 (переезд рубежа с `in_dev → review`); ADR-0020, п. 3; SPEC 01M3N3Z1ZHTGMSQZ4SNRYNJ2SJ, требования 6-8; ADR-0021 п.12 |
+| 28 | Чтение артефактов задачи оркестратором (маршрутизация `spec_gate`, бриф роли developer, трассируемость AC, лок `acceptance_tests/`, sha догфуд-фиксации, статус SPEC.md и батч QUESTIONS.md на переходе `spec_writing → spec_gate`, вердикт REVIEW.md — status и iteration — на переходе `review → acceptance/in_dev`) не зависит от того, какая ветка сейчас выписана в рабочем дереве пульта: источник истины — ссылка документов задачи `refs/artifacts/<id>` (ADR-0021 п.3; до неё — ветка задачи), читаемая `git show`/`git ls-tree`, чужой чекаут её не подменяет; ветка ещё не создана ролью — прежнее поведение (рабочая копия), не именованный отказ | `test_gitcmd_branch_reads.OnForeignBranchTest`; end-to-end по каждому месту чтения — `tasks/T031/acceptance_tests/test_branch_correct_reads.py` (`SpecGateBranchRoutingTest`, `BriefBuildBranchTest`, `TraceabilityBranchTest`, `LockBranchTest`, `FixationBranchTest`, `NoUnhandledExceptionOnMissingBranchTest`); `tasks/T047/acceptance_tests/test_branch_correct_status_reads.py` (`SpecWritingBranchRoutingTest`, `ReviewBranchRoutingTest`, `NoTaskBranchDegradationTest`, `NoGitDegradationTest`) | tasks/T031/SPEC.md, требования 1–2; tasks/T030 (класс-дефект «артефакто-чтения ветко-зависимы», журнал ~17:35 25.08.2026); tasks/T047/SPEC.md, требования 1–4 (инциденты T046 27.08.2026, T045 27.08.2026) |
 | 29 | Стоимость шага не остаётся неучтённой молча: если финальное событие потока (`type: result`) не пришло из-за таймаута шага или обрыва stdout-пайпа, в журнал попадает либо частичная сумма из промежуточных usage-событий с пометкой «частичная», либо событие «стоимость шага неизвестна» с открытым алертом `alerts` (`kind=incident`, `source=spend.unknown_cost`); `spent_usd` при этом не дописывается фиктивной суммой | `tasks/T040/acceptance_tests/test_step_cost_on_missing_final_event.py::MissingFinalEventCostTest`; `test_step_cost.ChargeMissingResultTest`; `test_step_cost.CmdRunPartialCostTest` | tasks/T040/SPEC.md, требования 1–3 |
 | 30 | Таймаут шага с незакоммиченным WIP в рабочем дереве ветки задачи коммитится оркестратором чекпоинтом (`<id>: WIP-чекпоинт после таймаута шага <role>`, журнал actor=`orchestrator`) без участия Оператора; провал шага по коду возврата (не таймаут) и таймаут при уже чистом дереве чекпоинт не коммитят | `tasks/T041/acceptance_tests/test_checkpoint_after_timeout.py::CheckpointAfterTimeoutTest`; `test_timeout_checkpoint.CommitTimeoutCheckpointTest` | tasks/T041/SPEC.md, требования 1–4; прецеденты tasks/T022, tasks/T037 (ручной чекпоинт Оператора) |
 | 31 | Агентный шаг роли не читает и не исполняет project-/local-слой клиентских настроек репозитория (`.claude/settings.json`, `.claude/settings.local.json`, включая хуки — ни главной копии пульта, ни worktree роли): `run_agent_once` вызывает `claude` с `--setting-sources user` (`config.AGENT_SETTING_SOURCES`), исключающим оба слоя из резолвинга CLI независимо от cwd. Времянка «операторские хуки обязаны безвредно деградировать» (27.08, инцидент T046) остаётся вторым рубежом (defense-in-depth), не единственной защитой | `test_agent_prompt.PromptChannelTest` (argv несёт флаг); `test_doctor.IsolationSmokeTest` (структурный маркер); `tasks/T058/acceptance_tests/test_ac1_ac2_role_hook_isolation.py` (канарейка реально не/срабатывает — role/operator) | ADR-0003 п.14; tasks/T058/SPEC.md, требования 1–2; инцидент T046 27.08.2026 |
 | 32 | Потолок `MAX_PARALLEL_TASKS` блокирует старт агентного шага (`run`/`auto`), пока число других задач с живым lease (heartbeat не старше `LEASE_STALE_AFTER_SEC`, pid адресуем) не опустится ниже потолка; отказ именует занятые задачи и их `session_id`, пишется в журнал, не обходится ни повторным `run`, ни `advance` следующим за отказавшим шагом; собственный lease стартующей задачи и протухшие/мёртвые чужие lease в счёт не идут; `kill`/`status`/`approve`/`reject`/`budget`/`log`/`release`/`doctor` лимитером не затронуты | `test_invariants.ParallelTaskLimitIsNotBypassableTest`; `tasks/T060/acceptance_tests/test_max_parallel_tasks.py`; `tasks/T062/acceptance_tests/test_ac1_ac2_ac3_ac5_release_command.py::Ac5ReleaseBypassesLeaseAndLimiterTest` | tasks/T060/SPEC.md, требования 1-6; решение Оператора 28.08.2026 (очередь п.2б роадмапа); tasks/T062/SPEC.md, требование 4 |
-| 33 | Тесты не пишут в настоящий репозиторий пульта: полный прогон `tests/` не меняет набор ссылок (`refs/heads/*`, `refs/artifacts/*`) настоящего репозитория; вся плотницкая запись артефактной ветки (`artifact_branch.write_commit`/`commit_files`, `snapshot.py`, `pin.py`) идёт через единую точку подмены `gitcmd` (не `subprocess.run`/`Popen` напрямую), которую `tests/sandbox.py::TmpRootTest` патчит по умолчанию для всех наследников | `test_invariants.CarpentryGitCallsGoThroughGitcmdTest`; CI job `python` (сторож ссылок вокруг `unittest discover`, `.github/workflows/ci.yml`); `tasks/01M1KVGD18P9H5WR7VM8TGPV1T/acceptance_tests/test_ac1_full_suite_ref_isolation.py`, `test_ac2_previous_verdict_sha_test_migration.py`, `test_ac3_unified_git_choke_point.py` | tasks/01M1KVGD18P9H5WR7VM8TGPV1T/SPEC.md, требования 1-3 (класс-дефект: `tests.test_review_package.PreviousVerdictShaTest` заводил задачу через `cmd_new` без подмены `config.ROOT`, `artifact_branch.py` звал `subprocess.run` в обход `gitcmd` — сотни осиротевших веток `artifact/*` в настоящем репозитории пульта) |
-| 34 | Переход `in_dev → verifying` отказывает, если дифф ветки задачи трогает файлы вне объявленных `zones`/`zones_extension` и вне `config.COMMON_ZONES` (отказ называет конкретные файлы); исключение — раздел «## Расширение зон» PLAN.md, подкреплённый строкой `Расширение зон разрешено: <пути>` в ANSWER-n.md, ЧЕЙ ПОСЛЕДНИЙ КОММИТ доказанно не автокоммит артефактов шага роли (`checkpoint.py::own_commit_marker`) — developer не может подложить себе мандат Оператора через собственный автокоммит `tasks/<id>/` | `tests/test_zones_gate.py`; `tasks/01M1P9QCHPHSCEA6TK13PV85SP/acceptance_tests/` | tasks/01M1P9QCHPHSCEA6TK13PV85SP/SPEC.md, требования 1-3; REVIEW.md итерация 2, R2-F1; ADR-0015 (переезд рубежа с `in_dev → review`) |
+| 33 | Тесты не пишут в настоящий репозиторий пульта: полный прогон `tests/` не меняет набор ссылок (`refs/heads/*`, `refs/artifacts/*`) настоящего репозитория; вся плотницкая запись ссылки документов `refs/artifacts/<id>` (`artifact_branch.write_commit`/`commit_files`, коммит закрытия `snapshot.py`, `pin.py`; ADR-0021 п.3) идёт через единую точку подмены `gitcmd` (не `subprocess.run`/`Popen` напрямую), которую `tests/sandbox.py::TmpRootTest` патчит по умолчанию для всех наследников | `test_invariants.CarpentryGitCallsGoThroughGitcmdTest`; CI job `python` (сторож ссылок вокруг `unittest discover`, `.github/workflows/ci.yml`); `tasks/01M1KVGD18P9H5WR7VM8TGPV1T/acceptance_tests/test_ac1_full_suite_ref_isolation.py`, `test_ac2_previous_verdict_sha_test_migration.py`, `test_ac3_unified_git_choke_point.py` | tasks/01M1KVGD18P9H5WR7VM8TGPV1T/SPEC.md, требования 1-3 (класс-дефект: `tests.test_review_package.PreviousVerdictShaTest` заводил задачу через `cmd_new` без подмены `config.ROOT`, `artifact_branch.py` звал `subprocess.run` в обход `gitcmd` — сотни осиротевших веток `artifact/*` в настоящем репозитории пульта) |
+| 34 | Переход `in_dev → verifying` отказывает, если дифф ветки задачи трогает файлы вне объявленных `zones`/`zones_extension` и вне `config.COMMON_ZONES` (отказ называет конкретные файлы); исключение — раздел «## Расширение зон» PLAN.md, подкреплённый строкой `Расширение зон разрешено: <пути>` в ANSWER-n.md, ЧЕЙ ПОСЛЕДНИЙ КОММИТ в истории ссылки документов `refs/artifacts/<id>` (ADR-0021 п.3) доказанно не автокоммит артефактов шага роли (`checkpoint.py::own_commit_marker`) — developer не может подложить себе мандат Оператора через собственный автокоммит `tasks/<id>/` | `tests/test_zones_gate.py`; `tasks/01M1P9QCHPHSCEA6TK13PV85SP/acceptance_tests/` | tasks/01M1P9QCHPHSCEA6TK13PV85SP/SPEC.md, требования 1-3; REVIEW.md итерация 2, R2-F1; ADR-0015 (переезд рубежа с `in_dev → review`) |
 | 35 | Тесты не читают сеть по DNS-имени: ни один файл `tests/**/*.py` не несёт адреса вида `http(s)://<DNS-имя>`, кроме `localhost`/`127.0.0.1` (допустимые исключения — именованная константа с обоснованием на каждую строку); сетевые git-команды (`fetch`/`push`/`ls-remote`/`clone`) с таким адресом перехватываются `tests/sandbox.py::TmpRootTest` мгновенным именованным отказом («сеть в тестах запрещена: `<команда>` `<адрес>`»), без обращения к сети | `test_invariants.NoNetworkAddressesInTestsTest`; `tasks/01M1QHQ277PQQA894X97RVEX9Y/acceptance_tests/test_ac1_network_command_interception.py`, `test_ac2_local_bare_repo_not_blocked.py`, `test_ac9_network_interception_speed.py` | tasks/01M1QHQ277PQQA894X97RVEX9Y/SPEC.md, требования 1, 3 (инцидент 05.09: `git fetch -q https://example.invalid/sled main` висел минуты на DNS-резолвере при обрыве сети — фикстурный адрес `sled`-target'а в `tests/test_git_fixation.py`) |
 | 36 | Прогон CI существует для каждого пуша в `main`, `task/**`, `artifact/**`: секция `on.push` в `.github/workflows/ci.yml` не несёт фильтров `paths`/`paths-ignore`; лишние на данном классе пуша проверки снимаются условием на job (статус `skipped`, зелёный для `ci.GREEN`), причём job `python` не исключает `refs/heads/task/` и не строится как `== 'true'` по output соседнего job (fail-open), а job `guard` не исключает `refs/heads/artifact/` | `test_invariants.CiJobsByPushClassInvariantTest` | ADR-0016; `ci.verifying_status`/`ci.branch_status` читают пуш без прогона как «проверок нет вовсе» и держат задачу до потолка ожидания (инвариант 19) |
 | 36 | Порядок состояний FSM — `in_dev → verifying → review → acceptance → merge_gate`: CI подтянутой головы кодовой ветки проверяется ДО ревьювера, не после. Девять рубежей перехода `in_dev → review` (подтяжка main, прогон приёмочной планки, гейт зон, гейт заявки мутации — новые и изменённые тесты `tests/` без строки «Ловит мутацию:» в докстринге, 01M29A0F88P9GKSXFW90F99H2N, гейт неослабления тестов — удаление, переименование и ослабление тестов `tests/` без мандата Оператора, 01M3FQ2V77QNK95Z599DM124QN, гейт ёмкости, лок планки, гейт «замечания ревью не отработаны», сверка головы на origin) стоят на `in_dev → verifying` целиком, без повтора на `verifying → review`; в `review` из `verifying` ведёт только зелёный CI головы. Возврат `changes_requested` — в `in_dev`, повторный вход в `review` — снова через `verifying` | `tasks/01M1TQ0TRCZPRZX22C4084NCPB/acceptance_tests/test_ac01_ac09_state_order.py`; `tasks/01M1TQ0TRCZPRZX22C4084NCPB/acceptance_tests/test_ac02_ac08_gates_moved_to_verifying.py`; `test_auto_cycle.py::FSM_STATES` | ADR-0015 (docs/adr/0015-ci-before-review.md); tasks/01M1TQ0TRCZPRZX22C4084NCPB/SPEC.md, требования 1-3 |
 | 37 | Класс `tests/*.py` с собственным `PATCHED_ATTRS` для `tests.sandbox.TmpRootTest` патчит `config.WORKTREES`, либо явно значится в `ALLOWLIST` скана с обоснованием, почему запись по этому пути для него недостижима (read-only сценарий или подмена самого `workspace.ensure`, не пути) — непропатченный `WORKTREES` не двигается вместе с `config.ROOT` (вычислен один раз при импорте) и уводит настоящий `git worktree add` в `.artel/worktrees` реального корня пульта, а не песочницы теста | `test_invariants.SandboxPatchedAttrsCoverWorktreesInvariantTest` | tasks/01M2CN465WEDCF6D77V37FJ82E/SPEC.md; docs/audits/code-revision-2026-09-12.md (CR-2026-09-12-1 ★), docs/audits/code-revision-2026-09-13.md (повтор) |
-| 38 | Удаление, переименование и ослабление тестов `tests/**/*.py` без мандата Оператора не проходят: переход `in_dev → verifying` отказывает именованным действием «переход отклонён: гейт неослабления тестов», гейт мержа тем же узлом сравнения переводит задачу в `escalated` до попытки merge. Находка — удалённый файл, пара переименования (`git diff -M`), исчезнувший из head тестовый метод изменённого файла и появившийся в head пропуск (`@skip`/`@skipIf`/`@skipUnless`/`@expectedFailure`/`@pytest.mark.skip`/`skipif`/`xfail`, вызов `self.skipTest(`/`pytest.skip(`), которого не было в base на том же имени; файл с нулём тестовых методов в base находкой не считается. Утверждение тестового метода, сохранившего имя, которого в head нет в той же нормальной форме (оператор `assert`, вызов `assert*`/`fail`, `pytest.raises`/`pytest.warns`; сообщение, локальные имена и корень импортированного модуля не различаются), — находка наблюдения: запись журнала «изменены утверждения тестов (наблюдение)» на обоих рубежах и раздел ревью-пакета, переход и мерж от неё не зависят (SPEC 01M3Y753QNG6TS5C7MTJS1MEV6). Мандат — строка `Ослабление тестов разрешено: <пути и имена>` в `tasks/<id>/ANSWER-n.md`, ЧЕЙ ПОСЛЕДНИЙ КОММИТ доказанно не автокоммит артефактов шага роли (тот же рубеж, что у мандата зон в инварианте 34): роль не выписывает разрешение себе сама. Молчание git на переходе — отказ (fail-closed, ADR-0002), на мерже — fail-open, как у соседнего рубежа защищённых путей | `test_invariants.TestWeakeningNeedsTheOperatorTest`; `tests/test_test_integrity_gate.py` (в том числе `AssertionObservationTest`); `tests/test_guard_test_ast.py` (в том числе `ChangedAssertionsTest`); `tests/test_01m3y753qng6ts5c7mtjs1mev6_assertion_observation.py`; `tasks/01M3FQ2V77QNK95Z599DM124QN/acceptance_tests/` | tasks/01M3FQ2V77QNK95Z599DM124QN/SPEC.md, требования 1-7; ADR-0002 (принцип целостности); строка бэклога П2 от 26.09.2026 «Гейт неослабления тестов в пульте» |
+| 38 | Удаление, переименование и ослабление тестов `tests/**/*.py` без мандата Оператора не проходят: переход `in_dev → verifying` отказывает именованным действием «переход отклонён: гейт неослабления тестов», гейт мержа тем же узлом сравнения переводит задачу в `escalated` до попытки merge. Находка — удалённый файл, пара переименования (`git diff -M`), исчезнувший из head тестовый метод изменённого файла и появившийся в head пропуск (`@skip`/`@skipIf`/`@skipUnless`/`@expectedFailure`/`@pytest.mark.skip`/`skipif`/`xfail`, вызов `self.skipTest(`/`pytest.skip(`), которого не было в base на том же имени; файл с нулём тестовых методов в base находкой не считается. Утверждение тестового метода, сохранившего имя, которого в head нет в той же нормальной форме (оператор `assert`, вызов `assert*`/`fail`, `pytest.raises`/`pytest.warns`; сообщение, локальные имена и корень импортированного модуля не различаются), — находка наблюдения: запись журнала «изменены утверждения тестов (наблюдение)» на обоих рубежах и раздел ревью-пакета, переход и мерж от неё не зависят (SPEC 01M3Y753QNG6TS5C7MTJS1MEV6). Мандат — строка `Ослабление тестов разрешено: <пути и имена>` в `tasks/<id>/ANSWER-n.md`, ЧЕЙ ПОСЛЕДНИЙ КОММИТ в истории ссылки документов `refs/artifacts/<id>` доказанно не автокоммит артефактов шага роли (тот же рубеж, что у мандата зон в инварианте 34): роль не выписывает разрешение себе сама. Молчание git на переходе — отказ (fail-closed, ADR-0002), на мерже — fail-open, как у соседнего рубежа защищённых путей | `test_invariants.TestWeakeningNeedsTheOperatorTest`; `tests/test_test_integrity_gate.py` (в том числе `AssertionObservationTest`); `tests/test_guard_test_ast.py` (в том числе `ChangedAssertionsTest`); `tests/test_01m3y753qng6ts5c7mtjs1mev6_assertion_observation.py`; `tasks/01M3FQ2V77QNK95Z599DM124QN/acceptance_tests/` | tasks/01M3FQ2V77QNK95Z599DM124QN/SPEC.md, требования 1-7; ADR-0002 (принцип целостности); строка бэклога П2 от 26.09.2026 «Гейт неослабления тестов в пульте» |
 
 ## На ревью — тестом не выражаются
 
```

## Ответ Оператора (ANSWER-1, 02.10.2026)
Эскалация закрыта ответом `tasks/01M3Z2DMQRD0BD7AARFVTCVVG8/ANSWER-1.md`:
1. Мандат на удаление 32 тестов снятой механики выдан строкой
   `Ослабление тестов разрешено: …` в ANSWER-1 (перечень — таблица
   «Удалены» выше).
2. Изменённые утверждения 14 методов приняты. Оговорка Оператора: ссылка
   документов внешнего target отправляется в origin пульта, а не target
   (расхождение с ADR-0021 п.3) — в этой части не исправляется, перенесено
   в часть (б) строкой бэклога Оператора.
3. Инвариант 25: «(или грязная копия)» остаётся до части (б).

Код и тесты после ответа не менялись до возврата из verifying (ниже).

## Возврат из verifying (CI ветки, прогон 37083080729)
Причина: `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py::
MergeGuardAfterSnapshotTest::test_ac1_clean_snapshot_merges_as_before` и
`::test_ac1_guard_violation_after_snapshot_refuses_before_push` красные в CI.
Фикстура `MergeSandbox.make_task` клала документы в ветку `artifact/<id>`, а
гейт мержа после части (а) накладывает снимок из `refs/artifacts/<id>`:
ссылки нет — накладывать и проверять guard'ом нечего, нарушение проходит,
а файл чистого снимка не доезжает до origin/main. Воспроизведено локально
без `ARTEL_ROLE` — ровно эти два метода, остальные 30 зелёные.

Исправление — только подготовка, утверждения не тронуты: `make_task`
пишет файлы снимка в `refs/artifacts/<id>` через
`artifact_branch.commit_files` (тот же узел, что у пульта; он же
отправляет ссылку в origin, с которым гейт мержа сверяет её до мержа —
AC-6), после `store.insert_task`; ветка `artifact/<id>` больше не
заводится; докстринги `MergeSandbox`/`make_task` приведены к ссылке.
Импорт `artifact_branch` добавлен в файл.

Проверка (без `ARTEL_ROLE`): файл целиком и `tests/test_main_ci_line.py` —
32 passed, 4 subtests passed. Временная мутация (подмена
`fsm_merge_gate._guard_all_violations` на «нарушений нет» в процессе
pytest, файл не правился) — `test_ac1_guard_violation_after_snapshot_refuses_before_push`
красный, т.е. тест снова ловит свою мутацию на ссылке документов.
Остальные тесты, списанные прежней сдачей на `ARTEL_ROLE`
(`tests/test_main_ci_line.py::FixesMainArgTest::test_flag_without_reason_is_refused`
и прочие методы этого файла), без признака зелёные — их краснота
действительно была от окружения шага. Широкий прогон без признака — раздел
«Покрытие требований».

## Возврат из ревью, итерация 1 (R1-F1…R1-F3)
- **R1-F1 (major)** — новый `tests/test_artifact_ref_sync.py`, 15 методов
  на настоящем git с bare origin (`AutoOriginSandbox`), у каждого заявка
  «Ловит мутацию». Код узла записи, гейта мержа и `kill` не менялся.
- **R1-F2 (minor)** — `orchestrator/doctor/artifact_branches.py::
  _fix_unsent_closed_refs`, вызов в `doctor/cli.cmd_doctor` под `--fix`
  до `all_checks`. Досылает закрытую ссылку, у которой локальная голова
  равна коммиту закрытия из журнала, а в origin другое значение. Отправка
  идёт обычным `artifact_branch.push` без force, исход пишется в журнал
  задачи. Ссылку, изменённую после закрытия, не досылает: о ней говорит
  `check_artifact_ref_sync`. Общий отбор закрытых задач вынесен в
  `_closed_with_closing_sha`, его зовут и проверка, и досылка.
- **R1-F3 (minor)** — `gitcmd.commit_exists` (`cat-file -e
  <sha>^{commit}`). `doctor/recovery.recovery_check` признаёт фиксацию
  прежнего устройства по отсутствию объекта в базе пульта, а не по «не
  предок головы». Прежняя фиксация — коммит отдельного репозитория
  `.artel/projects/<target>/` (`main:orchestrator/fixation.py::
  _fix_external`), в базе пульта его нет, поэтому ложных инцидентов на
  старых задачах не будет.

Временные мутации: подмена в процессе pytest, файлы кода не правились,
кроме последней (в ней строка удалена и затем возвращена). Прогон —
`tests/test_artifact_ref_sync.py` без `ARTEL_ROLE`, все красные:
1. `origin_sync_refusal → None` — 5 failed (сверка, гейт мержа, `kill`);
2. `update-ref` без прежнего значения — `CompareAndSwapRaceTest` failed;
3. `send_pending → no-op` — `test_refusal_is_journaled_commit_kept_and_retried_on_transition` failed;
4. `_send → no-op` — 9 failed;
5. `_refuse_unsynced_docs → no-op` — `KillDocsRefTest::test_unsynced_ref_refuses_kill_and_keeps_state` failed;
6. `_docs_ref_unsynced → False` — `MergeGateDocsRefTest::test_unsynced_ref_stops_the_gate_named` failed;
7. `_fix_unsent_closed_refs → no-op` — `test_fix_pushes_the_closing_commit` failed;
8. `commit_exists → False` (то же, что прежнее «не предок») — `test_ref_rewritten_outside_its_history_is_a_mismatch` failed;
9. `commit_exists → True` (признак прежнего устройства снят) — `test_fixation_of_the_old_device_is_not_compared` failed;
10. в досылке убрана сверка головы с коммитом закрытия —
    `test_fix_does_not_resend_a_ref_moved_after_closing` failed.

Прогоны без `ARTEL_ROLE`: `test_artifact_ref_sync`, `test_doctor`,
`test_doctor_artifact_branch_sync`, `test_doctor_fix_ignored_artifacts`,
`test_gitcmd_branch_reads`, `test_codebase_map`, `test_invariants`,
`test_artifact_branch_push`, `test_snapshot_closing_outcome` — 290 passed,
218 subtests passed. Планка задачи — 46 passed. Карта регенерирована.

## Отказ гейта ёмкости diff (после итерации 2)
Переход `in_dev → verifying` отказал: diff кода 262 678 байт при потолке
262 144 байт. Задачу не делим: монолит принят Оператором (SPEC, «Оценка
объёма и деление»). Превышение составило 534 байта, поэтому сокращены
только докстринги нового кода, которые повторяли докстринг модуля или
описывали снятую механику. Код, тесты и утверждения не менялись.
- `orchestrator/doctor/artifact_branches.py` — абзац модуля о снятых
  проверках ветки; докстринги `_fix_unsent_closed_refs` и
  `check_artifact_ref_sync`. Там же поправлен пробел в `ok = doctor…`.
- `orchestrator/artifact_branch.py` — в `commit_files`, `_send` и
  `origin_sync_refusal` убраны повторы докстринга модуля.
- `orchestrator/snapshot.py` — сокращён абзац модуля о прежнем снимке.

Итог: diff кода 259 453 байт (`git diff 65a128b8 -- . ':!docs/codebase-map.md'
':!tasks'`), запас 2,7 КБ. Прогоны без `ARTEL_ROLE`: `test_artifact_ref_sync`,
`test_doctor_artifact_branch_sync`, `test_snapshot_closing_outcome`,
`test_artifact_branch_push`, `test_doctor`, `test_codebase_map`,
`test_fsm_merge_gate_done_snapshot` — 189 passed, 3 subtests passed;
планка задачи — 46 passed. Карта регенерирована.
