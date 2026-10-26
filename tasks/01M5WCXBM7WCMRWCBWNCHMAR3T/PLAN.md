---
task: 01M5WCXBM7WCMRWCBWNCHMAR3T
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: GitLab А1.1 — интерфейс адаптера, реализация GitLab, подключение ci

## Подход
Три модуля, связанные только через публичные функции.

- `orchestrator/forge.py` — интерфейс хостинга. Типы результатов
  (dataclass `PipelineStatus`, `JobResult`, `TestReport`, `MergeRequest`,
  `TokenUser`, `TokenExpiry`, `Protections`, `ProjectInfo`,
  `BranchPipeline`, `Job`; у каждого все поля со значением по умолчанию и
  поле `reason`), константы итогов `GREEN`/`RED`/`RUNNING`/`NONE`/`UNKNOWN`
  и единственный словарь-реестр `IMPLEMENTATIONS = {"github": _GitHub,
  "gitlab": gitlab_adapter}`. Выбор — `IMPLEMENTATIONS[value]` после
  проверки членства `value not in IMPLEMENTATIONS`; запись проекта
  `forge.py` берёт сам `targets.target(target)`. Функция, которой у
  реализации нет, — результат своего типа с причиной «<функция>: не
  реализовано для <хостинг>» (так для github отказывают все функции,
  кроме `pipeline_status`, без `gh`). `_GitHub.pipeline_status` — обёртка
  над `ci.check_runs` по порядку требования 2. `ci_by_pipeline(target)` —
  признак «итог CI проекта даёт `pipeline_status`, а не check runs ci»;
  `hosting(target)` — значение хостинга для текстов отказа ci.
- `orchestrator/gitlab_adapter.py` — реализация GitLab на HTTP API v4
  (контракты ANSWER-1 В-1…В-5): `transport` — единственное место
  `urllib.request`/`http.client` (4xx/5xx — числом, сеть — `URLError`,
  таймаут — `TimeoutError`); `request(target, method, path, body)` —
  единственная функция, зовущая транспорт: таблица разрешённых пар
  (`:id` — только проект записи), разрешённые поля тела POST/PUT MR,
  сверка заголовка с текущим (чтение MR до правки), токен
  `gitcmd.hosting_token` в `PRIVATE-TOKEN` (пара `(None, None)` — «токен не
  получен»), повтор только 429/5xx (`RETRY_ATTEMPTS`), именованные
  причины 401/403/404/429/5xx/таймаут/«сеть недоступна: …» без токена в
  тексте. Постраничное чтение со сверкой `X-Total` (нет заголовка или
  число не сошлось — неполная выдача). Итог конвейера — старший по
  `red → unknown → running → none → green` из статуса самого конвейера и
  правил заданий требования 5 (стадии — по наименьшему id, обязательные —
  `entry.get("ci_required_jobs") or []`); неполная выдача заданий — `unknown`
  конвейера при любых статусах; причина итога — только причины старшего
  итога (тексты причин не содержат «ещё идёт»/«неизвестен»/«не зелёный:»,
  на которых стоят `status_kind`/`verifying_is_red`).
- `orchestrator/ci.py` — `_pipeline_project(repo)`: имя проекта клона,
  если `forge.ci_by_pipeline` его признаёт. Для такого проекта
  `verifying_status`/`branch_status`/`failed_check_names` строят ответ из
  `forge.pipeline_status` по таблице требования 8; `main_line_status`,
  `trigger_rerun`, `find_run_id`, `check_run_workflow_run` — отказ
  «<что>: не поддержано для <хостинг>» до любого `gh`; `head_sha` не
  меняется. Литералов хостинга и чтения поля `forge` в `ci.py` нет.

Циклический импорт `ci ↔ forge ↔ gitlab_adapter` — только модульные
ссылки, атрибуты читаются при вызове (реестр хранит объект модуля).

## Шаги
1. `forge.py` + `gitlab_adapter.py`; долгоживущие тесты
   `tests/test_01m5wcxbm7wcmrwcbwnchmar3t_*.py` зелёные.
2. Ветка `ci.py`; тесты `tests/test_ci*.py`, `github_adapter`, сторож А0 и
   инвариантов — зелёные; карта `scripts/codebase_map.py`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 2 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1 |
| 5 | 1 |
| 6 | 1 |
| 7 | 1 |
| 8 | 2 |
| 9 | 1 |

## Влияние на систему
Для записей `forge: github` и артели поведение `ci` не меняется: новая
развилка срабатывает только при `forge.ci_by_pipeline(имя) is True`, а
GitHub-реализация отвечает `False`; `targets.SUPPORTED_FORGES` не
расширен, так что GitLab-ветка в потоке задач недостижима. Инвариант 19
(«неизвестный статус не зелёный») для GitLab держится тем, что `green`
даёт только явное правило, а `none`/`unknown`/неполная выдача —
никогда. Сторожа А0 и `tests/test_invariants.py` не правятся.
`config.py`, `targets.py` не трогаются. Откат — revert merge-коммита:
новые модули ни от кого, кроме `ci.py`, не зависят.

## Риски
- Дополнительный вызов `targets.target` в `ci` для внешних проектов —
  подмены записи в старых тестах `ci`. Проверено: `tests/test_ci_*.py`,
  `test_main_ci_line`, `test_invariants`, `test_github_adapter`, сторож А0 и
  тесты внешних проектов `ci` — 311 passed, 1275 subtests.
- Цикл импорта `ci ↔ forge ↔ gitlab_adapter`: аннотации с `forge.*` в
  `ci.py` — строкой, в `gitlab_adapter.py` — `from __future__ import
  annotations`; импорт каждого из трёх модулей первым проверен.
- Тесты: 211 долгоживущих задачи и `tests/test_forge_gitlab_request.py`
  (чужой `:id`, адрес scp, `ci_by_pipeline`) — зелёные; мутации последнего
  проверены временной правкой (все три краснят свой тест).

## Предложения системе
- Планка задачи — только `markers.py`, `plank-run` отвечает «планки нет»:
  при поведении, целиком ушедшем в долгоживущие файлы `tests/`, команда
  могла бы сообщать это штатно, а не отказом (orchestrator/plank_run.py).
