---
task: 01M6TRM6H57TN8V14HGFV0NQXJ
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/forge.py, orchestrator/github_adapter.py, orchestrator/ci.py, orchestrator/targets.py, orchestrator/doctor/project_checks.py, orchestrator/config.py, docs/codebase-map.md, tests/
budget_usd: 50
---

# SPEC: Итог и отчёт тестов задания CI у адаптера GitHub: job_result и job_test_report

## Контекст
Источник полного набора `full_suite: ci | both` читает итог задания CI и его
отчёт junit через `forge`: `ci.job_full_suite` (`orchestrator/ci.py:1367`) →
`forge.pipeline_status`, `forge.job_result`, `forge.job_test_report`
(`orchestrator/forge.py:420-432`). Тот же отчёт нужен гейту исходов на
`verifying` (ADR-0026, `outcome_integrity._ci_report`,
`orchestrator/advance_gates/outcome_integrity.py:1065`) и проверке «красные до
кода» на выходе из `tests_writing` (`orchestrator/fsm_advance.py:648-653`). В
реестре `IMPLEMENTATIONS` (`orchestrator/forge.py:365`) у `_GitHub` есть только
`pipeline_status` по check runs коммита (`orchestrator/forge.py:231-257`), и
`Job` в нём строится без `id` (`:238-240`). Две другие функции отвечают
`"<имя>: не реализовано для github"` (`orchestrator/forge.py:410-417`). Поэтому
проект на GitHub, в том числе артель, не может перейти на запись компонента с
`report` и `full_suite: ci`: `targets._check_full_suite_source`
(`orchestrator/targets.py:1299-1322`) пускает `ci` только при наличии
`job_test_report` в реестре. Если бы запись и загрузилась, итог каждой приёмки
был бы «неизвестно». Задача — этап 4а ADR-0031 (принят Оператором 07.11.2026,
`9d60fe8f`).

## Требования

1. `job_result` для GitHub возвращает статус попытки задания `job_name` у
   коммита `sha`, прочитанный по check runs коммита. Попытка — check run с
   именем, равным `job_name`, с наибольшим номером (`id`) среди исполненных.
   Check run, пропущенный условием (заключение `skipped`), не считается
   попыткой, если есть исполненный. Последняя попытка ещё не завершена —
   возвращается ожидающий статус, а не итог прежней попытки. Если задания нет,
   возвращается `JobResult(None, <причина с именем задания>)`.
2. Перевод заключения и состояния check run в статус пульта:

   | GitHub | статус `JobResult` |
   |---|---|
   | `success` | `success` |
   | `failure`, `timed_out` | `failed` |
   | `cancelled` | `canceled` |
   | `skipped` | `skipped` |
   | `neutral`, `action_required`, `stale` | негодный статус: не входит ни в `ci.JOB_FINISHED` (`orchestrator/ci.py:1338`), ни в ожидающие статусы (`orchestrator/advance_gates/outcome_integrity.py:1048`); причина называет заключение |
   | `queued`, `in_progress`, `waiting`, `pending`, `requested` (состояние незавершённого check run) | `running` |
   | любое иное значение заключения или состояния | негодный статус (как строкой выше: ни в `ci.JOB_FINISHED`, ни в ожидающих); причина называет это значение |

3. `job_test_report` для GitHub возвращает отчёт junit той же попытки, что
   `job_result`. Отчёт берётся из артефакта прогона Actions этой попытки.
   Имя артефакта — поле `ci_report_artifact` того компонента записи, у
   которого `ci_job` равно `job_name`. Артефакт годен для попытки, только
   если его `created_at` лежит между `started_at` и `completed_at` check run
   этой попытки. Возвращается `TestReport(None, <причина>)`, а не пустой
   отчёт, в каждом из случаев:
   - ни одного или больше одного компонента записи с `ci_job == job_name`;
   - у прогона нет годного артефакта с этим именем (в том числе единственный
     артефакт с этим именем создан до `started_at` попытки), срок его
     хранения истёк или архив не разобран;
   - у прогона больше одного годного артефакта с этим именем;
   - в архиве не ровно один файл `*.xml`;
   - архив больше предела или суммарный размер его содержимого после
     распаковки больше предела;
   - скачивание не уложилось в предел времени;
   - путь внутри архива ведёт за пределы каталога распаковки;
   - ключ `<classname>::<name>` встречается в отчёте больше одного раза (как
     у адаптера GitLab, `orchestrator/gitlab_adapter.py:512-515`).
