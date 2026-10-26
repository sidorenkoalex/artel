---
task: 01M5WCXBM7WCMRWCBWNCHMAR3T
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/forge.py, orchestrator/gitlab_adapter.py, orchestrator/ci.py, orchestrator/github_adapter.py
merge_after: 01M5W27CY7K7NR9347NKD8F0NX
budget_usd: 50
---

# SPEC: GitLab А1.1 — интерфейс адаптера, реализация GitLab, подключение ci

## Контекст
Это часть 1 деления задачи 01M5W670PHF08VPZWDRM5BY56W (ADR-0029 п. 8, шаг
А1 после А0 — `targets.unsupported_reason`). Сейчас хостинг проекта —
только GitHub через `gh`. Внешние входы `orchestrator/ci.py`
(`verifying_status` :977, `branch_status` :1155, `failed_check_names`
:1115, `head_sha` :204, `main_line_status` :1422, `trigger_rerun` :1636,
`find_run_id` :1532, `check_run_workflow_run` :1609) знают только check
runs GitHub (`check_runs` :250). Задача вводит общий интерфейс хостинга
`orchestrator/forge.py`, реализацию GitLab на HTTP API v4
(`orchestrator/gitlab_adapter.py`) и подключает к нему `ci` для записи
`forge: gitlab`. Требования и критерии взяты из SPEC родителя с учётом
ANSWER-1 родителя и решений его гейта SPEC 26.10 (О-2…О-9): требования
1–10 и 14 родителя, критерии AC-1…AC-15, AC-19, AC-20, AC-22…AC-24
родителя (перенумерованы сквозь, соответствие — в «Материалах»). AC-12
здесь проверяет журнал и тексты причин ошибок; вывод `doctor`/`forge-probe`
проверяет часть 2. Поддержка остаётся закрытой (`targets.SUPPORTED_FORGES`
= `("github",)`, `orchestrator/targets.py:29`), поэтому GitLab-ветка в
потоке задач пока недостижима, а новые функции проверяются на подменённом
транспорте.

## Требования

1. **Интерфейс адаптера** — новый модуль `orchestrator/forge.py`.
   Реализация выбирается одним реестром в `forge.py`: словарём, ключи
   которого — значения поля `forge` записи проекта; выбор — поиском по
   ключу, без сравнения значения `forge` с литералами. `ci.py` выбирает
   реализацию через `forge`. Иных сравнений значения `forge` с литералами
   `"github"`/`"gitlab"` задача не добавляет. Сторож А0
   `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py::test_ac9_no_support_literals_outside_targets`
   не правится: запись `EXEMPT` для `forge.py` не нужна и не добавляется.
   В `ci.py` поле `forge` записи проекта не читается ничем, кроме передачи
   в функцию `forge`; результат функции `forge` в `ci.py` не сравнивается
   с литералом значения `forge` (`"github"`, `"gitlab"`,
   `targets.FORGES[...]`). В `forge.py` реализация выбирается индексом
   словаря-реестра по значению поля `forge`; проверка членства значения в
   реестре (`in` реестра) внутри `forge.py` разрешена. Параметр `target` функций
   `forge` — имя проекта (`str`), запись проекта `forge` получает сам.
   Функции `forge`:
   - `pipeline_status(target, sha)` — итог CI ровно этого sha (`green` /
     `red` / `running` / `none` / `unknown`, у не-`green` есть причина) и
     задания с именами и статусами;
   - `job_result(target, sha, job_name)` — статус задания с этим именем в
     конвейере этого sha;
   - `job_test_report(target, sha, job_name)` — «идентификатор теста →
     исход» либо `None` с причиной;
   - `open_mr(target, branch, base, title, body, draft, assignee)`,
     `undraft_mr(target, mr)`, `assign_mr(target, mr, assignee)`,
     `mr_status(target, mr)`;
   - только чтение: `token_user(target)`, `token_expiry(target)`,
     `protections(target)`; «сведения проекта» — ветка проекта по
     умолчанию и уровень доступа пользователя токена в проекте;
     «последний конвейер ветки» — sha, итог и задания последнего конвейера
     названной ветки.
