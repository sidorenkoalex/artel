---
task: 01M5WCXBM7WCMRWCBWNCHMAR3T
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: GitLab А1.1 — интерфейс адаптера, реализация GitLab, подключение ci

## Фаза A — план
Таблица покрытия PLAN полна: требования 1–9 разнесены на два шага. Шаг 1 — `forge.py` и `gitlab_adapter.py`, шаг 2 — ветка `ci.py`. Оба шага размером с MR. Подход не противоречит архитектуре: реестр `IMPLEMENTATIONS` единственный, а `ci.py` ветвится только через `forge.ci_by_pipeline`. Секция «Влияние на систему» сходится с diff: изменены `ci.py`, добавлены `forge.py`, `gitlab_adapter.py` и `tests/test_forge_gitlab_request.py`. `config.py`, `targets.py`, сторожа А0 и инвариантов не тронуты. Откат — revert. Замечаний к плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | В `forge.py` литералы `"github"`/`"gitlab"` есть только в ключах `IMPLEMENTATIONS`. Выбор — `IMPLEMENTATIONS[value]` после `value not in IMPLEMENTATIONS`. В `ci.py` нет литералов хостинга, нет `FORGES` и поле `forge` не читается: ветвление идёт через `_pipeline_project` → `forge.ci_by_pipeline`. Запись проекта `forge` получает сам, через `targets.target`. Сторож AC-17/AC-21 зелёный. |
| 2 | OK | `_GitHub.pipeline_status` (forge.py) разбирает check runs в порядке «red → running → none → green → unknown». `ci.GREEN` = {success, skipped, neutral}. Остальные функции для github возвращают отказ из `_call` с текстом «не реализовано для github» и `gh` не вызывают. Ветка check runs в ci для github не изменена: `CI_BY_PIPELINE = False`. |
| 3 | OK | Адрес и путь проекта берутся из `url` записи (`_address`, в том числе форма scp), токен — `gitcmd.hosting_token`, передаётся в `PRIVATE-TOKEN`. Пара `(None, None)` даёт отказ «токен не получен», транспорт не вызывается. |
| 4 | OK | `ALLOWED_PAIRS` проверяется через fullmatch, `:id` — только проект записи. Ключи запроса ограничены. У POST и PUT разрешены только перечисленные поля тела. Смена заголовка допускает лишь префикс `Draft: ` (`_title_refusal`: MR читается до правки). Сеть есть только в `transport`, а `transport` зовёт только `request`. |
| 5 | OK | Старшинство — `forge.senior`/`PRECEDENCE`. Конвейеры sha и задания читаются постранично со сверкой `X-Total` (`_read_all`); если заголовка нет, итог `unknown`. Статус самого конвейера учтён. Стадии упорядочены по минимальному id. Задания `manual`/`created`/`skipped` проверяются по `ci_required_jobs` (`entry.get(...) or []`). У `allow_failure` есть пометка с именем задания. |
| 6 | OK | Для попытки берётся наибольший id. Ключ отчёта — `classname::name`; при дубле — `AMBIGUOUS_ID`. Если отчёта нет, он истёк или набор пуст — `None` с причиной. |
| 7 | OK | 401/403/404/429/5xx и таймаут дают разные причины. Повтор только на 429/5xx, всего `RETRY_ATTEMPTS = 3` попытки. `URLError`/`OSError` дают «сеть недоступна: …». |
| 8 | OK | `verifying_status`/`branch_status`/`failed_check_names` следуют таблице через `_pipeline_note`. При красном итоге без упавшего задания причина «краснота без упавшего задания». `main_line_status`/`trigger_rerun`/`find_run_id`/`check_run_workflow_run` отказывают до `gh`. `head_sha` не тронут. |
| 9 | OK | `TOKEN_EXPIRY_WARN_DAYS = 14`, `TOKEN_NO_EXPIRY_TASKS_WARN = 10`, повторы и таймаут объявлены в `gitlab_adapter.py`. `config.py` и `SUPPORTED_FORGES` не тронуты. |

Тесты. Долгоживущие файлы задачи покрывают AC-1…AC-32. Планка — только `markers.py`, без пометок manual/skip. В новом `tests/test_forge_gitlab_request.py` три теста: чужой `:id`, адрес scp, `ci_by_pipeline`. Их долгоживущие файлы не повторяют. Заявки «Ловит мутацию» называют наблюдаемое расхождение. Существующих тестов diff не меняет и не удаляет: правок `tests/` вне новых файлов нет. Карта кодовой базы свежая.

## Замечания
Блокирующих и major нет. Ниже наблюдения для следующих шагов деления (Б1/Б2). В реестр они не заведены: по SPEC этой задачи это не дефекты.

- `orchestrator/gitlab_adapter.py::undraft_mr` распознаёт черновик только по префиксу `Draft: `. GitLab считает черновиком и `[Draft]`, `(Draft)`, `Draft:` без пробела. На таком MR функция вернёт текущий MR с `draft=True` и пустым `reason`. Б2, подключая снятие черновика в поток, должен проверять `draft` результата, а не только `reason`. Расширять формы заголовка SPEC здесь запрещает (требование 4).
- `orchestrator/gitlab_adapter.py::_address` принимает `http://`: тогда токен уйдёт открытым текстом. Адрес задаёт Оператор в записи. Стоит решить в Б1 при объявлении схемы записи.
- `_job_findings`: обязательное задание, которого в конвейере нет вовсе, не мешает `green`. SPEC об этом молчит; это вопрос к Б1, который объявляет `ci_required_jobs`.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Замечаний итерации 1 нет: реестр пуст.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m5wcxbm7wcmrwcbwnchmar3t_forge_guards.py tests/test_01m5wcxbm7wcmrwcbwnchmar3t_gitlab_forge.py tests/test_forge_gitlab_request.py tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py tests/test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard.py` — 236 passed, 45 subtests.
- `python3 -m pytest -q -p no:cacheprovider tests/test_ci_*.py tests/test_github_adapter*.py tests/test_main_ci_line*.py tests/test_invariants.py` — 261 passed, 1128 subtests.
- `artel.py plank-run 01M5WCXBM7WCMRWCBWNCHMAR3T` — отказ «планки нет»: в планке только `markers.py`, все AC вынесены в долгоживущие файлы `tests/`.
- Временная мутация 1: в `_job_findings` правило «manual в более ранней стадии» заменено на «есть любой manual». Красные `test_ac5_without_earlier_manual[created/skipped]` и `test_ac20_stage_order_by_smallest_id[jobs1-False]` (3 failed). Код возвращён (`git checkout`).
- Временная мутация 2: в `_pair_refusal` шаблон `:id` заменён на `[^/]+`. Красный `test_foreign_project_refused_before_transport`. Код возвращён.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` без строки `built_at_sha` — расхождений нет, файл восстановлен. `git status` после всех проверок чистый.

## Предложения системе
- `plank-run` на задаче, у которой все AC ушли в долгоживущие `tests/`, отвечает отказом «планки нет». Ревьюверу и разработчику пригодился бы штатный ответ «AC в long_lived: <файлы>» с прогоном этих файлов (orchestrator/plank_run.py). То же наблюдение есть в PLAN.