4. Отчёт разбирается своим кодом адаптера, не
   `reporters/outcome.parse_junit`: тот отдаёт ключи компонента и исходы
   `passed`/`failed`/`error`/`skipped` (`orchestrator/reporters/outcome.py:25-28`,
   `:163-201`). Ключ — `<classname>::<name>` из атрибутов `testcase`. Исход:
   `testcase` без вложенного `failure`/`error`/`skipped` — `success`, с
   `failure` — `failed`, с `error` — `error`, со `skipped` — `skipped`, то есть
   значения `ci.JOB_REPORT_OUTCOMES` (`orchestrator/ci.py:1334`).
5. Чтение идёт через `gh api`. Вход `gh` у `job_result`, `job_test_report` и
   строки `doctor` (требование 8) — тот же, что у `_GitHub.pipeline_status`
   (`orchestrator/forge.py:232-233`): для записи артели — без `repo`, для
   прочих записей — с `repo` клона записи; `forge.github_call`, отказывающий
   артели (`orchestrator/forge.py:202-205`), для этих вызовов не
   используется. JSON-ответы — через `ci.gh`. Архив артефакта скачивается
   отдельным двоичным вызовом `gh` в `orchestrator/ci.py` с тем же правилом
   входа: `ci.gh` работает в текстовом режиме (`orchestrator/ci.py:91`), и
   двоичный вывод даёт в нём непойманный `UnicodeDecodeError`. Транспорт
   GitLab не вызывается. Пределы — константы `orchestrator/config.py`:
   `CI_REPORT_ARCHIVE_MAX_BYTES` (размер скачиваемого архива по фактически
   полученным байтам, не по полю `size_in_bytes`),
   `CI_REPORT_UNPACKED_MAX_BYTES` (суммарный размер после распаковки),
   `CI_REPORT_DOWNLOAD_TIMEOUT_SEC` (время скачивания; превышение —
   `TestReport(None, <причина о пределе времени>)`). Пути внутри архива
   проверяются до распаковки. Архив распаковывается во временный каталог, его
   содержимое не исполняется, каталог удаляется после разбора.
6. Новое необязательное поле компонента записи `ci_report_artifact`
   (`orchestrator/targets.py`), по умолчанию `junit`. Значение неверного типа —
   отказ загрузки записи с именем поля.
7. `_GitHub.pipeline_status` заполняет `Job.id` номером check run у всех
   check runs, в том числе пропущенных. `job_result` и `job_test_report`
   берут ту же попытку. Сверка «одна попытка»
   в `ci.job_full_suite` (`orchestrator/ci.py:1383-1386`) и в
   `outcome_integrity._ci_report` (`orchestrator/advance_gates/outcome_integrity.py:1085-1087`)
   действует и для GitHub (ANSWER-1, п. 2).
8. `doctor` для компонента записи на GitHub с `report` и `full_suite: ci`
   ищет последний зелёный коммит базы: прогоны workflow ветки `base`
   (`gh api` `actions/runs?branch=<base>&status=success`), первый, у которого
   задание `ci_job` исполнено. У его коммита проверяется, что задание и
   артефакт отчёта читаются. Итог — строка `ok`, либо `warn` с причиной, если
   зелёный коммит не найден или отчёт не читается. Проверка только читает
   (`orchestrator/doctor/project_checks.py`). Строка выводится для любой
   такой записи, в том числе для записи артели, и не ограничивается
   записями с мержем людьми (условие `human`,
   `orchestrator/doctor/project_checks.py:461`, её не касается). Хостинг
   выбирается через реестр, не строкой `"github"` в коде.