2. **Реализация GitHub в `forge`.** `pipeline_status` для `forge: github`
   оборачивает нынешнее чтение check runs `ci` и не меняет его поведение.
   Итог по check runs коммита, в порядке проверки:
   - есть run с исходом `failure`, `cancelled` или `timed_out` — `red`;
   - есть run со статусом `queued` или `in_progress` — `running`;
   - check runs нет — `none`;
   - все runs завершены с исходом `success`, `skipped` или `neutral` —
     `green`;
   - всё прочее (иной исход или статус, чтение не удалось) — `unknown`.

   Остальные функции `forge` для `forge: github` возвращают именованный
   отказ «не реализовано для github» и `gh` не вызывают. Внешние входы
   `ci.py` и `github_adapter.py` сохраняют сигнатуры и для GitHub работают
   как сейчас.
3. **Реализация GitLab** — новый модуль `orchestrator/gitlab_adapter.py`.
   Запросы идут к HTTP API v4 средствами стандартной библиотеки. Адрес
   сервера и путь проекта берутся из `url` записи, токен — из слота
   `token_slot`. Токен передаётся заголовком `PRIVATE-TOKEN` и не попадает
   в журнал, вывод и сообщения ошибок. Если токен не получен (у записи нет
   слота, связка ключей отказала, слот пуст, вызов из процесса роли),
   адаптер не делает запроса и отдаёт именованную причину. Пара
   `(None, None)` из `gitcmd.hosting_token` (`orchestrator/gitcmd.py:121`;
   для GitHub это «прежняя авторизация») для `forge: gitlab` — отказ с
   причиной «токен не получен», запроса нет.
4. **Единственная функция запроса** `gitlab_adapter` с таблицей
   разрешённых пар «метод — шаблон пути». Разрешено:
   - чтение конвейеров по sha;
   - чтение конвейеров ветки (`GET /projects/:id/pipelines?ref=<ветка>`);
   - чтение проекта (`GET /projects/:id`); из ответа используются только
     `default_branch` и `permissions`;
   - чтение заданий, отчёта тестов, MR, пользователя токена, сведений о
     токене, защищённых веток и тегов;
   - создание MR;
   - правка MR только полями «исполнитель» и заголовок, причём новый
     заголовок может отличаться от текущего только наличием или
     отсутствием префикса `Draft: `.

   Любая иная пара (в том числе участники `/members…`) и иная смена
   заголовка — отказ до отправки запроса, с именем пары. `urllib` и
   `http.client` вызываются только в одной функции транспорта
   `gitlab_adapter`, которую подменяют тесты; транспорт вызывается только
   функцией запроса.
