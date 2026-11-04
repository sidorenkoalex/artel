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
   одним вызовом `gh` с argv ровно в порядке `pr create --head <branch>
   --base <base> --title <title> --body <body>`, затем `--draft` (только при
   `draft`), затем `--assignee=<имя>` одним аргументом (только при заданном
   исполнителе); вызов — через `forge.github_call` (требование 7).
   Номер PR разбирается ТОЛЬКО из стандартного вывода `pr create` при коде
   выхода 0. Номер — десятичное число хвоста адреса `/pull/<номер>`;
   владелец и имя репозитория в адресе PR сверяются с владельцем и именем
   адреса проекта (`url` записи) тем же разбором, что `ci._owner_and_name`
   (`orchestrator/ci.py:104-115`: https с необязательными `.git` и `/` в
   конце, scp `git@<хост>:<владелец>/<имя>` с необязательным `.git`);
   буквальное сравнение адреса PR с префиксом адреса проекта не
   допускается. Владелец или имя не совпали (или адрес проекта не
   разобран) — результат с причиной, без `iid`. Успех —
   `forge.MergeRequest` с номером PR в `iid`, адресом в `url` и прочими
   полями из `mr_status` этого номера (требование 4). Код выхода 0, адрес в
   stdout не разобран — результат с причиной, без `iid`. Код выхода не 0 —
   результат с причиной без `iid`; адрес в stderr (в том числе адрес
   существующего PR в тексте проверки `gh` «already exists») не разбирается.
   Частичный успех — адрес разобран, последующее чтение `mr_status`
   отказало — результат несёт `iid` и `url` вместе с причиной.
2. **Сохранение ссылки при частичном успехе.** `github_adapter.open_forge_mr`
   (общая точка обоих путей открытия — черновика `ensure_forge_draft_mr` на
   входе в `verifying` и `_deliver_mr` гейта мержа) сохраняет ссылку на MR в
   БД (`store.set_mr_link`) всегда, когда результат несёт `iid`, при любом
   исходе чтения. Запись журнала «MR открыт» (`MR_OPENED_ACTION`) при
   частичном успехе НЕ пишется — только при результате без причины; запись
   журнала о частичном успехе не называет его «MR не открыт» (сейчас отказ
   `_deliver_mr` пишется текстом `MR не открыт: <причина>`,
   `orchestrator/fsm_merge_gate.py:1869-1870`): PR открыт, ссылка
   сохранена, не удалось чтение.
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

   Результат с этим признаком не несёт `iid` (требование 1), ссылка на MR в
   БД не пишется. `_deliver_mr` эскалирует «MR ветки уже существует, ссылки в
   БД нет» по этому полю так же, как по коду 409 GitLab; распознавание 409 GitLab по
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
   `Could not resolve to a PullRequest`. Всё прочее — та же подстрока при
   любом ином коде выхода (например 2 или 4), отсутствие репозитория
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
7. **Закрытый список вызовов `gh` у `_GitHub`.** Все вызовы `gh` функций
   `open_mr`, `mr_status`, `undraft_mr`, `assign_mr` идут через одну
   публичную функцию `forge.github_call(target, *args) ->
   subprocess.CompletedProcess`: она сверяет `args` с закрытым списком ниже
   и только для разрешённой формы вызывает `ci.gh(*args, repo=<адрес
   проекта>)`, где адрес проекта — `ctx.remote` контекста проекта
   (`repo_context.resolve(target).remote` — `url` записи, как
   `github_adapter._gh_repo_kwargs`, `orchestrator/github_adapter.py:107-115`).
   `repo` задан у каждого вызова: `ci.gh` без `repo` работает в корне
   артели (`config.ROOT`) и не дописывает `--repo` (`orchestrator/ci.py:72-93`)
   — команда изменила бы PR с тем же номером в репозитории артели; поэтому
   проект, контекст которого не разрешён (`repo_context.resolve` даёт
   `None`), и проект-артель (`repo_context.is_artel(target)`: её
   `ctx.remote` — имя `origin`, а `_gh_repo_kwargs` отдаёт для неё пустой
   словарь, `orchestrator/github_adapter.py:107-115`) — тоже отказ без
   вызова `ci.gh`: `repo` у вызова `ci.gh` никогда не пустой. Причина
   отказа для артели — непустой текст, выбирает разработчик. Отказ —
   `subprocess.CompletedProcess(args, 1, "", <причина>)` без вызова
   `ci.gh`; причина вызова вне списка начинается ровно с текста
   `вызов gh не разрешён адаптеру GitHub — gh не запущен: ` и продолжается
   argv отказанного вызова через пробел; причина проекта без контекста —
   `адрес проекта <target> не разрешён — gh не запущен`. Отказ
   `github_call` функция `_GitHub` превращает в результат с причиной (по
   образцу `orchestrator/gitlab_adapter.py:157`). Прежнее чтение check runs
   `pipeline_status` (`ci.check_runs`) идёт как сейчас, не через
   `github_call`. Разрешены только:
   `pr create --head <ветка> --base <база> --title <заголовок> --body <текст>`
   с необязательными `--draft` и `--assignee=<имя>`; `pr view <номер> --json
   <ровно набор полей требования 4>`; `pr ready <номер>`; `pr edit <номер>
   --add-assignee=<имя>`; и прежнее чтение check runs `pipeline_status`
   (`ci.check_runs`, вне `github_call`). `<номер>` — целое в десятичной
   записи. Список сверяет argv целиком, включая хвост (по образцу полной
   сверки запроса `orchestrator/gitlab_adapter.py:143-171`): подкоманду,
   флаги, отсутствие лишних аргументов после разрешённой формы и
   десятичность номера. Например `pr edit <номер> --base x`,
   `pr view <номер> --json number`, `pr ready 7 --undo`,
   `pr edit 7 --add-assignee=alice --base x`, `pr view 7a --json <набор>`,
   `pr ready 7a` — вне списка. `pr merge`, `pr close`,
   `pr comment` и `api` с методом записи `_GitHub` не вызывает никогда.
