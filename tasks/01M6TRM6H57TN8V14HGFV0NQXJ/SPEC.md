---
task: 01M6TRM6H57TN8V14HGFV0NQXJ
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/forge.py, orchestrator/github_adapter.py, orchestrator/ci.py, orchestrator/targets.py, orchestrator/doctor/project_checks.py, docs/codebase-map.md, tests/
budget_usd: 50
---

# SPEC: Итог и отчёт тестов задания CI у адаптера GitHub: job_result и job_test_report

## Контекст
Источник полного набора `full_suite: ci | both` читает итог задания CI и его
отчёт junit через `forge`: `ci.job_full_suite` (`orchestrator/ci.py:1367`) →
`forge.pipeline_status`, `forge.job_result`, `forge.job_test_report`
(`orchestrator/forge.py:420-432`). Тот же отчёт нужен гейту исходов на
`verifying` (ADR-0026) и проверке «красные до кода» на выходе из
`tests_writing` (`orchestrator/fsm_advance.py:648-653`). В реестре
`IMPLEMENTATIONS` (`orchestrator/forge.py:365`) у `_GitHub` есть только
`pipeline_status` по check runs коммита (`orchestrator/forge.py:231-257`).
Две другие функции отвечают `"<имя>: не реализовано для github"`
(`orchestrator/forge.py:410-417`). Поэтому проект на GitHub, в том числе
артель, не может перейти на запись компонента с `report` и `full_suite: ci`:
`targets._check_full_suite_source` (`orchestrator/targets.py:1299-1322`)
пускает `ci` только при наличии `job_test_report` в реестре. Если бы запись и
загрузилась, итог каждой приёмки был бы «неизвестно». Задача — этап 4а
ADR-0031 (принят Оператором 07.11.2026, `9d60fe8f`).

## Требования

1. `job_result` для GitHub возвращает статус последней попытки задания
   `job_name` у коммита `sha`, прочитанный по check runs коммита. Попытка —
   check run с именем, равным `job_name`. Если таких несколько, берётся
   последний по времени завершения. Check run, пропущенный условием
   (`skipped`), не считается попыткой, если есть исполненный. Статус
   выражается теми же значениями, что у адаптера GitLab
   (`orchestrator/gitlab_adapter.py`, `job_result`). Если задания нет,
   возвращается `JobResult(None, <причина с именем задания>)`.
2. `job_test_report` для GitHub возвращает отчёт junit последней исполненной
   попытки задания. Отчёт берётся из артефакта прогона Actions с именем из
   записи компонента: поле `ci_report_artifact`, файл внутри — первый `*.xml`.
   Отчёт разбирается общим разборщиком junit пульта
   (`orchestrator/reporters/outcome.py`, `parse_junit`) в отображение
   «`<classname>::<name>` → исход». Исходы — те же, что у GitLab
   (`ci.JOB_REPORT_OUTCOMES`, `orchestrator/ci.py:1334`). Если артефакта нет,
   его срок хранения истёк или архив не разобран, возвращается
   `TestReport(None, <причина>)`, а не пустой отчёт.
3. Чтение идёт через `gh api` тем же входом, что прочие вызовы адаптера GitHub
   (`ci.gh`, репозиторий записи). Транспорт GitLab не вызывается. У скачивания
   архива есть предел размера и предел времени. Архив распаковывается во
   временный каталог, его содержимое не исполняется. Путь внутри архива,
   ведущий за пределы каталога, даёт отказ.
4. Новое необязательное поле компонента записи `ci_report_artifact`
   (`orchestrator/targets.py`), по умолчанию `junit`. Значение неверного типа —
   отказ загрузки записи с именем поля.
5. `_GitHub.pipeline_status` заполняет `Job.id` номером check run.
   `job_result` и `job_test_report` берут ту же попытку. Сверка «одна попытка»
   в `ci.job_full_suite` (`orchestrator/ci.py:1352-1386`) действует и для
   GitHub (ANSWER-1, п. 2).
6. `doctor` для компонента записи на GitHub с `report` и `full_suite: ci`
   проверяет, что задание `ci_job` и артефакт отчёта читаются у последнего
   зелёного коммита базы. Итог — строка `ok` или `warn` с причиной. Проверка
   только читает (`orchestrator/doctor/project_checks.py`).