5. **Зелёный CI на GitLab** — итог `pipeline_status`:
   - старшинство итогов: `red` → `unknown` → `running` → `none` → `green`
     (левее — старше). Итог конвейера — старший из итога по статусу самого
     конвейера и итогов по его заданиям; итог sha — старший из итогов его
     конвейеров;
   - берутся конвейеры ровно этого sha; если их несколько, `green` только
     при зелёных всех. Список конвейеров sha читается постранично до
     конца со сверкой числа с заголовком `X-Total`;
   - статус самого конвейера: `green` возможен, только если он `success`
     или `manual` и задания удовлетворяют правилам ниже. Конвейер `failed`
     — `red`, даже при всех видимых заданиях `success`. Конвейер
     `running`, `pending`, `waiting_for_resource`, `preparing` или
     `scheduled` — `running`. Конвейер `canceled` или с иным статусом —
     `unknown`. Ни в одном из этих случаев итог не `green`;
   - завершённые задания без права падать для `green` — `success`;
   - задание `manual` допустимо, если оно вне `policy.ci_required_jobs`
     записи; задание `manual` из `policy.ci_required_jobs` даёт итог
     `running`, не `green`. Поле читается из плоской записи
     `targets.target(<имя проекта>)` как `entry.get("ci_required_jobs") or
     []` (по образцу прочих полей `policy` в `targets._flatten`,
     `orchestrator/targets.py:585-588`): нет ключа — список пуст. Запись
     адаптер получает загрузчиком `targets.target`, а не словарём,
     переданным в обход него;
   - задание `created` или `skipped` допустимо, только если в том же
     конвейере есть задание `manual` в более ранней стадии и само задание
     вне `policy.ci_required_jobs`. Задание `created` без задания `manual`
     в более ранней стадии — `running`; задание `skipped` без задания
     `manual` в более ранней стадии — `unknown`; задание `created` или
     `skipped` из `policy.ci_required_jobs` — не `green`;
   - порядок стадий — по наименьшему id задания стадии (меньше — раньше),
     не по порядку выдачи API;
   - есть `failed` без права падать — `red` при любом статусе конвейера;
     исключение — неполная выдача: тогда `unknown`;
   - есть `running`, `pending`, `waiting_for_resource`, `preparing` или
     `scheduled` — `running`;
   - у sha нет конвейера — `none` с причиной «конвейер не создан (ветка не
     под правилом workflow?)»;
   - `unknown` с причиной дают: `canceled` у задания без права падать или
     у конвейера; неизвестный статус задания или конвейера; неполная
     выдача. Задания читаются постранично до конца со сверкой числа с
     `X-Total`. Неполная выдача (заданий или конвейеров sha) даёт
     `unknown` при любых прочитанных статусах, в том числе при `failed`;
   - `unknown` и `none` никогда не `green`;
   - упавшее задание с правом падать даёт пометку в итоге с именем
     задания.
6. **`job_result` и `job_test_report`.** `job_result` — статус задания с
   запрошенным именем; если такого задания нет — именованная причина;
   если у имени несколько попыток — статус последней. `job_test_report` —
   ключ `<classname>::<name>`, значение — исход; совпадение ключей в одном
   отчёте — `None` с причиной «неоднозначный идентификатор»; отчёта нет
   или он истёк — `None` с причиной.
7. **Ошибки HTTP** (401, 403, 404, 429, 5xx, таймаут) — именованные
   причины. Повтор — только на 429/5xx, ограниченное число раз. Прочие
   `URLError` и отказ соединения — причина «сеть недоступна: <текст>»; для
   `pipeline_status` это итог `unknown` с этой причиной.
8. **`ci` для `forge: gitlab`:**
   - `verifying_status`, `branch_status` и `failed_check_names` берут итог
     через `forge.pipeline_status` и отображают его в виды GitHub по
     таблице ниже;
   - `head_sha` остаётся локальным, транспорт хостинга не вызывается,
     сигнатура не меняется;
   - `main_line_status`, `trigger_rerun`, `find_run_id` и
     `check_run_workflow_run` возвращают именованный отказ «не поддержано
     для gitlab» без вызова `gh`. Отказ `trigger_rerun` содержит «не
     запущен». `main_line_status` отдаёт вид `ci.MAIN_UNKNOWN`.
     `find_run_id` и `check_run_workflow_run` отдают `("", причина)`.

   | Итог `pipeline_status` | `verifying_status` | `verifying_is_red(note)` | `branch_status` | `status_kind(note)` | `failed_check_names` |
   |---|---|---|---|---|---|
   | `green` | `VERIFYING_GREEN` | `False` | `(True, …)` | — | пустое множество |
   | `red` | `VERIFYING_RED`, `note` содержит «CI коммита <sha[:8]> не зелёный:» | `True` | `(False, …)` | `"red"` | имена упавших заданий без права падать |
   | `running` | `VERIFYING_RUNNING` | `False` | `(False, …)`, `note` содержит «ещё идёт» | `"running"` | пустое множество |
   | `none` | `VERIFYING_NONE` | `False` | `(False, …)`, `note` содержит «неизвестен» | `"unknown"` | `(None, причина)` |
   | `unknown` | `VERIFYING_NONE` | `False` | `(False, …)`, `note` содержит «неизвестен» | `"unknown"` | `(None, причина)` |

   Для красного `note` `red_status_sha(note)` даёт `sha[:8]`;
   `rerun_started` у отказа `trigger_rerun` — `False`.