9. Поведение записей без `report` и проектов на GitLab остаётся прежним
   побайтно.
10. Из параметризации
    `tests/test_01m6m1799ycy5hxmhhd71shjet_github_mr_units.py::test_ac16_other_functions_not_implemented_without_gh`
    (`:935-937`) и из словаря `GH_CALLS`
    `tests/test_01m5wcxbm7wcmrwcbwnchmar3t_gitlab_forge.py` (`:370-372`,
    утверждение `test_ac13_github_other_functions_refuse`, `:1196-1197`)
    убираются ключи `job_result` и `job_test_report` и ничего больше: четыре
    варианта `[job_result]` и `[job_test_report]` этих двух тестов. Прочие
    функции остаются под прежним утверждением. Имена тестов и остальные
    утверждения не меняются. Основание — мандат ANSWER-1.md на эти два файла.
11. Варианты `[ci]` и `[both]`
    `tests/test_01m6ezxvfgxc6wbda9qjesazrw_hosting_registry.py::test_ac15_full_suite_check_without_ci_module`
    переходят из «прошёл» в «пропущен» по своему условию `skipif` (`:114`): в
    реестре не остаётся хостинга без `job_test_report`. Файл не правится.
    Свойство «запись `full_suite: ci|both` хостинга без `job_test_report`
    отказывает одинаково в процессе с модулем `ci` и без него» переходит к
    тесту-замене задачи (AC-9). Основание — мандат ANSWER-2.md на этот файл.

## Критерии приёмки

Пути `gh api`, которые тесты подменяют (подмена программы `gh`, общая для
`ci.gh` и двоичного вызова, либо подмена обоих входов; `{owner}/{repo}` — как
в `ci.check_runs_page`, `orchestrator/ci.py:293`):
- check runs коммита — `repos/{owner}/{repo}/commits/<sha>/check-runs`
  (поля `id`, `name`, `status`, `conclusion`, `started_at`, `completed_at`,
  `details_url` вида `…/actions/runs/<run_id>/job/<id>`);
- задание прогона — `repos/{owner}/{repo}/actions/jobs/<id>` (поле `run_id`);
  подмена отвечает согласованно с `details_url`;
- артефакты прогона — `repos/{owner}/{repo}/actions/runs/<run_id>/artifacts`
  (поля `id`, `name`, `expired`, `size_in_bytes`, `created_at`);
- скачивание артефакта — `repos/{owner}/{repo}/actions/artifacts/<id>/zip`
  (двоичный ответ);
- прогоны ветки базы для `doctor` —
  `repos/{owner}/{repo}/actions/runs?branch=<base>&status=success`.

AC-1. Дано: подменённые ответы `gh api`, где у коммита два check run с именем
`job_name`, исполненный и пропущенный условием (`skipped`), и у прогона
исполненного — артефакт с junit. Когда `forge.job_result` и
`forge.job_test_report` вызваны для записи на GitHub, тогда статус и отчёт взяты
у исполненной попытки. Ключи отчёта — `<classname>::<name>`, исходы лежат в
`ci.JOB_REPORT_OUTCOMES`. Дано отдельно: два исполненных check run с именем
`job_name`, у большего номера состояние `in_progress`. Тогда `job_result`
возвращает `running`, а не статус меньшего номера. В обоих случаях вызван
`gh api`, транспорт GitLab не вызван (условие матрицы ANSWER-1.md). Тот же
первый сценарий проходит и в варианте записи артели: песочница, где
`config.TARGETS` указывает на файл во временном каталоге теста с вымышленной
записью артели, программа `gh` подменена; статус и отчёт прочитаны, отказа
«артель» (`forge.github_call`) нет.

AC-2. Дано: у коммита нет check run с именем `job_name`. Тогда
`forge.job_result` возвращает `JobResult(None, причина)`, и причина называет
имя задания.

