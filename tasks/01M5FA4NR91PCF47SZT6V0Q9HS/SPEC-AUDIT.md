---
task: 01M5FA4NR91PCF47SZT6V0Q9HS
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: "в) пути-признаки (тесты): tests/, tests/sandbox.py, tests/test_01m3pymq6n4scaj9wwttkh6xng_canary_clone_models.py, tests/test_01m3pymq6n4scaj9wwttkh6xng_role_models.py, tests/test_01m3s9hfdds9s4274w6tbqjbh7_canary_acceptance.py, tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py, tests/test_01m3sk48d7rdqpsen78894gda5_codex_home.py, tests/test_01m3v4zpb6hfdj36mtdaqg5vnt_canary_profile.py, tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py, tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py, tests/test_01m3ychp14179r32sfjvkqb32g_model_sets.py, tests/test_01m3yxyax5pw9bm67mb4gk85d1_step_provider_preflight.py, tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py, tests/test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied.py, tests/test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py, tests/test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py, tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py, tests/test_01m484rnv3qbdy3b0m16j916zp_artel_predicate.py, tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py, tests/test_01m48wre8bhfdy011q0hqgq91b_profile_limit_field.py, tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py, tests/test_01m4axpy1py4ps1yafamd47vby_canary_doctor.py, tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py, tests/test_01m4beg0003ch0qa1gy0pxat03_canary_suite_skip.py, tests/test_01m4c954hbjwegd3azs7q3eha4_doctor.py, tests/test_01m4c954hbjwegd3azs7q3eha4_watch.py, tests/test_01m4fytb8qwjnhycp35k8qc4e3_worktree_db_clean.py, tests/test_01m4g8mnepecnx1tcedw4t4rpx_origin_sweep.py, tests/test_01m4jd3srn66sd6bm63xaghb11_merge_gate_in_base.py, tests/test_01m4jmmh70nwjg72g422bfy1kc_postmerge_map_interpreter.py, tests/test_01m4k2767fxkz8ew7ame81sz9n_suite_near_limit.py, tests/test_01m4m67sgneymn9f1c7xvx24xe_merge_closing.py, tests/test_01m4m68557tt4kyn814h8az01a_history_snapshots.py, tests/test_01m4rzbpg6exm74mtbptegw2d4_note_merge_gate.py, tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py, tests/test_01m4s24ebvb72b8wyj3jy96y0e_merge_reference.py, tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py, tests/test_01m545edths47hsb59akc1ez9c_project_token.py, tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py, tests/test_01m57pm7nbfx34319tr0f9cb4f_mutex_readers_all_rows.py, tests/test_01m583rm59dhdrdh877aeravmd_early_signal.py, tests/test_01m58pg72pg64gs790xm2ews61_doctor_components.py, tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_registry.py, tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_window.py, tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py, tests/test_canary_live_registry_units.py, tests/test_canary_template_flag.py, tests/test_doc_commit.py, tests/test_doc_commit_held_base.py, tests/test_doc_commit_suite_gate.py, tests/test_doctor.py, tests/test_doctor_canary_pool.py, tests/test_fsm_merge_gate_done_snapshot.py, tests/test_invariants.py, tests/test_merge_gate_ci_wait.py, tests/test_notes.py, tests/test_notes_apply.py, tests/test_notes_row_format.py, tests/test_plan_appendix.py, tests/test_providers.py; в) защищённые пути: tests/test_invariants.py"
spec_sha: dd4526840b8e36cb7adb6ae9b20d105b2249ec7f
schema_version: 5
---

# SPEC-AUDIT: Механика канарейки, часть Б-2: реестр живой канарейки

Аудит круга 3: SPEC после решений Оператора на гейте SPEC (круги 1 и 2) и
ANSWER-1 (признак (3) и `FsmTest`). sha проверенного SPEC сверен
(`git hash-object` = `dd4526840b8e36cb7adb6ae9b20d105b2249ec7f`).

## ТЗ и SPEC
ТЗ → SPEC: пп. 1–6 ТЗ на месте; отступления от ТЗ все прямо заданы решениями
Оператора:
- «уборка допустима и в `doctor` без `--fix`» (ТЗ п. 4) → только чтение,
  `warn`, уборка `doctor --fix` — решение круга 1 п. 3; требование 4, AC-18 ✓;
- отказ «прогона <run_stamp> в реестре нет» (ТЗ п. 3) → «в реестре нет», код 0
  — решение круга 1 п. 6; требование 3, AC-14 ✓;
- «снимаются все такие записи этого `run_stamp` и его метка» → метка
  снимается, только если записей не осталось — решение круга 2 п. 4;
  требование 3, AC-9 ✓;