8. **Исполнитель по имени для GitHub.** Сигнатура —
   `github_adapter.mr_assignee(policy, target=None)`; вид исполнителя задаёт
   реализация в реестре `forge.IMPLEMENTATIONS` под значением `forge` записи
   проекта — атрибутом реализации `ASSIGNEE_BY_NAME` (истина — исполнитель
   по имени; `_GitHub` несёт его со значением `True`), а не сравнением
   значения `forge` с литералом (сторож литералов
   `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:425-435`,
   `:488` сравнение через `forge.hosting(t) == "github"` не видит — поэтому
   признак закреплён критерием AC-15 с подменой реестра):
   - реализация без атрибута `ASSIGNEE_BY_NAME` (GitLab и подделки реестра
     в прежних тестах) — только целое, как сейчас, с прежними текстами;
   - реализация с `ASSIGNEE_BY_NAME` (GitHub) — имя по правилу имён GitHub (латинские буквы, цифры, одиночные
     `-` не в начале и не в конце, длина до 39 знаков) или целое (его
     `targets.delivery_policy` уже сделал из строки цифр), которое
     передаётся строкой (`42` → `--assignee=42`);
   - не назначен (запись журнала `MR_ASSIGNEE_ACTION`): поле
     `policy.mr_assignee` не задано, булево, `@me`, `@copilot` и любое
     значение с `@`, список через запятую, значение с ведущим `-`, значение
     с пробелом, имя вне правила;
   - запись о неназначенном для реализации с `ASSIGNEE_BY_NAME` — своим
     текстом без подстроки «не числовой id», в том числе при незаданном поле
     (сейчас без поля пишется `ASSIGNEE_NOT_NUMERIC: policy.mr_assignee не
     задан`, `orchestrator/github_adapter.py:379-380`); для реализации без
     атрибута и для вызова без проекта — прежние тексты `ASSIGNEE_NOT_NUMERIC`
     (`orchestrator/github_adapter.py:342`, `:379-381`);
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
сначала с позиционными аргументами, равными точному списку в этом порядке:
`pr`, `create`, `--head`, `<branch>`, `--base`, `<base>`, `--title`,
`<title>`, `--body`, `<body>`, затем `--draft` (только при черновике), затем
`--assignee=<имя>` одним элементом (только при исполнителе); затем `pr view
<номер>` требования 4. У каждого вызова именованный аргумент `repo` подделки
равен `url` записи проекта. Ответ `pr create` — код 0, stdout `<url
проекта>/pull/<номер>`. Результат: `iid` — номер из адреса PR, `url` —
адрес, остальные поля — из ответа чтения, `reason` пуст. Разбор номера
по владельцу и имени (требование 1), три случая через `open_forge_mr`:
`url` записи проекта вида `https://<хост>/<владелец>/<имя>.git` и вида
`git@<хост>:<владелец>/<имя>` при stdout `pr create`
`https://<хост>/<владелец>/<имя>/pull/<номер>` — номер разобран, ссылка на
MR в БД сохранена; stdout с адресом PR чужого репозитория
(`https://<хост>/<другой владелец>/<имя>/pull/<номер>`) — результат с
причиной, `iid` `None`, ссылки на MR в БД нет.