AC-3. Дано по отдельности: артефакта нет / срок хранения истёк (`expired`) /
единственный артефакт с именем `ci_report_artifact` создан (`created_at`) до
`started_at` попытки / архив повреждён / два годных артефакта с именем
`ci_report_artifact` у прогона / в архиве ноль или два файла `*.xml` / в
архиве путь вне каталога / архив больше `CI_REPORT_ARCHIVE_MAX_BYTES` / поле
`size_in_bytes` занижено, а фактически полученные байты больше
`CI_REPORT_ARCHIVE_MAX_BYTES` / содержимое после распаковки больше
`CI_REPORT_UNPACKED_MAX_BYTES` (тест подменяет обе константы) / подменная
программа `gh` при скачивании спит дольше подменённой константы
`CI_REPORT_DOWNLOAD_TIMEOUT_SEC` (около 1 с) / в отчёте один ключ
`<classname>::<name>` встречается дважды: сначала с `failure`, затем без
вложенных элементов / в записи ноль или два компонента с
`ci_job == job_name`. Тогда `forge.job_test_report` возвращает
`TestReport(None, причина)`, причина называет случай (для предела времени —
предел времени; для пути вне каталога тест сверяет именно причину, так как
`zipfile` сам снимает `..`), вне временного каталога не создано ни одного
файла, и временный каталог после вызова удалён. Архивы собираются в тесте во
временном каталоге.

AC-4. Каждое заключение и состояние check run из таблицы требования 2 даёт в
`forge.job_result` статус из той же строки таблицы. Для `neutral`,
`action_required`, `stale` статус не входит ни в `ci.JOB_FINISHED`, ни в
ожидающие статусы, а причина называет заключение. Состояние `requested`
даёт `running`. Вымышленное значение, которого нет в таблице, даёт статус
вне `ci.JOB_FINISHED` и вне ожидающих, а причина называет это значение. Дано: вымышленная запись
компонента на GitHub с `report` и `full_suite: ci` и зелёный отчёт задания.
Когда идёт приёмка, тогда итог — «принят из задания CI» с числом тестов
отчёта. Если задание завершилось с `failure` и в отчёте упавший тест, итог
красный, и в нём названо имя теста.

AC-5. Если у компонента не задано `ci_report_artifact`, берётся артефакт
`junit`. Если поле задано значением неверного типа, загрузка записи
отказывает, и в отказе названо имя поля `ci_report_artifact`.

AC-6. `doctor` для компонента записи на GitHub с `report` и `full_suite: ci`
выводит строку о чтении отчёта у последнего зелёного коммита базы,
найденного по `actions/runs?branch=<base>&status=success`: `ok`, если отчёт
читается; `warn` с причиной, если зелёного прогона с исполненным заданием
`ci_job` нет или артефакта у него нет. Строка выводится и для записи без мержа
людьми, и в варианте записи артели (песочница: `config.TARGETS` из временного
каталога теста, программа `gh` подменена).

AC-7. Дано: при первом чтении попытка задания — check run с номером N; между
чтением статуса и чтением отчёта появляется новая попытка — check run того же
имени с номером больше N, завершённая с `success`, с зелёным отчётом. Тогда
`ci.job_full_suite` для записи на GitHub возвращает `ci.JOB_UNKNOWN` с
причиной «перезапущено во время чтения», а `outcome_integrity._ci_report` на
том же сценарии возвращает `None` с той же причиной. `PipelineStatus.jobs` у
`_GitHub` несёт `Job.id`, равный номеру check run, у каждого check run, в том
числе пропущенного.

AC-8. Итоги записей GitLab и записей без `report` прежние: `job_result`,
`job_test_report`, `pipeline_status` и приёмка на тех же входах дают те же
результаты, что до задачи. У `_GitHub.pipeline_status` `verdict`, `reason` и
`failed` прежние, `jobs` отличаются только полем `id`.

AC-9. Дано: реестр хостингов, подменённый в процессе теста так, что в нём
есть хостинг без `job_test_report`, и запись компонента этого хостинга с
`full_suite: ci` (и отдельно `both`), `ci_job` и `report`. Тогда загрузка
записи отказывает в процессе без модуля `ci` (его нет в `sys.modules` до
загрузки) и в процессе после импорта `orchestrator.ci`, тексты отказа
одинаковы и называют `full_suite`. Мутация «реестр подставляется в `targets`
при импорте `ci`» делает тест красным. Настоящие `targets.yaml` и реестр в
файлах не меняются.

