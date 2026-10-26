---
task: 01M5W670PHF08VPZWDRM5BY56W
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/forge.py, orchestrator/gitlab_adapter.py, orchestrator/ci.py, orchestrator/github_adapter.py, orchestrator/doctor/misc_checks.py, orchestrator/doctor/cli.py, orchestrator/artel.py
merge_after: 01M5W27CY7K7NR9347NKD8F0NX
budget_usd: 70
---

# SPEC: GitLab А1 — адаптер хостинга: общий интерфейс, реализация GitLab, проверочная команда только на чтение

## Контекст
Хостинг проекта сейчас — только GitHub через `gh`: `orchestrator/ci.py`
(внешние входы `verifying_status`, `main_line_status`, `branch_status`,
`head_sha`, `failed_check_names`, `trigger_rerun`, `accepted_full_suite`,
`find_run_id`, `check_run_workflow_run`, `gh`) и
`orchestrator/github_adapter.py` (`ensure_draft_mr`, `undraft_mr`,
`ensure_head_in_origin`; `_is_github_target` пропускает не-GitHub);
`doctor/misc_checks.py:check_base_branch` для не-GitHub отдаёт `skip`.
ADR-0029 (принят 26.10.2026), п. 8 вводит проект на GitLab; шаг А1 —
адаптер хостинга после А0 (`targets.unsupported_reason`). Токен проекта —
слот связки ключей `token_slot` записи (для `gh` — `GH_TOKEN`,
`doctor/misc_checks.py::gh_env`). Внешние HTTP-адреса в тестах запрещены
сторожем `tests/test_invariants.py::NoNetworkAddressesInTestsTest` — сеть в
тестах только подменой.

## Требования

1. **Интерфейс адаптера** — новый модуль `orchestrator/forge.py`, функции
   выбирают реализацию по полю `forge` записи проекта:
   - `pipeline_status(target, sha)` — итог CI ровно этого sha (`green` /
     `red` / `running` / `none` с причиной) и список заданий с именами и
     статусами;
   - `job_result(target, sha, job_name)` — статус задания по имени в
     конвейере этого sha;
   - `job_test_report(target, sha, job_name)` — разобранный отчёт тестов
     задания (идентификатор теста → исход) либо `None` с причиной;
   - `open_mr(target, branch, base, title, body, draft, assignee)`,
     `undraft_mr(target, mr)`, `assign_mr(target, mr, assignee)`,
     `mr_status(target, mr)`;
   - `token_user(target)`, `token_expiry(target)`, `protections(target)` —
     только чтение.
   Реализация GitHub — обёртка над нынешними `ci`/`github_adapter` без
   изменения их поведения и вывода; внешние входы `ci.py` сохраняют
   сигнатуры и для GitHub работают как сейчас.
2. **Реализация GitLab** — новый модуль `orchestrator/gitlab_adapter.py`:
   HTTP API v4 средствами стандартной библиотеки (без новых зависимостей);
   адрес сервера и путь проекта — из `url` записи; токен — из слота
   `token_slot`, передаётся заголовком `PRIVATE-TOKEN` и не попадает в
   журнал, вывод и сообщения ошибок.
3. **Единственная функция запроса** `gitlab_adapter` с таблицей
   разрешённых пар «метод — шаблон пути»: чтение конвейеров по sha,
   заданий конвейера, отчёта тестов конвейера/задания, MR, пользователя
   токена, сведений о токене, защищённых веток и тегов; создание MR; правка
   MR только полями «черновик» (заголовок) и «исполнитель». Любая другая
   пара (слияние, закрытие MR, комментарии, запуск/повтор/отмена заданий,
   теги, релизы, ветки, настройки, переменные, участники) — отказ до
   отправки запроса, с именем пары.
