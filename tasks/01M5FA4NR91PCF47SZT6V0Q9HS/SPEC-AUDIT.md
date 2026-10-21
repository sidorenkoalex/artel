---
task: 01M5FA4NR91PCF47SZT6V0Q9HS
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: "в) пути-признаки (тесты): tests/, tests/sandbox.py, tests/test_01m3pymq6n4scaj9wwttkh6xng_canary_clone_models.py, tests/test_01m3pymq6n4scaj9wwttkh6xng_role_models.py, tests/test_01m3s9hfdds9s4274w6tbqjbh7_canary_acceptance.py, tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py, tests/test_01m3sk48d7rdqpsen78894gda5_codex_home.py, tests/test_01m3v4zpb6hfdj36mtdaqg5vnt_canary_profile.py, tests/test_01m3y75gcresc2kds9vprjk4ps_stale_cycles.py, tests/test_01m3y75x6k2zmd85971tcwv41e_held_base.py, tests/test_01m3ychp14179r32sfjvkqb32g_model_sets.py, tests/test_01m3yxyax5pw9bm67mb4gk85d1_step_provider_preflight.py, tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py, tests/test_01m443hv9sjyvyqthjsq87qv68_merge_gate_applied.py, tests/test_01m44ep0d47f498tee08mngbyt_merge_gate_merge_after.py, tests/test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py, tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py, tests/test_01m484rnv3qbdy3b0m16j916zp_artel_predicate.py, tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py, tests/test_01m48wre8bhfdy011q0hqgq91b_profile_limit_field.py, tests/test_01m4araxf7vss5xz8c99bx8de2_doctor_duration.py, tests/test_01m4axpy1py4ps1yafamd47vby_canary_doctor.py, tests/test_01m4axpy1py4ps1yafamd47vby_canary_lifecycle.py, tests/test_01m4beg0003ch0qa1gy0pxat03_canary_suite_skip.py, tests/test_01m4c954hbjwegd3azs7q3eha4_doctor.py, tests/test_01m4c954hbjwegd3azs7q3eha4_watch.py, tests/test_01m4fytb8qwjnhycp35k8qc4e3_worktree_db_clean.py, tests/test_01m4g8mnepecnx1tcedw4t4rpx_origin_sweep.py, tests/test_01m4jd3srn66sd6bm63xaghb11_merge_gate_in_base.py, tests/test_01m4jmmh70nwjg72g422bfy1kc_postmerge_map_interpreter.py, tests/test_01m4k2767fxkz8ew7ame81sz9n_suite_near_limit.py, tests/test_01m4m67sgneymn9f1c7xvx24xe_merge_closing.py, tests/test_01m4m68557tt4kyn814h8az01a_history_snapshots.py, tests/test_01m4rzbpg6exm74mtbptegw2d4_note_merge_gate.py, tests/test_01m4s0jvb85w9ty1esgnbh97fp_doc_commit.py, tests/test_01m4s24ebvb72b8wyj3jy96y0e_merge_reference.py, tests/test_01m52eehsrd93wmphwb5vjyrkd_profile_callers.py, tests/test_01m545edths47hsb59akc1ez9c_project_token.py, tests/test_01m563947r26nzw2tjekm36qrd_note_window_project.py, tests/test_01m57pm7nbfx34319tr0f9cb4f_mutex_readers_all_rows.py, tests/test_01m583rm59dhdrdh877aeravmd_early_signal.py, tests/test_01m58pg72pg64gs790xm2ews61_doctor_components.py, tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_registry.py, tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_window.py, tests/test_01m5ddtvzea40zb9bheh4ydee7_merge_outcome_gate.py, tests/test_canary_live_registry_units.py, tests/test_canary_template_flag.py, tests/test_doc_commit.py, tests/test_doc_commit_held_base.py, tests/test_doc_commit_suite_gate.py, tests/test_doctor.py, tests/test_doctor_canary_pool.py, tests/test_fsm_merge_gate_done_snapshot.py, tests/test_invariants.py, tests/test_merge_gate_ci_wait.py, tests/test_notes.py, tests/test_notes_apply.py, tests/test_notes_row_format.py, tests/test_plan_appendix.py, tests/test_providers.py; в) защищённые пути: tests/test_invariants.py"
spec_sha: 397bad3eb4fe27b47c370c351684ca8036094c1a
schema_version: 5
---

# SPEC-AUDIT: Механика канарейки, часть Б-2: реестр живой канарейки

Аудит круга 2: SPEC после решений Оператора на гейте SPEC (круг 1, пп. 1–6).
ANSWER-n.md у задачи нет.

