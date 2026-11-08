---
task: 01M6TRM6H57TN8V14HGFV0NQXJ
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Итог и отчёт тестов задания CI у адаптера GitHub: job_result и job_test_report

## Фаза A — план
- Таблица покрытия PLAN полна: требования 1–11, у каждого есть шаг и имена функций.
- Шаги размера MR. Шаг 3а — правка `entry_checks` по мандату ANSWER-3, в таблице связана с требованием 10.
- Подход не конфликтует с архитектурой: реестр `IMPLEMENTATIONS` не меняется. Новые функции — атрибуты `_GitHub`. Строка doctor выбирается через `forge.implements`, без литералов хостинга. Вход `gh` вынесен в `ci._gh_entry`, общий для `ci.gh` и `ci.gh_bytes`.
- «Влияние на систему» совпадает с diff: 5 модулей кода и 3 файла тестов по мандатам ANSWER-1/3. `docs/codebase-map.md` — генерация. Откат описан.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `forge.py::_gh_attempt`: наибольший `id` среди check runs с `conclusion != "skipped"`, иначе среди пропущенных. У незавершённого check run `conclusion` равно None, поэтому он входит в исполненные и даёт `running`. Задания нет — `JobResult(None, …«<имя>»…)`. |
| 2 | OK | `_GH_CONCLUSION_STATUS`, `_GH_UNFINISHED_STATES`. Прочие значения дают `unfit:<значение>`: этот статус не входит ни в `JOB_FINISHED`, ни в ожидающие, причина называет значение. |
| 3 | OK | Ровно один компонент с `ci_job`. Окно `started_at ≤ created_at ≤ completed_at` проверяется с точностью до секунды (`_gh_time` берёт `[:19]`). Есть отказы: 0 или >1 годных артефактов, `expired`, ровно один `*.xml`, повтор ключа, путь вне каталога, оба предела размера, предел времени. |
| 4 | OK | `_parse_junit` — свой разбор на `ElementTree`: ключ `classname::name`, вложенные `failure`/`error`/`skipped` дают `failed`/`error`/`skipped`, без вложенных — `success`. DTD/ENTITY отказываются до разбора (защита от раздувания сущностями). |
| 5 | OK | `ci.gh_bytes` на `Popen`+`select`: предел размера проверяется по фактически прочитанным байтам при чтении, предел времени — по дедлайну. В обоих случаях группа процесса снимается `killpg`. Вход — `_gh_entry`, тот же, что у `ci.gh`. `forge.github_call` не используется. Константы в `config.py` читаются в момент вызова. Пути проверяются до распаковки (`_unsafe_member`), при распаковке — повторно через `resolve`. Каталог — `TemporaryDirectory`. |
| 6 | OK | Поле `targets.COMPONENT_FIELDS["ci_report_artifact"]`. Проверка — непустая строка, отказ называет поле. Умолчание — `CI_REPORT_ARTIFACT_DEFAULT = "junit"`. |
| 7 | OK | `pipeline_status` пишет `id=_check_run_number(r)` у каждого check run. AC-7 зелёный: сверка «одна попытка» срабатывает. |
| 8 | OK | `project_checks.check_ci_report`. Условие строки — `report`, `full_suite ∈ (ci, both)` и `forge.implements(name, "green_base_commit")`, без условия `human`. В окружении роли — `skip`/`ROLE_SKIP`. Литералов хостинга нет: это держит AC-6, тест зелёный. |
| 9 | OK | У `gitlab_adapter` нет `green_base_commit`, строка GitLab не добавляется (AC-6). Рефакторинг `ci.gh` — перенос правила входа один к одному, тексты отказов прежние. |
| 10 | OK | Убраны ровно ключи `job_result`/`job_test_report` в двух файлах (мандат ANSWER-1). Докстринг `test_ac16` по-прежнему перечисляет обе функции — это мелочь, не дефект. |
| 11 | OK | `hosting_registry.py:114` — `[ci]`/`[both]` пропущены по своему `skipif`, файл не правился. Свойство держит AC-9 (`registry_without_report.py`). |

