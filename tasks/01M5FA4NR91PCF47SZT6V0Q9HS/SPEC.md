---
task: 01M5FA4NR91PCF47SZT6V0Q9HS
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/canary.py, orchestrator/artel.py, orchestrator/doctor/canary_pool.py, orchestrator/doctor/cli.py, orchestrator/doctor/__init__.py, tests/
budget_usd: 27
---

# SPEC: Механика канарейки, часть Б-2: реестр живой канарейки

## Контекст
Часть А (коммит 25bd2f22) ввела реестр живого прогона канарейки: запись
`<run_stamp>-<pid>.json` и метку `<run_stamp>.lock` (`orchestrator/canary.py:2823`,
`_live_run_record`), сверку живости (`_live_verdict`, `:2862`), уборку
(`_drop_live_record`, `:2895`), чтение (`live_runs`, `:2911`, видит только
записи) и причину (`live_run_note`, `:2941`). Потребители реестра — окно тишины
(`orchestrator/notes.py:266`), отказ мержа (`orchestrator/fsm_merge_gate.py:1255`)
и обходы окна (`refuse_main_move_during_canary`, `orchestrator/canary.py:2959`).
Сегодня реестр не видит метку без записи, поэтому удаление записи при
оставленной метке молча снимает окно тишины и отказ мержа. Запись живого, но
зависшего процесса можно снять только удалением файла руками, а до этого она
держится до потолка (при `--k 5` — 41 ч). Реестр не показывают ни отдельная
команда, ни `doctor`. Тест
`CmdCanaryTemplateSelectionTest` (`tests/test_canary_template_flag.py:186`) и
тесты тела окна мержа читают и пишут настоящий реестр пульта (строки бэклога
`docs/backlog.md:286`, `:287`; перенос 2 гейта SPEC части А). Решения Оператора
21.10: метка без записи при живом pid означает живой прогон; `doctor`
предупреждает о записи старше `CANARY_DRIVE_TIMEOUT_SEC` (8 ч); `--drop` берётся
в строгом варианте: снимает только зависшее, на живой прогон отказывает.
Решения Оператора на гейте SPEC (круг 1) по
отклонениям аудита вошли в требования 1–5 и критерии ниже.

Граница задачи: новое поведение — только у метки без записи, у подкоманды
`canary live` и у проверки `doctor` реестра (одна новая строка `canary-live`),
плюс изоляция тестов. Прогон канарейки, запись реестра, `live_runs` и
потребители реестра при наличии записи остаются прежними побайтно.

## Требования

1. **Метка без записи.** `live_runs()` не меняется и по-прежнему читает только
   записи. Метки без записи читает новая функция. Порядок в одном вызове
   `live_run_note`: сначала записи с их прежней уборкой мёртвых
   (`_drop_live_record`), затем метки, у которых после этой уборки не осталось
   ни одной записи того же `run_stamp`. Метку, рядом с которой после уборки
   осталась запись того же `run_stamp`, новая логика не трогает. Для метки без
   записи:
   - pid в метке жив — прогон живой, причина «идёт канарейка <run_stamp>
     (запись реестра отсутствует)». Окно тишины, отказ мержа и отказ обходов
     окна держатся. Для отказа мержа такой прогон считается прогоном набора по
     умолчанию: набор неизвестен, и это безопасная сторона;
   - метка пустая или непустая, но не число (не читается), и моложе 60 с по
     времени правки — прогон живой. Старше 60 с — метка убирается строкой
     журнала пульта `LIVE_RUN_SWEPT_ACTION`;
   - pid мёртв — метка убирается той же строкой журнала.
   Отказ повтора `run_stamp` при оставшейся метке — прежний. Уборка мёртвых
   записей и меток выполняется только этим путём: прежними читателями реестра
   (`note`, `doc-commit`, `approve` и прочие команды с окном тишины),
   `canary live` (требования 2–3) и `doctor --fix` (требование 4).