AC-2. `forge.open_mr` для `github`, когда `pr create` завершился кодом 0, а
его stdout не содержит разбираемого адреса PR, отдаёт результат с непустой
причиной и `iid` `None`; подделка `ci.gh` вызвана с `pr create` (шпион видел
хотя бы один такой вызов);
`open_forge_mr` при таком результате не пишет ссылку на MR в БД и запись
«MR открыт».

AC-3. Частичный успех на гейте мержа: `pr create` вернул адрес PR, `pr view`
отказал — после `approve` на `merge_gate` ссылка на MR (номер и адрес) в БД
задачи сохранена, задача осталась на гейте, причина в журнале, записи
«MR открыт» нет и запись журнала о частичном успехе не содержит подстроки
«MR не открыт»; повторный `approve` не уходит в эскалацию «MR ветки уже
существует, ссылки в БД нет».

AC-4. Частичный успех на входе в `verifying`: `ensure_forge_draft_mr` при
`pr create` с адресом и отказе чтения возвращает причину, ссылка на MR в БД
сохранена, записи «MR открыт» нет; следующий вызов `ensure_forge_draft_mr`
не вызывает `pr create` повторно и не получает «уже существует».

AC-5. `pr create` отказал (код выхода 1) со stderr, содержащим
`a pull request for branch "<ветка>" into branch "<база>" already exists:`
и следом адрес существующего PR `<url проекта>/pull/<номер>`, — результат
`forge.open_mr` несёт признак «уже существует» требования 3 и `iid` `None`;
после `approve` на `merge_gate` ссылки на MR в БД задачи нет, задача в
эскалации «MR ветки уже существует, ссылки в БД нет». То же (признак есть,
`iid` нет, ссылки нет, эскалация) для stderr с `A pull request already
exists` (отказ сервера 422).

AC-6. `pr create` отказал иным текстом — подделка `ci.gh` вызвана с
`pr create` (шпион видел хотя бы один такой вызов), признака «уже
существует» у результата нет; `approve` на `merge_gate` оставляет
задачу на гейте, причина в журнале, ссылки на MR в БД нет, эскалации нет.

AC-7. `forge.mr_status` для `github` по ответу `pr view` сопоставляет поля по
требованию 4: `state` `OPEN`/`MERGED`/`CLOSED` → `opened`/`merged`/`closed`;
`isDraft` → `draft`; `login` первого из `assignees` → `assignee`, пустой
`assignees` → `None`; `baseRefName`/`headRefName`/`headRefOid` →
`target_branch`/`source_branch`/`sha`; `mergeCommit.oid` →
`merge_commit_sha`, `mergeCommit: null` → `None`; `squash_commit_sha` —
`None` при любом ответе; argv — `pr view <номер> --json
number,url,title,state,isDraft,assignees,baseRefName,headRefName,headRefOid,mergeCommit`,
именованный аргумент `repo` подделки равен `url` записи проекта.

AC-8. `mr_status` со `state`, отличным от трёх известных, — `approve` на
`merge_gate` отказывает «статус MR неизвестен»; вывод `pr view` не JSON или
JSON без `number` — результат с причиной без `(404)`.

AC-9. «Не найден» и «не прочитан» в `mr-sync`: `pr view` с кодом выхода 1 и
stderr, содержащим `Could not resolve to a PullRequest`, — причина с
подстрокой `(404)`, `mr-sync` даёт «MR не найден», `mr-sync --confirm`
отказывает; та же подстрока `Could not resolve to a PullRequest` в stderr при
коде выхода 4 и при коде выхода 2, `Could not resolve to a Repository …`,
код выхода 4 и сбой сети — причина без `(404)`, `mr-sync` даёт «не прочитан», а не «MR не найден»;
ответ без `baseRefName` — `mr-sync` даёт «неизвестно».

AC-10. `mr-sync` в песочнице с локальным голым `origin`: PR влит каждым из
трёх методов — коммитом слияния, сжатием, перебазированием (воспроизводится
git-командами, `mergeCommit.oid` подделки — получившийся коммит в
`origin/<base>`), `state: MERGED` — итог «влит этим MR» по признаку (а),
`--confirm` переводит задачу в `done` с `closed_as=merged_upstream`; PR
закрыт (`CLOSED`), правка внесена в base иначе — итог «в базе, влит иначе».

