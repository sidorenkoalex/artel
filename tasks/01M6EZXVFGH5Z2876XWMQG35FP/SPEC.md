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
`PipelineStatus`, `Protections`, `BranchPipeline` (`orchestrator/forge.py:42-50`,
`:99-103`, `:113-119`) кода ответа нет, а адаптер теряет `Reply.status`
в `_read_all` (`orchestrator/gitlab_adapter.py:282-308`). `forge-probe`
читает только последний конвейер базы (`orchestrator/artel.py:2436`).
Разборщика `.gitlab-ci.yml` в пульте нет: общий `orchestrator/yamlmini.py`
блочных списков не разбирает (`yamlmini.py:1-24`).

Обозначения ниже: «запись GitLab» — запись, у которой
`forge.ci_by_pipeline(<имя>)` истинно (сегодня это `forge: gitlab`,
`orchestrator/gitlab_adapter.py:44`); «запись с `target-human`» — запись,
у которой `targets.merged_by_project_people(entry)` истинно
(`orchestrator/targets.py:566-570`); «файл CI» — `.gitlab-ci.yml` в корне
клона проекта (имя задаёт ТЗ, п. 2); «права» — код ответа 401, 403 или 404
(тот же набор, что `_GhProbe.denied` для GitHub, `project_checks.py:269-272`),
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
   вызывает `gh` (ни `gh api`, ни `gh auth token`, ни `ci.gh`, ни
   `doctor.gh_env`) — в том числе когда `gh` установлен
   (`shutil.which("gh")` даёт путь).
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
   тело). `orchestrator/gitlab_adapter.py` заполняет поле только из
   `Reply.status` (`gitlab_adapter.py:76-87`, `:261-263`), никогда не
   разбором текста `reason`: `Reply` без `status` даёт `None`, даже если
   текст причины несёт код. Так — во всех путях `protections`,
   `pipeline_status`, `branch_pipeline`, включая отказ чтения заданий
   конвейера (`_pipeline_findings`, `:376-395`). Проведение кода от
   `request` до результата (смена сигнатуры/возврата внутренних помощников
   `_read_all`, `_pipeline_findings` и т. п.) — часть заполнения поля.
   Прочее поведение этих двух файлов (тексты `reason`, итоги, разрешённые
   пары, прочие функции и их результаты) не меняется.
5. **`project-ci-token-<имя>` для записи GitLab** читает
   `forge.branch_pipeline(<имя>, <base записи>)`, а не GitHub Actions:
   - итог прочитан (`verdict` — `green`, `none`, `red` или `running`) —
     `ok`, в тексте значение `verdict`;
   - итог не прочитан (`verdict` `unknown`) и `http_status` — права:
     `fail` с текстом «статус CI проекта пульт не увидит» (как сейчас для
     Actions, `project_checks.py:341-345`);
   - итог не прочитан и `http_status` иной либо `None` (временный отказ):
     `skip` с причиной.
   Различение — только по `verdict`/`http_status`, не по тексту `reason`.
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
   - правило в тексте строки называется в форме «правило workflow №<n>
     (if: <выражение>)», правило без `if` — «правило workflow №<n>»;
   - ветка не под конвейером — `warn`; в тексте сработавшее правило с
     `when: never` либо, если не сработало ни одно, все правила;
   - ветка под конвейером — `ok`, в тексте сработавшее правило;
   - ключа `workflow:rules` нет: при ключе `include:` в файле — `skip`
     «workflow может прийти из include — не проверено», без него — `ok`
     (GitLab создаёт конвейер любой ветки);
   - выражение `if` вне поддержанного вида (переменная, строка в
     кавычках, регулярное выражение `/…/`, операторы `==`, `!=`, `=~`,
     `!~`, `&&`, `||`, скобки) или у правила ключи `changes`/`exists` до
     решения — `skip`, в тексте правило и причина;
   - клона нет — `warn` (как сейчас 5.3); файла CI нет — `warn` «файла
     .gitlab-ci.yml нет — конвейер ветки не создаётся»; файл не разобран
     (требование 12) — `warn` «.gitlab-ci.yml не разобран: <место>».
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
   Перезапуск — любая из семи форм:
   1) ключ `retry` самого задания (кроме `0`);
   2) `retry` (кроме `0`), унаследованный из `default:`;
   3) `retry` (кроме `0`), унаследованный по `extends:` в пределах файла;
   4) в `script`/`before_script`/`after_script` задания — аргумент из
      `targets.RERUN_FLAGS` (`orchestrator/targets.py:1109`);
   5) в значениях `variables` задания или верхнего уровня — аргумент из
      `targets.RERUN_FLAGS` либо `-p` с плагином из `targets.RERUN_PLUGINS`;
   6) в `script`/`before_script`/`after_script` задания — `-p` с плагином
      из `targets.RERUN_PLUGINS` (тот же перечень, что у
      `targets._rerun_argument`, `orchestrator/targets.py:1114-1124`);
   7) в `script`/`before_script`/`after_script` задания — установка
      `pytest-rerunfailures`.
   `retry` у другого задания, не `ci_job`, — не находка. Файла CI нет или
   задания `ci_job` в нём нет — `skip` с причиной; файл не разобран
   (требование 12) — `warn` «.gitlab-ci.yml не разобран: <место>». У
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
12. **Разбор файла CI.** Файл CI разбирает собственный минимальный
    разборщик в `orchestrator/doctor/project_checks.py`;
    `orchestrator/yamlmini.py` не меняется и для файла CI не
    используется. Разборщик обязан понимать то, что читают требования 6 и
    9: `workflow.rules[]` с ключами `if`, `when`, `changes`, `exists`;
    ключ верхнего уровня `include`; задания — отображения верхнего уровня
    со `script` (а также скрытые `.имя`, на которые ссылается `extends`) с
    ключами `script`, `before_script`, `after_script`, `retry`, `extends`,
    `variables`; `default` и `variables` верхнего уровня. Форма, которую
    разборщик не распознал, — исход «файл не разобран» с местом (номер
    строки файла) в тексте; строка требования 6 или 9 тогда `warn`
    «.gitlab-ci.yml не разобран: <место>», не `ok`.
