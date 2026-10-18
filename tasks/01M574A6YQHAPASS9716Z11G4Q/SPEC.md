---
task: 01M574A6YQHAPASS9716Z11G4Q
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/ci.py, orchestrator/doctor/project_checks.py, orchestrator/doctor/cli.py, tests/
budget_usd: 35
---

# SPEC: CI внешнего проекта при токене без права Checks — итог по Actions runs и проверка прав токена в doctor

## Контекст
Живой случай 18.10 (задача sled 01M55SKHZ293CCAK0N7T4H7ZMR, пин 03fa6903):
персональный токен проекта sled получает HTTP 403 «Resource not accessible
by personal access token» на `GET /repos/{owner}/{repo}/commits/{sha}/check-runs`
(`orchestrator/ci.py:224` `check_runs_page`, `:250` `check_runs`), а
`gh run list` (Actions) ему доступен. Поэтому `verifying_status` уходит в
`_no_checks_by_branch` (`ci.py:805`), тот по `gh run list` видит запуск и
отвечает «проверки идут» — до потолка 5400 с и эскалации; итог CI пульт не
узнаёт никогда. `doctor` (`orchestrator/doctor/project_checks.py:220`
`check_project_token`) при этом отвечает `ok`: право читать проверки коммита
не проверяется.

Сверка вызовов `check_runs` и `_no_checks_by_branch` на пути задачи внешнего
проекта (требование 4 ТЗ) — все вызовы в зоне (`orchestrator/ci.py`):
- `ci.py:748` `verifying_status` (и его `_no_checks_by_branch`, `:758`,
  `:769`) — на пути: `verifying` (`fsm_advance.py:453`), автогейт
  (`fsm_autogate.py:287`), `ci-rerun` (`ci_rerun.py:123`, `:158`),
  `acceptance.py:2260`;
- `ci.py:892` `failed_check_names` — на пути: `ci-rerun` для головы ветки и
  вершины main проекта (`ci_rerun.py:276`, `:291`), а также
  `_inherited_from_main` (`ci.py:611`) на красном исходе статуса ветки;
- `ci.py:920` `branch_status` — на пути: гейт мержа (`fsm_merge_gate.py:299`,
  `:353`), ограничения `is_artel` там нет;
- `ci.py:1326` `find_run_id` — на пути ре-рана; при отказе `check_runs`
  уже деградирует на первый красный прогон и зелёным ничего не читает —
  правки не требует;
- `ci.py:969` `accepted_full_suite` — не на пути: для не-артели возврат до
  вызова (`ci.py:967`);
- `ci.py:1213` `main_line_status` — не на пути: вызыватели только артель
  (`pin.py:86`, `fsm_merge_gate.py:583`/`:626` под `is_artel`,
  `doctor/main_ci.py`).
Вне зон находок нет — эскалация до SPEC не нужна.

## Требования

1. Когда чтение check-runs коммита ветки задачи или вершины main внешнего
   проекта отказано правами — HTTP 403 с текстом «Resource not accessible by
   personal access token» или «Resource not accessible by integration», —
   статус CI этого коммита определяется по запускам GitHub Actions этого
   коммита (`/actions/runs?head_sha=<sha>` и задания запусков, право
   Actions: read) того же репозитория проекта. Требование действует на всех
   входах пути задачи внешнего проекта из «Контекста»: `verifying_status`,
   `branch_status`, `failed_check_names` (в том числе через
   `_inherited_from_main`).
2. Итог по Actions (инвариант 19 — неизвестное или неполное не читается
   как зелёное):
   - зелёный — только когда все запуски коммита с триггером, которым CI
     проекта проверяет ветку (у sled — `pull_request`, то же объявление
     workflow, что читает doctor `project-ci-pull-request-<проект>`),
     завершены успешно;
   - есть незавершённый запуск — «проверки идут»;
   - любой красный запуск — красный, с именами упавших заданий (их же
     возвращает `failed_check_names` и называют сводки статуса);
   - у коммита нет запусков — прежнее поведение для коммита без проверок
     («проверок нет»);
   - ответ Actions не получен, не разобран или неполон (заданий/запусков
     меньше обещанного) — статус неизвестен, не зелёный.
3. Причина перехода на Actions видна в выводе статуса одной строкой:
   «check-runs недоступны токену проекта (403) — итог по Actions runs».
4. Прочие ответы чтения check-runs внешнего проекта (сеть, 401, 404, 5xx,
   неразобранный ответ) — исход и тексты как до правки.
5. Артель (свой репозиторий, токен Оператора) — путь и тексты статуса CI
   прежние; это фиксируется тестами до правки, и они остаются зелёными
   после неё.
6. `doctor`: новая проверка для каждого внешнего проекта — читает ли токен
   проекта проверки коммита базовой ветки (check-runs) и запуски Actions.
   Исходы: оба доступны — `ok`; check-runs 403, Actions доступны — `warn` с
   текстом «CI читается по Actions runs; для check-runs токену нужно право
   Checks: read»; Actions недоступны — `fail` (пульт CI проекта не увидит);
   сеть недоступна — `skip` с причиной, не `fail`. Значение токена в вывод
   не попадает.
