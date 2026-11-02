---
task: 01M6EZXVFGH5Z2876XWMQG35FP
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/doctor/project_checks.py, orchestrator/artel.py, orchestrator/forge.py, orchestrator/gitlab_adapter.py, tests/
budget_usd: 40
---

# SPEC: GitLab Б2.3-3: строки doctor проекта и forge-probe по ветке или коммиту

## Контекст
Часть 3 из 4 деления задачи 01M6EXF3TMNRKCZH8CS9BXXG1Z (GitLab Б2.3);
основание — ADR-0029 п. 8 и ANSWER-1 п. 5 той задачи (находки `doctor` по
локальному стенду GitLab, 02.11). Строки `doctor` по записи проекта
(`orchestrator/doctor/project_checks.py::project_entry_checks`, `:34-58`)
написаны под GitHub: для записи `forge: gitlab` строка защит идёт в
`gh api` и даёт skip «gh: Bad credentials (HTTP 401)», строка прав токена
на CI проверяет GitHub Actions и даёт FAIL «запуски Actions недоступны»,
строка триггера CI ищет `pull_request` в `.github/workflows`, строка
токена сверяет его с `gh auth token` Оператора. Строк, нужных проекту с
`target-human` (роль токена для защит, правила `workflow`, файл CI в
`no_paths`, перезапуски в `ci_job`, подмодули), нет. Отказ правами и
временный отказ хостинга различимы только по тексту `reason`: у
`PipelineStatus`, `Protections`, `BranchPipeline` (`orchestrator/forge.py:42-49`,
`:99-103`, `:113-119`) кода ответа нет, а адаптер теряет `Reply.status`
в `_read_all` (`orchestrator/gitlab_adapter.py:282-308`). `forge-probe`
читает только последний конвейер базы (`orchestrator/artel.py:2436`).

Обозначения ниже: «запись GitLab» — запись, у которой
`forge.ci_by_pipeline(<имя>)` истинно (сегодня это `forge: gitlab`,
`orchestrator/gitlab_adapter.py:44`); «запись с `target-human`» — запись,
у которой `targets.merged_by_project_people(entry)` истинно
(`orchestrator/targets.py:566-570`, единственное место сравнения
`merge_gate` с литералом); «файл CI» — `.gitlab-ci.yml` в корне клона
проекта (имя задаёт ТЗ, п. 2); «права» — код ответа 401, 403 или 404 (тот
же набор, что `_GhProbe.denied` для GitHub, `project_checks.py:269-272`),
«временный отказ» — любой иной исход без ответа (код иной либо его нет).

## Требования

1. **Выбор проверки.** Строки `project-base-protection-<имя>`,
   `project-ci-token-<имя>`, `project-ci-pull-request-<имя>`,
   `project-token-<имя>` выбирают путь GitLab по `forge.ci_by_pipeline(<имя>)`;
   новые строки требований 8–10 — по
   `targets.merged_by_project_people(entry)` (через фасад `doctor`). Иных
   способов выбора нет: `hasattr(<реализация>, "pipeline_status")` хостинги
   не различает (`_GitHub.pipeline_status`, `orchestrator/forge.py:132`).
   Сравнение значения хостинга или `merge_gate` с литералом в
   `orchestrator/doctor/project_checks.py` (в том числе
   `forge.hosting(...) == "gitlab"`, `entry.get("forge") == …`, сравнение
   реализации из `forge.IMPLEMENTATIONS` с `gitlab_adapter`/`_GitHub`)
   запрещено; новые исключения `EXEMPT` сторожа ac9
   (`tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:416-421`)
   не добавляются.
2. **Без `gh` для GitLab.** Для записи GitLab ни одна строка `doctor` по
   записи проекта (`project-*-<имя>`, включая `project-token-<имя>`) не
   вызывает `gh` (ни `gh api`, ни `gh auth token`, ни `doctor.gh_env`).
3. **`project-base-protection-<имя>` для записи GitLab** читает
   `forge.project_info(<имя>)` и `forge.protections(<имя>)`:
   - `project_info` с непустым `reason` или `access_level` `None` — `skip`
     с этой причиной (строка информационная, как сейчас 5.4: данных нет —
     не `fail`);
   - `access_level` ниже 40 (Maintainer) — `skip`, в тексте «нужна роль
     Maintainer» (API при такой роли отдаёт защиты неполно);
   - `access_level` 40 и выше, `protections` без `reason` — `ok`, в тексте
     имена защищённых веток и тегов из `Protections.branches`/`.tags`;
   - `access_level` 40 и выше, у `protections` непустой `reason` — `skip`
     с этой причиной.
