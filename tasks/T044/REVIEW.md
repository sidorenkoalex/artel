---
task: T044
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 2
---

# REVIEW: Lease задачи: advisory-замок параллельных сессий

## Фаза A — гейт плана

Покрытие требований в PLAN.md полное (таблица «Покрытие требований»
закрывает 1–13 и AC-1..AC-7), шаги — единицы размера MR, не микрооперации.
Подход (тонкая обёртка `cmd_x` → `_cmd_x`, флаг «взят с нуля» у `acquire`,
удержание lease `auto` на весь цикл) не конфликтует с конвенциями:
`store.py` остаётся единственным писателем SQL, новый модуль `lease.py`
следует тому же стилю, что `alerts.py`/`spend.py`.

Один пробел плана: раздел «Влияние на систему» разбирает гонку
release↔acquire между шагами `auto`, но не разбирает атомарность самого
`acquire()` (read-then-write между `lease_row` и `insert_lease`/
`update_lease`) под конкурентным доступом ДВУХ сессий — то есть именно
тот случай, ради которого затевалась задача. Это не formal-блокер
Фазы A (план допустимо было принять к реализации), но воспроизведённый
ниже дефект — прямое следствие этого пробела в анализе.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `leases(task_id PK, session_id, pid, hostname, heartbeat_ts)` — `store.py` SCHEMA и `migrate()` |
| 2 | OK | Все 7 команд обёрнуты (`runner.cmd_run`, `auto.cmd_auto`, `fsm.cmd_advance/approve/reject`, `cleanup.cmd_kill`, `budget.cmd_budget`) |
| 3 | Не так под конкуренцией | см. Замечание 1 — «взять/продлить» не атомарно между `lease_row` и записью |
| 4 | Не так под конкуренцией | см. Замечание 1 — вместо именованного отказа возможен необработанный `sqlite3.IntegrityError` |
| 5 | Не так под конкуренцией | см. Замечание 1 — два перехвата одного протухшего lease оба «успешны» молча |
| 6 | OK | `config.LEASE_STALE_AFTER_SEC = 7200`, обоснование в PLAN «Риски» |
| 7 | OK | `auto` передаёт свой `session_id` в `cmd_run`/`cmd_advance` на каждом шаге — они видят «свой» lease и продлевают (`orchestrator/auto.py:113,131`) |
| 8 | OK | флаг «взят с нуля» из `acquire()`; `release()` в `finally` только при нём — подтверждено AC-4 |
| 9 | OK (открытое SPEC-решение) | `resolve_session_id`: явный параметр → `ARTEL_SESSION_ID` → `ppid-<getppid()>`; источник SPEC не фиксирует, решение обосновано в PLAN |
| 10 | OK | `catalog.py` не тронут; AC-5 зелёный |
| 11 | OK | `doctor.check_leases`, `os.kill(pid, 0)`, `alerts.raise_alert(kind="incident", source="doctor.leases")`, подключена в `all_checks()` |
| 12 | OK | lease нигде не читается `advance`/`approve`/`reject` при решении о переходе — только на входе обёртки |
| 13 | OK | `python3 -m unittest discover -s tests` — те же 3 падения, что и на `main` (см. Замечание 2), новых регрессий нет; `scripts/guard.py` на SPEC/PLAN — ок |
| AC-1..AC-7 | Зелёные локально (см. Замечание 1) | приёмочные тесты и `tests/test_lease.py`, `tests/test_auto_cycle.py::AutoLeaseTest`, `tests/test_doctor.py::LeasesCheckTest` — все ok в последовательном однопроцессном прогоне; ни один тест не эмулирует реальную конкурентную гонку двух подключений, поэтому Замечание 1 ими не поймано |

## Замечания

