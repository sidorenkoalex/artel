---
task: T057
type: plan
author_role: developer
status: ready
schema_version: 2
---

# PLAN: Дедупликация liveness-хелперов и lease-обвязки

## Подход

Требование 1 (`_age_seconds`/`_pid_alive`): новый маленький лист графа
импортов — `orchestrator/liveness.py`. Ни `lease.py`, ни `merge_lock.py`
не годятся единственным домом обеих функций разом: `_age_seconds`
дублирована между `lease.py`/`merge_lock.py`, `_pid_alive` — между
`doctor.py`/`merge_lock.py`, и ни один из этих трёх модулей не является
естественным «владельцем» обеих сразу без обратной или кросс-слойной
зависимости (`lease.py` не должен знать о `doctor.py`, а `merge_lock.py`
не должен становиться домом для чужого хелпера просто потому, что
дублировал обе). `liveness.py` не импортирует ничего из пакета
(`os`, `datetime` — только stdlib) — так же лист, как и сам `lease.py`
сейчас. `lease.py`, `merge_lock.py`, `doctor.py` переходят на
`from . import liveness` и зовут `liveness._age_seconds`/
`liveness._pid_alive` — дословный перенос тела, без изменения формата
`heartbeat_ts` и семантики (требование «не входит»).

Требование 2 (общая точка обвязки lease): плюс `lease.run_locked(conn,
task_id, session_id, body, *, on_refusal="exit")` — обычная функция, не
контекст-менеджер (SPEC явно допускает «или эквивалент»): контекст-
менеджер здесь пришлось бы городить поверх исключения ради ветки
отказа, которая не бросает `sys.exit`, а печатает и возвращает
`False`/`None` (advance/auto) — функция с параметром канала отказа
проще и без лишней машинerии. `body(sid)` — тело самой команды с уже
разрешённым `session_id`; `on_refusal="exit"` (умолчание, 6 из 8
вызывателей: approve/reject/run/budget/kill/workspace) — `sys.exit`
прежним текстом; `on_refusal="print"` (advance/auto) — печатает отказ и
возвращает `None`, а вызыватель сам приводит это к своему прежнему
`False`/пустому возврату. `fresh`-семантика release не меняется:
`release()` зовётся в `finally` только когда `acquire()` вернул
`fresh=True`, ровно как в прежних 8 копиях.

Найденная по ходу засада: приёмочный тест AC-3
(`test_ac3_shared_lease_binding.py`) проверяет отсутствие пары
`.acquire(`/`.release(` как ГОЛЫХ ПОДСТРОК по всему тексту каждого из 6
файлов-вызывателей — не различая lease и `merge_lock`. `fsm.py` держит,
кроме трёх lease-обвязок (advance/approve/reject), ещё и не относящуюся
к этой задаче обвязку мьютекса merge-окна (`merge_lock.acquire`/
`.release` внутри `_cmd_approve` при `state == merge_gate`, SPEC T053) —
её присутствие в тексте `fsm.py` само по себе валит тест независимо от
lease-рефактора. SPEC T057 явно не просит трогать `merge_lock`
(«не входит: изменение семантики lease/merge_lock/doctor»), но
локальный тест залочен (tasks/T023: код чинится под тест, не наоборот),
и он написан достаточно широко, чтобы требовать того же переноса и для
merge_lock-обвязки. Решение — симметричный `merge_lock.run_window(conn,
task_id, session_id, body)` в `orchestrator/merge_lock.py` (не в
`fsm.py`): переносит существующий код `_cmd_approve`'s merge_gate-ветки
(acquire -> `sys.exit` -> `try/finally release` безусловно, БЕЗ понятия
`fresh` — тем же приёмом, что и сейчас, SPEC T053 требование 3) один в
один, `fsm.py` зовёт готовую точку. Семантика okna не меняется ни на
байт — перенесён код, не логика; `merge_lock.py` не входит в список
`CALLER_FILES` теста, поэтому его собственный текст `.acquire(`/
`.release(` тестом не проверяется.

## Шаги

1. `orchestrator/liveness.py` (новый): `_age_seconds`, `_pid_alive` —
   дословный перенос тел из `lease.py`/`merge_lock.py`/`doctor.py`.
   `lease.py`, `merge_lock.py`, `doctor.py` — свои копии убирают, зовут
   `liveness._age_seconds`/`liveness._pid_alive`. Правка комментария
   `store.py:426` (ссылка на `lease._age_seconds` → `liveness._age_seconds`).
   Юнит-тесты не пишутся отдельно — существующие `tests/test_lease.py`,
   `tests/test_merge_lock.py`, `tests/test_doctor.py` уже кроют поведение
   этих функций через публичные `acquire`/`check_leases`/`check_merge_lock`
   и останутся зелёными без правки ассертов (AC-5).
