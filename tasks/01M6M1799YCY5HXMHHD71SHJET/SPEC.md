---
task: 01M6M1799YCY5HXMHHD71SHJET
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/forge.py, orchestrator/github_adapter.py, orchestrator/fsm_merge_gate.py, docs/codebase-map.md, tests/test_01m6m1799ycy5hxmhhd71shjet_*.py, tests/test_01m5wcxbm7wcmrwcbwnchmar3t_gitlab_forge.py
budget_usd: 40
---

# SPEC: Ручной мерж для GitHub, часть 1 — функции MR хостинга GitHub через `gh` (`open_mr`, `undraft_mr`, `assign_mr`, `mr_status`)

## Контекст

Решение Оператора 01.11: хостинг `github` в `forge` получает функции MR
через `gh`, чтобы пару `github` + `target-human` можно было открыть.
Работа поделена на две задачи: эта (часть 1) — функции MR реализации
`_GitHub` без открытия пары; часть 2 — открытие пары
(`targets.SUPPORTED_PAIRS`), проверки записи и строки `doctor`.

Сейчас у `forge._GitHub` есть только `pipeline_status`
(`orchestrator/forge.py:127-164`); `open_mr`/`undraft_mr`/`assign_mr`/
`mr_status` для `github` отвечают «не реализовано для github»
(`orchestrator/forge.py:205-212`). Гейт мержа людей проекта узнаёт
«MR уже существует» только по тексту кода 409 адаптера GitLab
(`orchestrator/fsm_merge_gate.py:1587-1590`, `:1863-1868`), исполнитель MR
бывает только целым (`orchestrator/github_adapter.py:372-381`), а
`open_forge_mr` не сохраняет ссылку на MR, если результат несёт причину
(`orchestrator/github_adapter.py:421-423`). Номера строк сверены по HEAD
89698bf92 ветки задачи.

Решения Оператора по батчу вопросов — `ANSWER-1.md`: мандат на удаление
четырёх ключей `GH_CALLS` (вопрос 1, вариант A), признак «PR не найден»
(вопрос 2, вариант A), отдельное булево поле «уже существует» в
`forge.MergeRequest`, `mr_assignee` при неопределённом хостинге — как без
проекта, бюджет $40.

## Требования

1. **`_GitHub.open_mr(target, branch, base, title, body, draft, assignee)`**
   одним вызовом `gh pr create --head <branch> --base <base> --title <title>
   --body <body>` — с `--draft` только при `draft`, с `--assignee=<имя>`
   одним аргументом только при заданном исполнителе; `gh` — через `ci.gh` с
   `repo` = адрес проекта (`ctx.remote`, как `github_adapter._gh_repo_kwargs`,
   `orchestrator/github_adapter.py:107-115`). Номер PR берётся из адреса PR
   в выводе `pr create`. Успех — `forge.MergeRequest` с номером PR в `iid`,
   адресом в `url` и прочими полями из `mr_status` этого номера (требование
   4). Адрес PR в выводе не разобран — результат с причиной, без `iid`.
   Частичный успех — адрес разобран, последующее чтение `mr_status`
   отказало — результат несёт `iid` и `url` вместе с причиной.
2. **Сохранение ссылки при частичном успехе.** `github_adapter.open_forge_mr`
   (общая точка обоих путей открытия — черновика `ensure_forge_draft_mr` на
   входе в `verifying` и `_deliver_mr` гейта мержа) сохраняет ссылку на MR в
   БД (`store.set_mr_link`) всегда, когда результат несёт `iid`, при любом
   исходе чтения. Запись журнала «MR открыт» (`MR_OPENED_ACTION`) при
   частичном успехе НЕ пишется — только при результате без причины.
   Результат с причиной вызывающий по-прежнему обрабатывает как отказ (задача
   на гейте с причиной / вход в `verifying` отклонён). Поведение для GitLab не
   меняется: его реализация не отдаёт `iid` вместе с причиной.
3. **Признак «PR этой ветки уже существует».** `forge.MergeRequest` получает
   отдельное булево поле (по умолчанию `False`; имя выбирает разработчик),
   которое ставит только `_GitHub.open_mr`, когда отказ `gh pr create` несёт
   любой из двух текстов:
   - проверка самого `gh`: `a pull request for branch "<ветка>" into branch
     "<база>" already exists`;
   - отказ сервера 422: `A pull request already exists`.

   `_deliver_mr` эскалирует «MR ветки уже существует, ссылки в БД нет» по
   этому полю так же, как по коду 409 GitLab; распознавание 409 GitLab по
   тексту причины (`orchestrator/fsm_merge_gate.py:1589-1590`), тексты и
   поведение GitLab не меняются.
