---
task: 01M5FA4NR91PCF47SZT6V0Q9HS
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: "в) пути-признаки (тесты): tests/, tests/sandbox.py, tests/test_01m3pymq6n4scaj9wwttkh6xng_canary_clone_models.py, tests/test_01m3pymq6n4scaj9wwttkh6xng_role_models.py, tests/test_01m3s9hfdds9s4274w6tbqjbh7_canary_acceptance.py, tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py, tests/test_01m3sk48d7rdqpsen78894gda5_codex_home.py, tests/test_01m3v4zpb6hfdj36mtdaqg5vnt_canary_profile.py, tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py, tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py, tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py, tests/test_01m3ychp14179r32sfjvkqb32g_model_sets.py, tests/test_01m3yxyax5pw9bm67mb4gk85d1_step_provider_preflight.py, tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py, tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py, tests/test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied.py, tests/test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py, tests/test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py, tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py, tests/test_01m484rnv3qbdy3b0m16j916zp_artel_predicate.py, tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py, tests/test_01m48wre8bhfdy011q0hqgq91b_profile_limit_field.py, tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py, tests/test_01m4axpy1py4ps1yafamd47vby_canary_doctor.py, tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py, tests/test_01m4beg0003ch0qa1gy0pxat03_canary_suite_skip.py, tests/test_01m4c954hbjwegd3azs7q3eha4_doctor.py, tests/test_01m4c954hbjwegd3azs7q3eha4_watch.py, tests/test_01m4fytb8qwjnhycp35k8qc4e3_worktree_db_clean.py, tests/test_01m4g8mnepecnx1tcedw4t4rpx_origin_sweep.py, tests/test_01m4jd3srn66sd6bm63xaghb11_merge_gate_in_base.py, tests/test_01m4jmmh70nwjg72g422bfy1kc_postmerge_map_interpreter.py, tests/test_01m4k2767fxkz8ew7ame81sz9n_suite_near_limit.py, tests/test_01m4m67sgneymn9f1c7xvx24xe_merge_closing.py, tests/test_01m4m68557tt4kyn814h8az01a_history_snapshots.py, tests/test_01m4rzbpg6exm74mtbptegw2d4_note_merge_gate.py, tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py, tests/test_01m4s24ebvb72b8wyj3jy96y0e_merge_reference.py, tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py, tests/test_01m545edths47hsb59akc1ez9c_project_token.py, tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py, tests/test_01m57pm7nbfx34319tr0f9cb4f_mutex_readers_all_rows.py, tests/test_01m583rm59dhdrdh877aeravmd_early_signal.py, tests/test_01m58pg72pg64gs790xm2ews61_doctor_components.py, tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_registry.py, tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_window.py, tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py, tests/test_canary_live_registry_units.py, tests/test_canary_template_flag.py, tests/test_doc_commit.py, tests/test_doc_commit_held_base.py, tests/test_doc_commit_suite_gate.py, tests/test_doctor.py, tests/test_doctor_canary_pool.py, tests/test_doctor_closed_ref_fix.py, tests/test_fsm_merge_gate_done_snapshot.py, tests/test_git_hooks.py, tests/test_invariants.py, tests/test_merge_gate_ci_wait.py, tests/test_notes.py, tests/test_notes_apply.py, tests/test_notes_row_format.py, tests/test_plan_appendix.py, tests/test_providers.py; в) защищённые пути: tests/test_invariants.py"
spec_sha: cb29ed4092ac3024f60116408e2ca894fd823bf9
schema_version: 5
---

# SPEC-AUDIT: Механика канарейки, часть Б-2: реестр живой канарейки

Проверена версия SPEC с sha `cb29ed40` (`git hash-object` совпал) на коде
рабочего каталога f1f805b6. Сверено и с main cb58b144: тесты, добавленные после
58c9a84b (на этом коде шёл прогон шпиона), реестра не достигают.

## ТЗ и SPEC
- Требования ТЗ 1–6 есть в SPEC (требования 1–7, AC-1…AC-21). Расхождения с ТЗ
  есть, но каждое прямо снимает решение Оператора на гейте SPEC:
  - `doctor` без `--fix` реестр только читает — круг 1, п. 3, заменяет
    формулировку ТЗ «уборка допустима и в `doctor` без `--fix`»;
  - «canary live: в реестре нет <run_stamp>» с кодом 0 вместо отказа «прогона
    <run_stamp> в реестре нет» — круг 1, п. 6;
  - метка при `--drop` снимается, только если не осталось записей того же
    `run_stamp` — круг 2, п. 4;
  - перечень классов, проверки признаков (1)–(3), `FsmTest`, `DoctorFixOrderTest`
    и классы с `cmd_doctor(fix=True)` — круги 2 и 4 и ANSWER-1, пп. 1–2.