AC-11. `forge.undraft_mr` для `github`: PR-черновик — `pr ready <номер>`
вызван ровно один раз, результат — по новому чтению (`draft` `False`); PR не
черновик — `pr ready` не вызван, результат — чтение; у каждого вызова
(`pr view`, `pr ready`) именованный аргумент `repo` подделки равен `url`
записи проекта; отказ `pr ready` (PR — черновик) — подделка вызвана с
`pr ready` (шпион видел такой вызов), результат с причиной,
`_ready_existing_mr` оставляет задачу на гейте.

AC-12. `forge.assign_mr` для `github` вызывает `ci.gh` с argv `pr edit
<номер> --add-assignee=<login>` (флаг и значение — один элемент argv), затем
чтение; у каждого вызова именованный аргумент `repo` подделки равен `url`
записи проекта; отказ `pr edit` — подделка вызвана с `pr edit` (шпион видел
такой вызов), `_ready_existing_mr` оставляет задачу на гейте с причиной.

AC-13. Шпион на `ci.gh` при вызовах четырёх функций `_GitHub` (AC-1–AC-12)
видел каждый из вызовов `pr create`, `pr view`, `pr ready`, `pr edit` хотя
бы один раз и только вызовы из закрытого списка требования 7; транспорт GitLab
(`gitlab_adapter`) не вызван ни разу; `pr merge`, `pr close`, `pr comment`
не появились ни разу. Вне ограничения списка (вызовы не из `_GitHub`):
`ci.check_runs`/`ci.check_runs_page` (чтение CI гейта, в том числе через
`_GitHub.pipeline_status`), `ci.run_list`, `ci.find_run_id`,
`ci.trigger_rerun`, путь гейта `operator` (`github_adapter.ensure_draft_mr`,
`github_adapter.undraft_mr`) и закрытие PR при `kill`
(`cleanup._close_project_pr`).

AC-14. `forge.github_call` для проекта `forge: github`, вызванная напрямую с
`pr edit 7 --base x`, `pr merge 7`, `pr close 7`, `pr comment 7`,
`pr view 7 --json number`, `pr ready 7 --undo`,
`pr edit 7 --add-assignee=alice --base x`, `pr view 7a --json <набор
требования 4>`, `pr ready 7a`, отдаёт `subprocess.CompletedProcess` с кодом 1 и
`stderr`, начинающимся с `вызов gh не разрешён адаптеру GitHub — gh не
запущен: `; шпион `ci.gh` не вызван. Каждая разрешённая форма требования 7
(`pr create` в четырёх сочетаниях `--draft`/`--assignee=<имя>`, `pr view 7
--json <набор требования 4>`, `pr ready 7`, `pr edit 7
--add-assignee=alice`) — шпион `ci.gh` вызван ровно с этими позиционными
аргументами и `repo`, равным `url` записи проекта, `github_call` отдаёт его
ответ. Проект, для которого `repo_context.resolve` даёт `None`, — код 1,
`ci.gh` не вызван. Проект — артель (`repo_context.is_artel`) с разрешённой
формой `pr ready 7` — код 1, непустой `stderr`, `ci.gh` не вызван.

AC-15. Исполнитель: проект GitHub и `mr_assignee` `alice` — `pr create`
с `--assignee=alice`, `pr edit` с `--add-assignee=alice`; GitHub и целое
`42` — `--assignee=42`; GitHub и `@copilot`, `@me`, `a,b`, `-x`, `a b` —
не назначен: в argv `pr create` нет флага исполнителя, запись журнала
«исполнитель MR» без подстроки «не числовой id»; GitHub без поля
`policy.mr_assignee` — не назначен, запись журнала без подстроки «не
числовой id»; GitLab и `alice` — не назначен с прежней записью
`ASSIGNEE_NOT_NUMERIC`; булево — не назначен; `mr_assignee(policy)` без
проекта и с проектом без `forge` — прежние ответы. Подмена реестра
`forge.IMPLEMENTATIONS` (реализация GitHub для подмены берётся из
`forge.IMPLEMENTATIONS["github"]`, не по имени `forge._GitHub`): она под
ключом `gitlab` — `mr_assignee` с
проектом `forge: gitlab` принимает `alice`; объект без атрибута
`ASSIGNEE_BY_NAME` под ключом `github` — `mr_assignee` с проектом `forge:
github` не назначает `alice` и назначает целое `42`.

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

## Решения Оператора на гейте SPEC