4. **Зелёный CI на GitLab** (ADR-0029 п. 8), итог `pipeline_status`:
   - берутся конвейеры ровно этого sha; если их несколько (ветка и MR) —
     зелёными должны быть все;
   - все завершённые задания без права падать — `success`;
   - задания `created`/`skipped`/`manual` допустимы, только если стоят за
     ручным заданием и не перечислены в `policy.ci_required_jobs` записи
     (поле читается, если есть; его объявление — шаг Б1);
   - есть `failed` без права падать — `red`;
   - есть `running`/`pending` — `running`;
   - конвейера нет — `none` с причиной «конвейер не создан (ветка не под
     правилом workflow?)»;
   - упавшее задание с правом падать — пометка в итоге (для ревьюера).
5. **Ошибки HTTP** GitLab (401, 403, 404, 429, 5xx, таймаут) — именованные
   причины, не исключения; повтор — только на 429/5xx, с ограниченным
   числом попыток.
6. **Подключение к потребителям без изменения поведения для GitHub:**
   `verifying_status`, `branch_status`, `head_sha`, `failed_check_names`
   `ci.py` для проекта с `forge: gitlab` идут через
   `forge`/`gitlab_adapter`. `main_line_status`, `trigger_rerun`,
   `find_run_id` для `forge: gitlab` — именованный отказ «не поддержано
   для gitlab».
7. **`doctor`:** `check_base_branch` для `forge: gitlab` — сверка базовой
   ветки через адаптер вместо `skip` (исходы — как у ветки GitHub той же
   функции: сходится — `ok`, расходится — `warn`, сверка невозможна —
   `skip` с именованной причиной адаптера). Отдельная строка `doctor` о
   сроке токена GitLab: предупреждение, если до истечения не больше
   `gitlab_adapter.TOKEN_EXPIRY_WARN_DAYS` дней; токен без срока —
   информационно. Строка регистрируется в `doctor/cli.py`.
8. **Команда `forge-probe <проект> [--job <имя>]`** (`orchestrator/artel.py`)
   — только чтение: пользователь токена и его роль в проекте, срок токена,
   защищённые ветки и теги, последний конвейер базовой ветки (sha, итог,
   задания); при `--job` — сводка отчёта тестов задания (число тестов по
   исходам). Ничего не создаёт и не меняет; вызовы — только чтение из
   белого списка требования 3.
9. **Поддержка остаётся закрытой:** `targets.SUPPORTED_FORGES` в этой задаче
   не расширяется. `forge-probe` и `doctor` работают и для записи с
   неподдержанным хостингом (только чтение).
10. Константы адаптера (`TOKEN_EXPIRY_WARN_DAYS`, число повторов, таймаут)
    живут в `gitlab_adapter.py`/`forge.py`, не в `orchestrator/config.py`.

## Критерии приёмки

AC-1. Каждая запрещённая пара функции запроса `gitlab_adapter` — слияние
MR, закрытие MR, комментарий, запуск задания, повтор задания, удаление
ветки, создание тега — отказ до вызова HTTP: подменённый транспорт не
вызван, причина отказа называет пару.

AC-2. Каждая разрешённая пара требования 3 (чтение конвейеров по sha,
заданий, отчёта тестов, MR, пользователя токена, сведений о токене,
защищённых веток и тегов; создание MR; правка MR полями «черновик» и
«исполнитель») доходит до подменённого транспорта; правка MR любым другим
полем (например, `state_event`) — отказ до транспорта.

AC-3. `forge.pipeline_status` для GitLab на подменённых ответах API:
конвейер с заданиями `success` и `manual` (за ручным заданием) → `green`.

AC-4. `pipeline_status`: задание в `created`, перечисленное в
`policy.ci_required_jobs` записи → итог не `green`.

AC-5. `pipeline_status`: задание `failed` без права падать → `red`.

AC-6. `pipeline_status`: задание `failed` с правом падать (`allow_failure`)
→ `green` с пометкой, называющей это задание.