- ТЗ п. 5 описывает «тест-шпион» с вызовом каждого класса перечня. Круг 2,
  п. 1, заменил его статической проверкой плюс динамической для признака (2).
  SPEC этому решению следует.
- Требований сверх ТЗ и решений Оператора в SPEC не нашлось. Строки «Не
  входит» совпадают с ТЗ, плюс два уточнения: запрет правки `_live_run_record`
  и `live_runs` (следует из «прежние побайтно» в ТЗ) и
  `tests/test_doctor_closed_ref_fix.py` (круг 4).
- Расхождений между решениями Оператора не нашлось.

## Факты против кода
Подтверждено:
- `orchestrator/canary.py`: `CANARY_DRIVE_TIMEOUT_SEC` — `:280`; `_live_dir` —
  `:2796`; `_live_run_record` — `:2823`; запись без `parent_pid` и шаблона —
  `:2847–2851`; `_live_verdict` — `:2862`; потолок — `:2876`;
  `_drop_live_record` — `:2895` (метку чужого pid не трогает); `live_runs` —
  `:2911` (только `*.json`); `live_run_note` — `:2941`;
  `refuse_main_move_during_canary` — `:2959`.
- Потребители реестра: `orchestrator/notes.py:266`/`:285`, `:1433`, `:1564`;
  `orchestrator/fsm_merge_gate.py:1255`/`:1268` (`default_set_only=True`);
  `orchestrator/pool_seal.py:329`.
- `orchestrator/artel.py`: справка — `:181`; `_cmd_canary` — `:1539`;
  `_fixes_main_arg` — `:1762`; `_role_allowed_command` — `:2017`.
  `canary` нет ни в белом списке (`:2003`), ни в `_ROLE_ALLOWED_SUBCOMMANDS`,
  поэтому `canary live` под ролью откажет и без правки.
- `orchestrator/doctor/cli.py`: `all_checks` — `:35`; `check_canary_trigger` —
  `:153`; ветка `--fix` в `cmd_doctor` — `:194`. Реэкспорт —
  `orchestrator/doctor/__init__.py:154`. `doctor` без `--fix` до
  `live_run_note` не доходит: `check_pending_notes` зовёт только
  `notes.pending_notes`. Поэтому чтение без удаления (требование 4)
  достижимо.
- Тесты: `tests/sandbox.py:90`, `:1581`, `:1897`;
  `tests/test_invariants.py:149`, `:245–267` (обёртка `approve`), `:3155`,
  `:3176–3186`; `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py:138`,
  `:1244`; `tests/test_doctor_canary_pool.py:249` (`setUp` подменяет
  `config.ROOT`); `tests/test_doctor_closed_ref_fix.py:150`/`:183`;
  `tests/test_canary_template_flag.py:186` (основа `_PoolDirTest`, `ROOT` не
  подменён); `tests/test_canary_live_registry_units.py:36`, `:56`;
  `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_registry.py:477`. Тест `:477`
  с новым поведением совместим: метка живого pid ребёнка не убирается, а
  `cmd_canary` реестр не читает.
- Перечень требования 5: 119 классов в 61 файле, все существуют. Разбор AST:
  - у 114 классов есть признак (1) без сужения `PATCHED_ATTRS` без `ROOT` и
    без `setUp` без `super().setUp()`. `AllChecksProviderNamesTest` дошёл до
    основы через алиасы `tests/test_providers.py:35–36` и
    `tests/test_doctor.py:195`;
  - `CanaryPoolDriftCheckTest` — признак (2);
  - `MainCopyGitUnchangedDuringTaskTest` — признак (3), в классе один
    тестовый метод;
  - `CmdCanaryTemplateSelectionTest` и `DoctorFixOrderTest` получат признак (2)
    по задаче.
  Единственное в `tests/` сужение без `ROOT` —
  `tests/test_doctor.py:2088` (`_RoleHomeReferenceTmpRootTest`), и наследников
  в перечне у него нет.

