---
task: 01M1NEEYSP0QWPMXHG0BK591M7
type: plan
author_role: developer
status: ready
schema_version: 3
---

# PLAN: Предупреждение при чужом живом lease (pause, release)

## Подход
Один общий хелпер в `orchestrator/lease.py`, вызванный из начала тел
`cmd_pause`/`cmd_release` — до любой ветки "уже на паузе"/"нет lease",
чтобы факт "задачу ведёт другая сессия" печатался независимо от того,
окажется ли сама команда no-op'ом под гонкой.

- `lease.foreign_live_lease(conn, task_id, session_id)` — чистая функция:
  возвращает строку `leases`, если она принадлежит ДРУГОЙ сессии и жива
  (heartbeat не старше `config.LEASE_STALE_AFTER_SEC` И pid адресуем через
  `liveness._pid_alive`), иначе `None`. Переиспользует существующие
  `store.lease_row`/`liveness._age_seconds`/`liveness._pid_alive` — без
  копипасты проверки живости, которая уже есть в `lease.acquire` и
  `merge_lock.py`.
- `lease.warn_foreign_live(conn, task_id, session_id)` — печатает
  предупреждение (держатель, pid, hostname, возраст heartbeat в секундах)
  и дублирует его `store.journal(..., session_id=<держателя>)` (требование
  3 явно называет identity держателя, не текущей сессии). Ничего не делает
  при `foreign_live_lease is None` (свой lease, лизинга нет, чужой
  мёртв/протух).
- `cmd_pause`/`cmd_release` вызывают `lease.warn_foreign_live(conn,
  task_id, resolve_session_id())` сразу после резолва префикса id, до
  остального тела. Ни блокировки, ни подтверждения — просто печать и
  журнал, выполнение идёт дальше как раньше.

Адресуемость pid чужого lease здесь проверяется БЕЗ различения host — в
отличие от `catalog._lease_holder_suffix`/`lease.acquire`, где
неадресуемый pid ЧУЖОГО host трактуется как «жив» (безопаснее в сторону
«не перехватывать чужой активный lease»). Для предупреждения логика
обратная: печатать нужно только то, что действительно проверено с этой
машины, поэтому чужой host с непроверяемым pid — не «адресуем», и
предупреждения не будет. Задокументировано докстрокой
`foreign_live_lease` — не отдельным ADR: это трактовка одного и того же
уже существующего критерия живости под новую задачу, а не смена самого
критерия.

Read-only команды (`status`, `log`, `show`, `doctor`) не тронуты вовсе —
им негде подключать `warn_foreign_live`, так что требование 4 выполняется
отсутствием вызова, а не отдельной проверкой.

## Шаги

1. `lease.foreign_live_lease` + `lease.warn_foreign_live` в
   `orchestrator/lease.py`, юнит-тесты в изоляции (`tests/test_lease.py`,
   класс `ForeignLiveLeaseTest`): нет lease, свой живой lease, чужой живой
   lease, чужой протухший heartbeat, чужой мёртвый pid, состав
   предупреждения, журнальная запись с identity держателя, отсутствие
   печати/журнала для "свой"/"нет lease".
2. Подключение к `cmd_pause` (`orchestrator/pause.py`) и `cmd_release`
   (`orchestrator/release.py`) — по одному вызову `lease.warn_foreign_live`
   в начале тела каждой команды; юнит-тесты на то, что вызов подключён
   (`tests/test_pause.py`, `tests/test_release.py`) — не дублируют логику
   `foreign_live_lease`, только сквозной путь "команда печатает и
   журналирует при чужом живом lease".
3. Приёмочные тесты AC-1..AC-8 (уже поставлены test_author'ом,
   `tasks/01M1NEEYSP0QWPMXHG0BK591M7/acceptance_tests/`) — залочены,
   код чинится под них. Прогнаны зелёными без правок состава.
4. Регенерация `docs/codebase-map.md` тем же коммитом (правка
   `orchestrator/*.py`).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (предупреждение до выполнения, pause/release) | 1, 2 |
| 2 (свой/мёртвый-протухший lease — без предупреждения) | 1 |
| 3 (дубль в журнал тем же API, identity держателя) | 1 |
| 4 (read-only команды не предупреждают) | 2 (отсутствием вызова) |
| 5 (approve/reject/budget/kill/answer не меняются) | — (не входит, не тронуты) |

## Влияние на систему
Затронуты только `orchestrator/lease.py` (два новых публичных имени,
существующие функции модуля не изменены), `orchestrator/pause.py` и
`orchestrator/release.py` (по одной вставке вызова в начале тела команды,
до имеющихся веток — порядок остального тела не менялся). Существующие
проверки живости (`LEASE_STALE_AFTER_SEC`, `_pid_alive`) переиспользованы
как есть, не ослаблены и не продублированы. `approve`/`reject`/`budget`/
`kill`/`answer` и их хард-блок через `lease.run_locked(...,
on_refusal="exit")` не тронуты (SPEC, «Не входит» + ANSWER-1, вариант A) —
проверено `git diff --stat`: эти файлы в диффе не фигурируют. Механика
`lease.py`/`liveness.py` (сам замок, критерий живости) не менялась — только
новое чтение поверх неё. Откат — реверт трёх файлов
(`lease.py`/`pause.py`/`release.py`) и их тестов; данных/схемы БД правка
не касается.

## Риски
Строка предупреждения на русском и содержит structured-данные
(session_id/pid/hostname/возраст) через f-string — не через журнальный
detail напрямую, поэтому инъекции в SQL/журнал нет (тот же
`store.journal`, что и у прочих событий).

## Предложения системе
(пусто)
