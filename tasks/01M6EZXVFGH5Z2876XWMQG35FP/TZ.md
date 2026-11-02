---
task: 01M6EZXVFGH5Z2876XWMQG35FP
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: GitLab Б2.3-3: строки doctor проекта и forge-probe по ветке или коммиту

Родительская задача: 01M6EXF3TMNRKCZH8CS9BXXG1Z — GitLab Б2.3: хук pre-push в клоне, сверки отправки, строки doctor, отказ при сбое, открытие gitlab и target-human
Зоны: orchestrator/doctor/project_checks.py, orchestrator/artel.py, orchestrator/forge.py, orchestrator/gitlab_adapter.py, tests/
Порядок: без зависимостей, параллельно частям 1–2 (зоны не пересекаются)
Рамка: $40

Часть 3 из 4 деления задачи 01M6EXF3TMNRKCZH8CS9BXXG1Z (GitLab Б2.3). Основание — ADR-0029 п. 8 (адаптер, срок токена) и ANSWER-1 п. 5 той же задачи (находки `doctor` по локальному стенду GitLab, 02.11).

Состояние кода (main):
- Строки проекта в `doctor` — `orchestrator/doctor/project_checks.py`: `project_entry_checks` `:34-58`, `check_ci_pull_request` `:138`, `check_base_protection` `:176`, `check_project_token` `:225` (зовёт `gh auth token` через `_operator_gh_token` `:211`), `check_ci_token` `:300`, `check_no_paths` `:359`, `component_checks` `:400`.
- `forge-probe <проект> [--job <имя>]` — `orchestrator/artel.py`, читает последний конвейер базы.
- Защиты веток через API хостинга при роли токена Developer читаются не полностью: часть полей отдаёт только роль Maintainer.

Требуется:
1. Строки `doctor` проекта с `target-human` (только чтение):
   - защиты веток: если уровень доступа токена (`forge.project_info(...).access_level`) ниже Maintainer (40) и API поэтому отдаёт неполные сведения — `skip` «нужна роль Maintainer», а не `fail`. Уровень Maintainer (40) и выше даёт обычную строку;
   - шаблон ветки задачи против правил `workflow` конфигурации CI проекта: если ветка по шаблону не попадает под конвейер — `warn`, где правило названо номером и выражением `if` (правила `workflow:rules` GitLab безымянны);
   - у записи с компонентом `full_suite: ci|both` файл конфигурации CI должен быть в `no_paths`, иначе `fail`;
   - в задании `ci_job` нет перезапуска упавших тестов (`pytest-rerunfailures`/`--reruns`, `retry` задания), иначе `warn` (инвариант 41: отчёт хостинга повторов не видит);
   - подмодули проекта на том же хостинге: адрес подмодуля доступен по тому же слоту токена — `ok`, иначе `fail` с причиной.
2. Строки `doctor` проекта выбирают проверку по `forge` записи. Для `gitlab` GitHub-проверки не применяются, и ни одна строка `doctor` по записи проекта не вызывает `gh`:
   - `project-base-protection-<имя>` идёт через `forge.protections` (API GitLab), а не `gh` (сейчас skip «gh: Bad credentials (HTTP 401)»);
   - `project-ci-token-<имя>` проверяет доступ токена к конвейерам через `forge.pipeline_status`/`branch_pipeline`, а не GitHub Actions (сейчас FAIL «запуски Actions недоступны»). Если конвейеры недоступны токену по правам — `fail` «статус CI проекта пульт не увидит», как сейчас для Actions (`project_checks.py:341-345`); временный отказ — `skip`;
   - отказ по правам и временный отказ различаются по коду ответа хостинга. Его передаёт поле результата `forge` (например `status`/`kind` в `Protections`, `PipelineStatus`, `BranchPipeline`), а не разбор текста `reason` (сейчас у этих типов только `reason: str`, `orchestrator/forge.py:42-49`, `:99-103`, `:113-119`; текст «(403)» — `orchestrator/gitlab_adapter.py:202-203`). Поле добавляется в `orchestrator/forge.py` и заполняется в `orchestrator/gitlab_adapter.py`; другие правки этих двух файлов в эту часть не входят;
   - `project-ci-pull-request-<имя>` для `gitlab` заменяется проверкой `workflow`-правил `.gitlab-ci.yml` для шаблона ветки (п. 1), а не поиском `pull_request` в `.github/workflows`;
   - `project-token-<имя>`: проверка слота (`warn` без `token_slot`, `fail` при пустом слоте) остаётся. Сверка с токеном `gh` Оператора для `gitlab` не выполняется, строка прямо называет, что она не делалась.
   Выбор проверки идёт через реестр `forge` (наличие функции у реализации, `forge.ci_by_pipeline`), как `misc_checks.check_base_branch` (`orchestrator/doctor/misc_checks.py:91-140`). Сравнение значения хостинга с литералом (в том числе `forge.hosting(...) == "gitlab"`, `entry.get("forge") == …`) и новые исключения `EXEMPT` сторожа ac9 (`tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:416-421`) запрещены. Строки проектов `github` остаются прежними.
3. `forge-probe <проект> --ref <ветка> | --sha <sha>` выводит сведения конвейера названной ветки или коммита вместо последнего конвейера базы. Прочий вывод прежний.

Критерии приёмки:
- `doctor`, отдельные строки:
  - уровень доступа токена Developer (30) — строка защит `skip` «нужна роль Maintainer»;
  - уровень доступа Maintainer (40) — строка защит не `skip` «нужна роль Maintainer» (ловит `<=` вместо `<`);
  - ветка вне `workflow` — `warn`, в тексте которого номер правила и его выражение `if`;
  - файл CI не в `no_paths` при `full_suite: ci` — `fail`;
  - `--reruns` в задании — `warn`; `retry:` у задания — `warn`;
  - недоступный подмодуль — `fail` с причиной;
- запись `forge: gitlab` на подменённом `forge`:
  - ни одна строка `project-*-<имя>` не вызывает `gh`, включая `project-token-<имя>`;
  - строки дают `ok`/`warn`/`skip` по данным GitLab;
  - конвейеры недоступны токену по правам (поле кода ответа в результате `forge`) — `project-ci-token-<имя>` даёт `fail`, временный отказ — `skip`; подмена несёт одинаковый текст `reason` в обоих случаях, так что различение по тексту тест краснит;
- `forge-probe --ref` и `--sha` на подменённом `forge` выводят конвейер названной ветки или коммита;
- артель и проекты `github` + `operator`: поведение и существующие тесты прежние; тест ac9 и `EXEMPT` не изменены.

Только чтение: `orchestrator/doctor/misc_checks.py`; `orchestrator/forge.py` и `orchestrator/gitlab_adapter.py` — кроме поля кода ответа.

Не входит: хук, его строка `doctor`, клон подмодулей и сверки отправки (часть 2); открытие `gitlab`/`target-human` (часть 4).