AC-7. `pipeline_status`: у sha два конвейера (ветка и MR), один из них
`red` → `red`; задание `running`/`pending` без `failed` → `running`.

AC-8. `pipeline_status`: конвейеров у sha нет → `none` с причиной
«конвейер не создан (ветка не под правилом workflow?)».

AC-9. `forge.job_test_report` для GitLab разбирает фикстуру отчёта тестов
GitLab в отображение «идентификатор теста → исход»; при отсутствующем или
истёкшем отчёте — `None` с причиной.

AC-10. Ответы 401, 403, 404, 429, 5xx и таймаут транспорта — именованные
причины, а не исключения; на 429/5xx запрос повторяется ограниченное число
раз, на 401/403/404 — не повторяется (число вызовов подменённого
транспорта).

AC-11. Фикстурное значение токена не встречается в журнале шагов, выводе
`doctor`, выводе `forge-probe` и тексте именованных причин ошибок
(включая 401/403).

AC-12. `ci.main_line_status`, `ci.trigger_rerun`, `ci.find_run_id` для
записи `forge: gitlab` возвращают именованный отказ «не поддержано для
gitlab», не обращаясь ни к `gh`, ни к HTTP.

AC-13. `ci.verifying_status`, `ci.branch_status`, `ci.head_sha`,
`ci.failed_check_names` для записи `forge: gitlab` берут данные через
`forge`/`gitlab_adapter` (подменённый транспорт вызван, `gh` — нет); для
`forge: github` их сигнатуры не изменены.

AC-14. `doctor.check_base_branch` для `forge: gitlab` на подменённом API:
база совпадает — `ok`, расходится — `warn`; строка срока токена: срок через
`TOKEN_EXPIRY_WARN_DAYS` дней или меньше — `warn`, токен без срока —
информационная строка, не `warn`.

AC-15. `forge-probe <проект> --job <имя>` на подменённом API печатает
пользователя токена и роль, срок токена, защищённые ветки и теги,
последний конвейер базовой ветки (sha, итог, задания) и сводку отчёта
тестов по исходам; все вызовы транспорта за прогон — метод `GET`; команда
работает для записи с неподдержанным хостингом.

## Оценка объёма и деление
Сработавшие сигналы: файлов зоны 7 (≥ 5); критериев приёмки 15 (≥ 10);
рамка Оператора $70 (`budget_usd` ≥ $30).

Решение — **нарезка на 2 части** по границам зон:

- Часть 1 «механика адаптера и подключение `ci`» (требования 1–6, 9–10;
  AC-1…AC-13, AC-11 — в части журнала и ошибок): `forge.py`,
  `gitlab_adapter.py`, `ci.py`, `github_adapter.py`. Это механика, на
  которую опирается часть 2. Самостоятельно мержима: GitHub-поведение
  `ci`/`github_adapter` не меняется, GitLab-ветка закрыта
  `SUPPORTED_FORGES` (требование 9), новые функции покрыты тестами на
  подменённом транспорте — промежуточного нерабочего состояния нет.
- Часть 2 «doctor и `forge-probe`» (требования 7–9; AC-11 в части вывода,
  AC-14, AC-15): `doctor/misc_checks.py`, `doctor/cli.py`, `artel.py`.
  Пользуется `forge.token_user/token_expiry/protections/pipeline_status/
  job_test_report` части 1 — без неё не имеет смысла; после неё мержима
  отдельно, только читает.

Рамки: часть 1 — $45 (до 15 критериев, 4 файла, две итерации ревью),
часть 2 — $25 (до 5 критериев, 3 файла). Зависимость от А0
(01M5W27CY7K7NR9347NKD8F0NX) заявлена ТЗ строкой «Порядок: после …» и
перенесена в обе части.

## Деление

### GitLab А1.1: интерфейс адаптера, реализация GitLab, подключение ci

Зоны: orchestrator/forge.py, orchestrator/gitlab_adapter.py, orchestrator/ci.py, orchestrator/github_adapter.py
Порядок: после 01M5W27CY7K7NR9347NKD8F0NX
Рамка: $45

