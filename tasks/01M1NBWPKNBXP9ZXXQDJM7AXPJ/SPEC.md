---
task: 01M1NBWPKNBXP9ZXXQDJM7AXPJ
type: spec
author_role: analyst
status: ready
schema_version: 3
budget_usd: 25
---

# SPEC: Сверка свежести ветки против main артели на origin

## Контекст
После A7 запущенная версия пульта живёт на пине (локальный `main` главной
копии, двигается только `pin-update`), а мерж задач пишется в main артели
на origin (`fsm_merge_gate._origin_main_sha`, `fetch origin main`).
Сверка свежести ветки задачи (`fsm._pull_main_or_escalate` — общий узел
для переходов `in_dev -> review`, `acceptance -> merge_gate` и окна
`merge_gate`) при этом считает отставание `gitcmd.commits_behind(branch)`
относительно ЛОКАЛЬНОГО `config.MAIN_BRANCH`, то есть пина. Когда пин
отстаёт от origin/main между двумя мержами, проверка ложно отвечает
«ветка не отстала», подтяжка не делается, и мерж упирается в конфликт с
настоящим main (инцидент 04.09, hotfix 01M1KT0792125J9ZNJNZJ86E9Q:
`docs/codebase-map.md`) — задача уходит в `in_dev`, повторный `advance`
даёт тот же ложный ответ, подтяжку приходится делать Оператору руками.
Следствие того же дефекта: на пути «ветка свежая» approve `merge_gate`
после push головы читает статус CI один раз, видит «нет ни одной
проверки» и отказывает вместо ожидания — путь «pulled»
(`_wait_for_branch_ci_green`) уже ждёт CI циклом, путь «fresh» — нет.

## Требования
1. Сверка свежести и подтяжка идут против main артели на origin, не
   против локального пина: перед `commits_behind` — `fetch origin
   <MAIN_BRANCH>`, база сравнения и источник merge в worktree задачи —
   `FETCH_HEAD`/`origin/<MAIN_BRANCH>` (тот же источник, что уже несёт
   `fsm_merge_gate._origin_main_sha`).
2. Гейт `merge_gate` после push головы ветки задачи в origin ждёт
   появления и завершения проверок CI тем же циклом ожидания, что и
   после подтяжки (путь «pulled», `_wait_for_branch_ci_green`), а не
   отказывает немедленно по «нет ни одной проверки»; потолок ожидания —
   существующая константа `config.MERGE_GATE_CI_WAIT_CEILING_SEC`.
3. Расхождение локального пина (`config.MAIN_BRANCH` главной копии) с
   main артели на origin не влияет ни на одну проверку конвейера, кроме
   `doctor` (root-pin): ни на сверку свежести, ни на merge, ни на чтение
   артефактов.
4. Существующие тесты сверки свежести и ожидания CI на `merge_gate`
   остаются зелёными без ослабления — расширяются новыми случаями, не
   переписываются.

5. Имя remote и репозиторий, против которых идёт сверка и подтяжка,
   берутся из конфигурации target задачи (запись `targets.yaml` /
   `store.task_target`), а не захардкожены как origin пульта: для
   self-target это origin пульта, для внешнего target — его origin
   (исследование готовности к внешнему проекту, 04.09; редактура
   Оператора на гейте).

## Критерии приёмки

AC-1. `fsm._pull_main_or_escalate` перед вызовом `gitcmd.commits_behind`
делает `git fetch origin <MAIN_BRANCH>` и сравнивает отставание ветки
задачи относительно `FETCH_HEAD`/`origin/<MAIN_BRANCH>`, а не
относительно локального `config.MAIN_BRANCH`.

AC-2. Merge внутри `_pull_main_or_escalate` (подтяжка ветки задачи в её
worktree) выполняется из того же источника, что и сверка в AC-1 —
`FETCH_HEAD`/`origin/<MAIN_BRANCH>` — не из локального
`config.MAIN_BRANCH`.

AC-3. Ни одна из трёх точек вызова `_pull_main_or_escalate` (`in_dev ->
review`, `acceptance -> merge_gate`, окно `merge_gate`) не читает и не
использует локальный `config.MAIN_BRANCH` (пин главной копии) для
сверки свежести или подтяжки.

AC-4. Юнит-тест: ветка задачи отстаёт от main артели на origin, но
совпадает с (не отстаёт от) локальным `config.MAIN_BRANCH` — подтяжка
всё равно выполняется (отставание обнаруживается по origin, не по
пину).

AC-5. Гейт `merge_gate` после push головы ветки задачи в origin —
включая случай, когда `approve` этим же вызовом впервые публикует
голову в origin (`github_adapter.ensure_head_in_origin`) — ждёт
появления и завершения проверок CI тем же циклом
(`_wait_for_branch_ci_green`), что и путь «pulled», вместо немедленного
отказа по статусу «нет ни одной проверки».

AC-6. Потолок ожидания CI на пути «fresh после push» — существующая
константа `config.MERGE_GATE_CI_WAIT_CEILING_SEC` (та же, что уже несёт
путь «pulled»); отдельного нового лимита не заводится.

AC-7. Юнит-тест: путь «fresh» после push головы ветки в origin ждёт CI
циклом ожидания, не отказывает немедленно по «нет ни одной проверки».

AC-8. Расхождение локального `config.MAIN_BRANCH` (пина) с main артели
на origin не меняет исход ни сверки свежести (AC-1–AC-4), ни merge, ни
чтения артефактов задачи (`gitcmd.show`/ветко-корректные чтения) — кроме
уже существующей проверки `doctor` (root-pin), которая этой задачей не
меняется.

AC-9. Тесты `tests/test_branch_freshness_gate.py`,
`tests/test_fsm_map_conflict_autoresolve.py`,
`tests/test_gitcmd_branch_reads.py`, `tests/test_merge_gate_ci_wait.py`
остаются зелёными; случаи из AC-4 и AC-7 добавлены как новые тесты, ни
один существующий тест этих файлов не переписан и не ослаблен.

AC-10. Источник сверки и подтяжки (remote и репозиторий) определяется
конфигурацией target задачи, не константой «origin пульта»; юнит-тест:
задача с target, у которого remote назван иначе, сверяется и
подтягивается против него.

## Не входит

- Изменение механики пина и `pin-update`.
- Авто-обновление пина по расхождению с origin/main.
- Новый отдельный потолок ожидания CI для пути «fresh после push» —
  используется существующая константа `config.MERGE_GATE_CI_WAIT_CEILING_SEC`
  (AC-6).
- Изменение поведения авторазрешения конфликта подтяжки
  `docs/codebase-map.md` (`_auto_resolve_map_conflict`) — меняется
  только источник свежести/подтяжки, не разбор конфликта.

## Материалы
- Инцидент 04.09, hotfix 01M1KT0792125J9ZNJNZJ86E9Q.
- `orchestrator/fsm.py::_pull_main_or_escalate`.
- `orchestrator/gitcmd.py::commits_behind`.
- `orchestrator/fsm_merge_gate.py::_origin_main_sha`,
  `_wait_for_branch_ci_green`, `_cmd_approve_merge_gate`.
- `orchestrator/github_adapter.py::ensure_head_in_origin`.