2. `orchestrator/lease.py`: `run_locked(conn, task_id, session_id, body,
   *, on_refusal="exit")` — общая точка обвязки (требование 2). Юнит-тесты
   в `tests/test_lease.py` (успех/refusal-exit/refusal-print/fresh-release/
   renew-без-release).
3. `orchestrator/merge_lock.py`: `run_window(conn, task_id, session_id,
   body)` — симметричная точка для мьютекса merge-окна (см. «Подход»,
   засада AC-3). Юнит-тесты в `tests/test_merge_lock.py`.
4. Восемь вызывателей переходят на `lease.run_locked` (требование 3):
   `orchestrator/fsm.py` (`cmd_advance` — `on_refusal="print"`,
   `cmd_approve`, `cmd_reject`), `orchestrator/runner.py` (`cmd_run`),
   `orchestrator/auto.py` (`cmd_auto` — `on_refusal="print"`),
   `orchestrator/budget.py` (`cmd_budget`), `orchestrator/cleanup.py`
   (`cmd_kill`), `orchestrator/workspace.py` (`cmd_workspace`). В этом же
   шаге `fsm._cmd_approve`'s `merge_gate`-ветка переходит на
   `merge_lock.run_window` (шаг 3). Существующие тесты (`test_advance_
   guard.py`, `test_auto_cycle.py`, `test_workspace.py`, `test_kill_
   cleanup.py`, `test_spec_budget.py`, `test_merge_lock.py` и т.д.) уже
   проверяют поведение через реальные строки БД (`INSERT INTO leases`) —
   правок ассертов не требуют (AC-5).
5. `python3 scripts/codebase_map.py` тем же коммитом (новый модуль
   `liveness.py`, новые импорты) + прогон `scripts/guard.py` на своих
   артефактах + полный `python3 -m unittest discover -s tests`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 2 |
| 3 | 4 |
| 4 | 2, 4 |
| 5 | 2, 3, 4 (тексты отказов и `body()` — дословный перенос) |
| 6 | 2, 3, 4 (существующие тесты не трогают ассерты) |
| 7 | 1, 5 (карта регенерируется тем же коммитом) |

## Влияние на систему

Периметр изменения — три внутренних модуля пакета (`lease.py`,
`merge_lock.py`, `doctor.py`) плюс новый лист `liveness.py`, и точки
вызова в шести вызывателях плюс сама `fsm.py`'s `merge_gate`-ветка;
внешне наблюдаемое поведение (CLI-вывод, тексты отказов, журнал,
`doctor`, схема БД) не меняется ни на строку — рефакторинг переносит
код, не логику, и это прямое требование SPEC (5, 6), проверяемое
существующими тестами без правки ассертов.

Инварианты 9/12/14/18/19 (lease не второй конечный автомат, `kill`
работает из любого нетерминального состояния, approve/reject остаются
за Оператором, merge — только под мьютексом) не задеты: `run_locked`/
`run_window` — тот же порядок операций (`resolve_session_id` →
`acquire` → отказ → тело → `release`-если-fresh/безусловно), просто в
одном месте вместо восьми/двух копий. `fresh`-семантика `lease.release`
(снимает только то, что взял с нуля этот же вызов) не меняется — тот же
булев флаг из `acquire()` прокидывается в `finally` `run_locked`, как и
раньше в каждой из 8 копий.

Откат: `git revert` коммита(ов) задачи — новый модуль и обе точки
обвязки изолированы, ни одна другая задача веткой T057 не поднята
(рабочий каталог — собственный worktree).

## Риски

- `merge_lock.run_window` — не в тексте SPEC T057 буквально (см. «Подход»,
  засада AC-3): вынужденное расширение периметра ради залоченного
  приёмочного теста, а не самостоятельное решение вкуса. Семантика окна
  (SPEC T053) не меняется — только перенос уже существующего кода из
  `fsm.py` в `merge_lock.py`. Если Оператор сочтёт это выходом за периметр
  задачи — просьба дать знать на ревью, откат тривиален (шаг 3 обратим
  независимо от шагов 1/2/4).

## Предложения системе
- `tasks/T057/acceptance_tests/test_ac3_shared_lease_binding.py`: голая
  подстрока `.acquire(`/`.release(` по всему тексту файла не различает
  цель вызова — залоченный тест валит `fsm.py` из-за НЕ относящейся к
  SPEC T057 обвязки `merge_lock` (SPEC T053), пока и её тоже не вынесешь
  за точку (см. «Подход»). Класс: приёмочный тест, написанный до кода
  test_author'ом, сформулирован на уровне текстового grep вместо AST/
  семантики — придётся смотреть, повторится ли класс «grep вместо AST
  ловит непричастный код» в будущих задачах на дедупликацию.
