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
локальному стенду GitLab, 02.11). Сейчас строки `doctor` по записи
проекта (`orchestrator/doctor/project_checks.py::project_entry_checks`,
`:34-58`) написаны под GitHub: для записи `forge: gitlab` строка защит
идёт в `gh api` и даёт skip «gh: Bad credentials (HTTP 401)», строка прав
токена на CI проверяет GitHub Actions и даёт FAIL «запуски Actions
недоступны», строка триггера CI ищет `pull_request` в `.github/workflows`,
строка токена сверяет его с `gh auth token` Оператора. Строк, нужных
GitLab-проекту (роль токена для защит, правила `workflow`, файл CI в
`no_paths`, перезапуски в `ci_job`, подмодули), нет. Различить отказ
правами и временный отказ хостинга сейчас можно только по тексту
`reason` (`orchestrator/forge.py:42-49`, `:99-103`, `:113-119`;
`orchestrator/gitlab_adapter.py:202-203`). `forge-probe` читает только
последний конвейер базы.

## Требования

1. Строки `doctor` по записи проекта выбирают проверку по `forge` записи
   через реестр `forge` — наличие функции у реализации
   (`forge.IMPLEMENTATIONS`) и `forge.ci_by_pipeline`, как
   `misc_checks.check_base_branch` (`orchestrator/doctor/misc_checks.py:91-140`).
   Сравнение значения хостинга с литералом (в том числе
   `forge.hosting(...) == "gitlab"`, `entry.get("forge") == …`) запрещено;
   новые исключения `EXEMPT` сторожа ac9
   (`tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:416-421`)
   не добавляются.
2. Для записи `forge: gitlab` ни одна строка `doctor` по записи проекта
   (`project-*-<имя>`, включая `project-token-<имя>`) не вызывает `gh`
   (ни `gh api`, ни `gh auth token`); GitHub-проверки к ней не
   применяются.
3. `project-base-protection-<имя>` для `gitlab` читает защиты через
   `forge.protections` (API GitLab). Если уровень доступа токена
   (`forge.project_info(...).access_level`) ниже Maintainer (40), и API
   поэтому отдаёт неполные сведения, — строка `skip` с текстом «нужна роль
   Maintainer», а не `fail`. Уровень 40 и выше даёт обычную строку защит
   (не этот `skip`).
4. В результат `forge` добавляется поле кода ответа хостинга (например
   `status`/`kind`) у типов `Protections`, `PipelineStatus`,
   `BranchPipeline` (`orchestrator/forge.py`); его заполняет
   `orchestrator/gitlab_adapter.py`. Отказ правами и временный отказ
   строки `doctor` различают по этому полю, а не по разбору текста
   `reason`. Иных правок `orchestrator/forge.py` и
   `orchestrator/gitlab_adapter.py` нет.
5. `project-ci-token-<имя>` для `gitlab` проверяет доступ токена к
   конвейерам через `forge.pipeline_status`/`forge.branch_pipeline`, а не
   через GitHub Actions. Конвейеры недоступны токену по правам (по полю
   требования 4) — `fail` с текстом «статус CI проекта пульт не увидит»
   (как сейчас для Actions, `project_checks.py:341-345`); временный отказ —
   `skip`.
6. `project-ci-pull-request-<имя>` для `gitlab` заменяется проверкой шаблона
   ветки задачи против правил `workflow:rules` файла конфигурации CI
   проекта (`.gitlab-ci.yml`), а не поиском `pull_request` в
   `.github/workflows`. Ветка по шаблону не попадает под конвейер — `warn`,
   в тексте которого правило названо номером и выражением `if` (правила
   `workflow:rules` GitLab безымянны).
7. `project-token-<имя>` для `gitlab`: проверка слота остаётся прежней
   (`warn` без `token_slot`, `fail` при пустом слоте); сверка с токеном
   `gh` Оператора не выполняется, и текст строки прямо называет, что она
   не делалась.
8. Новая строка `doctor` (только чтение): у записи с компонентом
   `full_suite: ci|both` файл конфигурации CI проекта должен быть в
   `no_paths` записи, иначе `fail`.
9. Новая строка `doctor` (только чтение): в задании `ci_job` компонента нет
   перезапуска упавших тестов (`pytest-rerunfailures`/`--reruns`, `retry`
   задания), иначе `warn` (инвариант 41: отчёт хостинга повторов не
   видит).
10. Новая строка `doctor` (только чтение): подмодули проекта на том же
    хостинге — адрес подмодуля доступен по тому же слоту токена — `ok`,
    иначе `fail` с причиной.
11. Все строки требований 3, 5–10 — только чтение (ни записи в хостинг,
    ни правки клона).
12. `forge-probe <проект> --ref <ветка> | --sha <sha>` выводит сведения
    конвейера названной ветки или коммита вместо последнего конвейера
    базы; прочий вывод команды прежний. Без флагов — прежнее поведение.
13. Строки артели и проектов `forge: github` (в том числе без `token_slot`,
    с авторизацией `operator`) остаются прежними.

## Критерии приёмки