Часть 1 деления задачи 01M5W670PHF08VPZWDRM5BY56W (ADR-0029 п. 8, шаг А1
после А0 — `targets.unsupported_reason`). Требования и критерии берутся из
SPEC родителя: требования 1–6, 9, 10; AC-1…AC-13 (AC-11 — журнал и тексты
причин ошибок; вывод `doctor`/`forge-probe` — часть 2).

Требуется:
1. Модуль `orchestrator/forge.py`, выбор реализации по полю `forge` записи:
   `pipeline_status(target, sha)` (итог `green`/`red`/`running`/`none` с
   причиной + задания с именами и статусами), `job_result(target, sha,
   job_name)`, `job_test_report(target, sha, job_name)` («идентификатор
   теста → исход» или `None` с причиной), `open_mr(target, branch, base,
   title, body, draft, assignee)`, `undraft_mr(target, mr)`,
   `assign_mr(target, mr, assignee)`, `mr_status(target, mr)`,
   `token_user(target)`, `token_expiry(target)`, `protections(target)` —
   последние три только чтение. Реализация GitHub — обёртка над нынешними
   `ci`/`github_adapter` без изменения их поведения и вывода; внешние входы
   `ci.py` сохраняют сигнатуры.
2. Модуль `orchestrator/gitlab_adapter.py`: HTTP API v4 стандартной
   библиотекой; сервер и путь проекта — из `url` записи; токен — слот
   `token_slot`, заголовок `PRIVATE-TOKEN`, в журнал, вывод и сообщения
   ошибок не попадает. Единственная функция запроса с таблицей
   разрешённых пар «метод — шаблон пути»: чтение конвейеров по sha,
   заданий, отчёта тестов конвейера/задания, MR, пользователя токена,
   сведений о токене, защищённых веток и тегов; создание MR; правка MR
   только полями «черновик» (заголовок) и «исполнитель». Иная пара —
   отказ до отправки запроса с именем пары.
3. Зелёный CI: конвейеры ровно этого sha (несколько — зелёными все);
   завершённые задания без права падать — `success`;
   `created`/`skipped`/`manual` допустимы только за ручным заданием и вне
   `policy.ci_required_jobs` (читается, если есть); `failed` без права
   падать — `red`; `running`/`pending` — `running`; конвейера нет — `none`
   с причиной «конвейер не создан (ветка не под правилом workflow?)»;
   упавшее задание с правом падать — пометка в итоге.
4. Ошибки HTTP (401, 403, 404, 429, 5xx, таймаут) — именованные причины;
   повтор только на 429/5xx, ограниченно.
5. `ci.verifying_status`, `branch_status`, `head_sha`,
   `failed_check_names` для `forge: gitlab` — через `forge`/
   `gitlab_adapter`; `main_line_status`, `trigger_rerun`, `find_run_id`
   для gitlab — именованный отказ «не поддержано для gitlab».
6. `targets.SUPPORTED_FORGES` не расширяется; константы адаптера — в
   `gitlab_adapter.py`/`forge.py`, `orchestrator/config.py` не трогать
   (зону держит Б1).

Не входит: `doctor` и команда `forge-probe` (часть 2); создание/снятие
черновика MR в потоке задачи (Б1/Б2); чтение отчётов в гейте по исходам
(В1); расширение `SUPPORTED_FORGES` (Б2); поля ветки и коммитов (Б1).
Существующие тесты `ci`/`github_adapter` для GitHub — зелёные без правки.

### GitLab А1.2: doctor и проверочная команда forge-probe

Зоны: orchestrator/doctor/misc_checks.py, orchestrator/doctor/cli.py, orchestrator/artel.py
Порядок: после части 1, 01M5W27CY7K7NR9347NKD8F0NX
Рамка: $25