## ТЗ и SPEC
Решения круга 1 перенесены все:
- п. 1 (перечень называет SPEC, дополнять можно, убирать нельзя, критерий
  поклассово): требование 5, 116 классов в 58 файлах, и AC-19 ✓;
- п. 2 (изоляция охватывает `doctor.all_checks`/`canary-live` и
  `canary live`): определение изоляции в требовании 5 ✓;
- п. 3 (`doctor` без `--fix` только читает, мёртвое — `warn` с подсказкой,
  уборка — `doctor --fix` и прежние читатели): требование 4, AC-18 ✓. Решение
  ТЗ «уборка допустима и в `doctor` без `--fix`» заменено, как сказано в
  решении;
- п. 4 (порядок: записи с уборкой, затем метки без записи): требование 1 и
  AC-5 (i)/(ii) ✓. Оба исхода сверены с кодом `_drop_live_record`
  (`orchestrator/canary.py:2905`): метка чужого непустого pid остаётся, метка
  pid записи убирается;
- п. 5 (нечисловая метка как пустая; остаток по формуле `canary.py:2876`;
  уборка при показе `canary live`): AC-3, AC-7, AC-8 ✓;
- п. 6 (`--drop`: сначала уборка; нет `<run_stamp>` — «в реестре нет», код 0,
  без строки `operator`): требование 3, AC-14 ✓. Это заменяет отказ ТЗ
  «прогона <run_stamp> в реестре нет».

ТЗ → SPEC: пп. 1–6 ТЗ на месте. Отказ повтора `run_stamp` при оставшейся метке
своего AC не получил, но его держит неизменяемый
`tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_registry.py:477`.

SPEC → ТЗ: лишнего нет. Реэкспорт «и её починки» в `doctor/__init__.py`
(требование 4, «Не входит») чуть шире формулировки ТЗ «только реэкспорт новой
проверки», но прямо следует из решения 3 (починка под `--fix`). Отклонением не
считаю.

## Факты против кода
Подтвердилось:
- `_live_dir` — `orchestrator/canary.py:2796` (`config.ROOT/.artel/…`);
  `_live_run_record` — `:2823` (метка `O_EXCL` `:2840`, pid в метку `:2845`,
  поля записи `:2847–2851` без `parent_pid` и шаблона); `_live_verdict` —
  `:2862` (потолок `× tasks + 3600` — `:2876`; время старта не определилось
  при записи `:2881` или при сверке `:2887` → живая — это и есть случай (б)
  требования 3); `_drop_live_record` — `:2895`; `live_runs` — `:2911`;
  `live_run_note` — `:2941`; `refuse_main_move_during_canary` — `:2959`.
- Потребители: `notes.py:285`, `:1433`, `:1564`; `fsm_merge_gate.py:1268`
  (`default_set_only=True`, выход при `not is_artel` `:1265`);
  `pool_seal.py:329`. Других вызовов `live_run_note`/`live_runs`/`_live_dir`
  в `orchestrator/` нет (`git grep`).
- `doctor/cli.py:153` — `check_canary_trigger`; `:194` — `if fix:` в
  `cmd_doctor` ✓.
- `artel.py:181–183` (справка `canary`), `:1539` (`_cmd_canary`, подкоманда
  `pool-seal` разбирается первой — место для `live` есть), `:1762`
  (`_fixes_main_arg`), `:2017` (`_role_allowed_command`). `canary` нет ни в
  `_ROLE_ALLOWED_COMMANDS`, ни в `_ROLE_ALLOWED_SUBCOMMANDS`
  (`artel.py:2003–2014`) ✓. `doctor` разрешён роли без `--fix`/`--restore`
  (`:2009`), поэтому только читающая проверка (решение 3) песочницу не
  расширяет.
- Перечень требования 5: все 116 классов существуют в названных 58 файлах
  (разбор SPEC + поиск `^class <имя>` по каждому файлу).
- Утверждение «на main каталог реестра лежал под настоящим корнем только у
  `CmdCanaryTemplateSelectionTest`» я проверил своим шпионом. Он обёртывал
  `canary._live_dir`, `doctor.all_checks`, `doctor.cli.all_checks` и
  `fsm_merge_gate._refuse_during_canary` и при каждом вызове сверял
  `config.ROOT/.artel/<CANARY_LIVE_DIRNAME>` с
  `Path(orchestrator.__file__).resolve().parents[1]`. Прогон шёл по всем
  116 классам на коде этой ветки (= main 58c9a84b + артефакты). Итог —
  в разделе «Вердикт», п. СПАЙ.