2. **Команда `canary live`.** Без аргументов печатает реестр:
   - по записи — `run_stamp`, pid, `parent_pid` и шаблон (если они есть в
     записи), sha7, набор, время начала, возраст и остаток до потолка. Потолок
     считается по прежней формуле `CANARY_DRIVE_TIMEOUT_SEC` × число задач
     записи + 1 ч (`orchestrator/canary.py:2876`);
   - по метке без записи — `run_stamp`, pid и возраст по времени правки;
   - на пустом реестре — «живых прогонов канарейки нет».
   Перед показом мёртвые записи и метки убираются прежним путём чтения реестра
   (требование 1, как у `note`).
3. **Снятие записи.** `canary live --drop <run_stamp> "<основание>"`.
   - Сначала проверяются аргументы: `<run_stamp>` должен соответствовать
     шаблону `^\d{8}T\d{6}Z$`, иначе отказ до чтения каталога реестра.
     Отказывают также `--drop` без `run_stamp`, пустое основание (по образцу
     `_fixes_main_arg`, `orchestrator/artel.py:1762`) и лишние аргументы
     `canary live`.
   - Затем выполняется прежняя уборка чтения реестра (требование 1).
   - Если записи и метки `<run_stamp>` после уборки нет — вывод «canary live: в
     реестре нет <run_stamp>», код выхода 0, строки журнала `operator` нет.
     Уборку журналирует прежняя строка `LIVE_RUN_SWEPT_ACTION`.
   - Иначе команда снимает только: (а) запись старше `CANARY_DRIVE_TIMEOUT_SEC`;
     (б) запись, у которой время старта процесса не определилось при записи
     или при сверке; (в) метку без записи. Снимаются все такие записи этого
     `run_stamp` и его метка. Процессы сигналов не получают.
   - Если снимать нечего — отказ «canary live: прогон <run_stamp> жив (pid
     <pid>, возраст <ч>) — снимать нечего; дождись итога или используй
     --during-canary у конкретной команды».
   - Успешное снятие пишет строку журнала пульта без задачи от `operator`
     новой константой действия. Деталь — имена удалённых файлов и основание.
     Если процесс прогона жив, вывод команды и деталь журнала несут «процесс
     <pid> жив — прогон продолжается без защиты окна».
   - Под ролью обе формы `canary live` отказывают прежним механизмом
     `_role_allowed_command` (`orchestrator/artel.py:2017`), разрешённой
     подкоманда не становится.
   - Справка команды (`orchestrator/artel.py:181`) называет подкоманду.
4. **Реестр в `doctor`.** Проверка `canary-live` реестр только читает: ничего
   не удаляет и журнал не пишет.
   - Живых прогонов нет — `ok` «живых прогонов канарейки нет».
   - Есть живые — `ok` со списком «<run_stamp> на <sha7>, pid <pid>, возраст
     <ч>». Метка без записи идёт в списке с пометкой «запись реестра
     отсутствует» и возрастом.
   - Запись старше `CANARY_DRIVE_TIMEOUT_SEC` или метка без записи старше
     `CANARY_DRIVE_TIMEOUT_SEC` по времени правки — `warn` с подсказкой
     `canary live --drop <run_stamp> "<основание>"`.
   - Мёртвые записи и метки (их убрала бы уборка требования 1) — `warn` с
     подсказкой `doctor --fix` или `canary live --drop`. Файлы остаются, строки
     журнала нет.
   `doctor --fix` до проверок убирает мёртвые записи и метки прежним путём
   чтения реестра (требование 1), со строкой журнала `LIVE_RUN_SWEPT_ACTION`.
   Новая проверка (и её починка под `--fix`) реэкспортируется в
   `orchestrator/doctor/__init__.py`. Собирается она рядом с проверками
   канарейки (`orchestrator/doctor/cli.py:153`), починка — в ветке `--fix`
   `cmd_doctor` (`orchestrator/doctor/cli.py:194`). Подпись `all_checks`
   прежняя.