4. **`_GitHub.mr_status(target, mr)`** — `gh pr view <номер> --json
   number,url,title,state,isDraft,assignees,baseRefName,headRefName,headRefOid,mergeCommit`.
   Сопоставление полей `forge.MergeRequest`:
   - `iid` ← `number`; `url` ← `url`; `title` ← `title`; `draft` ←
     `isDraft is True`;
   - `state` ← `OPEN` → `opened`, `MERGED` → `merged`, `CLOSED` → `closed`;
     иное значение — как есть;
   - `assignee` ← `login` первого элемента `assignees`, пусто — `None`;
   - `target_branch` ← `baseRefName`; `source_branch` ← `headRefName`;
     `sha` ← `headRefOid`;
   - `merge_commit_sha` ← `mergeCommit.oid`, `mergeCommit: null` — `None`;
     `squash_commit_sha` — всегда `None` (GitHub отдаёт коммит вливания одним
     полем при всех трёх методах вливания).

   «PR не найден» — причина с подстрокой `(404)` — ТОЛЬКО когда `gh`
   завершился кодом выхода 1 и его stderr содержит подстроку
   `Could not resolve to a PullRequest`. Всё прочее — отсутствие репозитория
   (`Could not resolve to a Repository …`), нехватка прав, код выхода 4
   (нужна авторизация), сбой сети, отказ слота токена — причина без `(404)`.
   Вывод не JSON или JSON без `number` — причина без `(404)`.
5. **`_GitHub.undraft_mr(target, mr)`** — читает PR (`mr_status`); черновик —
   `gh pr ready <номер>`, затем результат по новому чтению; не черновик —
   результат чтения без вызова `pr ready`. Отказ чтения или `pr ready` —
   результат с причиной.
6. **`_GitHub.assign_mr(target, mr, assignee)`** — `gh pr edit <номер>
   --add-assignee=<имя>` (флаг и значение одним аргументом), затем результат
   по новому чтению. Отказ — результат с причиной. `--add-assignee`
   добавляет исполнителя, а не заменяет его (у GitLab — замена): если
   `policy.mr_assignee` сменили между черновиком и гейтом, у PR будут оба, а
   `assignee` результата — первый из `assignees`; поведение не выравнивается.
7. **Закрытый список вызовов `gh` у `_GitHub`.** Разрешены только:
   `pr create --head <ветка> --base <база> --title <заголовок> --body <текст>`
   с необязательными `--draft` и `--assignee=<имя>`; `pr view <номер> --json
   <ровно набор полей требования 4>`; `pr ready <номер>`; `pr edit <номер>
   --add-assignee=<имя>`; и прежнее чтение check runs `pipeline_status`
   (`ci.check_runs`). Список проверяет и подкоманду, и флаги: например
   `pr edit <номер> --base x` — вне списка. Вызов вне списка отказывает до
   запуска `gh` (без вызова `ci.gh`) результатом с именованной причиной (по
   образцу `orchestrator/gitlab_adapter.py:157`). `pr merge`, `pr close`,
   `pr comment` и `api` с методом записи `_GitHub` не вызывает никогда.
8. **Исполнитель по имени для GitHub.** `github_adapter.mr_assignee` получает
   необязательный проект; вид исполнителя задаёт реализация в реестре `forge`
   (признак реализации, а не сравнение значения `forge` с литералом —
   сторож литералов `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:425-435`, `:488`):
   - GitLab — только целое, как сейчас;
   - GitHub — имя по правилу имён GitHub (латинские буквы, цифры, одиночные
     `-` не в начале и не в конце, длина до 39 знаков) или целое (его
     `targets.delivery_policy` уже сделал из строки цифр), которое
     передаётся строкой (`42` → `--assignee=42`);
   - не назначен (запись журнала `MR_ASSIGNEE_ACTION`): булево, `@me`,
     `@copilot` и любое значение с `@`, список через запятую, значение с
     ведущим `-`, значение с пробелом, имя вне правила;
   - запись о неназначенном для GitHub — своим текстом без подстроки
     «не числовой id»; для GitLab и для вызова без проекта — прежний текст
     `ASSIGNEE_NOT_NUMERIC` (`orchestrator/github_adapter.py:342`);
   - вызов без проекта (`mr_assignee(policy)`) и вызов с проектом, хостинг
     которого не определён (запись без `forge` или значение вне реестра
     `forge.IMPLEMENTATIONS`), отвечают как сейчас.

   Вызовы `orchestrator/github_adapter.py:416` (`open_forge_mr`) и
   `orchestrator/fsm_merge_gate.py:1894` (`_ready_existing_mr`) передают
   проект.