- Существующие тесты с меткой: `tests/test_canary_live_registry_units.py:36`
  и `:56` проверяют только `live_runs()` и файлы, с новой логикой совместимы.
  `:477` после удаления записи вызывает только повторный `canary`, не `note`.
  Тестов, сверяющих полный список имён проверок `doctor`, не нашёл
  (`tests/test_providers_codex.py:663` — только preflight codex), так что
  новая строка `canary-live` существующие утверждения не ломает. Раздел
  «Меняемое поведение» не нужен.

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | `live_run_note` не читает метки; метка без записи пропускается при `default_set_only=True` (`approve` проходит); `refuse_main_move_during_canary` не видит метку (`note --now` проходит); потерян суффикс «(запись реестра отсутствует)» |
| AC-2 | да | порог 60 с снят, перевёрнут или считается не по `st_mtime`; убрано без строки журнала |
| AC-3 | да | нечисловая метка роняет чтение (`ValueError`) или сразу считается мёртвой |
| AC-4 | да | метка с мёртвым pid остаётся навсегда или убирается молча |
| AC-5 | да | метки оцениваются до уборки записей (в (i) первый вызов не удержан); метка чужого живого pid снимается вместе с мёртвой записью; в (ii) метка остаётся |
| AC-6 | да | новая логика трогает метку живой записи; `live_runs()` возвращает метки |
| AC-7 | да | пропущено поле; остаток без `× tasks` или без `+1 ч` (тест с `tasks` = N ≥ 2 различит); нет строки пустого реестра |
| AC-8 | да | показ без предварительной уборки |
| AC-9 | да | не снимается один из (а)/(б)/(в); снимается запись, но не метка; `os.kill` процессу |
| AC-10 | да | журнал не от `operator`, с задачей, без имён файлов или основания; нет строки «процесс <pid> жив…» |
| AC-11 | да | строгость потеряна: живая свежая запись снимается |
| AC-12 | да | шаблон проверяется после чтения каталога или ослаблен |
| AC-13 | да | каждый отказ отдельно |
| AC-14 | да | «нет в реестре» как отказ (код ≠ 0) или со строкой `operator`; `--drop` без предварительной уборки снимает мёртвую запись от `operator` |
| AC-15 | да (страж) | `canary live` в белом списке роли; справка без подкоманды. До реализации часть «под ролью» уже зелёная |
| AC-16 | да | пустой реестр не `ok`; нет sha7/pid/возраста; метка без пометки |
| AC-17 | да | нет `warn` для записи/метки старше 8 ч; порог взят как потолок, а не `CANARY_DRIVE_TIMEOUT_SEC` (запись `tasks` = 1 возрастом 8–9 ч различит); подсказка без `--drop` |
| AC-18 | да | `doctor` без `--fix` убирает файлы или пишет журнал (через `live_runs`); `--fix` не убирает |
| AC-19 | да, но см. «Вердикт» п. 1 | `setUp` `CmdCanaryTemplateSelectionTest` без подмены `_live_dir`; новый класс с настоящим корнем |
| AC-20 | да (страж) | регрессия пути с записью — держат существующие тесты части А |

## Зоны
- Зоны SPEC покрывают всё, что заставят менять требования. Новые функции
  чтения меток, показа и снятия, константа действия — `canary.py`. Разбор
  `canary live` и справка — `artel.py` (`_cmd_canary` `:1539`). Проверка —
  `doctor/canary_pool.py`, сборка и `--fix` — `doctor/cli.py`, реэкспорт —
  `doctor/__init__.py`. Изоляция — `tests/`. Карта — `config.COMMON_ZONES`.
- `cmd_canary` и `_live_run_record` не меняются: новая логика ложится в
  `live_run_note` и новые функции. `_live_verdict` пригоден для
  неубирающей проверки `doctor` без правки.
- Защищённый путь `tests/test_invariants.py` — только чтение, четыре класса
  оттуда в перечне, правка — эскалация ✓.
- Песочница ролей не расширяется: `canary live` под ролью отказывает,
  `doctor` без `--fix` только читает (решение 3).

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| `live_run_note` читает метки без записи | окно тишины и отказ мержа по живой записи — `canary.py:2941`, `notes.py:285`, `fsm_merge_gate.py:1268` | да, плюс новый источник | тесты части А без правок + AC-1, AC-5, AC-20 | остаётся |
| уборка метки новой логикой | метка чужого живого pid не снимается — `tests/test_canary_live_registry_units.py:56` | да | `:56` без правок + AC-5 (i) | остаётся |
| уборка нечитаемой записи с меткой | `tests/test_canary_live_registry_units.py:36` | да | `:36` без правок | остаётся |
| отказ повтора `run_stamp` | `O_EXCL` `canary.py:2840`; `tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_registry.py:477` | да; `--drop` (в) и (а) по решению Оператора штатно снимают метку живого процесса — после этого повтор того же `run_stamp` пройдёт | `:477` без правок; снятие защиты повтора после `--drop` своего теста не имеет | остаётся (посекундный `run_stamp`, риск мал; разработчик сохраняет `:477` зелёным) |
| закрытый белый список роли | `artel.py:2017`, `:2003–2014` | да | AC-15 | остаётся |
| `doctor` без `--fix` не меняет состояние пульта | `artel.py:2009` | да (решение 3) | AC-18 | остаётся |
| изоляция тестов от настоящего реестра | `tests/sandbox.py:90` | расширяется | AC-19 поклассово по перечню | остаётся, см. «Вердикт» п. 1 |
| утверждения `tests/test_canary_template_flag.py` и классов перечня | сами утверждения | да — только добавление изоляции | гейт неослабления тестов | остаётся |
| время полного прогона `tests/` | `FULL_SUITE_TIMEOUT_SEC = 900` (`config.py:223`), `timeout = 120` на тест (`pyproject.toml:13`) | под угрозой при наивной реализации AC-19 | не покрыто | вопрос Оператору («Вердикт» п. 1) |