- **blocker** — `orchestrator/lease.py:38-58` (`acquire`) — `acquire()` не
  атомарна: между `store.lease_row()` (SELECT) и последующим
  `store.insert_lease()`/`store.update_lease()` (INSERT/UPDATE + commit)
  нет транзакционной защиты (ни `BEGIN IMMEDIATE`, ни UPSERT с проверкой
  `cursor.rowcount`). Воспроизвёл вживую двумя независимыми
  `sqlite3.Connection` к одной БД (симуляция двух процессов/сессий,
  ровно тот сценарий, ради которого создана задача — см. Контекст SPEC,
  инцидент `tasks/T036/TZ.md`):
  1) **Свободный lease, гонка на INSERT.** Обе сессии читают `lease_row
     is None`, обе решают вставить строку. Первая коммитит успешно;
     вторая падает необработанным `sqlite3.IntegrityError: UNIQUE
     constraint failed: leases.task_id` — вместо именованного отказа
     (требование 4) наружу уходит трейсбек Python из недр `lease.acquire`,
     не пойманный нигде в цепочке (`runner.cmd_run` и остальные пять
     `sys.exit`-команд не оборачивают `lease.acquire` в `try/except`).
  2) **Протухший чужой lease, гонка на UPDATE — хуже.** Обе сессии читают
     ОДНУ И ТУ ЖЕ протухшую строку (`age > LEASE_STALE_AFTER_SEC` истинно
     для обеих), обе идут в ветку перехвата и обе делают `UPDATE`. Ни
     одна не получает отказ (`refusal=None` у обеих), обе считают, что
     lease теперь их — уходит по одной каждая, побеждает молча только та,
     чей `UPDATE` выполнился последним, но ОБЕ продолжают выполнять тело
     мутирующей команды параллельно на одной и той же задаче. Это
     буквально тот сценарий («тихая гонка» вместо именованного отказа),
     который SPEC называет мотиватором задачи (перезапись
     `tasks/T036/TZ.md`), воспроизведённый уже внутри самого механизма
     защиты от него.
  Оба случая проверены напрямую (два `sqlite3.Connection` на одном файле
  БД, ручная интерливация `SELECT`/`INSERT`/`UPDATE` в порядке гонки) —
  не гипотеза. Предложение: сделать `acquire()` атомарной — единственный
  `UPDATE`/`INSERT` с условием в `WHERE` (own session ИЛИ свободно ИЛИ
  протухло) и проверкой `cursor.rowcount == 0` как признаком проигранной
  гонки (после чего перечитать строку и вернуть обычный именованный
  отказ), либо обернуть весь `acquire()` в `BEGIN IMMEDIATE` для
  сериализации с другими писателями. Затрагивает только `lease.py` +
  `store.insert_lease`/`update_lease` — остальные 7 обёрток не меняются.

- **minor** — `orchestrator/lease.py:60` — запись перехвата в журнал
  всегда идёт с `actor="fsm"` (`store.journal(conn, task_id, "fsm",
  "lease перехвачен", detail)`), даже когда перехват спровоцирован
  вызовом `budget`, `kill`, `run` и т.п., не связанным с FSM. В
  `artel.py log <id>` это читается как «fsm сделал перехват», хотя
  реального актора (роль/команду) в `lease.py` в принципе не знает.
  Небольшая путаница для Оператора, читающего журнал; не влияет на
  прохождение AC-3 (тест ищет только подстроку «перехват»/«lease»,
  не actor). Предложение: либо передавать в `acquire()` имя вызывающей
  команды и класть его в `actor`, либо завести отдельного actor'а вроде
  `"lease"` вместо переиспользования `"fsm"`.

## Дополнительно проверено (не замечание)

- Полный прогон `python3 -m unittest discover -s tests`: 671 тестов,
  3 падения — все три в `tests/test_multitarget.py::RoleEnvTest`
  (`test_env_carries_the_git_identity`,
  `test_identity_already_in_the_environment_is_not_overridden`,
  `test_absent_identity_is_journalled_before_the_step`), утечка
  локального `git config --global` машины ревьювера в тест git-identity
  слоя — не связано с T044/lease. Сверено на `main` тем же прогоном —
  идентичные 3 падения там же, до этой ветки. Не регрессия этой задачи,
  но и не «зелёный» набор в буквальном смысле AC-7 — фиксирую факт, не
  прошу чинить в рамках T044.
- `scripts/guard.py tasks/T044/SPEC.md tasks/T044/PLAN.md` — «ок (2 файлов)».
- `artel.py` (диспетчер CLI) не изменён; все существующие вызовы 7 функций
  в `tests/` и `artel.py` — позиционные, коллизии с новым `session_id=None`
  нет (подтверждено grep по `orchestrator/artel.py`).

## Вердикт

`changes_requested` — один blocker (Замечание 1): `lease.acquire()`
нужно сделать атомарной операцией read-modify-write (транзакция или
условный UPDATE/UPSERT с проверкой затронутых строк), иначе механизм
защиты от параллельных сессий сам воспроизводит защищаемую от неё гонку.
Minor (Замечание 2) — на усмотрение разработчика, не блокирует.