Остальные изменения тестов:
- **`entry_checks.py::test_ac3`.** Подмена `forge.IMPLEMENTATIONS["github"]` через `monkeypatch.setitem` ограничена методом. Утверждение отказа не менялось. Правка в границах мандата ANSWER-3.
- **Сверка с разделом «Изменённые утверждения тестов».** Три строки гейта по `gitlab_forge.py` (`test_ac3_no_token_no_request`, `test_ac13…`, `test_ac18_network_down_reason`) — следствие того же удаления двух ключей из общего словаря `GH_CALLS`. Мандат ANSWER-1 это покрывает: правка словаря и есть разрешённое. Скрытого сужения данных нет: остальные ключи словаря на месте.
- **Тесты задачи.** Заявки «Ловит мутацию» есть у каждого метода и называют наблюдаемое расхождение. Группы планки размечены.

## Замечания

Blocker и major нет. Наблюдения ниже не дефекты и в реестр не заносятся:
- **`forge.py::green_base_commit`.** Задания прогона читаются одной страницей `per_page=100`, без пагинации. У workflow, где больше 100 заданий, задание `ci_job` может не найтись, и строка doctor покажет ложный `warn`. Для артели это не актуально.
- **`forge.py::job_test_report`.** `expired` проверяется после фильтра окна. Если в окне есть два артефакта, просроченный и свежий, вызов откажет причиной «больше одного», а не возьмёт свежий. Сценарий почти невозможен: имя одно, попытка одна.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Реестр пуст: замечаний уровня blocker/major/minor к исправлению нет.

## Вердикт
approved

## Проверено исполнением
- `python3 …/artel.py plank-run 01M6TRM6H57TN8V14HGFV0NQXJ` — 6 passed, код выхода pytest 0.
- `python3 -m pytest -p no:cacheprovider -q -rs` по `tests/test_01m6trm6h57tn8v14hgfv0nqxj_github_ci_report.py`, `tests/test_01m6trm6h57tn8v14hgfv0nqxj_registry_without_report.py`, `tests/test_01m6m1799ycy5hxmhhd71shjet_github_mr_units.py`, `tests/test_01m5wcxbm7wcmrwcbwnchmar3t_gitlab_forge.py`, `tests/test_01m6n7cykdamakenx60cbk7vqx_entry_checks.py`, `tests/test_01m6ezxvfgxc6wbda9qjesazrw_hosting_registry.py`, `tests/test_01m5wcxbm7wcmrwcbwnchmar3t_forge_guards.py`, `tests/test_01m5xzskk8gzteca2kwafhe029_component_fields.py` — 384 passed, 2 skipped. Пропущены ровно `hosting_registry.py:114` `[ci]`/`[both]` («в реестре forge нет хостинга без job_test_report»), как требует ANSWER-2.
- CI коммита d818f5f2 по пакету зелёный (16 проверок).
- Временную мутацию (`Job.id=None`, `_unsafe_member → False`) запустить не удалось: команду правки с восстановлением отклонил режим прав. Поэтому чувствительность проверена чтением кода. Без `Job.id` номера до и после чтения оба равны None, и сверка `ci.job_full_suite` не срабатывает — AC-7 покраснел бы. Проверка путей дублируется `resolve`-сверкой при распаковке, так что мутация одной из двух проверок AC-3 не краснит. Это наблюдение о заявке, защита при этом сохраняется.

## Предложения системе
- Приём «временная мутация» из review-checklist требует правки кода и восстановления. В шаге ревью составная команда `cp`+правка+восстановление уходит на подтверждение, которого никто не даст. Полезна команда пульта `mutate-run <id> <файл> <замена> <тесты>` с автоматическим восстановлением.