## Пути обхода гейтов
1. **Шпион AC-19 молчит, если класс сам подменил `_live_dir`.** Если шпион
   обёртывает `canary._live_dir` на уровне модуля, то класс, который в
   `setUp` подменяет тот же атрибут (так требование 5 и предписывает для
   `CmdCanaryTemplateSelectionTest`), заменяет обёртку. Шпион не видит ни
   одного вызова и проходит пусто, даже если подменённый путь лежит под
   корнем (например, `ROOT/tmp/...`). По букве «путь `_live_dir()` при
   обращении» выполнен, по смыслу — нет. Нужна сверка пути, который получают
   сами функции реестра (результат `_live_dir()` внутри `live_runs` и новой
   функции чтения меток либо каталоги, созданные за прогон класса), а не
   наличия вызова обёртки.
2. **Пустой проход класса засчитывается.** Класс перечня, который при
   прогоне ни разу не дошёл до реестра (тест упал раньше или сменился мок),
   даёт зелёный шпион. Это верно для изоляции, но нужно, чтобы шпион
   проверял и то, что класс вообще запустился без ошибок. Иначе падение
   вложенного прогона читается как «изоляция держится».
3. **Снятие метки при оставшейся живой записи.** Требование 3: «снимаются все
   такие записи этого `run_stamp` и его метка». Если у `run_stamp` две
   записи (старая по (а) и свежая живая — в Б-2 редкость, в Б-1 штатно у
   дочерних процессов), по букве снимается и метка, хотя свежая запись
   остаётся. Окно держится (запись есть), но защита повтора `run_stamp` у
   живого прогона пропадает. На Б-2 почти не влияет, отмечаю для Б-1.

## Вердикт
**concerns.** SPEC переносит ТЗ и все шесть решений круга 1, факты о коде
подтверждены, критерии ловят правдоподобные мутации. Остались вопросы на
гейт:

1. AC-19 (SPEC.md, «Критерии приёмки») против `pyproject.toml:13` (`timeout =
   120` на тест) и `orchestrator/config.py:223` (`FULL_SUITE_TIMEOUT_SEC =
   900`). Шпион «поклассово по 116 классам», если он прогоняет классы внутри
   теста, не влезает в 120 с. Последовательный прогон перечня у меня шёл
   больше 10 минут: один `tests/test_01m4m67sgneymn9f1c7xvx24xe_merge_closing.py`
   — 95 с, `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py` — 49 с. Даже
   если разбить шпион на тест на каждый класс, перечень в полном прогоне
   выполнится дважды. SPEC не говорит, как устроен шпион. Решение
   Оператора: (а) шпион — вложенный прогон, разбитый на тест на класс, с
   ценой удвоения этих классов в полном прогоне; (б) шпион на уровне
   процесса (недоступен: `conftest.py` и `tests/sandbox.py` — только
   чтение); (в) вложенный прогон помечен долгоживущим/вне полного набора.
   Дефолт на случай молчания — (а), и разработчик меряет время полного
   прогона в отчёте.
2. Путь обхода 1: шпион AC-19 должен судить по пути, который получают
   функции реестра, а не по вызовам своей обёртки — иначе
   `CmdCanaryTemplateSelectionTest` с подменой `_live_dir` проходит пусто.
   Уточнение формулировки AC-19 или указание разработчику на гейте.
3. Путь обхода 2: вложенный прогон класса со сбоем не должен засчитываться
   как «изоляция держится».
4. Путь обхода 3, требование 3: «и его метка» при оставшейся живой записи
   того же `run_stamp`. Для Б-2 некритично; Оператор может уточнить «метка —
   только если после снятия не осталось записей этого `run_stamp`».

СПАЙ: <итог шпиона>