7. Тесты детерминированы, без сети и реального GitHub: подмена `gh`/ответов
   API на учебном внешнем проекте (403 на check-runs; Actions: идёт /
   зелёный / красный / пусто), сценарии doctor.

## Критерии приёмки

AC-1. Учебный внешний проект, check-runs коммита ветки отвечают 403
«Resource not accessible by personal access token», все Actions-запуски
коммита с триггером проверки ветки завершены успешно: `verifying_status`
даёт зелёный исход, `branch_status` — зелёный, задача выходит из
`verifying`.

AC-2. Тот же проект, один Actions-запуск коммита завершён красным:
`verifying_status` даёт красный исход, его вывод называет имя упавшего
задания; `failed_check_names` для этого коммита возвращает множество с
этим именем.

AC-3. Тот же проект, Actions-запуск коммита ещё идёт: `verifying_status`
даёт исход «проверки идут», `branch_status` — не зелёный.

AC-4. Тот же проект, у коммита нет ни одного Actions-запуска: исход
`verifying_status` тот же, что сегодня у коммита без проверок
(«проверок нет»); `branch_status` не зелёный.

AC-5. При 403 на check-runs ни пустой, ни неполный, ни неразобранный ответ
Actions не даёт зелёного исхода ни у `verifying_status`, ни у
`branch_status`, а `failed_check_names` возвращает «статус неизвестен»
(`None` с причиной), не пустое множество.

AC-6. На исходах AC-1..AC-3 вывод статуса содержит строку «check-runs
недоступны токену проекта (403) — итог по Actions runs»; тексты ответа
403 «Resource not accessible by integration» дают тот же переход на
Actions.

AC-7. Внешний проект, чтение check-runs отказывает сетью, 401, 404, 5xx
или неразобранным ответом: исход и текст `verifying_status`,
`branch_status` и `failed_check_names` совпадают с поведением до правки,
запросов к Actions по `head_sha` не делается.

AC-8. Артель на тех же подменах ответов (включая 403 на check-runs): исход
и текст `verifying_status`, `branch_status`, `failed_check_names` прежние —
тесты, зафиксированные до правки, зелёные и после неё.

AC-9. doctor для внешнего проекта: check-runs и Actions доступны — `ok`;
check-runs 403, Actions доступны — `warn` с текстом «CI читается по
Actions runs; для check-runs токену нужно право Checks: read»; Actions
недоступны — `fail`.

AC-10. doctor для внешнего проекта при обрыве сети — `skip` с причиной, не
`fail`; ни в одном из сценариев AC-9/AC-10 значение токена проекта не
встречается в выводе doctor.

## Оценка объёма и деление
Сработавшие сигналы: `budget_usd` ≥ $30 (рамка ТЗ $35); число критериев
приёмки = 10; зона задевает механизм инварианта 19 `docs/invariants.md`
(неизвестный статус CI не зелёный).

Обоснование монолита (материал для решения Оператора):
- Естественный шов есть — часть CI (`orchestrator/ci.py`, AC-1..AC-8) и
  часть doctor (`orchestrator/doctor/*`, AC-9..AC-10), обе с `tests/`.
  Часть CI мержима отдельно; часть doctor отдельно впереди CI — нет: её
  `warn` утверждает «CI читается по Actions runs», что до части CI ложь.
- Довод за монолит — цена: Оператор дал одну рамку $35 на всё; деление
  добавляет второй проход analyst/аудит SPEC/test_author (~$10 сверх), а
  часть doctor мала (одна проверка в `project_checks.py` и регистрация в
  `cli.py`). Атомарности механики здесь нет — это решение по цене, не по
  неразрезаемости.
- Если Оператор предпочтёт деление: часть 1 — CI (`orchestrator/ci.py`,
  `tests/`), первая; часть 2 — doctor (`orchestrator/doctor/project_checks.py`,
  `orchestrator/doctor/cli.py`, `tests/`), после части 1.

## Не входит
- Мерж через PR.
- Красный main внешнего проекта на гейте мержа (и `main_line_status` для
  внешнего проекта вообще — его вызыватели только артель).
- Смена токена sled — это делает Оператор.
- Задача sled 01M55SKHZ293CCAK0N7T4H7ZMR.
- Правка `find_run_id` (`ci.py:1279`) и `accepted_full_suite`
  (`ci.py:961`) — см. сверку в «Контексте».
- Правка вне зон: `orchestrator/fsm*.py`, `orchestrator/ci_rerun.py`,
  `orchestrator/doctor/main_ci.py`, `orchestrator/targets.py`,
  `targets.yaml`, `docs/backlog.md` — только чтение; потребность в такой
  правке — эскалация.

## Материалы
- ТЗ: `tasks/01M574A6YQHAPASS9716Z11G4Q/TZ.md`.
- Текст эскалации 18.10 — в «Фактах» ТЗ.
- Разбор объявления `pull_request` в workflow клона —
  `orchestrator/doctor/project_checks.py:104` `declares_pull_request`,
  `:133` `check_ci_pull_request`.
