---
task: 01M5WCXBM7WCMRWCBWNCHMAR3T
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: GitLab А1.1: интерфейс адаптера, реализация GitLab, подключение ci

Родительская задача: 01M5W670PHF08VPZWDRM5BY56W — GitLab А1: адаптер хостинга — общий интерфейс, реализация GitLab, проверочная команда только на чтение
Зоны: orchestrator/forge.py, orchestrator/gitlab_adapter.py, orchestrator/ci.py, orchestrator/github_adapter.py
Порядок: после 01M5W27CY7K7NR9347NKD8F0NX
Рамка: $50

Часть 1 деления задачи 01M5W670PHF08VPZWDRM5BY56W (ADR-0029 п. 8; шаг А1
после А0 — `targets.unsupported_reason`). Требования и критерии взяты из
SPEC родителя с учётом ANSWER-1 родителя и решений его гейта SPEC 26.10
(О-2…О-9): требования 1–10 и 14; AC-1…AC-15, AC-19, AC-20, AC-22…AC-24.
AC-12
здесь проверяет журнал и тексты причин ошибок; вывод
`doctor`/`forge-probe` проверяет часть 2.

Требуется:
1. Модуль `orchestrator/forge.py`. Реализация выбирается одним реестром в
   `forge.py` — словарём, ключи которого — значения поля `forge`; выбор —
   поиском по ключу, без сравнения с литералами. `ci.py` выбирает
   реализацию через `forge`. Иных сравнений значения `forge` с литералами
   `"github"`/`"gitlab"` нет. Сторож А0
   `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py::test_ac9_no_support_literals_outside_targets`
   не правится: запись `EXEMPT` для `forge.py` не нужна и не добавляется.
   Функции:
   - `pipeline_status(target, sha)` — итог
     `green`/`red`/`running`/`none`/`unknown` с причиной и задания с
     именами и статусами;
   - `job_result(target, sha, job_name)`;
   - `job_test_report(target, sha, job_name)` — «идентификатор теста →
     исход» или `None` с причиной;
   - `open_mr(target, branch, base, title, body, draft, assignee)`,
     `undraft_mr(target, mr)`, `assign_mr(target, mr, assignee)`,
     `mr_status(target, mr)`;
   - только чтение: `token_user(target)`, `token_expiry(target)`,
     `protections(target)`, «сведения проекта» (ветка по умолчанию и
     уровень доступа токена), «последний конвейер ветки» (sha, итог,
     задания).
2. Реализация GitHub. `pipeline_status` оборачивает нынешнее чтение check
   runs `ci` без изменения его поведения. Итог по check runs, по порядку:
   есть `failure`/`cancelled`/`timed_out` — `red`; есть
   `queued`/`in_progress` — `running`; check runs нет — `none`; все
   `success`/`skipped`/`neutral` — `green`; иное — `unknown`. Остальные
   функции — именованный
   отказ «не реализовано для github», `gh` не вызывается. Внешние входы
   `ci.py`/`github_adapter.py` сохраняют сигнатуры и поведение для GitHub.
3. Модуль `orchestrator/gitlab_adapter.py`: HTTP API v4 средствами
   стандартной библиотеки. Сервер и путь проекта — из `url` записи. Токен
   — слот `token_slot`, заголовок `PRIVATE-TOKEN`; в журнал, вывод и
   сообщения ошибок он не попадает. Если токен не получен (нет слота,
   отказ, пустой слот, процесс роли), запроса нет, возвращается
   именованная причина.
4. Единственная функция запроса с таблицей разрешённых пар «метод —
   шаблон пути». Разрешено:
   - чтение конвейеров по sha;
   - чтение конвейеров ветки (`GET /projects/:id/pipelines?ref=`);
   - чтение проекта (`GET /projects/:id`), из ответа используются только
     `default_branch` и `permissions`;
   - чтение заданий, отчёта тестов, MR, пользователя токена, сведений о
     токене, защищённых веток и тегов;
   - создание MR;
   - правка MR: «исполнитель» и заголовок, причём заголовок может только
     получить или потерять префикс `Draft: `.

   Иная пара (в том числе участники `/members…`) или иная смена заголовка
   — отказ до отправки запроса, с именем пары. `urllib`/`http.client`
   вызываются только в одной функции транспорта `gitlab_adapter`, которую
   подменяют тесты; транспорт вызывается только функцией запроса.