9. **Не меняется:** `token_user`, `token_expiry`, `protections`,
   `project_info`, `branch_pipeline`, `job_result`, `job_test_report` для
   `github` по-прежнему отвечают «не реализовано для github» без вызова `gh`
   (сверка автора «сверка автора — после адаптера» и строки `doctor`
   прежние); путь `gh` гейта `operator` (`github_adapter.ensure_draft_mr`,
   `github_adapter.undraft_mr`) — без изменений; `targets.SUPPORTED_PAIRS` —
   без изменений.
10. **Правка теста по мандату ANSWER-1.** Из словаря `GH_CALLS`
    (`tests/test_01m5wcxbm7wcmrwcbwnchmar3t_gitlab_forge.py:370-383`),
    которым параметризован
    `tests/test_01m5wcxbm7wcmrwcbwnchmar3t_gitlab_forge.py::test_ac13_github_other_functions_refuse`,
    удаляются ровно ключи `open_mr`, `undraft_mr`, `assign_mr`, `mr_status`.
    Утверждения метода не меняются; семь оставшихся ключей остаются;
    `skip`/`xfail` не допускаются; прочие тесты файла не меняются.

## Критерии приёмки

Общие условия всех критериев: пара `github` + `target-human` включается в
тесте подменой `targets.SUPPORTED_PAIRS`; `gh` — подделка `ci.gh`,
записывающая argv и отдающая заготовленный ответ (код выхода, stdout,
stderr); ни одного обращения к настоящему GitHub и к настоящему `gh`;
связка ключей не читается (`gitcmd.hosting_token` не вызывается или
подменён); проекты — вымышленные во временной песочнице `config`, `origin` —
локальный голый репозиторий; настоящий клон и настоящий локальный слой не
трогаются.

AC-1. `forge.open_mr` для проекта `forge: github` в четырёх сочетаниях
(черновик/не черновик × с исполнителем/без) вызывает подделку `ci.gh`
сначала ровно с argv `pr create --head <branch> --base <base> --title
<title> --body <body>` плюс `--draft` только при черновике и одним
аргументом `--assignee=<имя>` только при исполнителе, с `repo` = адрес
проекта; затем `pr view <номер>` требования 4. Результат: `iid` — номер из
адреса PR, `url` — адрес, остальные поля — из ответа чтения, `reason` пуст.

AC-2. `forge.open_mr` для `github`, когда вывод `pr create` не содержит
разбираемого адреса PR, отдаёт результат с непустой причиной и `iid` `None`;
`open_forge_mr` при таком результате не пишет ссылку на MR в БД и запись
«MR открыт».

AC-3. Частичный успех на гейте мержа: `pr create` вернул адрес PR, `pr view`
отказал — после `approve` на `merge_gate` ссылка на MR (номер и адрес) в БД
задачи сохранена, задача осталась на гейте, причина в журнале, записи
«MR открыт» нет; повторный `approve` не уходит в эскалацию «MR ветки уже
существует, ссылки в БД нет».

AC-4. Частичный успех на входе в `verifying`: `ensure_forge_draft_mr` при
`pr create` с адресом и отказе чтения возвращает причину, ссылка на MR в БД
сохранена, записи «MR открыт» нет; следующий вызов `ensure_forge_draft_mr`
не вызывает `pr create` повторно и не получает «уже существует».

AC-5. `pr create` отказал (код выхода не 0) со stderr, содержащим
`a pull request for branch "<ветка>" into branch "<база>" already exists`, —
`approve` на `merge_gate` даёт эскалацию «MR ветки уже существует, ссылки в
БД нет»; то же для stderr с `A pull request already exists` (отказ сервера
422).

AC-6. `pr create` отказал иным текстом — `approve` на `merge_gate` оставляет
задачу на гейте, причина в журнале, ссылки на MR в БД нет, эскалации нет.