- «тест-шпион при обращении каждого класса» (ТЗ п. 5) → статическая проверка
  и динамическая для признака (2), без вложенного прогона — решение круга 2
  п. 1; требование 5, AC-19, AC-20 ✓; время полного прогона в отчёте ✓.

Решения круга 1 пп. 1–6 перенесены (требования 1–5, AC-3, AC-5, AC-7, AC-8,
AC-14, AC-18). Решения круга 2 пп. 1–4 — требования 3, 5, AC-9, AC-19, AC-20.

ANSWER-1:
- п. 1 (признак (3)): требование 5, признак (3), AC-19 ✓. SPEC добавляет к
  «допускаются только определение класса и создание экземпляра»
  «докстринг, операторы `import` … вызовами не являются». Расширением это не
  считаю: доказательство, которое называет сам ANSWER-1
  (`tests/test_invariants.py:3177–3186`), содержит `import` до `setUp`
  (`:3176–3177`, разбор AST), и без этой оговорки признак не выполнялся бы
  на собственном доказательстве.
- п. 2 (`FsmTest` — изолирующая основа, остаток риска принят, полная подмена —
  бэклог Оператора): требование 5, признак (1); «Материалы» ✓.

SPEC → ТЗ: лишних требований нет. Реэкспорт «и её починки» в
`doctor/__init__.py` следует из решения круга 1 п. 3.

## Факты против кода
Подтвердилось (рабочий каталог = main f1f805b6 + артефакты):
- `orchestrator/canary.py`: `_live_dir` `:2796`; `_live_run_record` `:2823`
  (метка `O_EXCL`, pid в метку, поля записи `:2847–2851` без `parent_pid` и
  шаблона); `_live_verdict` `:2862` (потолок `× tasks + 3600` — `:2876`;
  время старта не определилось при записи или при сверке → живая);
  `_drop_live_record` `:2895` (метку чужого непустого pid не трогает);
  `live_runs` `:2911`; `live_run_note` `:2941`;
  `refuse_main_move_during_canary` `:2959`.
- Потребители: `notes.py:266` (`_silence_window_reason`, вызов `:285`),
  `notes.py:1433`, `:1564`; `fsm_merge_gate.py:1255` (`_refuse_during_canary`,
  `default_set_only=True` — `:1268`); `pool_seal.py:329`. В `orchestrator/`
  других обращений к реестру нет; `doctor` сегодня реестра не читает
  (`check_pending_notes` читает только файлы заметок, `notes.py:250`), так что
  AC-18 «без `--fix` файлы на месте» достижим без правки чужих проверок.
- `orchestrator/doctor/cli.py:153` (`check_canary_trigger`), `:194` (`if fix:`
  в `cmd_doctor`) ✓. `orchestrator/artel.py:181` (справка `canary`), `:1539`
  (`_cmd_canary`), `:1762` (`_fixes_main_arg`), `:2017`
  (`_role_allowed_command`); `canary` вне белых списков `:2003–2014` ✓.
- Основы изоляции: `TmpRootTest` — `tests/sandbox.py:1581`, `RealGitSandbox` —
  `:1897`, `ALL_CONFIG_ATTRS` — `:90` (содержит `ROOT`); `FsmTest` —
  `tests/test_invariants.py:149`, обёртка `approve_with_isolated_root` —
  `:245–267` ✓.
- Признак (3): `MainCopyGitUnchangedDuringTaskTest` — `tests/test_invariants.py:3155`,
  один тестовый метод (`:3170`): докстринг, `import` `:3176`, `:3177`,
  `class Flow(TaskFlowSandbox)` `:3180`, `flow = Flow()` `:3184`,
  `flow.setUp()` `:3185` ✓; цепочка `TaskFlowSandbox` (`project_area.py:1244`)
  → `ProjectAreaSandbox` (`:138`) → `RealGitSandbox` ✓.
- Признак (2): `CanaryPoolDriftCheckTest` — подмена `config.ROOT` в `setUp`,
  `tests/test_doctor_canary_pool.py:249` ✓.
- Разбор AST всех 116 классов перечня (58 файлов): каждый класс существует;
  113 наследуют от `TmpRootTest`/`RealGitSandbox`/`FsmTest`, ни у одного в
  цепочке нет сужения `PATCHED_ATTRS` и `setUp` без `super().setUp()`;
  `CanaryPoolDriftCheckTest` — признак (2); `CmdCanaryTemplateSelectionTest`
  (база `_PoolDirTest`, `setUp` без подмены) признака пока не имеет — его
  даёт требование 5; `MainCopyGitUnchangedDuringTaskTest` — признак (3).
  Утверждение SPEC «115 классов уже изолированы» на статическом уровне
  подтверждается.