## Оценка объёма и деление

Сработавшие сигналы: в зоне 6 файлов кода (`forge.py`, `github_adapter.py`,
`ci.py`, `targets.py`, `doctor/project_checks.py`, `config.py`);
`budget_usd` ≥ $30.

Материал для решения Оператора о монолите. Ядро — чтение check runs и
артефакта (требования 1–5, 7) вместе с полем `ci_report_artifact`
(требование 6) и константами пределов. Его нельзя разрезать:
`job_test_report` без поля не знает имени артефакта, а поле без функции —
мёртвая запись. Правки тестов по мандатам (требования 10, 11) и тест-замена
AC-9 обязаны ехать в той же ветке: без них четыре варианта краснеют, а два
переходят в «пропущен» без замены, и гейт исходов отказывает
(`orchestrator/advance_gates/outcome_integrity.py:226`). От ядра отделима
только строка `doctor` (требование 8, AC-6). Она опирается на
`job_test_report` и мержима отдельно второй частью «после части 1». Цена
деления — отдельный цикл analyst + аудит + test_author + developer + review
(около $15–20) ради одного критерия. Поэтому предлагается монолит; делить ли —
решает Оператор на гейте SPEC.

## Не входит

- Правка настоящего локального слоя `.artel/targets.yaml` в тестах и при
  разработке. Тесты не трогают настоящие `.artel/targets.yaml` и
  `targets.yaml` артели, не ходят в сеть и в настоящий репозиторий на GitHub:
  `gh` подменяется программой или входами `ci`, архивы собираются в тесте во
  временном каталоге, реестр хостингов подменяется в процессе теста.
- Правка `.github/workflows/ci.yml` (загрузка артефакта junit) и
  `targets.yaml` артели — этап 4б, правка Оператора после этой задачи.
- Наследование итога CI `main` (этап 5 ADR-0031).
- Изменение приёмки и гейта мержа. Логика `ci.job_full_suite` и
  `outcome_integrity._ci_report` не меняется: сверка «одна попытка» начинает
  действовать для GitHub через `Job.id` из требования 7.
- Правка файлов «только чтение» из ТЗ: `docs/adr/0031-test-runs-strategy.md`,
  `docs/adr/0026-project-components-and-outcome-gates.md`,
  `orchestrator/gitlab_adapter.py`, `orchestrator/acceptance.py`,
  `orchestrator/reporters/`, `.github/workflows/ci.yml`, `targets.yaml`,
  `tests/sandbox.py`, `orchestrator/fsm_advance.py`. В `orchestrator/ci.py` —
  только вызовы `gh` для артефактов.
- Правка существующих тестов сверх четырёх вариантов требования 10 и смена
  исхода существующих тестов сверх двух вариантов требования 11. Зелёный
  полный набор `tests/` держит пульт. Если от реализации, в том числе от
  заполнения `Job.id` (требование 7), краснеет существующий тест (например,
  сравнивающий `jobs` целиком), это эскалация с именем теста, без правки
  (ТЗ; ANSWER-1, п. 2).
- `docs/codebase-map.md` меняется только генерацией
  (`python3 scripts/codebase_map.py`).

## Материалы

- ТЗ: `tasks/01M6TRM6H57TN8V14HGFV0NQXJ/TZ.md`. Мандаты и матрицы
  неослабления: `ANSWER-1.md` (два файла, четыре варианта), `ANSWER-2.md`
  (`tests/test_01m6ezxvfgxc6wbda9qjesazrw_hosting_registry.py`, два варианта
  переходят в «пропущен»). Решения Оператора на гейте SPEC 07.11.2026
  (первый возврат 1–6, второй возврат 1–7).