4. **Поле кода ответа.** У `forge.Protections`, `forge.PipelineStatus`,
   `forge.BranchPipeline` (`orchestrator/forge.py`) появляется поле
   `http_status: int | None = None` — код HTTP-ответа хостинга, на котором
   функция отказала (ответ не 2xx); `None` — ответ получен либо отказ без
   HTTP-ответа (до запроса, сеть, таймаут, неполная выдача, неразобранное
   тело). `orchestrator/gitlab_adapter.py` заполняет поле из
   `Reply.status` (`gitlab_adapter.py:76-87`, `:261-263`), а не разбором
   текста `reason`, во всех путях `protections`, `pipeline_status`,
   `branch_pipeline`, включая отказ чтения заданий конвейера
   (`_pipeline_findings`, `:376-395`). Проведение кода от `request` до
   результата (смена сигнатуры/возврата внутренних помощников `_read_all`,
   `_pipeline_findings` и т. п.) — часть заполнения поля. Прочее поведение
   этих двух файлов (тексты `reason`, итоги, разрешённые пары, прочие
   функции и их результаты) не меняется.
5. **`project-ci-token-<имя>` для записи GitLab** читает
   `forge.branch_pipeline(<имя>, <base записи>)`, а не GitHub Actions:
   - `http_status` — права: `fail` с текстом «статус CI проекта пульт не
     увидит» (как сейчас для Actions, `project_checks.py:341-345`);
   - `reason` пуст, либо `http_status` `None` и `verdict` не `unknown`
     (в том числе `none` — «у ветки нет конвейеров»): `ok`;
   - иначе (временный отказ, в том числе `http_status` `None` при
     `verdict` `unknown`): `skip` с причиной.
   Различение — только по `http_status`/`verdict`, не по тексту `reason`.
6. **`project-ci-pull-request-<имя>` для записи GitLab** вместо поиска
   `pull_request` в `.github/workflows` сверяет шаблон ветки задачи
   (`entry.get("branch_template")` либо `targets.DEFAULT_BRANCH_TEMPLATE`,
   `orchestrator/targets.py:364`) с правилами `workflow:rules` файла CI.
   Ветка по шаблону — имя, в котором подстановки `{id}` (в нижнем
   регистре, как `catalog.branch_name`), `{slug}`, `{ref}` заменены
   образцовыми значениями (выбирает разработчик). Оценка — по правилам
   GitLab для конвейера отправки ветки:
   - переменные `$CI_COMMIT_BRANCH` и `$CI_COMMIT_REF_NAME` — имя ветки,
     `$CI_PIPELINE_SOURCE` — `"push"`, `$CI_DEFAULT_BRANCH` — `base` записи;
     прочие переменные не определены;
   - правила нумеруются с 1 в порядке файла; первое правило, чьё `if`
     истинно (правило без `if` — истинно), решает: `when: never` — ветка
     не под конвейером, иное — под конвейером; ни одно не сработало — не
     под конвейером;
   - ветка не под конвейером — `warn`; в тексте сработавшее правило с
     `when: never` (номер и выражение `if`) либо, если не сработало ни
     одно, все правила (номер и выражение `if` каждого);
   - ветка под конвейером — `ok`, в тексте номер сработавшего правила;
   - ключа `workflow:rules` нет: при ключе `include:` в файле — `skip`
     «workflow может прийти из include — не проверено», без него — `ok`
     (GitLab создаёт конвейер любой ветки);
   - выражение `if` вне поддержанного вида (переменная, строка в
     кавычках, регулярное выражение `/…/`, операторы `==`, `!=`, `=~`,
     `!~`, `&&`, `||`, скобки) или у правила ключи `changes`/`exists` до
     решения — `skip`, в тексте номер правила и причина;
   - клона нет — `warn` (как сейчас 5.3); файла CI нет — `warn` «файла
     .gitlab-ci.yml нет — конвейер ветки не создаётся»; файл не разобран —
     `skip` с причиной.