Не подтвердилось / неполно:
- Перечень требования 5 снят шпионом на коде main, где у `doctor --fix` пути к
  реестру не было. Новая починка требования 4 добавляет такой путь в
  `cmd_doctor` до `all_checks`. Класс `DoctorFixOrderTest`
  (`tests/test_doctor_closed_ref_fix.py:150`, `unittest.TestCase`, `config.ROOT`
  не подменён) зовёт `doctor.cmd_doctor(fix=True)` (`:183`), подменяя
  `all_checks` и перечисленные по имени починки (`:165–168`), — новая
  починка реестра в этот список не входит и пойдёт по настоящему реестру
  пульта, при `doctor.store.db` → `None` (`:173`). В перечне класса нет
  («Вердикт» п. 1).

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | `live_run_note` не читает метки; метка пропущена при `default_set_only=True` (`approve` проходит); `refuse_main_move_during_canary` не видит метку (`note --now` проходит); нет суффикса «(запись реестра отсутствует)» |
| AC-2 | да | порог 60 с снят, перевёрнут или не по `st_mtime`; уборка без строки журнала |
| AC-3 | да | нечисловая метка роняет чтение (`ValueError`) или сразу мёртвая |
| AC-4 | да | метка мёртвого pid остаётся или убирается молча |
| AC-5 | да | метки оцениваются до уборки записей; метка чужого живого pid снимается с мёртвой записью; в (ii) метка остаётся |
| AC-6 | да | новая логика трогает метку живой записи; `live_runs()` отдаёт метки |
| AC-7 | да | пропущено поле; остаток без `× tasks` или без `+1 ч` (запись с N ≥ 2 различит) |
| AC-8 | да | показ без предварительной уборки |
| AC-9 | да | не снимается один из (а)/(б)/(в); метка снята при оставшейся свежей записи; сигнал процессу |
| AC-10 | да | журнал не от `operator`, с задачей, без имён файлов/основания; нет «процесс <pid> жив…» |
| AC-11 | да | живая свежая запись снимается |
| AC-12 | да | шаблон после чтения каталога или ослаблен |
| AC-13 | да | любой из трёх отказов снят |
| AC-14 | да | «нет в реестре» с кодом ≠ 0 или строкой `operator`; `--drop` без предварительной уборки |
| AC-15 | да (страж) | `canary live` в белом списке роли; справка без подкоманды |
| AC-16 | да | пустой реестр не `ok`; нет sha7/pid/возраста; метка без пометки |
| AC-17 | да | нет `warn` старше 8 ч; порог взят как потолок (запись `tasks` = 1 возрастом 8–9 ч различит); подсказка без `--drop` |
| AC-18 | да | `doctor` без `--fix` убирает или журналирует (через `live_runs`); `--fix` не убирает |
| AC-19 | да, с оговорками «Вердикт» пп. 1–3 | `CmdCanaryTemplateSelectionTest` без подмены в `setUp`; класс перечня переведён на `unittest.TestCase`; вызов вне песочницы до `flow.setUp()`. Не ловит: наследника `TmpRootTest` с `PATCHED_ATTRS` без `ROOT`; класс вне перечня (`DoctorFixOrderTest`) |
| AC-20 | да | `setUp` подменяет `_live_dir` путём под настоящим корнем; подменена обёртка, а не путь функции реестра; сбой `setUp` засчитан |
| AC-21 | да (страж) | регрессия пути с записью — держат существующие тесты части А |

## Зоны
- Зоны SPEC покрывают требования: функции чтения меток, показа, снятия и
  константа действия — `canary.py`; разбор `canary live` и справка —
  `artel.py`; проверка — `doctor/canary_pool.py`; сборка и `--fix` —
  `doctor/cli.py`; реэкспорт — `doctor/__init__.py`; изоляция и тесты —
  `tests/`; карта — `config.COMMON_ZONES` (`config.py:814`).
- Изоляция `DoctorFixOrderTest` («Вердикт» п. 1) — в зоне `tests/`, путь не
  защищённый.
- Защищённый путь `tests/test_invariants.py` — только чтение; четыре его
  класса изолированы признаками (1) и (3) без правки ✓.