5. **Изоляция тестов реестра.** Классы тестов из перечня ниже при прогоне не
   читают и не пишут настоящий реестр пульта. Каталог реестра (`_live_dir()`)
   при их прогоне не лежит под настоящим корнем пульта. Способ — песочница
   `ALL_CONFIG_ATTRS` (`tests/sandbox.py:90`) или подмена пути реестра; для
   `CmdCanaryTemplateSelectionTest` — подмена `canary._live_dir` на временный
   каталог в `setUp`. В определение изоляции входят все пути к реестру: тело
   окна мержа до `_refuse_during_canary`, `live_run_note`, `live_runs`, чтение
   и уборка реестра, `doctor.all_checks` с проверкой `canary-live` и команда
   `canary live`. Перечень разработчик может только дополнять, с записью о
   каждом добавленном классе в отчёте; убрать класс из перечня нельзя. Классы
   защищённого пути `tests/test_invariants.py` входят в перечень; если такой
   класс требует правки для изоляции — эскалация, а не правка. Это добавление
   изоляции: существующие утверждения не меняются и не удаляются.

   Перечень — 116 классов в 58 файлах. Он найден прогоном 236 файлов `tests/`,
   которые упоминают потребителей реестра, `doctor`, `note`, `approve`,
   `doc-commit`, `canary` или `artel.main`. Прогон шёл со шпионом на
   `canary._live_dir`, `doctor.all_checks` и
   `fsm_merge_gate._refuse_during_canary` на коде main 58c9a84b. В перечень
   вошёл каждый класс, хотя бы один тест которого дошёл до одной из этих
   функций:

   - `tests/test_01m3pymq6n4scaj9wwttkh6xng_canary_clone_models.py`: `BaselineModelsChangeTest`, `CodexRoleOfTheSetTest`, `DefaultRunCloneLayerTest`, `RunSummaryModelsTest`, `SetByRolesTest`
   - `tests/test_01m3pymq6n4scaj9wwttkh6xng_role_models.py`: `RoleModelsDoctorLinesTest`
   - `tests/test_01m3s9hfdds9s4274w6tbqjbh7_canary_acceptance.py`: `CanaryAcceptanceResultTest`
   - `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`: `DoctorMainCiLineTest`, `MergeGuardAfterSnapshotTest`, `MergeWaitsForMainCiTest`, `NextMergeRefusedOnRedMainTest`, `RedMergeThenDocCommitTest`
   - `tests/test_01m3sk48d7rdqpsen78894gda5_codex_home.py`: `CanaryCodexHomeTest`
   - `tests/test_01m3v4zpb6hfdj36mtdaqg5vnt_canary_profile.py`: `CanaryProfileTest`
   - `tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py`: `DoctorStaleCyclesTest`
   - `tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py`: `DropPendingTest`, `HeldRecordBaseTest`, `ImmediatePinCheckTest`, `LegacyRecordTest`, `MatchingBaseSendTest`, `NewFileBaseTest`, `PendingListTest`, `RoleRefusalTest`, `StaleBaseRefusalTest`
   - `tests/test_01m3ychp14179r32sfjvkqb32g_model_sets.py`: `AdmitShortfallTest`, `AdmitWriteTest`, `CleanRunTest`
   - `tests/test_01m3yxyax5pw9bm67mb4gk85d1_step_provider_preflight.py`: `DoctorSetProvidersTest`
   - `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py`: `CloneCreationTest`, `CloneHooksFromPinTest`, `EndToEndMainCopyUntouchedTest`, `HeldRecordBaseFromCloneTest`, `MergeGateStepsOnCloneTest`, `OperatorCommandsThroughCloneTest`
   - `tests/test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied.py`: `AlreadyAppliedAppendixTest`
   - `tests/test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py`: `MergeGateDoneDependenciesTest`
   - `tests/test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py`: `ArtelFullSuiteClassesTest`, `ExternalAppendixTest`, `GeneratorMapTest`, `NoGeneratorMapTest`, `ProfileSuiteTest`, `ProtectedDiffTest`
   - `tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py`: `MergeGateUnchangedTest`
   - `tests/test_01m484rnv3qbdy3b0m16j916zp_artel_predicate.py`: `PredicateGitTest`
   - `tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py`: `ProfileLimitCutsGateRunTest`
   - `tests/test_01m48wre8bhfdy011q0hqgq91b_profile_limit_field.py`: `DoctorLimitLineTest`
   - `tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py`: `DoctorDurationTest`
   - `tests/test_01m4axpy1py4ps1yafamd47vby_canary_doctor.py`: `CanaryDoctorTest`
   - `tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py`: `CanaryLifecycleTest`
   - `tests/test_01m4beg0003ch0qa1gy0pxat03_canary_suite_skip.py`: `AutogateSkipTest`, `CanaryCloneSkipTest`
   - `tests/test_01m4c954hbjwegd3azs7q3eha4_doctor.py`: `HookAndDocumentationTest`
   - `tests/test_01m4c954hbjwegd3azs7q3eha4_watch.py`: `WatchContractTest`
   - `tests/test_01m4fytb8qwjnhycp35k8qc4e3_worktree_db_clean.py`: `DoctorWorktreeDbTest`
   - `tests/test_01m4g8mnepecnx1tcedw4t4rpx_origin_sweep.py`: `OriginSweepTest`
   - `tests/test_01m4jd3srn66sd6bm63xaghb11_merge_gate_in_base.py`: `MergeGateAlreadyInBaseTest`
   - `tests/test_01m4jmmh70nwjg72g422bfy1kc_postmerge_map_interpreter.py`: `PostMergeMapInterpreterTest`
   - `tests/test_01m4k2767fxkz8ew7ame81sz9n_suite_near_limit.py`: `NotesNearLimitTest`
   - `tests/test_01m4m67sgneymn9f1c7xvx24xe_merge_closing.py`: `ArtelMergeTest`, `ClosingFailureTest`, `ExternalMergeTest`
   - `tests/test_01m4m68557tt4kyn814h8az01a_history_snapshots.py`: `DoctorQuietTest`, `DoctorTamperTest`
   - `tests/test_01m4rzbpg6exm74mtbptegw2d4_note_merge_gate.py`: `NoteMergeGateTest`
   - `tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py`: `KnowledgeCommitTest`
   - `tests/test_01m4s24ebvb72b8wyj3jy96y0e_merge_reference.py`: `ArtelCodeMergeTest`, `ArtelMergeTest`
   - `tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py`: `MergeGateTest`, `PultUnchangedTest`
   - `tests/test_01m545edths47hsb59akc1ez9c_project_token.py`: `ProjectDoctorTest`
   - `tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py`: `NoteWindowProjectTest`
   - `tests/test_01m57pm7nbfx34319tr0f9cb4f_mutex_readers_all_rows.py`: `SilenceWindowAllRowsTest`
   - `tests/test_01m583rm59dhdrdh877aeravmd_early_signal.py`: `EarlySignalCanaryTest`
   - `tests/test_01m58pg72pg64gs790xm2ews61_doctor_components.py`: `DoctorOnComponentRecordsTest`, `PathsSourceTest`, `TestProfileRecordsUnchangedTest`, `ToolVersionTest`, `WorkdirTest`
   - `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_registry.py`: `CanaryRegistryTest`
   - `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_window.py`: `CanaryWindowTest`
   - `tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py`: `Ac14OutOfBoundsTest`, `Ac4ProofTest`, `Ac5ProofMismatchTest`, `Ac6LegacyRecordTest`, `Ac7MergeBaseTest`
   - `tests/test_canary_live_registry_units.py`: `LiveRunsSweepTest`
   - `tests/test_canary_template_flag.py`: `CmdCanaryTemplateSelectionTest`
   - `tests/test_doc_commit.py`: `DocCommitPushTest`, `DocCommitRefusalTest`, `PinBaseCheckTest`, `SilenceWindowAndFlushTest`
   - `tests/test_doc_commit_held_base.py`: `NetworkHoldBaseTest`
   - `tests/test_doc_commit_suite_gate.py`: `AcceptRedOnDocsPathTest`, `AcceptRedTest`, `GateRefusalLeavesNoDirtTest`, `HeldConfigRecordFlushTest`, `RedSuiteTest`, `SuiteTreeTest`
   - `tests/test_doctor.py`: `DoctorCommandTest`
   - `tests/test_doctor_canary_pool.py`: `CanaryPoolDriftCheckTest`
   - `tests/test_fsm_merge_gate_done_snapshot.py`: `DonePathSnapshotTest`
   - `tests/test_invariants.py`: `MainCopyGitUnchangedDuringTaskTest`, `ManualGatesNeedTheOperatorTest`, `MergeNeedsGreenCiTest`, `MergeOnlyFromMergeGateTest`
   - `tests/test_merge_gate_ci_wait.py`: `MovedMainRetryInCycleTest`
   - `tests/test_notes.py`: `CmdNoteArgumentValidationTest`, `SilenceWindowReasonTest`, `WindowBypassAndNoWindowTest`, `WindowHoldsValidNoteTest`
   - `tests/test_notes_apply.py`: `ApplyRefusalTest`, `ApplySilenceWindowTest`, `ApplySuccessTest`
   - `tests/test_notes_row_format.py`: `StateFlagAliasTest`
   - `tests/test_plan_appendix.py`: `MergeAppendixTest`
   - `tests/test_providers.py`: `AllChecksProviderNamesTest`

   На main 58c9a84b каталог реестра лежал под настоящим корнем пульта только у
   `CmdCanaryTemplateSelectionTest`. Для остальных 115 классов, в том числе
   для четырёх классов `tests/test_invariants.py`, изоляция уже держалась, и
   по требованию их нужно только проверить (AC-19).