9. **Константы** `TOKEN_EXPIRY_WARN_DAYS = 14`,
   `TOKEN_NO_EXPIRY_TASKS_WARN = 10`, число повторов и таймаут живут в
   `gitlab_adapter.py`/`forge.py`. `orchestrator/config.py` не правится
   (его зону держит Б1). `targets.SUPPORTED_FORGES` не расширяется.

## Критерии приёмки

AC-1. Каждая запрещённая пара функции запроса `gitlab_adapter` — отказ до
вызова HTTP: подменённый транспорт не вызван, причина отказа называет
пару. Проверяются пары: слияние MR, закрытие MR, комментарий, запуск
задания, повтор задания, удаление ветки, создание тега, чтение участников
проекта (`/members…`).

AC-2. Каждая разрешённая пара требования 4 доходит до подменённого
транспорта: чтение конвейеров по sha и по ветке, проекта, заданий, отчёта
тестов, MR, пользователя токена, сведений о токене, защищённых веток и
тегов; создание MR; правка MR полем «исполнитель»; правка заголовка,
которая добавляет или снимает префикс `Draft: `. Отказ до отправки
запроса правки дают: правка заголовка с иной сменой текста и правка любым
другим полем (например, `state_event`).

AC-3. Если токен не получен, функции `forge` для `forge: gitlab` (параметр
`target` — имя проекта, `str`) возвращают именованную причину, а
подменённый транспорт не вызван. Проверяются три случая подменённого
`gitcmd.hosting_token`: `(None, None)` — причина содержит «токен не
получен»; `(None, <отказ>)` из-за пустого слота; `(None, <отказ>)` из-за
процесса роли.

AC-4. `forge.pipeline_status` для GitLab на подменённых ответах API даёт
`green` в двух случаях. Первый — задания `success` и `manual`. Второй —
задание `created` или `skipped` стадией позже задания `manual` того же
конвейера, не перечисленное в `policy.ci_required_jobs`.

AC-5. `pipeline_status` для GitLab:
- задание `created`, перечисленное в `policy.ci_required_jobs` записи, —
  итог не `green`;
- задание `created`, перед которым в более ранней стадии нет задания
  `manual`, хотя оно не перечислено в `ci_required_jobs`, — `running`;
- задание `skipped`, перед которым в более ранней стадии нет задания
  `manual`, хотя оно не перечислено в `ci_required_jobs`, — `unknown`;
- запись без поля `policy.ci_required_jobs`: задание `manual` (при
  остальных `success`) — `green`.

AC-6. `pipeline_status`: задание `failed` без права падать → `red`;
задание `failed` с правом падать (`allow_failure`) → `green` с пометкой,
которая называет это задание.

AC-7. `pipeline_status`:
- у sha два конвейера (ветка и MR), один из них `red` → `red`;
- задание `running`, `pending`, `waiting_for_resource`, `preparing` или
  `scheduled` без `failed` → `running`;
- конвейеров у sha нет → `none` с причиной «конвейер не создан (ветка не
  под правилом workflow?)».

AC-8. `pipeline_status` даёт `unknown` с причиной в шести случаях:
- задание `canceled` без права падать;
- конвейер `canceled`;
- статус задания не из перечисленных в требовании 5;
- статус конвейера не из перечисленных в требовании 5 (например,
  `skipped`), при всех заданиях `success`;
- число прочитанных заданий не совпало с `X-Total`;
- число прочитанных конвейеров sha не совпало с `X-Total`.