5. Зелёный CI:
   - берутся конвейеры ровно этого sha; если их несколько — зелёными
     должны быть все. Список конвейеров sha читается постранично со
     сверкой числа с `X-Total`;
   - статус самого конвейера: `green` возможен только при `success` или
     `manual` и при соблюдении правил заданий ниже; `failed` — `red`
     (даже при всех видимых заданиях `success`);
     `running`/`pending`/`waiting_for_resource`/`preparing`/`scheduled`
     — `running`; `canceled` или иной статус — `unknown`; ни в одном из
     этих случаев не `green`;
   - завершённые задания без права падать — `success`;
   - `manual` допустимо, если задание вне `policy.ci_required_jobs` (поле
     читается, если есть); `manual` из `policy.ci_required_jobs` — итог
     `running`, не `green`;
   - `created`/`skipped` допустимо, только если в том же конвейере есть
     `manual` в более ранней стадии и задание вне
     `policy.ci_required_jobs`;
   - порядок стадий — по наименьшему id задания стадии (меньше — раньше),
     не по порядку выдачи API;
   - `failed` без права падать — `red`;
   - `running`/`pending`/`waiting_for_resource`/`preparing`/`scheduled` —
     `running`;
   - конвейера нет — `none` с причиной «конвейер не создан (ветка не под
     правилом workflow?)»;
   - `unknown` с причиной: `canceled` у задания без права падать или у
     конвейера, неизвестный статус задания или конвейера, неполная выдача. Задания читаются
     постранично до конца со сверкой числа с `X-Total`;
   - `unknown` и `none` никогда не `green`;
   - упавшее задание с правом падать — пометка в итоге с именем задания.
6. `job_result`: статус задания с запрошенным именем; если задания нет —
   именованная причина; если попыток несколько — статус последней.
   `job_test_report`: ключ `<classname>::<name>`; совпадение ключей —
   `None` с причиной «неоднозначный идентификатор»; отчёта нет или он
   истёк — `None` с причиной.
7. Ошибки HTTP (401, 403, 404, 429, 5xx, таймаут) — именованные причины.
   Повтор — только на 429/5xx, ограниченно. Прочие `URLError` и отказ
   соединения — причина «сеть недоступна: <текст>»; для `pipeline_status`
   — итог `unknown` с этой причиной.
8. `ci` для `forge: gitlab`:
   - `verifying_status`, `branch_status` и `failed_check_names` берут итог
     через `forge.pipeline_status` и отображают его в виды GitHub по
     таблице требования 10 SPEC родителя. `red` даёт `note` с «CI коммита
     <sha[:8]> не зелёный:». `running` даёт «ещё идёт» и
     `failed_check_names` = пустое множество. `none` и `unknown` дают
     `VERIFYING_NONE` и «неизвестен» и не бывают зелёными;
   - `head_sha` остаётся локальным, транспорт не вызывается;
   - `main_line_status`, `trigger_rerun`, `find_run_id` и
     `check_run_workflow_run` возвращают именованный отказ «не поддержано
     для gitlab» без вызова `gh`. Отказ `trigger_rerun` содержит «не
     запущен». `main_line_status` отдаёт вид `MAIN_UNKNOWN`.
     `find_run_id`/`check_run_workflow_run` отдают `("", причина)`.
9. Константы `TOKEN_EXPIRY_WARN_DAYS = 14`, `TOKEN_NO_EXPIRY_TASKS_WARN =
   10`, число повторов и таймаут живут в `gitlab_adapter.py`/`forge.py`.
   `orchestrator/config.py` не трогать: его зону держит Б1.
   `targets.SUPPORTED_FORGES` не расширяется.

Не входит: `doctor`, команда `forge-probe` и подмена транспорта в
`tests/sandbox.py` (часть 2); создание и снятие
черновика MR в потоке задачи (Б1/Б2); чтение отчётов в гейте по исходам
(В1); расширение `SUPPORTED_FORGES` (Б2); поля ветки и коммитов (Б1);
поведение `ci.accepted_full_suite` для `forge: gitlab` (Б2/В1); правка
сторожа А0 и его `EXEMPT`. Существующие тесты `ci`/`github_adapter` для GitHub остаются зелёными без
правки.