6. Тесты задачи детерминированы, работают без сети, без настоящих ролей и без
   ожидания по часам. Время правки метки задаётся через `os.utime`.
7. Без метки без записи поведение `note`, `doc-commit`, `approve` и вывод
   `canary` остаются прежними. Существующие тесты (в том числе
   `tests/test_canary_live_registry_units.py`) не получают правок утверждений.

## Критерии приёмки

AC-1. Метка без записи с живым pid: `note` удержан окном тишины, `approve` на
`merge_gate` отказывает, `note --now` отказывает. Причина содержит «идёт
канарейка <run_stamp> (запись реестра отсутствует)».

AC-2. Пустая метка без записи моложе 60 с по времени правки (`os.utime`)
считается живым прогоном. Такая же метка старше 60 с убрана, в журнале пульта
есть строка `LIVE_RUN_SWEPT_ACTION`.

AC-3. Непустая нечисловая метка без записи (например, `abc`) моложе 60 с по
времени правки считается живым прогоном. Старше 60 с — убрана, в журнале пульта
есть строка `LIVE_RUN_SWEPT_ACTION`.

AC-4. Метка без записи с мёртвым pid убрана, в журнале пульта есть строка
`LIVE_RUN_SWEPT_ACTION`.

AC-5. Метка и мёртвая запись того же `run_stamp`, один вызов `note`:
(i) метка несёт живой pid, не совпадающий с pid записи. Запись убрана со
строкой `LIVE_RUN_SWEPT_ACTION`, метка осталась, и этот же вызов `note` удержан
окном тишины с причиной «(запись реестра отсутствует)».
(ii) метка несёт pid мёртвой записи. Убраны и запись, и метка, и этот же вызов
`note` окном тишины не удержан.