13. **`forge-probe <проект> --ref <ветка> | --sha <sha>`.** `--ref` —
    строка конвейера печатается по `forge.branch_pipeline(<проект>,
    <ветка>)` вместо `base`; `--sha` — по `forge.pipeline_status(<проект>,
    <sha>)` (sha, итог, причина, задания). С `--job` отчёт тестов читается
    у этого конвейера. `--ref` и `--sha` вместе — отказ с подсказкой
    использования. Прочий вывод команды прежний; без флагов — прежнее
    поведение.
14. **Запись без `token_slot`.** У записи GitLab без `token_slot` строки,
    идущие в хостинг, — `project-base-protection-<имя>`,
    `project-ci-token-<имя>`, а у записи с `target-human` без `token_slot`
    — `project-submodules-<имя>` — дают `skip` «нет token_slot» без
    обращения к хостингу (ни `forge`, ни пробы `ls-remote`), то есть без
    авторизации Оператора. Строка `project-token-<имя>` — по требованию 7.
15. Строки артели и записей `forge: github` с `merge_gate: operator` (в
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
`правило workflow №1 (if: $CI_COMMIT_BRANCH =~ /^feature\//)`. Тот же
файл, `branch_template: feature/{id}` — `ok`, в тексте `правило workflow
№1`.

AC-4. Запись GitLab, правила: 1) `if: $CI_COMMIT_BRANCH =~ /^task\//`,
`when: never`; 2) `if: $CI_COMMIT_BRANCH`. Шаблон по умолчанию: строка —
`warn`, в тексте `правило workflow №1 (if: $CI_COMMIT_BRANCH =~ /^task\//)`
и нет `правило workflow №2`. Файл CI без ключа `workflow` и без
`include` — `ok`. Файл CI с формой вне разборщика (якорь `&x` в строке 3)
— `warn`, в тексте `.gitlab-ci.yml не разобран:` и номер строки `3`.

AC-5. Запись с `target-human` и компонентом `full_suite: ci`:
`no_paths` без файла CI — `project-ci-file-no-paths-<имя>` `fail`;
`no_paths` с `.gitlab-ci.yml` — `ok`.

AC-6. Та же запись, компонент с `ci_job: tests`; строка
`project-ci-reruns-<имя>-<компонент>` на каждом файле CI таблицы:

| Форма (треб. 9) | Файл CI (суть) | Статус |
|---|---|---|
| 1 | `tests: {script: [pytest], retry: 2}` | `warn` |
| 2 | `default: {retry: 1}`, `tests: {script: [pytest]}` | `warn` |
| 3 | `.base: {retry: 2}`, `tests: {extends: .base, script: [pytest]}` | `warn` |
| 4 | `tests: {script: ["pytest --reruns 2"]}` | `warn` |
| 5 | `tests: {variables: {PYTEST_ADDOPTS: "--reruns 3"}, script: [pytest]}` | `warn` |
| 5 | верхний `variables: {PYTEST_ADDOPTS: "-p rerunfailures"}`, `tests: {script: [pytest]}` | `warn` |
| 6 | `tests: {script: ["pytest -p rerunfailures"]}` | `warn` |
| 7 | `tests: {before_script: ["pip install pytest-rerunfailures"], script: [pytest]}` | `warn` |
| — | `tests: {script: [pytest], retry: 0}` | `ok` |
| — | `lint: {script: [ruff], retry: 2}`, `tests: {script: [pytest]}` | `ok` |