AC-1. Запись `forge: gitlab` на подменённом `forge`, `project_info`
даёт `access_level` 30 (Developer): строка
`project-base-protection-<имя>` — `skip`, в тексте «нужна роль
Maintainer».

AC-2. Та же запись, `access_level` 40 (Maintainer): строка
`project-base-protection-<имя>` — не `skip` «нужна роль Maintainer»
(ловит `<=` вместо `<`).

AC-3. Запись `forge: gitlab`, `.gitlab-ci.yml` клона с `workflow:rules`,
под которые ветка по шаблону ветки задачи не попадает: строка
`project-ci-pull-request-<имя>` — `warn`, в тексте номер правила и его
выражение `if`.

AC-4. Запись с компонентом `full_suite: ci`, файл конфигурации CI не в
`no_paths`: строка требования 8 — `fail`.

AC-5. `ci_job` компонента, в задании которого `--reruns`: строка
требования 9 — `warn`; задание с `retry:` — та же строка `warn`.

AC-6. Подмодуль на том же хостинге, недоступный по слоту токена записи:
строка требования 10 — `fail`, в тексте причина.

AC-7. Запись `forge: gitlab` на подменённом `forge`: ни одна строка
`project-*-<имя>` (включая `project-token-<имя>`) не вызывает `gh`
(подменённый вызов `gh` ни разу не запускается).

AC-8. Запись `forge: gitlab` на подменённом `forge` с данными GitLab
(защиты, конвейеры, `.gitlab-ci.yml`): строки `project-base-protection`,
`project-ci-token`, `project-ci-pull-request`, `project-token`
дают `ok`/`warn`/`skip` по этим данным, а не GitHub-отказы
(«gh: Bad credentials», «запуски Actions недоступны»).

AC-9. Запись `forge: gitlab`, подменённый `forge` возвращает отказ
конвейеров по правам (поле кода ответа требования 4):
`project-ci-token-<имя>` — `fail` с текстом «статус CI проекта пульт не
увидит»; тот же `reason`, но поле — временный отказ: `skip`. Подмена
несёт одинаковый текст `reason` в обоих случаях — различение по тексту
этот критерий краснит.

AC-10. Запись `forge: gitlab`, `project-token-<имя>`: без `token_slot` —
`warn`, при пустом слоте — `fail`, при заполненном — текст строки прямо
называет, что сверка с токеном `gh` Оператора не делалась.

AC-11. `forge-probe <проект> --ref <ветка>` на подменённом `forge`
выводит конвейер названной ветки (её sha/итог/задания), а не последний
конвейер базы; `forge-probe <проект> --sha <sha>` — конвейер названного
коммита.

AC-12. Артель и записи `forge: github` (включая авторизацию `operator`):
строки `doctor` по записи проекта прежние; тест ac9
(`tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py`) и его
`EXEMPT` не изменены, в коде выбора проверки нет сравнения значения
хостинга с литералом.

## Оценка объёма и деление
Сработавший сигнал: число критериев приёмки 12 ≥ `SPLIT_SIGNAL_AC_COUNT`
(10). Зона — 4 файла кода (+ общая `tests/`), бюджет $40 — ниже порогов.

Обоснование монолита (материал для решения Оператора): задача уже
является частью 3 из 4 деления 01M6EXF3TMNRKCZH8CS9BXXG1Z с рамкой $40.
Почти все критерии (AC-1…AC-10, AC-12) живут в одном файле
`orchestrator/doctor/project_checks.py` и одной развилке выбора проверки
по реестру `forge` (требование 1) — деление по ним режет эту зону
поперёк. Поле кода ответа (требование 4) нужно AC-9 и AC-1 в той же
развилке. Отделима только `forge-probe --ref|--sha` (AC-11,
`orchestrator/artel.py`) — одна небольшая правка, отдельная задача по ней
стоила бы дороже экономии.

## Не входит
- Хук pre-push, его строка `doctor`, клон подмодулей и сверки отправки —
  часть 2 деления.
- Открытие `gitlab`/`target-human` — часть 4 деления.
- Правки `orchestrator/doctor/misc_checks.py` (только чтение).
- Правки `orchestrator/forge.py` и `orchestrator/gitlab_adapter.py` сверх
  поля кода ответа (требование 4).
- Изменение теста ac9 и его `EXEMPT`.
- Полный зелёный набор `tests/` и неизменность существующих тестов —
  её держит пульт.

## Материалы
- ТЗ: `tasks/01M6EZXVFGH5Z2876XWMQG35FP/TZ.md`; родитель
  01M6EXF3TMNRKCZH8CS9BXXG1Z, ANSWER-1 п. 5.
- ADR-0029 п. 8; `docs/invariants.md`, инвариант 41.
- Код: `orchestrator/doctor/project_checks.py:34-58, 138, 176, 225, 300,
  341-345, 359`; `orchestrator/forge.py:42-49, 99-119, 193-197`;
  `orchestrator/gitlab_adapter.py:197-210`; `orchestrator/artel.py:2371-2444`
  (`forge-probe`); `orchestrator/catalog.py::branch_template`;
  `orchestrator/targets.py:1081-1101` (`full_suite`/`ci_job`).