AC-6. Метку, рядом с которой после уборки осталась живая запись того же
`run_stamp`, новая логика не трогает. `live_runs()` по-прежнему отдаёт только
записи и метку без записи не возвращает.

AC-7. `canary live` без аргументов показывает:
- запись: `run_stamp`, pid, `parent_pid` и шаблон при наличии в записи, sha7,
  набор, время начала, возраст и остаток до потолка. Для записи с `tasks` = N
  остаток равен `CANARY_DRIVE_TIMEOUT_SEC` × N + 1 ч минус возраст;
- метку без записи: `run_stamp`, pid и возраст по времени правки;
- пустой реестр: «живых прогонов канарейки нет».

AC-8. `canary live` без аргументов убирает мёртвую запись и метку с мёртвым pid
со строкой журнала `LIVE_RUN_SWEPT_ACTION` и в выводе их не показывает.

AC-9. `canary live --drop <run_stamp> "<основание>"` снимает каждый из случаев:
(а) запись старше `CANARY_DRIVE_TIMEOUT_SEC`, (б) запись с неопределённым
временем старта процесса, (в) метку без записи. Снимаются все такие записи
этого `run_stamp` и его метка, процесс прогона сигнала не получает.

AC-10. Успешный `--drop` пишет строку журнала пульта без задачи от `operator`
новой константой действия. Деталь — имена удалённых файлов и основание. При
живом процессе прогона вывод команды и деталь журнала содержат «процесс <pid>
жив — прогон продолжается без защиты окна».