7. Поведение записей без `report` и проектов на GitLab остаётся прежним
   побайтно.
8. Из параметризации
   `tests/test_01m6m1799ycy5hxmhhd71shjet_github_mr_units.py::test_ac16_other_functions_not_implemented_without_gh`
   (`:935-937`) и из словаря `GH_CALLS`
   `tests/test_01m5wcxbm7wcmrwcbwnchmar3t_gitlab_forge.py` (`:370-372`,
   утверждение `test_ac13_github_other_functions_refuse`, `:1196-1197`)
   убираются ключи `job_result` и `job_test_report` и ничего больше: четыре
   варианта `[job_result]` и `[job_test_report]` этих двух тестов. Прочие
   функции остаются под прежним утверждением. Имена тестов и остальные
   утверждения не меняются. Основание — мандат Оператора
   «Ослабление тестов разрешено» в ANSWER-1.md на эти два файла.

## Критерии приёмки

AC-1. Дано: подменённый ответ `gh api` с check runs коммита, где два check
run с именем `job_name`: исполненный и пропущенный условием (`skipped`), и
артефакт прогона с junit. Когда `forge.job_result` и `forge.job_test_report`
вызваны для записи на GitHub, тогда статус и отчёт взяты у последней
исполненной попытки. Статус выражен значением адаптера GitLab, исходы отчёта
лежат в `ci.JOB_REPORT_OUTCOMES` с ключами `<classname>::<name>`. Вызван
`gh api`, транспорт GitLab не вызван (условие матрицы неослабления
ANSWER-1.md).

AC-2. Дано: у коммита нет check run с именем `job_name`. Тогда
`forge.job_result` возвращает `JobResult(None, причина)`, и причина называет
имя задания.

AC-3. Дано по отдельности: артефакта нет / срок хранения артефакта истёк /
архив повреждён / в архиве путь вне каталога / архив больше предела. Тогда
`forge.job_test_report` возвращает `TestReport(None, причина)`, причина
называет случай, и вне временного каталога не создано ни одного файла.

AC-4. Дано: вымышленная запись компонента на GitHub с `report` и
`full_suite: ci` и зелёный отчёт задания. Когда идёт приёмка, тогда итог —
«принят из задания CI» с числом тестов отчёта. Если в отчёте упавший тест,
итог красный, и в нём названо имя теста.

AC-5. Если у компонента не задано `ci_report_artifact`, берётся артефакт
`junit`. Если поле задано значением неверного типа, загрузка записи
отказывает, и в отказе названо имя поля `ci_report_artifact`.

AC-6. `doctor` для компонента записи на GitHub с `report` и `full_suite: ci`
выводит строку о чтении отчёта у последнего зелёного коммита базы: `ok`, если
отчёт читается, и `warn` с причиной, если артефакта нет.

AC-7. Дано: задание перезапущено между чтением статуса и чтением отчёта, то
есть у check run с тем же именем появился новый номер. Тогда
`ci.job_full_suite` для записи на GitHub возвращает итог «неизвестно»
(`ci.JOB_UNKNOWN`), а не зелёный. `PipelineStatus.jobs` у `_GitHub` несёт
`Job.id`, равный номеру check run.

AC-8. Итоги записей GitLab и записей без `report` прежние: `job_result`,
`job_test_report`, `pipeline_status` и приёмка на тех же входах дают те же
результаты, что до задачи.

## Оценка объёма и деление

Сработавшие сигналы: в зоне 5 файлов кода (`forge.py`, `github_adapter.py`,
`ci.py`, `targets.py`, `doctor/project_checks.py`); `budget_usd` ≥ $30.

Материал для решения Оператора о монолите. Ядро — чтение check runs и
артефакта (требования 1–3, 5) вместе с полем `ci_report_artifact`
(требование 4). Его нельзя разрезать: `job_test_report` без поля не знает
имени артефакта, а поле без функции — мёртвая запись. Правка тестов по
мандату (требование 8) обязана ехать в той же ветке, иначе четыре варианта
краснеют. От ядра отделима только строка `doctor` (требование 6, AC-6). Она
опирается на `job_test_report` и мержима отдельно второй частью «после
части 1». Цена деления — отдельный цикл analyst + аудит + test_author +
developer + review (около $15–20) ради одного критерия. Поэтому предлагается
монолит; делить ли — решает Оператор на гейте SPEC.