Кроме того, задание `failed` на второй странице выдачи даёт `red`, а не
`green`: проверяется число вызовов транспорта по страницам. Конвейер
`red` на второй странице списка конвейеров sha тоже даёт `red`.

AC-9. `forge.job_result` для GitLab в конвейере с двумя заданиями разных
статусов возвращает статус задания с запрошенным именем. Если задания с
таким именем нет — именованная причина. Если у имени несколько попыток —
статус последней.

AC-10. `forge.job_test_report` для GitLab разбирает фикстуру отчёта тестов
GitLab (`test_suites[].test_cases[]`) в отображение `<classname>::<name>`
→ исход. Два теста с одинаковым `name` в разных `classname` дают два
разных ключа. Совпадение ключей в одном отчёте даёт `None` с причиной
«неоднозначный идентификатор». Отсутствующий или истёкший отчёт даёт
`None` с причиной.

AC-11. Ответы 401, 403, 404, 429, 5xx и таймаут транспорта — именованные
причины, а не исключения. На 429/5xx запрос повторяется ограниченное число
раз, на 401/403/404 и на таймаут — не повторяется. Проверяется по числу
вызовов подменённого транспорта.

AC-12. Фикстурное значение токена не встречается в журнале шагов и в
тексте именованных причин ошибок (включая 401/403).

AC-13. `forge.pipeline_status` для `forge: github` берёт итог из чтения
check runs `ci` (подменённого) и не вызывает транспорт GitLab. На
подменённых check runs итоги такие (требование 2):
- все runs `completed` с исходами `success`, `skipped`, `neutral` — `green`;
- один run `failure` (то же для `cancelled` и `timed_out`) при остальных
  `success` — `red`;
- один run `in_progress` (то же для `queued`) при остальных `success` —
  `running`;
- пустой список runs — `none`;
- run с исходом `action_required` при остальных `success` — `unknown`;
- чтение check runs не удалось — `unknown`.

Реализация с постоянным `green` на непустом ответе этот критерий не
проходит. Остальные функции `forge` для `forge: github` (`job_result`,
`job_test_report`, `open_mr`, `undraft_mr`, `assign_mr`, `mr_status`,
`token_user`, `token_expiry`, `protections`, сведения проекта, последний
конвейер ветки) возвращают именованный отказ «не реализовано для github»,
не вызывая ни `gh`, ни транспорт GitLab.

AC-14. Для записи `forge: gitlab` на подменённом транспорте каждый итог
`pipeline_status` (`green`, `red`, `running`, `none`, `unknown`) даёт
значения `ci.verifying_status`, `ci.verifying_is_red`,
`ci.red_status_sha`, `ci.branch_status`, `ci.status_kind` и
`ci.failed_check_names` по таблице требования 8; `gh` не вызван. Ни
`none`, ни `unknown`, ни `red` не дают `VERIFYING_GREEN` и не дают
`branch_status` = `True`. Итог `unknown` даёт ровно `VERIFYING_NONE`; итог
`running` даёт `failed_check_names` = `(set(), …)`. `ci.head_sha` для
`forge: gitlab` читает голову локально и транспорт не вызывает; сигнатура
`head_sha` не изменена.

AC-15. Для записи `forge: gitlab` функции `ci.main_line_status`,
`ci.trigger_rerun`, `ci.find_run_id` и `ci.check_run_workflow_run`
возвращают именованный отказ «не поддержано для gitlab». Они не обращаются
ни к `gh`, ни к HTTP. Кроме того:
- отказ `trigger_rerun` содержит «не запущен», и `ci.rerun_started` на нём
  даёт `False`;
- `main_line_status` отдаёт вид `ci.MAIN_UNKNOWN`;
- `find_run_id` и `check_run_workflow_run` отдают `("", причина)`.

AC-16. `pipeline_status` для GitLab по статусу самого конвейера
(требование 5):
- конвейер `failed`, все видимые задания `success` → `red`;
- конвейер `manual`, задания `success` и `manual` → `green`;
- конвейер `running`, все видимые задания `success` → `running`, не
  `green`.