Таблица записывается в файл CI блочной формой YAML (списки `- …`), не
потоковой. Каждый `warn` ссылается на инвариант 41.

AC-7. Запись с `target-human` и `token_slot`, в `.gitmodules` клона
подмодуль на том же хосте; подменённый `gitcmd.in_repo` на `ls-remote`
этого адреса отвечает кодом 128 и stderr `"fatal: Authentication
failed"` — `project-submodules-<имя>` `fail`, в тексте адрес и
`Authentication failed`; код 0 — `ok`. В процессе роли — `skip`, проба
`ls-remote` не запускается.

AC-8. Запись GitLab с `merge_gate: operator`, компонентом
`full_suite: ci` и подмодулем в `.gitmodules`: строк
`project-ci-file-no-paths-<имя>`, `project-ci-reruns-<имя>-*`,
`project-submodules-<имя>` в выводе нет; у той же записи с
`merge_gate: target-human` — все три есть.

AC-9. Запись GitLab на подменённом `forge`, `shutil.which("gh")` подменён
и возвращает путь: шпион вызовов `gh` — `doctor.subprocess.run` (и
`subprocess.run`) с `gh` первым аргументом и `ci.gh` — за прогон всех
строк `project-*-<имя>` (включая `project-token-<имя>`) не фиксирует ни
одного вызова.

AC-10. Запись GitLab на подменённом `forge` с данными GitLab
(`access_level` 40, защиты, `branch_pipeline` базы с `verdict` `green`,
файл CI с правилом, под которое ветка по шаблону попадает, заполненный
слот): строки `project-base-protection`, `project-ci-token`,
`project-ci-pull-request`, `project-token` — `ok`; ни одна не несёт
«gh:», «Bad credentials», «Actions», «pull_request».

AC-11. Запись GitLab, подменённый `forge.branch_pipeline`:
`BranchPipeline(reason="отказ", http_status=403)` —
`project-ci-token-<имя>` `fail`, в тексте «статус CI проекта пульт не
увидит»; тот же `reason="отказ"` с `http_status=503` и с `http_status=None`
— `skip`; `BranchPipeline(verdict="none")` — `ok`, в тексте `none`;
`BranchPipeline(verdict="red")` — `ok`, в тексте `red`.

AC-12. `gitlab_adapter` на подменённом `transport` (`gitlab_adapter.py:90`):
ответ 403 на `GET /projects/:id/pipelines` — `forge.branch_pipeline` и
`forge.pipeline_status` дают `http_status` 403; ответ 200 на конвейеры и
403 на `GET /projects/:id/pipelines/:n/jobs` — `branch_pipeline` даёт
`http_status` 403; 403 на `GET /projects/:id/protected_tags` —
`forge.protections` даёт `http_status` 403; `transport` бросает
`TimeoutError` — `http_status` `None`; при всех этих ответах тексты
`reason` прежние. На подменённом `gitlab_adapter.request`:
`Reply(status=403, reason="отказ")` (кода в тексте нет) — `http_status`
403 у `branch_pipeline`, `pipeline_status`, `protections`;
`Reply(status=None, reason="доступ запрещён (403) на GET …")` (код только
в тексте) — `http_status` `None` у тех же трёх.

AC-13. Запись GitLab, `project-token-<имя>`: без `token_slot` — `warn`,
при пустом слоте — `fail`, при заполненном — `ok`, текст называет, что
сверка с токеном `gh` Оператора не делалась. Запись GitLab с
`target-human` без `token_slot`: `project-base-protection-<имя>`,
`project-ci-token-<имя>`, `project-submodules-<имя>` — `skip`, в тексте
`нет token_slot`; шпионы `forge.project_info`, `forge.protections`,
`forge.branch_pipeline` и `gitcmd.in_repo` с `ls-remote` вызовов не
фиксируют.

AC-14. `forge-probe <проект> --ref feat` на подменённом `forge` печатает
sha, итог и задания `branch_pipeline(<проект>, "feat")`, а не базы;
`forge-probe <проект> --sha <sha>` — sha, итог и задания
`pipeline_status(<проект>, <sha>)`; `--ref` и `--sha` вместе — ненулевой
код и подсказка использования; без флагов вывод прежний.

