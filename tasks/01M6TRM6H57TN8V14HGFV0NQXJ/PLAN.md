---
task: 01M6TRM6H57TN8V14HGFV0NQXJ
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Итог и отчёт тестов задания CI у адаптера GitHub: job_result и job_test_report

## Подход
Монолит, как предложил SPEC. Вся логика чтения — в `_GitHub` (`orchestrator/forge.py`),
реестр `IMPLEMENTATIONS` не меняется: у класса появляются `job_result`,
`job_test_report` и `green_base_commit` (последний — для строки doctor).

- Попытка задания — `_gh_attempt`: check runs коммита через `ci.check_runs` с
  тем же входом, что у `pipeline_status` (артель — без `repo`, прочие — клон
  записи); среди одноимённых — наибольший `id` среди исполненных, иначе среди
  пропущенных. `forge.github_call` не используется.
- Статус — `_gh_job_status` по таблице требования 2; негодное значение —
  статус `unfit:<значение>` (вне `ci.JOB_FINISHED` и вне ожидающих), причина
  называет значение.
- Отчёт — компонент записи с `ci_job == job_name` (ровно один), имя артефакта
  `ci_report_artifact` (умолчание `targets.CI_REPORT_ARTIFACT_DEFAULT = "junit"`),
  `actions/jobs/<id>` → `run_id`, артефакты прогона с фильтром имени и окном
  `started_at ≤ created_at ≤ completed_at` (до секунды), скачивание
  `ci.gh_bytes`, разбор архива `_junit_report` (проверка путей до распаковки,
  предел распакованного размера, ровно один `*.xml`, временный каталог
  `TemporaryDirectory`), разбор junit своим `_parse_junit` (повтор ключа —
  отказ; DTD — отказ).
- `ci.gh_bytes` — двоичный `gh` через `Popen` + `select`: предел размера по
  фактически прочитанным байтам срабатывает при чтении, предел времени — по
  дедлайну; в обоих случаях снимается группа процесса (`start_new_session`,
  `killpg`). Правило входа (`GH_REPO`/`GH_TOKEN`) вынесено из `ci.gh` в
  `ci._gh_entry` без смены поведения `ci.gh`; литералов хостинга в нём нет.
- Пределы — `config.CI_REPORT_ARCHIVE_MAX_BYTES`, `CI_REPORT_UNPACKED_MAX_BYTES`,
  `CI_REPORT_DOWNLOAD_TIMEOUT_SEC`; читаются при вызове (тесты подменяют).
- `pipeline_status` у `_GitHub` заполняет `Job.id` номером check run.
- doctor: `project_checks.check_ci_report`, строка `project-ci-report-<префикс>`
  для компонента с `report` и `full_suite: ci|both`, если у хостинга записи есть
  `green_base_commit` (`forge.implements`, без литералов `"github"`/`"gitlab"`);
  в окружении роли — `skip` с `ROLE_SKIP`; без условия `human`.
- Поле `ci_report_artifact` — `targets.COMPONENT_FIELDS`, проверка типа в
  `_component_value_error` (непустая строка, в отказе имя поля).

Бюджет SPEC ($50) не переоценивается.

## Шаги
1. Ядро чтения: `ci._gh_entry`/`ci.gh_bytes`, константы `config`, поле
   `ci_report_artifact` в `targets`, `_GitHub.job_result`/`job_test_report`,
   `Job.id` в `pipeline_status` (сделано в первом шаге разработчика, WIP-чекпоинт
   `12ba333fc`).
2. Строка doctor: `_GitHub.green_base_commit`, `forge.implements`,
   `project_checks.check_ci_report` (там же).
3. Правки тестов по мандату ANSWER-1: убраны ключи `job_result`/`job_test_report`
   из параметризации `test_ac16_other_functions_not_implemented_without_gh` и
   словаря `GH_CALLS` (`test_ac13_github_other_functions_refuse`); больше ничего.
3а. Возврат из verifying (CI прогон 42439642328), мандат ANSWER-3:
   `tests/test_01m6n7cykdamakenx60cbk7vqx_entry_checks.py::test_ac3_github_people_full_suite_ci_refused`
   на время метода подменяет `forge.IMPLEMENTATIONS["github"]`
   (`monkeypatch.setitem`) пространством имён с атрибутами `_GitHub` без
   `job_test_report` — тем же приёмом, что `test_ac8_registry_attribute_decides_not_literal`.
   Утверждение отказа (`full_suite` в тексте), имя теста и прочие тесты файла не
   менялись. Мутация «`_check_full_suite_source` пропускает `github`» краснит
   метод (проверено временной правкой `targets.py`, возвращена); файл — 25 passed.