AC-17. В `orchestrator/forge.py` и `orchestrator/gitlab_adapter.py`
обращения к `urllib` и `http.client` стоят только внутри одной функции
транспорта `gitlab_adapter`, а саму функцию транспорта вызывает только
функция запроса. Проверяется разбором `ast` обоих модулей. Сторож ловит:
- вставленный вне транспорта вызов `urllib.request.urlopen`;
- импорт имени из `urllib` или `http.client` вне транспорта
  (`from urllib.request import urlopen`, в том числе с псевдонимом
  `as …`) и вызов такого имени или псевдонима вне транспорта;
- вызов транспорта из функции, которая не является функцией запроса.

Ссылки вне транспорта на классы исключений `urllib.error` (например,
`URLError`, `HTTPError` в `except`) и их импорт нарушением не считаются.

AC-18. Подменённый транспорт поднимает `URLError` (отказ соединения).
Функции адаптера возвращают причину, которая начинается с «сеть
недоступна:», а не исключение. `pipeline_status` даёт `unknown` с этой
причиной.

AC-19. `pipeline_status` для GitLab: конвейер `manual`, задания `success`
и задание `manual`, перечисленное в `policy.ci_required_jobs` записи, →
`running`, не `green`. То же задание `manual` вне
`policy.ci_required_jobs` → `green`.

AC-20. `pipeline_status` для GitLab: фикстура выдачи заданий идёт в
порядке убывания id. Задание `manual` стадии с меньшими id и задание
`created` стадии с большими id (вне `policy.ci_required_jobs`) → `green`.
Задание `created` стадии с меньшими id и задание `manual` стадии с
большими id → не `green`.

AC-21. Разбор `ast`: в `orchestrator/ci.py` поле `forge` записи проекта
(индекс или `.get` с ключом `"forge"`) встречается только как аргумент
вызова функции модуля `forge`, иных обращений к нему нет. В `ci.py` нет
сравнения (`==`, `!=`, `in`, `not in`) результата вызова функции модуля
`forge` с литералом значения `forge` (`"github"`, `"gitlab"`) или с
`targets.FORGES[...]`. В `orchestrator/forge.py` реализация выбирается
индексом словаря-реестра по значению поля `forge`; сравнений этого
значения с литералами (`==`, `!=`) нет, проверка членства в реестре
(`<значение> in <реестр>`) нарушением не считается. Сторож ловит:
- вставленное в `ci.py` ветвление `if entry["forge"] == targets.FORGES[1]:`;
- вставленное в `ci.py` сравнение `forge.<функция>(target) == "gitlab"`;
- выбор реализации в `forge.py` через `if <значение> == "gitlab":` вместо
  индекса реестра.

Проверка членства `if <значение> not in <реестр>:` в `forge.py` сторож не
краснит.

AC-22. `pipeline_status` для GitLab на сочетаниях статусов следует
старшинству `red` → `unknown` → `running` → `none` → `green`
(требование 5):
- задание `failed` и задание `canceled`, оба без права падать → `red`;
- конвейер `running`, задание `failed` без права падать → `red`;
- конвейер `canceled`, задание `failed` без права падать → `red`;
- задание `failed` без права падать, число прочитанных заданий не
  совпало с `X-Total` → `unknown`;
- задание `canceled` и задание `running`, оба без права падать →
  `unknown`;
- два конвейера sha: `red` и `unknown` → `red`; `unknown` и `running` →
  `unknown`; `running` и `green` → `running`.

AC-23. `forge.pipeline_status` для GitLab получает запись проекта
загрузчиком `targets.target(<имя проекта>)`: тест подменяет загрузчик
записи, а не передаёт словарь записи в функцию. Подменённый загрузчик
отдаёт плоскую запись `forge: gitlab` с ключом `"ci_required_jobs"`
(форма `targets._flatten` для поля `policy.ci_required_jobs`), в списке —
имя задания `manual`; конвейер `manual`, прочие задания `success` → итог
не `green`. Та же запись без ключа `"ci_required_jobs"` → `green`.