7. **`project-token-<имя>` для записи GitLab:** проверка слота прежняя
   (`warn` без `token_slot`, `fail` при пустом слоте); при заполненном
   слоте — `ok`, текст прямо называет, что сверка с токеном `gh`
   Оператора не делалась; `gh auth token` не вызывается.
8. **Новая строка `project-ci-file-no-paths-<имя>`** — у записи с
   `target-human`, в `components:` которой есть компонент с `full_suite`
   `ci` или `both`: файл CI покрыт `no_paths` записи (путь целиком или
   маской, `project_profile.mask_matches`) — `ok`, иначе `fail`. У прочих
   записей строки нет. Место — `project_entry_checks`, после прежних строк.
9. **Новая строка `project-ci-reruns-<имя>-<компонент>`** — у записи с
   `target-human` на каждый компонент с `full_suite` `ci`/`both`
   (`component_checks`): в задании `ci_job` компонента в файле CI нет
   перезапуска упавших тестов — `ok`, иначе `warn` со ссылкой на
   инвариант 41 (отчёт хостинга повторов не видит) и названной находкой.
   Перезапуск — любое из:
   - ключ `retry` задания (кроме `0`), в том числе унаследованный из
     `default:` или по `extends:` в пределах файла;
   - в `script`/`before_script`/`after_script` задания либо в значениях
     `variables` задания и верхнего уровня — аргумент из
     `targets.RERUN_FLAGS`, `-p` с плагином из `targets.RERUN_PLUGINS`
     (тот же перечень, что у `targets._rerun_argument`,
     `orchestrator/targets.py:1106-1121`) или установка
     `pytest-rerunfailures`.
   `retry` у другого задания, не `ci_job`, — не находка. Файла CI нет, он
   не разобран или задания `ci_job` в нём нет — `skip` с причиной. У
   прочих записей строки нет.
10. **Новая строка `project-submodules-<имя>`** — у записи с
    `target-human`. Подмодули — записи `.gitmodules` клона, адрес которых
    на том же хосте, что `url` записи (относительный адрес `../…`
    разрешается от `url` записи и тоже на том же хосте). Проба каждого —
    `doctor.gitcmd.in_repo(<клон>, "ls-remote", <адрес>)`: вызов с `-C
    <клон>` идёт с токеном слота записи (`gitcmd._hosting_project`,
    `orchestrator/gitcmd.py:98-122`, `:1005-1011`). Все пробы с кодом 0 —
    `ok` с перечнем; хоть одна иначе — `fail`, в тексте путь подмодуля,
    адрес и причина (stderr git). Подмодулей на том же хосте нет — `ok`
    с этим текстом; клона нет — `skip`. В процессе роли — `skip`
    `ROLE_SKIP` без пробы (как 5.1/5.2/5.5, `project_checks.py:46-55`).
    Место — `project_entry_checks`, после прежних строк. У прочих записей
    строки нет.
11. Строки требований 3, 5–10 — только чтение: ни записи в хостинг, ни
    правки клона.
12. **`forge-probe <проект> --ref <ветка> | --sha <sha>`.** `--ref` —
    строка конвейера печатается по `forge.branch_pipeline(<проект>,
    <ветка>)` вместо `base`; `--sha` — по `forge.pipeline_status(<проект>,
    <sha>)` (sha, итог, причина, задания). С `--job` отчёт тестов читается
    у этого конвейера. `--ref` и `--sha` вместе — отказ с подсказкой
    использования. Прочий вывод команды прежний; без флагов — прежнее
    поведение.
13. Строки артели и записей `forge: github` с `merge_gate: operator` (в
    том числе без `token_slot`) остаются прежними: тот же набор имён,
    статусов и текстов.

## Критерии приёмки

AC-1. Запись GitLab на подменённом `forge`: `project_info` даёт
`access_level` 30 — `project-base-protection-<имя>` `skip`, в тексте
«нужна роль Maintainer»; `project_info` с непустым `reason` — `skip`
с этим `reason` (не `fail`).

AC-2. Та же запись, `access_level` 40, `protections` с ветками
`["main", "release/*"]` и тегом `["v*"]`: строка — `ok`, в тексте `main`,
`release/*`, `v*`, и не «нужна роль Maintainer» (ловит `<=` вместо `<` и
строку, не читающую защиты).