AC-7. `forge.mr_status` для `github` по ответу `pr view` сопоставляет поля по
требованию 4: `state` `OPEN`/`MERGED`/`CLOSED` → `opened`/`merged`/`closed`;
`isDraft` → `draft`; `login` первого из `assignees` → `assignee`, пустой
`assignees` → `None`; `baseRefName`/`headRefName`/`headRefOid` →
`target_branch`/`source_branch`/`sha`; `mergeCommit.oid` →
`merge_commit_sha`, `mergeCommit: null` → `None`; `squash_commit_sha` —
`None` при любом ответе; argv — `pr view <номер> --json
number,url,title,state,isDraft,assignees,baseRefName,headRefName,headRefOid,mergeCommit`.

AC-8. `mr_status` со `state`, отличным от трёх известных, — `approve` на
`merge_gate` отказывает «статус MR неизвестен»; вывод `pr view` не JSON или
JSON без `number` — результат с причиной без `(404)`.

AC-9. «Не найден» и «не прочитан» в `mr-sync`: `pr view` с кодом выхода 1 и
stderr, содержащим `Could not resolve to a PullRequest`, — причина с
подстрокой `(404)`, `mr-sync` даёт «MR не найден», `mr-sync --confirm`
отказывает; `Could not resolve to a Repository …`, код выхода 4 и сбой сети
— причина без `(404)`, `mr-sync` даёт «не прочитан», а не «MR не найден»;
ответ без `baseRefName` — `mr-sync` даёт «неизвестно».

AC-10. `mr-sync` в песочнице с локальным голым `origin`: PR влит каждым из
трёх методов — коммитом слияния, сжатием, перебазированием (воспроизводится
git-командами, `mergeCommit.oid` подделки — получившийся коммит в
`origin/<base>`), `state: MERGED` — итог «влит этим MR» по признаку (а),
`--confirm` переводит задачу в `done` с `closed_as=merged_upstream`; PR
закрыт (`CLOSED`), правка внесена в base иначе — итог «в базе, влит иначе».

AC-11. `forge.undraft_mr` для `github`: PR-черновик — `pr ready <номер>`
вызван ровно один раз, результат — по новому чтению (`draft` `False`); PR не
черновик — `pr ready` не вызван, результат — чтение; отказ `gh` — результат
с причиной, `_ready_existing_mr` оставляет задачу на гейте.

AC-12. `forge.assign_mr` для `github` вызывает `ci.gh` с argv `pr edit
<номер> --add-assignee=<login>` (флаг и значение — один элемент argv), затем
чтение; отказ `gh` — `_ready_existing_mr` оставляет задачу на гейте с
причиной.

AC-13. Шпион на `ci.gh` при вызовах четырёх функций `_GitHub` (AC-1–AC-12)
видит только вызовы из закрытого списка требования 7; транспорт GitLab
(`gitlab_adapter`) не вызван ни разу; `pr merge`, `pr close`, `pr comment`
не появились ни разу. Вне ограничения списка (вызовы не из `_GitHub`):
`ci.check_runs`/`ci.check_runs_page` (чтение CI гейта, в том числе через
`_GitHub.pipeline_status`), `ci.run_list`, `ci.find_run_id`,
`ci.trigger_rerun`, путь гейта `operator` (`github_adapter.ensure_draft_mr`,
`github_adapter.undraft_mr`) и закрытие PR при `kill`
(`cleanup._close_project_pr`).

AC-14. Вызов `gh` из `_GitHub` вне закрытого списка — в том числе `pr edit
<номер> --base x`, `pr merge <номер>`, `pr view <номер>` с иным набором
`--json` — отказан результатом с именованной причиной, подделка `ci.gh` не
вызвана.

AC-15. Исполнитель: проект GitHub и `mr_assignee` `alice` — `pr create`
с `--assignee=alice`, `pr edit` с `--add-assignee=alice`; GitHub и целое
`42` — `--assignee=42`; GitHub и `@copilot`, `@me`, `a,b`, `-x`, `a b` —
не назначен: в argv `pr create` нет флага исполнителя, запись журнала
«исполнитель MR» без подстроки «не числовой id»; GitLab и `alice` — не
назначен с прежней записью `ASSIGNEE_NOT_NUMERIC`; булево — не назначен;
`mr_assignee(policy)` без проекта и с проектом без `forge` — прежние ответы.

AC-16. `token_user`, `token_expiry`, `protections`, `project_info`,
`branch_pipeline`, `job_result`, `job_test_report` для `github` — результат
с причиной «не реализовано для github», подделка `ci.gh` не вызвана; запись
«сверка автора — после адаптера» прежняя.