AC-24. `forge.open_mr` для GitLab на подменённом транспорте делает ровно
пару `POST /projects/:id/merge_requests` (`:id` — проект из `url` записи);
в теле запроса — ветка, база, заголовок, описание и исполнитель из
аргументов; при `draft=True` заголовок несёт префикс `Draft: `, при
`draft=False` — нет. Номер (`iid`) и адрес MR из ответа фикстуры
возвращаются разобранными.

AC-25. `forge.undraft_mr` для GitLab на подменённом транспорте правит MR
парой `PUT /projects/:id/merge_requests/:iid`, в теле которой только
заголовок — прежний без префикса `Draft: `; ответ фикстуры разобран в
результат без признака черновика.

AC-26. `forge.assign_mr` для GitLab на подменённом транспорте правит MR
парой `PUT /projects/:id/merge_requests/:iid`, в теле которой только поле
исполнителя с переданным значением; исполнитель из ответа фикстуры
возвращается разобранным.

AC-27. `forge.mr_status` для GitLab на подменённом транспорте делает
пару `GET /projects/:id/merge_requests/:iid`; состояние, признак черновика
и исполнитель из ответа фикстуры возвращаются разобранными.

AC-28. `forge.token_user` для GitLab на подменённом транспорте делает
пару `GET /user`; имя пользователя из ответа фикстуры возвращается
разобранным.

AC-29. `forge.token_expiry` для GitLab на подменённом транспорте делает
пару `GET /personal_access_tokens/self`; дата `expires_at` из ответа
фикстуры возвращается разобранной, а `expires_at: null` — признаком «без
срока».

AC-30. `forge.protections` для GitLab на подменённом транспорте делает
пары `GET /projects/:id/protected_branches` и
`GET /projects/:id/protected_tags`; имена защищённых веток и тегов из
ответов фикстуры возвращаются разобранными.

AC-31. Функция сведений проекта `forge` для GitLab на подменённом
транспорте делает пару `GET /projects/:id`; ветка по умолчанию
(`default_branch`) и уровень доступа пользователя токена (из
`permissions`) возвращаются разобранными, прочие поля ответа фикстуры в
результат не попадают.

AC-32. Функция последнего конвейера ветки `forge` для GitLab на
подменённом транспорте делает пару
`GET /projects/:id/pipelines?ref=<ветка>` и читает задания этого
конвейера; sha, итог и задания (имена и статусы) последнего конвейера из
ответов фикстуры возвращаются разобранными.

## Оценка объёма и деление
Сработавшие сигналы:
- критериев приёмки 32 (≥ 10);
- `budget_usd` $50 (≥ $30);
- зона задевает механизм, на который опирается инвариант 19
  («неизвестный статус не зелёный», `ci.py`).

Эта задача уже — часть 1 деления родителя 01M5W670PHF08VPZWDRM5BY56W
(ANSWER-1 родителя, п. 4; рамка $50 — решение Оператора). Материал для
решения о монолите: дальнейший разрез по зонам (`forge.py` +
`gitlab_adapter.py` против `ci.py` + `github_adapter.py`) не даёт
самостоятельно мержимых частей. Реализация GitHub в `forge`
(требование 2) оборачивает чтение check runs из `ci.py`, а GitLab-ветка
`ci` (требование 8) зовёт `forge.pipeline_status` — части связаны в обе
стороны. Без ветки `ci` интерфейс `forge` не имеет потребителя, а без
`forge` у `ci` нет источника итога GitLab. Инвариант 19 держит
`tests/test_invariants.py::MergeNeedsGreenCiTest` без правки, для GitLab
его продолжают AC-8, AC-14, AC-16, AC-19, AC-20, AC-22, AC-23. Решение о монолите — за
Оператором на гейте SPEC.