AC-11. `--drop` для живой свежей записи с определённым временем старта
отказывает: «canary live: прогон <run_stamp> жив (pid <pid>, возраст <ч>) —
снимать нечего; дождись итога или используй --during-canary у конкретной
команды». Запись остаётся.

AC-12. `--drop` с `run_stamp` не по шаблону `^\d{8}T\d{6}Z$` отказывает, каталог
реестра не читался.

AC-13. `canary live` отказывает при `--drop` без `run_stamp`, при пустом
основании и при лишних аргументах.

AC-14. `--drop <run_stamp>`, которого в реестре нет, а также `--drop` по
`run_stamp`, у которого была только мёртвая запись, выводят «canary live: в
реестре нет <run_stamp>», код выхода 0, строки журнала `operator` нет. Во
втором случае мёртвая запись убрана со строкой `LIVE_RUN_SWEPT_ACTION`.

AC-15. Под ролью обе формы `canary live` (показ и `--drop`) отказывают
механизмом `_role_allowed_command`. Справка команды называет подкоманду
`canary live`.

AC-16. `doctor`, проверка `canary-live`: на пустом реестре `ok` «живых
прогонов канарейки нет». Для живой записи `ok` со списком «<run_stamp> на
<sha7>, pid <pid>, возраст <ч>». Метка без записи с живым pid идёт с пометкой
«запись реестра отсутствует» и возрастом.

AC-17. `doctor`, проверка `canary-live`, даёт `warn` с подсказкой `canary live
--drop <run_stamp> "<основание>"` для записи старше `CANARY_DRIVE_TIMEOUT_SEC`
и для метки без записи старше `CANARY_DRIVE_TIMEOUT_SEC` по времени правки.

AC-18. `doctor` без `--fix` при мёртвой записи и при метке с мёртвым pid даёт
в проверке `canary-live` `warn` с подсказкой `doctor --fix` или `canary live
--drop`. Оба файла остаются на месте, новой строки журнала нет. `doctor --fix`
убирает их со строкой журнала `LIVE_RUN_SWEPT_ACTION`.

AC-19. Для каждого класса из перечня требования 5 (и для каждого класса,
добавленного разработчиком) при его прогоне каталог реестра `_live_dir()` не
лежит под корнем, снятым до подмен
(`Path(orchestrator.__file__).resolve().parents[1]`). Тест-шпион проверяет это
поклассово.

AC-20. Без метки без записи поведение `note`, `doc-commit`, `approve` и вывод
`canary` прежние.

## Оценка объёма и деление

Сработавшие сигналы:
- файлов зоны ≥ 5 (шесть: `orchestrator/canary.py`, `orchestrator/artel.py`,
  `orchestrator/doctor/canary_pool.py`, `orchestrator/doctor/cli.py`,
  `orchestrator/doctor/__init__.py`, `tests/`);
- критериев приёмки ≥ 10 (20).

