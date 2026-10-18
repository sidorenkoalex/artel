---
task: 01M574A6YQHAPASS9716Z11G4Q
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: CI внешнего проекта при токене без права Checks — итог по Actions runs и проверка прав токена в doctor

## Подход
Монолит, как в SPEC: часть CI (`orchestrator/ci.py`) и часть doctor
(`orchestrator/doctor/project_checks.py`) одним MR.

**CI.** Переход на Actions врезан в три входа сразу после `check_runs`:
`verifying_status`, `branch_status`, `failed_check_names`. Условие —
`_actions_fallback(repo, why)`. Оно истинно, если выполнены оба пункта:
- контекст клона — внешний проект (`_project_context` дал `ctx`; артель —
  никогда, требование 7);
- `why` отказа — HTTP 403 с «Resource not accessible by personal access
  token / by integration» (`checks_forbidden`, публичная, ею же пользуется
  doctor).

Прочие отказы (сеть, 401, 404, 5xx, 403 лимита, неразобранный ответ) идут
прежней веткой без единого запроса Actions (требование 4).

Чтение Actions:
- `_actions_pages` читает постранично и сверяет с `total_count`, как
  `check_runs`. Отсутствие `total_count` — тоже «неизвестен»: полноту не с
  чем сверить, а инвариант 19 запрещает читать неполное зелёным.
- `_actions_runs` берёт запуски `actions/runs?head_sha=` и задания
  `actions/runs/<id>/jobs` КАЖДОГО запуска, в том числе зелёного. Без этого
  не обнаружить неполный ответ заданий (AC-6).

`_actions_verdict` (требование 2):
- запуск с непустым чужим `head_branch` уходит из вердикта (фраза «вне
  вердикта» без подстрок разборщиков);
- красный выигрывает у идущего;
- «идёт»;
- нет завершённого запуска `pull_request` → исход `_no_checks_by_branch`
  у `verifying_status` и «статус неизвестен» у `branch_status`;
- иначе зелёный.

Имена упавших — задания с заключением не из `GREEN`; у красного запуска
без таких заданий — имя запуска. `failed_check_names` по Actions берёт все
события без отбора по ветке; нет запусков или ответа → `(None, причина)`.

Тексты повторяют формулы пути check-runs: «CI коммита <sha8> не зелёный:»,
«… ещё идёт:», «статус CI коммита <sha8> неизвестен: …». Поэтому
`verifying_is_red`/`red_status_sha`/`status_kind` читают их без правки.
Строка `ACTIONS_REASON` дописывается отдельной строкой в конец `note`
каждого исхода по Actions (требование 6), первая строка остаётся строкой
вердикта.

**Выбор константы «неизвестен» у `verifying_status` — `VERIFYING_NONE`.**
Это тот же исход, что у неопределённой головы ветки («статус CI
неизвестен», `ci.py` в начале `verifying_status`) и у `_no_checks_by_branch`,
когда `gh run list` не ответил. Ответа о CI нет вовсе, а `VERIFYING_RUNNING`
утверждал бы, что запуск виден. Для FSM разницы нет: оба ждут потолка
(`fsm_advance.verifying`), `auto` останавливается только на красном.

**doctor.** `check_ci_token` (строка `project-ci-token-<проект>`) добавлена
в `_names`/`project_entry_checks` после `project-token`. В процессе роли
строка — `ROLE_SKIP` без вызова `gh`, у артели — `NOT_APPLICABLE` (общий
путь). Авторизация — `gh_env`. Две пробы `gh api`:
`commits/<база>/check-runs?per_page=1` и
`actions/runs?branch=<база>&per_page=1`.

Порядок исходов:
- нет HTTP-ответа (таймаут, OSError, ненулевой код без «(HTTP n)») → `skip`;
- 403 не про права (лимит запросов) у любого из двух эндпоинтов, в том
  числе у обоих сразу → `skip`;
- Actions отказывают не правами (5xx, неразобранный ответ) → `skip`
  (ANSWER-1: `fail` за Actions — только отказ правами);
- Actions отказывают правами (403 «Resource not accessible …», 401, 404,
  `_GhProbe.denied`) → `fail`;