## Не входит
- `doctor`, команда `forge-probe` и подмена транспорта в
  `tests/sandbox.py` — часть 2 деления родителя.
- Вывод `doctor`/`forge-probe` в части AC-12 родителя — часть 2.
- Создание и снятие черновика MR в потоке задачи — шаги Б1/Б2.
- Чтение отчётов тестов в гейте по исходам — шаг В1.
- Расширение `targets.SUPPORTED_FORGES` — шаг Б2. Условие: для
  `gitlab` не открывать `SUPPORTED_FORGES` до мержа Б1
  (01M5WDB7F14SQ30QVWJY2XYBG2), который объявляет поле.
- Объявление и проверка поля `policy.ci_required_jobs` в схеме записи
  (`orchestrator/targets.py`) — Б1 (01M5WDB7F14SQ30QVWJY2XYBG2). Эта
  задача `targets.py` не трогает и читает поле из плоской записи
  `targets.target()` как `entry.get("ci_required_jobs") or []`. Та же
  форма (ключ `ci_required_jobs` плоской записи, перенос из `policy` в
  `_flatten`) обязательна для Б1; сегодня загрузчик `targets.yaml`
  отказывает неизвестному полю `policy` (`orchestrator/targets.py:441`),
  поэтому сквозная проверка от файла `targets.yaml` — критерий Б1, здесь
  AC-23 подменяет загрузчик `targets.target`.
- Строка срока токена в `doctor` (ориентир части 2): при ошибке HTTP или
  сети — skip с причиной; для `forge: github` такой строки нет.
- Поля ветки и коммитов — шаг Б1; правка `orchestrator/config.py` (его
  зону держит Б1).
- Поведение `ci.accepted_full_suite` для `forge: gitlab` — шаги Б2/В1.
- Правка сторожа А0
  (`tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py`) и его
  `EXEMPT`.
- Зелёность существующих тестов `ci`/`github_adapter` для GitHub без
  правки — её держит пульт (полный набор `tests/` и гейт неослабления).

## Материалы
- `tasks/01M5W670PHF08VPZWDRM5BY56W/SPEC.md` (ссылка
  `refs/artifacts/01M5W670PHF08VPZWDRM5BY56W`), разделы «Требования» и
  «Деление»; там же ANSWER-1 и SPEC-AUDIT родителя.
- Соответствие нумерации: требования 1–9 здесь — требования 1, 2, 3+4,
  5, 6, 7+8, 9, 10, 14 родителя; AC-1…AC-15 — те же номера родителя,
  AC-16 ← AC-19, AC-17 ← AC-20, AC-18 ← AC-22, AC-19 ← AC-23,
  AC-20 ← AC-24. AC-21 и AC-22 — решения гейта SPEC этой задачи (Д-1,
  Д-3); там же — Д-2 (`ci_required_jobs` у Б1), Ф-2 (`(None, None)`,
  тип `target`), уточнение сторожа AC-17 и ориентир строки срока токена.
  AC-23…AC-32 и правка AC-21 (сравнение результата функции `forge` в
  `ci.py`, членство в реестре в `forge.py`) — возврат гейта SPEC №2 этой
  задачи.
- Контракты текстов `ci`: `orchestrator/ci.py:1074` `verifying_is_red`,
  `:1100` `red_status_sha`, `:1247` `status_kind`, `:1679`
  `rerun_started`, `:1282` `MAIN_UNKNOWN`, `:341-344` `VERIFYING_*`,
  `:1115` `failed_check_names` (возвращает множество).
- `orchestrator/github_adapter.py:60` `_is_github_target`;
  `orchestrator/targets.py:29` `SUPPORTED_FORGES`, `:270`
  `unsupported_reason`; `orchestrator/gitcmd.py::hosting_token`.
- `docs/adr/0029-external-delivery-via-mr.md`, п. 8.
- `tests/test_invariants.py::MergeNeedsGreenCiTest`,
  `tests/test_invariants.py::NoNetworkAddressesInTestsTest`.