Решение — обоснование монолита (материал для Оператора). Задача уже является
частью деления, утверждённого Оператором 21.10 (часть Б делится на Б-2 и Б-1),
с рамкой бюджета $22–27. Внутри неё всё опирается на одну механику — чтение
меток без записи (требование 1): `canary live` их показывает, случай (в)
`--drop` их снимает, `doctor` о них предупреждает. Отрезать показ, снятие и
`doctor` от требования 1 можно только ценой второй версии тех же функций показа
(без меток) и повторного прохода по тем же файлам `canary.py`, `artel.py` и
`doctor/`. Часть только с требованием 1 закрывает молчаливое снятие окна, но не
даёт способа снять зависшую метку, кроме удаления файла руками (а без него она
держится до потолка). Изоляция тестов (требование 5) делит зону `tests/` с
тестами остальных требований. Порог `budget_usd` ≥ $30 не задет.

Решение по монолиту утверждает Оператор на гейте SPEC.

## Не входит

- Параллельный прогон `--parallel` и записи дочерних процессов (часть Б-1).
- Условие `pin-update`: весь прогон зелёный на том же коммите, флаг
  `--accept-older`, счётчик мержей кода от пина, предупреждение `new` о файлах
  зон, изменённых после пина (часть В).
- Сигнал процессу прогона из `canary live`.
- Класс `canary` в `watch`.
- Правка абзаца о канарейке в `docs/operator-session.md` — `doc-commit`
  Оператора после мержа.
- Изменения в `orchestrator/canary.py`: `cmd_canary`, ведение задач, запись
  реестра (`_live_run_record`) и `live_runs`.
- В `orchestrator/doctor/__init__.py` — что-либо кроме реэкспорта новой
  проверки и её починки.
- Правка `tests/sandbox.py`.
- В `tests/test_canary_template_flag.py` и в классах перечня требования 5 —
  что-либо кроме добавления изоляции.
- Правка файлов, которые ТЗ отводит только для чтения: `docs/backlog.md`,
  `orchestrator/notes.py`,
  `orchestrator/fsm_merge_gate.py`, `orchestrator/pool_seal.py` (подписи
  `live_run_note` и `refuse_main_move_during_canary` прежние),
  `orchestrator/store.py`, `orchestrator/liveness.py`,
  `orchestrator/doctor/stale_cycles.py`, `orchestrator/doctor/isolation.py`,
  `orchestrator/doctor/leases.py`, `orchestrator/providers/base.py`,
  `orchestrator/providers/claude.py` (подпись `all_checks` прежняя),
  `orchestrator/repo_context.py`, `orchestrator/__init__.py`, `conftest.py`,
  `tests/test_invariants.py` (защищённый путь; класс оттуда в перечне
  требования 5 — эскалация).
- Зелёный полный набор `tests/` и неослабление существующих тестов — их держит
  пульт.

## Материалы

- ТЗ: `tasks/01M5FA4NR91PCF47SZT6V0Q9HS/TZ.md`; решения Оператора 19.10–21.10
  (коммит 49ce342c — строка бэклога; 25bd2f22 — мерж части А); решения
  Оператора на гейте SPEC, круг 1 (причина возврата из `spec_gate`).
- `tasks/01M5FA4NR91PCF47SZT6V0Q9HS/SPEC-AUDIT.md` — отклонения аудита, на
  которые отвечают решения круга 1.
- Запись реестра (`orchestrator/canary.py:2847–2851`) сегодня не несёт ни
  `parent_pid`, ни шаблона: их показ (AC-7) проверяется на подложенной вручную
  записи.
- `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_registry.py:477`
  (`test_ac6_existing_mark_alone_refuses_without_registry_read`) — закреплённый
  частью А путь «удаление записи при оставленной метке».
- `tests/test_canary_live_registry_units.py:36`, `:56` — прежние утверждения о
  метке при уборке записи (остаются без правок; `:56` проверяет только
  `live_runs()`, и AC-5 (i) с ним совместим).
- Возможный текстовый конфликт в `orchestrator/doctor/__init__.py` с задачей
  G3а-2б-2 — разрешение объединением сторон.