- check-runs читаются → `ok`;
- check-runs 403 прав → `warn` с текстом SPEC;
- прочий отказ check-runs → `fail`.

Значение токена в detail не попадает: там только текст `gh`.

Возврат из verifying (линт «новый парсинг формата id задачи вне
генератора», прогон 39119775087): код HTTP в `_HTTP_CODE_RE`
(`project_checks.py:249`) разбирается выражением `[1-5][0-9][0-9]` вместо
`\d{3}` — линт не тронут. Коды, которые отдаёт `gh`, — 1xx–5xx, поведение
то же; линт CI повторён локально на диффе ветки к main (те же образцы
`scripts/id_format_patterns.txt`) — совпадений нет; тесты задачи и
`tests/test_ci_actions_fallback.py` — 17 passed.
`doctor/cli.py` правки не потребовал: строки проекта он уже собирает через
`project_entry_checks`.

## Шаги
1. `orchestrator/ci.py`: `CHECKS_FORBIDDEN_TEXTS`, `ACTIONS_REASON`,
   `checks_forbidden`, `_actions_fallback`, `_actions_pages`,
   `_actions_runs`, `_actions_verdict` и входы `_verifying_by_actions`,
   `_branch_by_actions`, `_failed_names_by_actions`; врезки в три
   публичных входа.
2. `orchestrator/doctor/project_checks.py`: `check_ci_token`, `_gh_probe`,
   строка в `project_entry_checks`.
3. `tests/test_ci_actions_fallback.py` — свойства, не покрытые
   долгоживущими файлами:
   - 403 прав только при коде 403;
   - ответ Actions без `total_count` → неизвестен;
   - 403 лимита у Actions в doctor → `skip`;
   - 403 лимита у обоих эндпоинтов → `skip` (ANSWER-1);
   - Actions 502/неразобранный ответ → `skip`, Actions 401/404/403 прав →
     `fail` (ANSWER-1).
   
   Каждый тест проверен временной мутацией (красный → код возвращён).
4. `python3 scripts/codebase_map.py` — карта регенерирована.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1, 3 |
| 5 | 1 |
| 6 | 1 |
| 7 | 1 |
| 8 | 2, 3 |
| 9 | 3 (и долгоживущие файлы задачи) |

Проверка:
- `tests/test_01m574a6yqhapass9716z11g4q_actions_verdict.py` — 10 passed;
- `tests/test_01m574a6yqhapass9716z11g4q_doctor_ci_token.py` — 2 passed;
- тесты затронутых модулей (`test_ci_*`, `test_invariants`, `test_doctor*`,
  внешние CI-тесты задач 01M55V7…, 01M545E…, 01M4PMQ…, 01M46D5…, 01M484R…) —
  зелёные.

## Влияние на систему
Инвариант 19 (неизвестный статус CI не зелёный) на новом пути соблюдён
так же строго, как на пути check-runs, а местами строже:
- неполный, неразобранный и не полученный ответ, а также ответ без
  `total_count` — «неизвестен»;
- зелёный — только при завершённом `pull_request` и всех зелёных запусках.

Существующий путь check-runs и путь артели не меняются: врезка срабатывает
только при `runs is None`, внешнем контексте и 403 прав. AC-9/AC-10
фиксируют это сравнением текстов. Гейты, лимиты и тесты не ослаблены,
существующие тестовые методы не тронуты.

У doctor добавилась строка внешнего проекта и до двух вызовов `gh` на
проект при `doctor` в сессии Оператора; в процессе роли сети нет.

Откат — revert merge-коммита задачи.

## Риски
- Число вызовов `gh` на пути Actions — 1 + число запусков коммита за
  опрос (задания каждого). У проектов с десятками запусков на коммит опрос
  `verifying` станет дороже по лимиту API; для sled это единицы.
- Строка «(HTTP n)» в stderr — формат `gh`. Если он сменится, doctor
  прочтёт HTTP-отказ как обрыв сети, то есть `skip`, а не ложный `ok`.

## Предложения системе
- `plank-run` отказывает, когда планка задачи — только долгоживущие файлы
  `tests/test_<id>_*.py` (нет `acceptance_tests/*.py`). Пришлось гонять их
  напрямую pytest; команде стоит принимать и такую планку
  (`orchestrator/plank_run.py`).