Не подтверждено (отклонение О-1): требование 5 (б) утверждает, что поиск
нашёл шесть классов с вызовом `cmd_doctor(fix=True)`. Поиск пропустил
позиционную форму `doctor.cmd_doctor(False, True)` в помощнике
`ProjectAreaSandbox.doctor_fix`
(`tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py:363`). Этот помощник
зовут `CloneCreationTest` (`:525`, `:530`) и `CloneHooksFromPinTest` (`:860`,
`:882`). Оба класса в перечне уже есть — по источнику (а), — так что пробела в
изоляции нет. Неверен сам факт, а AC-19 опирается на этот поиск (см.
«Проверяемость»).

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | метки не читаются / читаются только при `default_set_only=False` (мерж проходит) / причина без «(запись реестра отсутствует)» |
| AC-2 | да | порог 60 с заменён на 0 или ∞; пустая метка убирается без строки журнала |
| AC-3 | да | `int()` на `abc` бросает исключение или нечисловая метка считается мёртвой сразу |
| AC-4 | да | метка с мёртвым pid остаётся и держит окно |
| AC-5 | да | метки сверяются до уборки записей (i: метка не учтена; ii: окно держится) |
| AC-6 | да | новая логика убирает метку рядом с живой записью; `live_runs` возвращает метки |
| AC-7 | да | остаток считается без `+1 ч` или без × `tasks`; не показаны `parent_pid`/шаблон |
| AC-8 | да | показ не убирает мёртвое или убирает без строки журнала |
| AC-9 | да | `--drop` снимает свежую запись рядом со старой; метка снята при оставшейся записи; `os.kill` вызван |
| AC-10 | да | нет строки журнала `operator` / нет основания / нет фразы о живом процессе |
| AC-11 | да | `--drop` снимает живую свежую запись |
| AC-12 | да | шаблон не проверяется или проверяется после `_live_dir()` (шпион на `_live_dir`) |
| AC-13 | да | пустое основание принято; лишний аргумент проглочен |
| AC-14 | да | отказ с ненулевым кодом; строка журнала `operator` при отсутствии |
| AC-15 | да | `canary` добавлен в `_ROLE_ALLOWED_SUBCOMMANDS`; справка без `canary live` |
| AC-16 | да | формат строки списка; метка без пометки |
| AC-17 | да | `warn` не выдан для записи или метки старше 8 ч |
| AC-18 | да | `doctor` без `--fix` убирает файлы (вызов `live_runs`); `--fix` не убирает |
| AC-19 | частично | см. О-1 и О-3: сам критерий «каждый класс с `cmd_doctor(fix=True)`» не задаёт, как такие классы находятся, а признак (1) — как опознаётся основа |
| AC-20 | частично | см. О-2: не названы функции реестра, путь которых сверяется |
| AC-21 | да (существующим набором) | любая правка поведения без метки ловится существующими тестами окна, мержа и `canary` |

## Зоны
- Зоны SPEC покрывают требования: `orchestrator/canary.py` (чтение меток,
  `--drop`, константа действия), `orchestrator/artel.py` (разбор и справка),
  `orchestrator/doctor/canary_pool.py`, `cli.py`, `__init__.py` (проверка,
  починка, реэкспорт), `tests/` (новые тесты, `setUp` в двух классах). Карта
  `docs/codebase-map.md` входит в `COMMON_ZONES` (`orchestrator/config.py:814`).
- Защищённый путь `tests/test_invariants.py` не правится: четырём его классам
  изоляция дана признаками (1)/(3), остальное — эскалация. Пути `skills/`,
  `templates/` и `gates.yaml` задача не трогает. Песочница ролей не
  расширяется: `canary live` под ролью отказывает (AC-15).
- В `orchestrator/doctor/__init__.py` возможен конфликт с G3а-2б-2 (SPEC
  «Материалы»). Задача G3а-2б-1 уже в main cb58b144 — при подтяжке main
  разработчику нужна регенерация карты.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| `live_run_note` читает метки без записи | окно тишины и отказ мержа при живой записи — `orchestrator/notes.py:285`, `orchestrator/fsm_merge_gate.py:1268` | да, усиливается | AC-1, AC-5, AC-6, AC-21 и прежние тесты окна | ТЗ |