Возврат с гейта SPEC (девять решений) учтён так; все проверки — против
временного дублёра (подделка/шпион `ci.gh`, подмена реестра, песочница
пульта), не против настоящего GitHub, `gh` или репозитория артели:

- Решение 1 (номер PR — только из stdout при коде 0; адрес в stderr
  «already exists» не разбирается) — требования 1, 3; AC-5 (stderr с
  адресом существующего PR: признак есть, `iid` нет, ссылки в БД нет,
  эскалация). Сверено: ссылка пишется при результате без причины / с `iid`
  (`orchestrator/github_adapter.py:421-423`, требование 2), эскалация —
  `orchestrator/fsm_merge_gate.py:1863-1868`.
- Решение 2 (`forge.github_call`; отказ — `CompletedProcess` код 1 с
  именованной причиной без `ci.gh`) — требование 7 (текст причины
  закреплён); AC-14 через публичную функцию. Прежнее `pipeline_status`
  через `ci.check_runs` остаётся вне `github_call`.
- Решение 3 (признак реализации) — требование 8, имя атрибута
  `ASSIGNEE_BY_NAME`; AC-15, два случая подмены реестра. Подделки
  `IMPLEMENTATIONS["gitlab"]` прежних тестов
  (`tests/test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery.py:456` и др.)
  атрибута не несут и получают прежнее поведение «только целое».
- Решение 4 (`repo` = адрес проекта у каждого вызова) — требование 7
  (сверено: `orchestrator/ci.py:72-93` — без `repo` нет `--repo`, `cwd` —
  `config.ROOT`); AC-1, AC-7, AC-11, AC-12, AC-14 проверяют `repo` подделки.
- Решение 5 (порядок argv `pr create`) — требование 1; AC-1 точным списком.
- Решение 6 (`mr_assignee(policy, target=None)`; GitHub без поля —
  GitHub-текст) — требование 8 (сверено: `orchestrator/github_adapter.py:379-380`);
  AC-15. `tests/test_mr_delivery_units.py` зовёт без `target` — не ломается.
- Решение 7 (`Could not resolve to a PullRequest` при кодах 4 и 2 — без
  `(404)`) — требование 4; AC-9.
- Решение 8 (шпион видел вызов) — AC-2, AC-6 (`pr create`), AC-11
  (`pr ready`), AC-12 (`pr edit`), AC-13 (все четыре). Сверено: прежний
  отказ без вызова `gh` — `orchestrator/forge.py:205-212`.
- Решение 9 (заметки test_author) — раздел «Материалы».

Второй возврат (четыре решения), проверки — тоже против временного
дублёра (подделка `ci.gh`, песочница пульта):

- Решение 1 (номер — хвост `/pull/<n>`, владелец и имя — разбором
  `ci._owner_and_name`) — требование 1; AC-1, три новых случая. Сверено:
  виды адреса и разбор — `orchestrator/ci.py:104-115` (функция закрытая;
  `ci.py` в зону не входит — используется только чтением/вызовом).
- Решение 2 (сверка argv целиком, включая хвост и десятичность номера) —
  требование 7; AC-14, четыре новых отказных случая. Сверено: образец —
  `orchestrator/gitlab_adapter.py:143-171`.
- Решение 3 (артель и неразрешённый контекст — отказ без `ci.gh`) —
  требование 7; AC-14, случай артели. Сверено:
  `orchestrator/github_adapter.py:107-115`, `orchestrator/ci.py:39-98`.
- Решение 4 (заметки) — «Не входит» (формулировка о прежних тестах),
  требование 2 и AC-3 (запись о частичном успехе без «MR не открыт»;
  сверено: `orchestrator/fsm_merge_gate.py:1869-1870`), AC-15 (реализация
  из `forge.IMPLEMENTATIONS["github"]`, `orchestrator/forge.py:168`).

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
- Прежние тесты зелёные без правки, кроме мандата требования 10, — это
  держит пульт (полный зелёный набор `tests/`).

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
- Заметки для test_author (решение 9, проверок не меняют): адрес PR для
  разбора — `https://<хост>/<владелец>/<имя>/pull/<номер>`, владелец и
имя сверяются с адресом проекта разбором `ci._owner_and_name`
(требование 1); для AC-10 слияния в
  долгоживущем файле воспроизводятся git-командами по образцу
  `tests/test_01m6ab4ve2r0q2v5d4mmjgngh7_mr_sync.py` (`squash_with_other`,
  `:644`; `rebase_merge`, `:689`).
