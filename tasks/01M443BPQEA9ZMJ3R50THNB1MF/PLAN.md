---
task: 01M443BPQEA9ZMJ3R50THNB1MF
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Указание Оператора роли в разработке и ревью; подтяжка main перед шагом разработчика

## Подход

Две независимые правки (монолит принят Оператором 04.10).

**Указание Оператора (требования 1–5).** `orchestrator/answer.py::cmd_answer`
до взятия lease решает, указание ли это (`_instruction_text`): состояние
`in_dev`/`review` → рубеж `runner.in_role_environment()` (до чтения файла,
требование 3) → чтение файла → есть хоть одна строка маркера мандата зон или
тестов (`_has_mandate_lines`, даже с пустым/негодным списком) → `None`,
прежний путь под `lease.run_locked` без изменений (AC-3); пустой или из одних
пробелов файл → `sys.exit` «answer отказана — пустой файл указания …» (AC-4);
иначе — `_commit_instruction` БЕЗ lease (требование 5, AC-8: lease держит
идущий шаг, указание адресовано следующему). Коммит ANSWER и перефиксация
вынесены в общий `_commit_answer` (тот же путь, что у ответа/мандата).
Журнал: действие `ANSWER создан: указание Оператора` (константа
`answer.INSTRUCTION_ACTION`), деталь — путь ANSWER; отличается и от
«ANSWER создан, ждёт approve», и от «ANSWER создан (мандат …)» (AC-2).

Указание посреди шага безопасно для чекпоинта шага: ANSWER, последний коммит
которого не автокоммит роли, не кандидат на удаление
(`checkpoint._step_artifact_deletion_candidates`), а `record_fixation` после
коммита не даёт `_docs_ref_drift` принять сдвиг ссылки за запись роли.

**Бриф разработчика (требование 4).** `brief.developer_brief` вместо
`_answer_component` (последний ANSWER) несёт `_developer_answer_components`:
последний ANSWER плюс КАЖДЫЙ, чья запись приёма Оператора (деталь —
`tasks/<id>/ANSWER-n.md`) в журнале новее границы. Граница
(`_developer_answer_boundary`) — id последней записи `developer` «agent run
started»; до первого шага разработчика — последний `state -> in_dev`.
Бриф собирается до записи «agent run started» текущего шага (`runner.
_build_prompt` раньше `run_agent_once`), значит граница — старт ПРЕДЫДУЩЕГО
шага. Порядок — по номеру. Пакет ревью уже несёт все ANSWER (`review.py`),
AC-7 правки не требует.

**Подтяжка перед шагом разработчика (требования 6–7).** `runner.
_run_developer_step` после `_refuse_before_start` (пауза, стоп-кран,
чужая ветка worktree, pre-flight, инцидент целостности, скилы, модель — все
отказы до старта; замок зоны взят раньше, в `_cmd_run`) и до
`_build_prompt` зовёт `_pull_before_developer_step` → тот же узел
`fsm._pull_main_or_escalate(..., run_plank=False)`. Исходы: `fresh` —
ничего (голова не меняется, AC-9); `pulled` — запись «подтяжка main перед
шагом разработчика»; `escalated` — `return` без агента (метку «нужен шаг
роли» пишет `pull._handle_merge_failure`, `in_dev` ∈
`PULL_CONFLICT_MARKED_STATES`; захват зоны снимет `finally` в `_cmd_run`);
`refused` (посторонние файлы) — `sys.exit` с текстом. WIP-чекпоинт перед
слиянием, авторазрешение карты, `git merge --no-ff` (WIP-коммиты остаются
предками) — внутри узла, как на остальных точках.

Два решения сверх буквы SPEC, оба оставлены решением Оператора (ANSWER-1, п.4):
- `run_plank=False` (новый параметр `pull.evaluate`/`fsm.
  _pull_main_or_escalate`, по умолчанию `True` — прежние точки не
  меняются): планка перед шагом разработчика заведомо красна, её прогон
  после слияния эскалировал бы КАЖДУЮ подтяжку. Планку по-прежнему гоняет
  подтяжка на выходе из `in_dev`.
- Пропуск подтяжки, если метка `PULL_CONFLICT_ROLE_STEP_MARKER` записана
  после старта последнего шага разработчика (`_pull_conflict_awaits_role_
  step`, запись «подтяжка main перед шагом пропущена: …»): иначе после
  `approve` такой эскалации подтяжка перед шагом ловит тот же конфликт и
  эскалирует снова — роль, которой метка обещает шаг, его не получает
  никогда (вечный круг answer/approve).