| `--drop` снимает запись живого процесса | окно держится до потолка `orchestrator/canary.py:2876` | ослабляется по решению Оператора: ручной обход с основанием и строкой журнала `operator` | AC-9, AC-10, AC-11 (живая свежая запись — отказ) | ТЗ, решение 21.10 «строгий вариант» |
| Уборка метки без записи | отказ повтора `run_stamp` (`O_EXCL`, `canary.py:2840`) | да: убирается только мёртвая или старая нечитаемая метка | `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_registry.py:477`, AC-2…AC-4 | ТЗ |
| `doctor --fix` получает новую починку | порядок починок `tests/test_doctor_closed_ref_fix.py:183` | да: утверждения не меняются, добавляется `setUp` | AC-20 | круг 4 |
| Изоляция `CmdCanaryTemplateSelectionTest` | нет: пишет в настоящий реестр | становится | AC-19, AC-20 | ТЗ |
| `tests/test_canary_live_registry_units.py:56` | метка чужого pid остаётся, `live_runs` пуст | да, без правок | сам тест | ТЗ п. 6 |
| Белый список ролей | `orchestrator/artel.py:2017` | да, без правок | AC-15 | ТЗ |

Раздела «Меняемое поведение» в SPEC нет. Требование 7 запрещает правку
утверждений — согласовано.

## Пути обхода гейтов
- П-1 (О-2). Новые функции (чтение меток, `--drop`, проверка `canary-live` и
  её починка) могут взять каталог не через `_live_dir()`, а прямо через
  `config.ROOT / ".artel" / config.CANARY_LIVE_DIRNAME`. Тогда подмена
  `canary._live_dir` в `setUp` у `CmdCanaryTemplateSelectionTest` и
  `DoctorFixOrderTest` их не изолирует: `DoctorFixOrderTest` через новую
  починку `--fix` дойдёт до настоящего реестра. AC-20 при этом можно пройти,
  сверив путь одной `live_runs()`: SPEC говорит «функция реестра», не называя
  какие.
- П-2 (О-3). Признак (1) засчитывается по имени основы. Проверка, которая
  сравнивает имена баз строкой, засчитает и локальный класс с именем
  `TmpRootTest`, если он ничего не подменяет. SPEC не требует разрешать базы
  до определений `tests/sandbox.py:1581`/`:1897` и
  `tests/test_invariants.py:149` (с учётом алиасов `tests/test_doctor.py:195`
  и `tests/test_providers.py:35–36`).
- П-3 (О-1). Если перечень проверяется поиском ключевого `fix=True`, класс,
  который зовёт починку позиционно или через помощник
  (`tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py:363`), выпадет из
  проверки «перечень содержит каждый класс с `cmd_doctor(fix=True)`».
- Принятый остаток, не отклонение: у метки без записи с живым pid нет ни
  потолка, ни сверки времени старта. Если pid переиспользован, окно держится,
  пока Оператор не сделает `--drop`. Через 8 ч по времени правки `doctor`
  предупредит (требование 4, решение Оператора 21.10).

## Вердикт
concerns. Отклонения — уточнения критериев, Оператор может закрыть их на
гейте без возврата.

1. О-1. Требование 5 (б) (SPEC, абзац «Все классы, вызывающие
   `cmd_doctor(fix=True)`») пропускает позиционный вызов
   `doctor.cmd_doctor(False, True)` в
   `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py:363`. Его зовут
   `CloneCreationTest` (`:525`, `:530`) и `CloneHooksFromPinTest` (`:860`,
   `:882`). Оба класса уже в перечне, но AC-19 не говорит, как находятся
   классы с починкой. Предложение: искать по `cmd_doctor` с истинным
   аргументом `fix` — ключевым или вторым позиционным — включая вызовы через
   помощник класса-основы.
2. О-2. AC-20 и требование 5 не называют функции реестра и не требуют, чтобы
   все функции реестра (`live_runs`, новое чтение меток, `live_run_note`,
   `--drop`, проверка `canary-live` и её починка под `--fix`) брали каталог из
   `canary._live_dir()`. Подмена `_live_dir` у `DoctorFixOrderTest`
   (`tests/test_doctor_closed_ref_fix.py:150`) и
   `CmdCanaryTemplateSelectionTest` (`tests/test_canary_template_flag.py:186`)
   иначе не гарантирует изоляцию. Предложение: потребовать каталог через
   `_live_dir()`, а в AC-20 для `DoctorFixOrderTest` сверять путь новой
   починки.
3. О-3. Признак (1) не требует разрешать базу до её определения
   (`tests/sandbox.py:1581`, `:1897`, `tests/test_invariants.py:149`) с учётом
   алиасов (`tests/test_doctor.py:195`, `tests/test_providers.py:35–36`).
   Сравнение по имени засчитает признак локальному одноимённому классу.
