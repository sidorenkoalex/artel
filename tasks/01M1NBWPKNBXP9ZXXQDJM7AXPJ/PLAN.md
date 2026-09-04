---
task: 01M1NBWPKNBXP9ZXXQDJM7AXPJ
type: plan
author_role: developer
status: ready
schema_version: 3
---

# PLAN: Сверка свежести ветки против main артели на origin

## Подход

Два независимых узла:

1. **Сверка свежести против origin, не пина** (`orchestrator/fsm.py::
   _pull_main_or_escalate`, AC-1..AC-4, AC-8). Новая функция
   `fsm._origin_main_sha()` делает `git fetch origin <MAIN_BRANCH>` и
   возвращает `sha` (`rev-parse FETCH_HEAD`) — она СВОЯ копия узла
   `fsm_merge_gate._origin_main_sha` (тот же приём точечного
   дублирования по модулю, что уже несёт `MAP_REL`): `fsm_merge_gate`
   импортирует `fsm`, обратный импорт завёл бы цикл. `base = fsm.
   _origin_main_sha() or "FETCH_HEAD"` идёт и в `gitcmd.commits_behind
   (branch, base=base)` (сверка), и в `git merge --no-ff <base>` внутри
   worktree задачи (подтяжка) — один и тот же `base` для обеих
   операций, `config.MAIN_BRANCH` в коде узла остаётся только ИМЕНЕМ
   ветки, которую фетчим, не источником сравнения. `git fetch` пишет
   только в объектную базу/`FETCH_HEAD` `config.ROOT` — ни рабочее
   дерево, ни HEAD, ни зафиксированный там пин не трогает (AC-8);
   `gitcmd.commits_behind` уже принимает `base` параметром (существующая
   сигнатура, менять не пришлось).
   Три точки вызова `_pull_main_or_escalate` (`in_dev -> review`,
   `acceptance -> merge_gate`, окно `merge_gate`) не тронуты — они уже
   зовут этот единственный узел, менять их незачем (AC-3 закрывается
   самим фактом единственной точки правки).

2. **Ожидание CI на пути "fresh" после push** (`orchestrator/
   fsm_merge_gate.py::_cmd_approve_merge_gate`, AC-5..AC-7). На ветке
   `pull_outcome == "fresh"` тело гейта больше не зовёт `ci.
   branch_status` само и не отказывает по одному опросу: если
   `confirmed_ci_note is None`, возвращает `("wait", branch)` — тот же
   сигнал, что уже несёт ветка `"pulled"`. Внешний цикл
   `_cmd_approve_merge_gate_cycle` (не менялся) сам не различает, ПОЧЕМУ
   пришёл `("wait", ...)` — гоняет `_wait_for_branch_ci_green` вне
   мьютекса и на следующем заходе передаёт подтверждённый статус телу
   через уже существующий параметр `confirmed_ci_note`. Потолок ожидания
   — существующая `config.MERGE_GATE_CI_WAIT_CEILING_SEC`, второй
   константы не заводилось (AC-6): цикл её и так уже читает.

Оба узла используют существующие механизмы (`commits_behind(base=...)`,
`confirmed_ci_note`, `_wait_for_branch_ci_green`) — новых абстракций,
кроме одной маленькой функции `_origin_main_sha`, не вводилось.

## Шаги

1. `orchestrator/fsm.py`: `_origin_main_sha()` + `_pull_main_or_escalate`
   сверяется и мержит против `base` (origin), не `config.MAIN_BRANCH`.
2. `orchestrator/fsm_merge_gate.py`: путь `pull_outcome == "fresh"` без
   `confirmed_ci_note` возвращает `("wait", branch)` вместо разового
   опроса `ci.branch_status` и немедленного отказа.
3. Юнит-тесты: `tests/test_branch_freshness_gate.py` (AC-2, AC-4),
   `tests/test_merge_gate_ci_wait.py` (AC-7), `tests/
   test_ci_status_kind_gate.py` (класс поведения "running"/"unknown" на
   пути fresh сохранён, но через цикл ожидания — `FakeClock`, часы
   заглушены), `tests/test_invariants.py` (требование 6 — merge без
   зелёного CI — тот же приём заглушки часов). Правка существующего
   `tests/test_fsm_merge_gate_done_snapshot.py`: два теста звали тело
   гейта напрямую без `confirmed_ci_note` (докстрайл файла — приём,
   принятый ДО этой задачи) — с новым контрактом пути "fresh" такой
   вызов больше не завершается синхронно; передан явный
   `confirmed_ci_note`, совпадающий с уже замоканным в `setUp`
   `ci.branch_status` — тот же самый узел, что и настоящий внешний цикл
   подставил бы сюда сам. Ассерты (`done`, снапшот, удаление
   артефактной ветки) не ослаблены — изменился только способ дойти до
   вызова тела.
4. Приёмочные тесты `tasks/01M1NBWPKNBXP9ZXXQDJM7AXPJ/acceptance_tests/`
   (AC-1..AC-9) уже поставлены test_author — не редактировались.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (сверка/подтяжка против origin) | 1 |
| 2 (гейт ждёт CI циклом на пути fresh после push) | 2 |
| 3 (расхождение пина не влияет ни на что кроме doctor) | 1 (не тронут doctor.py вовсе) |
| 4 (существующие тесты зелёные, расширены не переписаны) | 3 |

## Влияние на систему

- Единственные тронутые узлы — `fsm._pull_main_or_escalate`/новая
  `fsm._origin_main_sha` и `fsm_merge_gate._cmd_approve_merge_gate`
  (одна ветка `if`). `doctor.py`, `pin.py`, механика `pin-update` не
  затронуты (SPEC «Не входит»), `_auto_resolve_map_conflict` не менялся.
- Гейты/лимиты/инварианты не ослаблены: путь "fresh" после push теперь
  СТРОЖЕ прежнего (ждёт подтверждённого зелёного CI циклом вместо
  разового опроса), не слабее. Мьютекс merge-окна и его дисциплина
  (взять/отпустить вокруг каждого захода в тело) не изменены — второй
  повод для `("wait", ...)` идёт по тому же самому пути, что и первый.
- `gitcmd.commits_behind` уже принимал `base` параметром до этой задачи
  (правка не потребовалась) — риска регресса вызывающих без `base`
  (используют `config.MAIN_BRANCH` по умолчанию, как раньше) нет.
- Откат — `git revert` двух коммитов правки (fsm.py/fsm_merge_gate.py +
  соответствующие тесты); ничего вовне этих двух модулей не зависит от
  нового поведения.
- Один существующий юнит-тест (`tests/
  test_fsm_merge_gate_done_snapshot.py`) адаптирован под новый
  синхронный контракт тела гейта (см. Шаг 3) — без ослабления проверяемых
  условий, только способ вызова.

## Риски

- `_origin_main_sha` в `fsm.py` дублирует одноимённый узел
  `fsm_merge_gate.py` (разный модуль, тот же код) — сознательно, чтобы
  не заводить цикл импорта (`fsm_merge_gate` уже импортирует `fsm`).
  Если оба узла разойдутся при будущей правке одного без другого — увидит
  ревью следующей задачи; отдельного докстрайна с явным упоминанием пары
  на обеих сторонах достаточно для сегодняшнего объёма.

## Предложения системе

(пусто)