Мьютекс merge-окна: на точках `in_dev -> verifying` и `acceptance` узел
мьютекс не берёт (его берёт только `merge_gate`, `fsm_merge_gate.
_cmd_approve_merge_gate_cycle`); новая точка ведёт себя так же — слияние идёт
в рабочей копии задачи, `origin/main` читается приватной ссылкой
`gitcmd.fetch_ref_sha`, гонка с чужим мержем даёт в худшем случае
устаревший на один коммит `base`, который догонит подтяжка на выходе.

## Шаги

1. `answer.py`: `_has_mandate_lines`, `_instruction_text`, `_commit_answer`,
   `_commit_instruction`, ветвление в `cmd_answer`; докстринг
   `_cmd_answer`.
2. `brief.py`: `_developer_answer_boundary`, `_developer_answer_names`,
   `_developer_answer_components` в `developer_brief`.
3. `pull.py`/`fsm.py`: параметр `run_plank`.
4. `runner.py`: `_pull_before_developer_step`,
   `_pull_conflict_awaits_role_step`, вызов в `_run_developer_step`.
5. `tests/test_runner_pre_step_pull.py` — углы вне долгоживущих файлов;
   `docs/codebase-map.md` регенерирована.
6. По ANSWER-1 (вариант (а) по всем вопросам; мандаты тестов и зон):
   - `tests/test_01m42nb9gkxnp74hayej7c7ca8_class_mandate.py::AnswerInDevWithoutMarkersTest::test_ac5_answer_in_dev_without_markers_keeps_old_refusal`
     переписан под тем же именем: файл с маркером мандата тестов НЕ в
     начале строки принимается указанием (ANSWER-1.md с текстом, `in_dev`,
     запись «указание Оператора», ни записи мандата, ни процитированного
     элемента в журнале); строка про AC-5 в докстринге модуля поправлена.
   - `tests/test_review_package.py::CmdRunReviewPackageTest::test_developer_step_has_no_package`:
     в точный список после скилов дописаны три вызова `fetch_ref_sha`
     (fetch, `rev-parse --verify`, `update-ref -d`) по одной приватной
     ссылке, сверка по префиксу `refs/artel/fetch/`; комментарий дополнен
     пунктом о подтяжке; ничего не подменено.
   - `docs/operator-session.md`: принятый абзац — в конец пункта про
     обходы (после «…БД руками для этого больше не нужна.»).
7. По отказу гейта зон («мандат есть, раздел PLAN не оформлен») — раздел
   «## Расширение зон» PLAN.md со строкой `Пути: docs/operator-session.md`
   и обоснованием; код не менялся.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 2 (ревью-пакет — без правки) |
| 5 | 1 |
| 6 | 3, 4 |
| 7 | 3, 4 |
| 8 | 5 (карта), 6 (operator-session) |

Прогоны после ANSWER-1 (передний план, `-p timeout -o timeout=120`):
- долгоживущие файлы задачи, `test_runner_pre_step_pull`,
  `test_review_package`, `test_01m42nb9…_class_mandate`, `test_answer`,
  `test_answer_gate`, `test_answer_mandate`, `test_answer_branch_reads`,
  `test_brief`, `test_invariants`, `test_codebase_map` — 348 passed,
  242 subtests; `test_canary_template_flag`, `test_catalog_zone_overlap`
  (читают `docs/operator-session.md`) — 42 passed.
- Мутация переписанного ac5 (`_has_mandate_lines` считает мандатом маркер
  где угодно в строке) — метод красный; код возвращён. Исходный
  `test_developer_step_has_no_package` красный на коде задачи без
  дописанных вызовов — список ловит подтяжку.
- `plank-run` — отказ «планки нет» (группа только долгоживущая, прогнана
  выше напрямую).

Прогоны до эскалации:
- `tests/test_01m443bpqea9zmj3r50thnb1mf_operator_instruction.py`,
  `tests/test_01m443bpqea9zmj3r50thnb1mf_developer_step.py` — 11 passed,
  8 subtests. `plank-run` отказывает «планки нет … нет файлов test_*.py»:
  планка задачи — только долгоживущая группа, она прогнана напрямую.
- `tests/test_runner_pre_step_pull.py` — 5 passed; каждый метод краснеет
  на своей мутации (проверено временной правкой кода, 6 мутаций).