## Не входит

- Правка настоящего локального слоя `.artel/targets.yaml` в тестах и при
  разработке. Тесты не трогают настоящие `.artel/targets.yaml` и
  `targets.yaml` артели, не ходят в сеть и в настоящий репозиторий на GitHub:
  `gh` подменяется программой или `ci.gh`, архивы собираются в тесте во
  временном каталоге.
- Правка `.github/workflows/ci.yml` (загрузка артефакта junit) и
  `targets.yaml` артели — этап 4б, правка Оператора после этой задачи.
- Наследование итога CI `main` (этап 5 ADR-0031).
- Изменение приёмки и гейта мержа. Логика `ci.job_full_suite` не меняется:
  сверка «одна попытка» начинает действовать для GitHub через `Job.id` из
  требования 5.
- Правка файлов «только чтение» из ТЗ: `docs/adr/0031-test-runs-strategy.md`,
  `docs/adr/0026-project-components-and-outcome-gates.md`,
  `orchestrator/gitlab_adapter.py`, `orchestrator/acceptance.py`,
  `orchestrator/reporters/`, `.github/workflows/ci.yml`, `targets.yaml`,
  `tests/sandbox.py`, `orchestrator/fsm_advance.py`. В `orchestrator/ci.py` —
  только вызовы `gh` для артефактов, если они нужны.
- Правка существующих тестов сверх четырёх вариантов требования 8. Зелёный
  полный набор `tests/` держит пульт. Если от реализации, в том числе от
  заполнения `Job.id` (требование 5), краснеет существующий тест (например,
  сравнивающий `jobs` целиком), это эскалация с именем теста, без правки
  (ТЗ; ANSWER-1, п. 2).
- `docs/codebase-map.md` меняется только генерацией
  (`python3 scripts/codebase_map.py`).

## Материалы

- ТЗ: `tasks/01M6TRM6H57TN8V14HGFV0NQXJ/TZ.md`. Ответ Оператора, мандат и
  матрица неослабления на два файла тестов:
  `tasks/01M6TRM6H57TN8V14HGFV0NQXJ/ANSWER-1.md`.
- Четыре варианта по мандату:
  - `tests/test_01m6m1799ycy5hxmhhd71shjet_github_mr_units.py::test_ac16_other_functions_not_implemented_without_gh[job_result]`;
  - `tests/test_01m6m1799ycy5hxmhhd71shjet_github_mr_units.py::test_ac16_other_functions_not_implemented_without_gh[job_test_report]`;
  - `tests/test_01m5wcxbm7wcmrwcbwnchmar3t_gitlab_forge.py::test_ac13_github_other_functions_refuse[job_result]`;
  - `tests/test_01m5wcxbm7wcmrwcbwnchmar3t_gitlab_forge.py::test_ac13_github_other_functions_refuse[job_test_report]`.
- `tests/test_01m5xzskk8gzteca2kwafhe029_component_fields.py::test_ac3_forge_without_job_test_report_refused`
  сам подменяет реестр (`:179-186`) и от реализации не краснеет.
- `forge.job_test_report(target, sha, job_name)` не получает компонент. Имя
  артефакта (`ci_report_artifact`) берётся из компонента записи, у которого
  `ci_job` равно `job_name`.
- `ci._last_job` (`orchestrator/ci.py:1352-1360`) берёт попытку с наибольшим
  `Job.id` среди одноимённых заданий. Если в `jobs` GitHub есть и
  исполненный, и пропущенный check run одного имени, нужно, чтобы номер
  попытки в итоге согласовался с попыткой, которую читают `job_result` и
  `job_test_report` (требования 1, 5). Как этого добиться — решение
  разработчика на этапе PLAN.
- CI артели: задание полного набора — check run `ci.FULL_SUITE_JOB`
  (`orchestrator/ci.py:36`). При открытом PR набор идёт на событии
  `pull_request`, а на `push` пропускается условием (`.github/workflows/ci.yml`,
  задание `changes`, ADR-0016). Оба check run привязаны к головному коммиту.