- Песочница ролей не расширяется: `canary live` под ролью отказывает,
  `doctor` без `--fix` только читает, `--fix` под ролью отказан
  (`artel.py:2009`).

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| `live_run_note` читает метки без записи | окно тишины и отказ мержа по живой записи — `canary.py:2941`, `notes.py:285`, `fsm_merge_gate.py:1268` | да, плюс новый источник | тесты части А без правок + AC-1, AC-5, AC-21 | остаётся |
| уборка метки новой логикой | метка чужого живого pid не снимается — `tests/test_canary_live_registry_units.py:56` | да | `:56` без правок + AC-5 (i) | остаётся |
| уборка нечитаемой записи с меткой | `tests/test_canary_live_registry_units.py:36` | да | `:36` без правок | остаётся |
| отказ повтора `run_stamp` | `O_EXCL` `canary.py:2840`; `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_registry.py:477` | да; `--drop` (в) штатно снимает метку живого процесса по решению Оператора | `:477` без правок | остаётся (риск принят строгим `--drop` ТЗ) |
| закрытый белый список роли | `artel.py:2017`, `:2003–2014` | да | AC-15 | остаётся |
| `doctor` без `--fix` не меняет состояние | `artel.py:2009` | да | AC-18 | остаётся |
| `doctor --fix` получает уборку реестра | изоляция тестов `--fix` от боевого пульта — подмена починок по имени, `tests/test_doctor_closed_ref_fix.py:165–172` | нет для новой починки | не покрыто (класса нет в перечне) | отклонение, «Вердикт» п. 1 |
| изоляция тестов от настоящего реестра | `tests/sandbox.py:90`, `:1581` | расширяется | AC-19, AC-20 | остаётся, с оговорками «Вердикт» пп. 2–3 |
| утверждения классов перечня и `tests/test_canary_template_flag.py` | сами утверждения | да — только добавление изоляции | гейт неослабления тестов | остаётся |
| время полного прогона `tests/` | `FULL_SUITE_TIMEOUT_SEC` (`config.py:223`) | да — проверка статическая (решение круга 2 п. 1) | время в отчёте PLAN.md | остаётся |

## Пути обхода гейтов
1. **Класс, получивший путь к реестру только после задачи, вне перечня.**
   Перечень снят на main; новые пути (починка `doctor --fix`) его не
   пополнили. Разработчик выполняет требование 5 буквально — проверяет
   116 классов — а `DoctorFixOrderTest`
   (`tests/test_doctor_closed_ref_fix.py:150`) читает и убирает настоящий
   реестр. «Перечень можно дополнять» обязанности дополнить не создаёт.
2. **Признак (1) без фактической подмены `ROOT`.** Признак проверяет только
   наследование. `TmpRootTest.PATCHED_ATTRS` параметризуем
   (`tests/sandbox.py:1599`), и прецедент наследника с `PATCHED_ATTRS` без
   `ROOT` есть (`tests/test_doctor.py:2088`, `_RoleHomeReferenceTmpRootTest`).
   Такой же наследник в перечне, как и `setUp` без `super().setUp()`, AC-19
   засчитает как изолированный. Сегодня в перечне таких нет (разбор AST),
   но AC-19 — постоянный тест на перечень, который разработчик дополняет.
3. **Признак (3) у одного метода из нескольких.** Требование 5 и AC-19
   говорят «тестовый метод определяет подкласс…», не «каждый тестовый метод
   класса». Класс, у которого один метод с вложенной песочницей, а второй
   без неё, признак (3) получит. Сегодня единственный такой класс имеет один
   метод (`tests/test_invariants.py:3170`).

## Вердикт
concerns — все три пункта решаемы Оператором на гейте одной строкой в SPEC
без возврата аналитику.

1. Перечень требования 5 (SPEC.md, требование 5, «Перечень — 116 классов»)
   не включает `DoctorFixOrderTest` (`tests/test_doctor_closed_ref_fix.py:150`,
   вызов `cmd_doctor(fix=True)` — `:183`, база `unittest.TestCase`, `ROOT` не
   подменён, `store.db` → `None` — `:173`). После требования 4 («`doctor --fix`
   до проверок убирает мёртвые записи и метки») класс дойдёт до настоящего
   реестра пульта: прочтёт его и, при мёртвой записи на машине Оператора,
   удалит её и упадёт на `store.journal(None, …)`. Предложение: добавить класс
   в перечень (изоляция подменой новой починки или `_live_dir` в `setUp` —
   признак (2), AC-20), либо обязать разработчика дополнить перечень классами,
   которые зовут `cmd_doctor(fix=True)`.
2. Признак (1) (SPEC.md, требование 5, «(1) класс наследует …») не требует,
   чтобы подмена `ROOT` действительно происходила: сужение `PATCHED_ATTRS`
   без `ROOT` (прецедент `tests/test_doctor.py:2088`) или `setUp` без
   `super().setUp()` проходят статическую проверку. Предложение: в признак (1)
   для основ `TmpRootTest`/`RealGitSandbox` добавить «в цепочке нет
   `PATCHED_ATTRS` без `ROOT` и `setUp` без вызова `super().setUp()`»
   (сегодня все 113 классов перечня с признаком (1) это выполняют).
3. Признак (3) (SPEC.md, требование 5, «(3) тестовый метод …»; AC-19) не
   говорит, должен ли он выполняться для каждого тестового метода класса.
   Предложение: «каждый тестовый метод класса».