AC-3. Запись GitLab, файл CI с `workflow:rules` из одного правила
`if: $CI_COMMIT_BRANCH =~ /^feature\//`, шаблон ветки по умолчанию
(`task/{id}-{slug}`): `project-ci-pull-request-<имя>` — `warn`, в тексте
`1` и выражение `$CI_COMMIT_BRANCH =~ /^feature\//`. Тот же файл,
`branch_template: feature/{id}` — `ok`.

AC-4. Запись GitLab, правила: 1) `if: $CI_COMMIT_BRANCH =~ /^task\//`,
`when: never`; 2) `if: $CI_COMMIT_BRANCH`. Шаблон по умолчанию: строка —
`warn`, в тексте номер `1` и его `if`. Файл CI без ключа `workflow` и без
`include` — `ok`.

AC-5. Запись с `target-human` и компонентом `full_suite: ci`:
`no_paths` без файла CI — `project-ci-file-no-paths-<имя>` `fail`;
`no_paths` с `.gitlab-ci.yml` — `ok`.

AC-6. Та же запись, `ci_job: tests`: в `script` задания `tests` есть
`pytest --reruns 2` — `project-ci-reruns-<имя>-<компонент>` `warn`; у
задания `tests` `retry: 2` — `warn`; `retry: 2` только у другого задания,
у `tests` перезапусков нет — `ok`.

AC-7. Запись с `target-human`, в `.gitmodules` клона подмодуль на том же
хосте; подменённый `gitcmd.in_repo` на `ls-remote` этого адреса отвечает
кодом 128 и stderr `"fatal: Authentication failed"` —
`project-submodules-<имя>` `fail`, в тексте адрес и `Authentication
failed`; код 0 — `ok`. В процессе роли — `skip`, проба `ls-remote` не
запускается.

AC-8. Запись GitLab с `merge_gate: operator`, компонентом
`full_suite: ci` и подмодулем в `.gitmodules`: строк
`project-ci-file-no-paths-<имя>`, `project-ci-reruns-<имя>-*`,
`project-submodules-<имя>` в выводе нет; у той же записи с
`merge_gate: target-human` — все три есть.

AC-9. Запись GitLab на подменённом `forge`: ни одна строка
`project-*-<имя>` (включая `project-token-<имя>`) не вызывает `gh`
(подменённый запуск `gh` — `subprocess.run` с `gh` первым аргументом —
ни разу не происходит).

AC-10. Запись GitLab на подменённом `forge` с данными GitLab
(`access_level` 40, защиты, `branch_pipeline` базы с `verdict` `green`,
файл CI с правилом, под которое ветка по шаблону попадает, заполненный
слот): строки `project-base-protection`, `project-ci-token`,
`project-ci-pull-request`, `project-token` — `ok`; ни одна не несёт
«gh:», «Bad credentials», «Actions», «pull_request».

AC-11. Запись GitLab, подменённый `forge.branch_pipeline` даёт
`BranchPipeline(reason="отказ", http_status=403)` —
`project-ci-token-<имя>` `fail`, в тексте «статус CI проекта пульт не
увидит»; тот же `reason="отказ"` с `http_status=503` и с `http_status=None`
— `skip`.

AC-12. `gitlab_adapter` на подменённом `transport` (`gitlab_adapter.py:90`):
ответ 403 на `GET /projects/:id/pipelines` — `forge.branch_pipeline` и
`forge.pipeline_status` дают `http_status` 403; ответ 200 на конвейеры и
403 на `GET /projects/:id/pipelines/:n/jobs` — `branch_pipeline` даёт
`http_status` 403; 403 на `GET /projects/:id/protected_tags` —
`forge.protections` даёт `http_status` 403; `transport` бросает
`TimeoutError` — `http_status` `None`; при всех этих ответах тексты
`reason` прежние.

AC-13. Запись GitLab, `project-token-<имя>`: без `token_slot` — `warn`,
при пустом слоте — `fail`, при заполненном — `ok`, текст называет, что
сверка с токеном `gh` Оператора не делалась.

AC-14. `forge-probe <проект> --ref feat` на подменённом `forge` печатает
sha, итог и задания `branch_pipeline(<проект>, "feat")`, а не базы;
`forge-probe <проект> --sha <sha>` — sha, итог и задания
`pipeline_status(<проект>, <sha>)`; `--ref` и `--sha` вместе — ненулевой
код и подсказка использования; без флагов вывод прежний.