Часть 2 деления задачи 01M5W670PHF08VPZWDRM5BY56W (ADR-0029 п. 8, шаг
А1). Опирается на `orchestrator/forge.py` и `orchestrator/gitlab_adapter.py`
части 1 (только чтение). Требования и критерии — из SPEC родителя:
требования 7–9; AC-11 (вывод `doctor`/`forge-probe`), AC-14, AC-15.

Требуется:
1. `doctor/misc_checks.py:check_base_branch` для `forge: gitlab` — сверка
   базовой ветки через адаптер вместо `skip`: сходится — `ok`,
   расходится — `warn`, сверка невозможна — `skip` с именованной причиной
   адаптера (как ветка GitHub той же функции).
2. Строка `doctor` о сроке токена GitLab: предупреждение за
   `gitlab_adapter.TOKEN_EXPIRY_WARN_DAYS` дней и меньше; токен без срока —
   информационно; регистрация строки в `doctor/cli.py`.
3. Команда `forge-probe <проект> [--job <имя>]` в `orchestrator/artel.py` —
   только чтение: пользователь токена и его роль в проекте, срок токена,
   защищённые ветки и теги, последний конвейер базовой ветки (sha, итог,
   задания), при `--job` — сводка отчёта тестов задания (число тестов по
   исходам). Ничего не создаёт и не меняет; только чтение из белого
   списка адаптера.
4. `forge-probe` и `doctor` работают и для записи с неподдержанным
   хостингом. Токен не появляется в выводе `doctor`/`forge-probe`.

Существующие тесты `doctor` для GitHub — зелёные без правки.
`tests/test_doctor.py::BaseBranchCheckTest::test_non_github_forge_is_skipped`
(запись gitlab с `url: file:///nonexistent/sled`) ожидается зелёным без
правки: адаптер не строит адрес сервера из такого `url` → `skip` с
причиной. Потребуется иная правка этого теста — эскалация (мандат
Оператора 26.10 — через гейт SPEC, с матрицей).

Не входит: изменения `forge.py`/`gitlab_adapter.py` сверх нужного части 2
— эскалация; расширение `SUPPORTED_FORGES` (Б2).

## Не входит
- Создание и снятие черновика MR в потоке задачи — шаги Б1/Б2; адаптер
  только даёт функции.
- Чтение отчётов тестов в гейте по исходам — шаг В1.
- Расширение `targets.SUPPORTED_FORGES` — шаг Б2.
- Поля ветки и коммитов, объявление `policy.ci_required_jobs` — шаг Б1.
- Правка `orchestrator/config.py` (зону держит параллельная Б1),
  `orchestrator/targets.py`, `orchestrator/fsm_merge_gate.py`,
  `orchestrator/fsm_advance.py`, `orchestrator/cleanup.py`,
  `docs/adr/0029-external-delivery-via-mr.md`,
  `docs/adr/0003-target-projects.md` — только чтение.
- Зелёность существующих тестов `ci`, `github_adapter`, `doctor` без
  правки — её держит пульт (полный набор `tests/` и гейт неослабления).
  `tests/test_doctor.py:670`
  (`BaseBranchCheckTest::test_non_github_forge_is_skipped`, названный в
  ТЗ кандидатом на правку) по требованию 7 остаётся зелёным: `url`
  `file:///…` не даёт адреса сервера, исход — `skip` с причиной; поэтому
  раздела «Меняемое поведение» нет. Понадобится иная правка — эскалация.

## Материалы
- `tasks/01M5W670PHF08VPZWDRM5BY56W/TZ.md`.
- `docs/adr/0029-external-delivery-via-mr.md`, п. 8 (правила зелёного CI).
- `orchestrator/doctor/misc_checks.py:90` (`check_base_branch`), `:80`
  (`gh_env`); `orchestrator/gitcmd.py::hosting_token`.
- `tests/test_invariants.py::NoNetworkAddressesInTestsTest`.