AC-15. Артель и запись `forge: github` с `merge_gate: operator` (с
`token_slot` и без): строки `doctor` по записи проекта — те же имена,
статусы и тексты, что на main; тест ac9 и его `EXEMPT` не изменены.
Выбор проверки без сравнения с литералом хостинга проверяется
поведенчески — шпионом AC-9; статического сторожа по тексту
`project_checks.py` критерий не требует.

## Оценка объёма и деление
Сработавшие сигналы: число критериев приёмки 15 ≥ 10; `budget_usd` $40 ≥
$30; зона — 4 файла кода и общий `tests/`; механизм рядом с инвариантом
41 (`docs/invariants.md`) — строка требования 9 только читает файл CI и
инвариант не меняет.

Обоснование монолита (материал для решения Оператора): задача уже —
часть 3 из 4 деления 01M6EXF3TMNRKCZH8CS9BXXG1Z с рамкой $40. Почти все
критерии (AC-1…AC-11, AC-13, AC-15) живут в одном файле
`orchestrator/doctor/project_checks.py` и одной развилке выбора проверки
(требование 1); там же разборщик файла CI (требование 12), общий для
строк требований 6 и 9 — деление по ним режет эту зону поперёк. Поле
кода ответа (требование 4, AC-12) нужно AC-11 в той же развилке: без
него строка `project-ci-token` различала бы отказы по тексту, что ТЗ
запрещает. Отделима только `forge-probe --ref|--sha` (AC-14,
`orchestrator/artel.py`) — одна небольшая правка; отдельная задача по ней
стоила бы дороже экономии. Бюджет — рамка деления $40 (по таблице
калибровки класс «до 15 критериев» даёт ~45, вниз — до рамки).

## Не входит
- Хук pre-push, его строка `doctor`, клон подмодулей и сверки отправки —
  часть 2 деления.
- Открытие `gitlab`/`target-human` — часть 4 деления.
- Правки `orchestrator/doctor/misc_checks.py` (только чтение),
  `orchestrator/yamlmini.py` (разбор файла CI — свой, требование 12) и
  `orchestrator/doctor/__init__.py` (нужные коллаборанты — `forge`,
  `targets`, `gitcmd`, `project_profile` — фасад уже несёт).
- Правки `orchestrator/forge.py` и `orchestrator/gitlab_adapter.py` сверх
  поля кода ответа и проведения кода до него (требование 4); новая
  функция интерфейса `forge` (проба подмодулей — через `gitcmd`).
- Полный YAML в разборщике файла CI: якоря и ссылки, теги (`!reference`),
  многострочные скаляры, несколько документов — исход «не разобран»
  (требование 12), не их поддержка.
- Поле записи, называющее файл конвейера (ADR-0029 п. 6 «если запись
  называет файл конвейера»): ТЗ задаёт `.gitlab-ci.yml`; файлы из
  `include:` не читаются.
- Оценка конвейеров событий MR (`merge_request_event`) в строке
  требования 6 — только конвейер отправки ветки.
- Новые строки требований 8–10 у записей без `target-human`, сверка
  токена `gitlab` с пользователем Оператора (ТЗ её не просит).
- Статический сторож по тексту `project_checks.py` на сравнение с
  литералом хостинга (решение Оператора на гейте SPEC: свойство держит
  шпион AC-9).
- Изменение теста ac9 и его `EXEMPT`.
- Полный зелёный набор `tests/` и неизменность существующих тестов — её
  держит пульт.

## Материалы
- ТЗ: `tasks/01M6EZXVFGH5Z2876XWMQG35FP/TZ.md`; родитель
  01M6EXF3TMNRKCZH8CS9BXXG1Z, ANSWER-1 п. 5; аудит
  `tasks/01M6EZXVFGH5Z2876XWMQG35FP/SPEC-AUDIT.md` (аудит 2) и решения
  Оператора по нему (возврат со spec_gate, пп. 1–9).
- ADR-0029 п. 6, 8, 13; `docs/invariants.md`, инвариант 41.
- Код: `orchestrator/doctor/project_checks.py:34-58, 138, 176-216, 225,
  254-296, 300-345, 359, 400`; `orchestrator/forge.py:42-50, 99-119,
  132, 163, 193-197`; `orchestrator/gitlab_adapter.py:76-119, 197-269,
  282-308, 376-395, 580-626`; `orchestrator/artel.py:2371-2457`
  (`forge-probe`); `orchestrator/targets.py:364, 560-570, 1109-1124`;
  `orchestrator/gitcmd.py:41, 98-146, 1221-1250`; `orchestrator/yamlmini.py:1-24`;
  сторож ac9 —
  `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:409-471`.
