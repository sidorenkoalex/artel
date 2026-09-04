---
task: 01M1NBWPKNBXP9ZXXQDJM7AXPJ
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Сверка свежести ветки против main артели на origin

# ТЗ: сверка свежести ветки задачи против main артели на origin (регрессия нового флоу A7 №5)

Источник: инцидент 04.09, hotfix 01M1KT0792125J9ZNJNZJ86E9Q. После
A7 запущенная версия живёт на пине (локальный `main` главной копии,
двигается только `pin-update`), а мерж пишется в main артели на
origin (`fsm_merge_gate._origin_main_sha`, `fetch origin main`).
Проверка свежести ветки (`fsm._pull_main_or_escalate`, узел для
переходов in_dev → review, acceptance → merge_gate и окна merge)
считает отставание `gitcmd.commits_behind(branch)` относительно
ЛОКАЛЬНОГО `config.MAIN_BRANCH`, то есть пина. Как только между двумя
мержами пин отстаёт от origin/main, проверка отвечает «ветка не
отстала», подтяжка не делается, мерж упирается в конфликт с
настоящим main (04.09: `docs/codebase-map.md`), задача возвращается в
in_dev, а повторный `advance` даёт тот же ложный ответ — подтяжку
пришлось делать Оператору руками. Следствие того же дефекта: на пути
«ветка свежая» approve merge_gate после push головы сразу читает
статус CI, видит «нет ни одной проверки» и отказывает вместо
ожидания (путь «pulled» ждёт CI, путь «fresh» — нет).

Требуется:
1. Сверка свежести и подтяжка идут против main артели на origin: перед
   `commits_behind` — `fetch origin <MAIN_BRANCH>`, база сравнения и
   источник мержа в worktree задачи — `FETCH_HEAD`/`origin/<MAIN_BRANCH>`
   (тот же источник, что у `_origin_main_sha`), не локальный `main`
   главной копии. Локальный `main` (пин) сверкой свежести не
   используется вовсе.
2. Гейт merge после push головы ветки в origin ждёт появления и
   завершения проверок CI тем же циклом ожидания, что и после
   подтяжки («pulled»), а не отказывает по «нет ни одной проверки»;
   потолок ожидания — существующая константа.
3. Расхождение пина с origin/main не влияет ни на одну проверку
   конвейера, кроме `doctor` (root-pin): ни свежесть, ни мерж, ни
   чтение артефактов.
4. Тесты: ветка отстаёт от origin/main при совпадении с локальным
   main — подтяжка делается; путь «fresh» после push ждёт CI;
   существующие тесты зелёные без ослабления (`tests/test_pull_main*`,
   `tests/test_merge_gate*` — расширяются, не переписываются).

Зоны: orchestrator/fsm.py (`_pull_main_or_escalate`),
orchestrator/gitcmd.py (`commits_behind`, база), orchestrator/
fsm_merge_gate.py (ожидание CI на пути «fresh»), tests/.

Не входит: изменение механики пина и `pin-update`; авто-обновление
пина.

Рамка: $25.