AC-15. Артель и запись `forge: github` с `merge_gate: operator` (с
`token_slot` и без): строки `doctor` по записи проекта — те же имена,
статусы и тексты, что на main; тест ac9 и его `EXEMPT` не изменены.
Новый AST-сторож по `orchestrator/doctor/project_checks.py`: в нём нет
сравнения (`==`, `!=`, `in`, `not in`, `is`, `is not`), один из операндов
которого — строковый литерал (или кортеж/список/множество литералов),
содержащий `github`, `gitlab`, `operator` или `target-human`, либо имя/
атрибут `gitlab_adapter`/`_GitHub`; сторож краснеет на вставке
`forge.hosting(name) == "gitlab"`.

## Оценка объёма и деление
Сработавшие сигналы: число критериев приёмки 15 ≥ 10; `budget_usd` $40 ≥
$30; зона — 4 файла кода и общий `tests/`; механизм рядом с инвариантом
41 (`docs/invariants.md`) — строка требования 9 только читает файл CI и
инвариант не меняет.

Обоснование монолита (материал для решения Оператора): задача уже —
часть 3 из 4 деления 01M6EXF3TMNRKCZH8CS9BXXG1Z с рамкой $40. Почти все
критерии (AC-1…AC-11, AC-13, AC-15) живут в одном файле
`orchestrator/doctor/project_checks.py` и одной развилке выбора проверки
(требование 1) — деление по ним режет эту зону поперёк. Поле кода ответа
(требование 4, AC-12) нужно AC-11 в той же развилке: без него строка
`project-ci-token` различала бы отказы по тексту, что ТЗ запрещает.
Отделима только `forge-probe --ref|--sha` (AC-14, `orchestrator/artel.py`)
— одна небольшая правка; отдельная задача по ней стоила бы дороже
экономии. Бюджет — рамка деления $40 (по таблице калибровки класс «до 15
критериев» даёт ~45, вниз — до рамки).

## Не входит
- Хук pre-push, его строка `doctor`, клон подмодулей и сверки отправки —
  часть 2 деления.
- Открытие `gitlab`/`target-human` — часть 4 деления.
- Правки `orchestrator/doctor/misc_checks.py` (только чтение) и
  `orchestrator/doctor/__init__.py` (нужные коллаборанты — `forge`,
  `targets`, `gitcmd`, `project_profile` — фасад уже несёт).
- Правки `orchestrator/forge.py` и `orchestrator/gitlab_adapter.py` сверх
  поля кода ответа и проведения кода до него (требование 4); новая
  функция интерфейса `forge` (проба подмодулей — через `gitcmd`).
- Поле записи, называющее файл конвейера (ADR-0029 п. 6 «если запись
  называет файл конвейера»): ТЗ задаёт `.gitlab-ci.yml`; файлы из
  `include:` не читаются.
- Оценка конвейеров событий MR (`merge_request_event`) в строке
  требования 6 — только конвейер отправки ветки.
- Новые строки требований 8–10 у записей без `target-human`, сверка
  токена `gitlab` с пользователем Оператора (ТЗ её не просит).
- Изменение теста ac9 и его `EXEMPT`.
- Полный зелёный набор `tests/` и неизменность существующих тестов — её
  держит пульт.

## Материалы
- ТЗ: `tasks/01M6EZXVFGH5Z2876XWMQG35FP/TZ.md`; родитель
  01M6EXF3TMNRKCZH8CS9BXXG1Z, ANSWER-1 п. 5; аудит
  `tasks/01M6EZXVFGH5Z2876XWMQG35FP/SPEC-AUDIT.md` (возврат 1).
- ADR-0029 п. 6, 8, 13; `docs/invariants.md`, инвариант 41.
- Код: `orchestrator/doctor/project_checks.py:34-58, 138, 176, 225,
  254-272, 300, 341-345, 359, 400`; `orchestrator/forge.py:42-49, 99-119,
  132, 163, 193-197`; `orchestrator/gitlab_adapter.py:76-119, 197-269,
  282-308, 376-395, 580-626`; `orchestrator/artel.py:2371-2452`
  (`forge-probe`); `orchestrator/targets.py:364, 566-570, 1079-1121`;
  `orchestrator/gitcmd.py:41, 98-146, 1221-1250`; сторож ac9 —
  `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:409-469`.