- Четыре варианта по мандату ANSWER-1:
  - `tests/test_01m6m1799ycy5hxmhhd71shjet_github_mr_units.py::test_ac16_other_functions_not_implemented_without_gh[job_result]`;
  - `tests/test_01m6m1799ycy5hxmhhd71shjet_github_mr_units.py::test_ac16_other_functions_not_implemented_without_gh[job_test_report]`;
  - `tests/test_01m5wcxbm7wcmrwcbwnchmar3t_gitlab_forge.py::test_ac13_github_other_functions_refuse[job_result]`;
  - `tests/test_01m5wcxbm7wcmrwcbwnchmar3t_gitlab_forge.py::test_ac13_github_other_functions_refuse[job_test_report]`.
- Два варианта по мандату ANSWER-2:
  - `tests/test_01m6ezxvfgxc6wbda9qjesazrw_hosting_registry.py::test_ac15_full_suite_check_without_ci_module[ci]`;
  - `tests/test_01m6ezxvfgxc6wbda9qjesazrw_hosting_registry.py::test_ac15_full_suite_check_without_ci_module[both]`.
- `tests/test_01m5xzskk8gzteca2kwafhe029_component_fields.py::test_ac3_forge_without_job_test_report_refused`
  сам подменяет реестр (`:179-186`) и от реализации не краснеет.
- Реестр для проверки записи `targets` берёт импортом `forge` при вызове
  (`orchestrator/targets.py:1341-1348`), а `forge` импортирует `ci`
  (`orchestrator/forge.py:20`). Как подменить реестр в процессе AC-9, не
  импортируя `ci` до загрузки записи, решает автор тестов.
- `ci._last_job` (`orchestrator/ci.py:1352-1360`) и `_ci_report.last_attempt`
  (`orchestrator/advance_gates/outcome_integrity.py:1073-1078`) берут
  наибольший `Job.id` среди одноимённых заданий `jobs`, включая пропущенные.
  Поэтому `JobSuite.job_id` (номер в записи приёмки,
  `orchestrator/acceptance.py:4266`) может оказаться номером пропущенного
  check run — это принято решением Оператора 6 (07.11).
- Пульт перезапускает задание в том же `run_id` прогона
  (`ci.trigger_rerun`, `orchestrator/ci.py:1819-1848`); артефакт прежней
  попытки отсекает окно `started_at`–`completed_at` попытки (требование 3).
- `zipfile` молча снимает `..` и ведущий `/` в именах при распаковке и не
  отказывает (опыт проверяющего 07.11): проверка путей — до распаковки, и
  мутацию «нет проверки путей» ловит только сверка причины отказа (AC-3).
- В новом двоичном вызове `gh` в `orchestrator/ci.py` нет строк `"github"`/
  `"gitlab"`; хостинг в `doctor` выбирается через реестр — их держит сторож
  `test_ac21_real_modules_select_forge_by_registry`
  (`tests/test_01m5wcxbm7wcmrwcbwnchmar3t_forge_guards.py:411-427`).
- Решения Оператора на гейте SPEC 07.11 (второй возврат) и чем проверены,
  везде против временного дублёра (подменённая программа `gh`, вымышленная
  запись, архивы во временной песочнице; настоящие файлы не меняются):
  1 (окно `created_at`) — требование 3, AC-3; 2 (вход `gh` как у
  `pipeline_status`, артель, `doctor` без условия `human`) — требования 5,
  8, AC-1, AC-6; 3 (пределы по фактическим байтам и по времени) —
  требования 3, 5, AC-3; 4 (`requested`, иное значение) — требование 2,
  AC-4; 5 (повтор ключа) — требование 3, AC-3; 6 (`Job.id` у всех check
  runs) — требование 7, AC-7; 7 (записки разработчику) — AC-3 и пункт выше.
- CI артели: задание полного набора — check run `ci.FULL_SUITE_JOB`
  (`orchestrator/ci.py:36`). При открытом PR набор идёт на событии
  `pull_request`, а на `push` пропускается условием (`.github/workflows/ci.yml`,
  задание `changes`, ADR-0016). Оба check run привязаны к головному коммиту.