4. Карта `docs/codebase-map.md` — генерацией `scripts/codebase_map.py`; прогон
   тестов затронутых модулей и планки.

Прогоны шага (передний план):
- долгоживущие файлы задачи + `github_mr_units`, `gitlab_forge`,
  `hosting_registry`, `forge_guards`, `component_fields`: 359 passed, 2 skipped
  (ровно `[ci]`/`[both]` `test_ac15_full_suite_check_without_ci_module` — мандат
  ANSWER-2);
- планка `plank-run`: 6 passed;
- `project_token`, `project_gh`, `ci_outcome_gate`, `ci_full_suite`,
  `gitlab_doctor_lines`, `doctor_lines`, `ci_result`, `ci_base_doctor`,
  `ci_job_full_suite`, `ci_project_gh_address`, `ci_status`, `submodule_tokens`:
  363 passed;
- `forge_probe_ref_sha`, `http_status`, `ci_base_push_guard`,
  `doctor_gitlab_ci_file`, `forge_gitlab_request`, `task_component_places`,
  `ci_base_fields`, `ci_base_gate`: 111 passed;
- `mr_delivery`, `mr_sync`: 83 passed.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 (`_gh_attempt`, `_GitHub.job_result`) |
| 2 | 1 (`_gh_job_status`, `_GH_CONCLUSION_STATUS`, `_GH_UNFINISHED_STATES`) |
| 3 | 1 (`_GitHub.job_test_report`, `_gh_report_artifact`, `_gh_run_artifacts`, `_junit_report`) |
| 4 | 1 (`_parse_junit`) |
| 5 | 1 (`ci._gh_entry`, `ci.gh_bytes`, `config.CI_REPORT_*`) |
| 6 | 1 (`targets.COMPONENT_FIELDS`, `_component_value_error`) |
| 7 | 1 (`Job.id` в `_GitHub.pipeline_status`) |
| 8 | 2 (`check_ci_report`, `green_base_commit`, `forge.implements`) |
| 9 | 1, 2 (GitLab и записи без `report` не затронуты; строка doctor — только при `green_base_commit` у хостинга) |
| 10 | 3 (и 3а — мандат ANSWER-3 на `entry_checks`) |
| 11 | 1 (в реестре нет хостинга без `job_test_report`; файл не правился) |

## Влияние на систему
- `ci.gh` переписан через `_gh_entry` дословным переносом правила входа —
  поведение прежнее (тесты `ci_project_gh_address`, `project_gh`,
  `project_token` зелёные).
- `pipeline_status` GitHub: меняется только `Job.id`; `verdict`/`reason`/
  `failed` прежние. Сверка «одна попытка» в `ci.job_full_suite` и
  `outcome_integrity._ci_report` теперь действует и для GitHub — логика этих
  функций не менялась.
- `targets._check_full_suite_source` теперь пускает `full_suite: ci` для GitHub
  (в реестре есть `job_test_report`); настоящие `targets.yaml` не менялись —
  переход артели — этап 4б, правка Оператора.
- Гейты, лимиты, инварианты не ослаблены; удалены только четыре варианта
  параметризации по мандату ANSWER-1; два варианта переходят в «пропущен» по
  мандату ANSWER-2, их свойство держит AC-9.
- Откат — revert merge-коммита задачи.

## Риски
- Пагинация артефактов прогона идёт с фильтром `name=`; при отсутствии
  фильтра у сервера список всё равно сверяется с `total_count`.
- Предварительная сверка `size_in_bytes` с пределом — дополнительная к пределу
  по фактическим байтам (не вместо него).
- `JobSuite.job_id` может быть номером пропущенного check run — принято
  решением Оператора 6 (07.11).

## Предложения системе
- Шаг разработчика оборвался таймаутом на прогоне соседних тестов
  (`mr_sync` + `mr_delivery` — ~9 мин): медленные соседние файлы съедают окно
  шага; полезна подсказка пульта «какие файлы tests/ затрагивает diff» с их
  ожидаемой длительностью (`suite_durations`).