- answer/brief/роль: `test_answer*`, `test_brief`, `test_01m3xtf5506…
  _role_refusal`, `test_01m3se87…_role_environment`, `test_canary_synthetic_
  answer`, `test_docs_ref_deleted_refusal`, `test_01m41ab5…_refixation`,
  `test_01m42nb9…_class_mandate` — 129 passed, 1 failed (метод ac5 — закрыт шагом 6).
- pull/runner: `test_pull*`, `test_branch_freshness_gate`,
  `test_fsm_map_conflict_autoresolve`, `test_zone_lock`, `test_agent_
  failure`, `test_agent_prompt`, `test_runner_*`, `test_step_cost`,
  `test_parallel_limit` — 237 passed.
- `test_auto_cycle`, `test_auto_escalated_return_rework_gate`,
  `test_detached_cycle`, `test_timeout_checkpoint`, `test_pause`,
  `test_long_lived_step_end_to_end`, `test_01m3vfyp…_pult_commit`,
  `test_01m409yk…_step_docs_dir`, `test_01m42pen…_project_area`,
  `test_role_commit_by_pult`, `test_agent_log`, `test_budget_live_lease_
  and_escalation`, `test_multitarget`, `test_git_fixation` — 345 passed.
- `test_invariants`, `test_multitarget_invariants`, `test_review_package`,
  `test_acceptance_tests_flow`, `test_artifact_materialization`,
  `test_01m3xtf1…_plan_escalation_marker`, `test_zones_gate` — 346 passed,
  1 failed (`test_developer_step_has_no_package` — закрыт шагом 6).
- провайдеры/предполёт/наборы/kill/workspace/merge-gate git-списки — 255
  passed.

## Влияние на систему

- Lease: единственное исключение из «answer берёт lease» — указание в
  `in_dev`/`review`; оно пишет только ссылку документов (тот же
  `artifact_branch.commit_files`, CAS-запись) и журнал, не трогает
  состояние, lease, рабочую копию и процесс шага. Мандаты и `escalated` —
  под lease, как прежде.
- Рубеж роли не ослаблен: для указания он стоит раньше чтения файла;
  внутренний рубеж ветки мандатов сохранён.
- Подтяжка: прежние три точки зовут узел с `run_plank=True` по умолчанию —
  байт-в-байт прежнее поведение. Новая точка добавляет git-вызовы fetch
  перед каждым шагом developer (сеть к `origin`; без ответа git —
  `Fresh`, шаг идёт).
- Метка `PULL_CONFLICT_ROLE_STEP_MARKER` читается `auto.py` по действию —
  новая точка пишет её тем же узлом, стоп-кран повторных конфликтов
  (`auto.py`) видит её как прежде.
- Откат — revert коммитов задачи; схема БД и форматы артефактов не
  меняются.

## Расширение зон

Пути: docs/operator-session.md

Обоснование: требование 8 SPEC — строка «указание в in_dev/review» в
разделе оператора про `answer`. Путь не защищённый
(`config.PROTECTED_PATHS`), поэтому приложением к PLAN его не провести;
Оператор выбрал правку в ветке задачи (ANSWER-1, п.3) и выдал мандат
«Расширение зон разрешено: docs/operator-session.md». Правка — один
принятый Оператором абзац в конце пункта про обходы (после «…БД руками
для этого больше не нужна.»), больше файл не меняется.

## Риски

- Указание, принятое без lease в момент смены состояния (например,
  `review -> in_dev`), попадёт в бриф другой роли — допустимо: оно и так
  адресовано следующему шагу задачи, ANSWER виден в ссылке.
- Граница брифа по журналу: ANSWER, закоммиченный мимо `answer` (руками),
  без записи журнала попадёт в бриф, только если он последний — как до
  задачи.

## Предложения системе

- SPEC требует строку `docs/operator-session.md` «приложением к PLAN
  (защищённый путь)», но `docs/operator-session.md` нет в
  `config.PROTECTED_PATHS` — guard отклоняет приложение к незащищённому
  пути (`appendix_unprotected_path_error`), а вне зон его не пропустит гейт
  зон. Аналитику (skills/spec-authoring.md) стоит сверять «приложением» с
  `PROTECTED_PATHS`, иначе такой пункт не исполним ни одним путём.
- `tests/test_review_package.py::CmdRunReviewPackageTest::
  test_developer_step_has_no_package` фиксирует ТОЧНЫЙ список git-вызовов
  шага developer: любая новая git-операция перед шагом (здесь — fetch
  подтяжки) требует мандата на правку утверждения, хотя свойство теста
  («diff разработчику не собирается») не меняется. Проверка «нет `show`
  diff/stat» вместо полного списка держала бы то же свойство без
  хрупкости.