AC-17. В `tests/test_01m5wcxbm7wcmrwcbwnchmar3t_gitlab_forge.py` словарь
`GH_CALLS` не содержит ключей `open_mr`, `undraft_mr`, `assign_mr`,
`mr_status` и содержит прежние семь (`job_result`, `job_test_report`,
`token_user`, `token_expiry`, `protections`, `project_info`,
`branch_pipeline`); утверждения `test_ac13_github_other_functions_refuse`
совпадают с main, на методе нет `skip`/`xfail`.

## Оценка объёма и деление

Сработавшие сигналы: `budget_usd` ≥ $30 ($40 — рамка ТЗ, принята в
ANSWER-1); число файлов зоны ≥ 5; число критериев приёмки ≥ 10.

**Обоснование монолита.** ТЗ уже — часть 1 деления Оператора на две задачи
(часть 2 — открытие пары, проверки записи и `doctor`). Что нельзя разрезать
дальше: функции `open_mr`/`mr_status`/`undraft_mr`/`assign_mr` опираются
друг на друга (`open_mr`, `undraft_mr` и `assign_mr` строят результат через
`mr_status`), а их потребители — гейт мержа (`_deliver_mr`,
`_ready_existing_mr`), `open_forge_mr` и `mr-sync` — проверяются критериями
только вместе с ними; закрытый список вызовов `gh` описывает именно эти
вызовы. Удаление четырёх ключей `GH_CALLS` по мандату обязано ехать в той же
ветке, что сами функции: без функций оно не нужно, без удаления ветка
красна. Часть с функциями без правок `github_adapter`/`fsm_merge_gate`
оставила бы частичный успех и «уже существует» без проверяемого поведения
(AC-3–AC-5).

## Не входит

- Открытие пары `github` + `target-human` (`targets.SUPPORTED_PAIRS`),
  проверки записи и строки `doctor` — часть 2.
- `token_user`, `token_expiry`, `protections`, `project_info`,
  `branch_pipeline`, `job_result`, `job_test_report` для GitHub.
- Вливание, закрытие и комментирование PR пультом через `_GitHub` (ADR-0029,
  «Решения Оператора 26.10» п. 5).
- Правка текстов «MR !<номер>» в выводе пульта на «#<номер>».
- Проба на живом проекте GitHub — после части 2, Оператором: поток вывода
  адреса PR, значения `state`, вид `assignees[].login` и `mergeCommit.oid`,
  коммит вливания при перебазировании, серверные тексты «не найден»
  (`Could not resolve to a PullRequest`) и 422, адрес `--repo` вида scp.
- Поправка ADR-0029 п. 8 («реализация GitHub без изменения поведения») —
  операторский коммит.
- Изменения `orchestrator/ci.py`, `config.py`, `store.py`,
  `gitlab_adapter.py`, `mr_sync.py`, `targets.py`, `gitcmd.py`, `cleanup.py`,
  `repo_context.py`, `doctor/misc_checks.py`, ADR-0029 — только чтение.
- Выравнивание `--add-assignee` (добавление) с заменой исполнителя у GitLab.
- Зелёность сторожа литералов и прежних тестов GitLab, гейта `operator`,
  `mr-sync`, `tests/test_mr_delivery_units.py::…::test_only_integer_id_is_assigned`
  без правки — её держит пульт (полный зелёный набор `tests/`).

## Материалы

- `TZ.md` задачи; `ANSWER-1.md` — мандат «Ослабление тестов разрешено:
  tests/test_01m5wcxbm7wcmrwcbwnchmar3t_gitlab_forge.py::test_ac13_github_other_functions_refuse»
  с матрицей неослабления и независимой проверкой; ответы на вопросы 1 и 2.
- Образец реализации — `orchestrator/gitlab_adapter.py:516-572`
  (`_merge_request`, `open_mr`, `undraft_mr`, `assign_mr`, `mr_status`),
  закрытый список — `ALLOWED_PAIRS` `orchestrator/gitlab_adapter.py:51-63`,
  отказ до отправки — `:143-171`.
- `ci.gh` — `orchestrator/ci.py:39-98`; адрес `--repo` —
  `orchestrator/github_adapter.py:107-115`.
- Гейт мержа людей проекта — `orchestrator/fsm_merge_gate.py:1593-1908`;
  `mr-sync` — `orchestrator/mr_sync.py:51-53`, `:319-359`.
