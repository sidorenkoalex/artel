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

### Заход после отказа advance («лок приёмочных тестов»)

`advance` был отклонён гейтом «лок приёмочных тестов» (`fsm_advance.py:
523`, `diff_paths(tests_locked_sha=9f61cb5, branch, "acceptance_tests")`).
Диагноз подтверждён прямой сверкой: `git diff 9f61cb5
artifact/01m1neeysp0qwpmxhg0bk591m7 -- .../acceptance_tests/*.py` —
пусто (ни одного изменённого теста); тот же диапазон без исключения
`*.py` показывает исключительно `__pycache__/*.pyc` (включая файлы с
именами вида `*-pytest-9.1.1.pyc`, отсутствовавшие на локе). Это
известный класс «регрессия A7 №4» (`orchestrator/checkpoint.py::
_commit_external_step_artifacts` собирает `tasks/<id>/` сырым
`rglob`, без учёта `.gitignore`; чисто аддитивная запись в
`artifact_branch.write_commit` никогда не удаляет однажды
закоммиченный `.pyc` сама) — подтверждён тем же классом на
`tasks/01M1HNNHDMP2C1AJTH5QF1BTN2/PLAN.md` (три независимых захода),
`tasks/01M1K7KP0D8ZKRM9KTE75DCCYR/PLAN.md`,
`tasks/01M1KCSTBYF1CRJBSY4P6VYQEA/PLAN.md`/`REVIEW.md`. Штатный фикс
корня — отдельная задача `01M1KVG3KSCY47HWXWF5HM0E76`
(«автокоммит артефактов шага учитывает .gitignore»), в main пока не
слита. По прецеденту ANSWER-5/ANSWER-6 (`01M1HNNHDMP2C1AJTH5QF1BTN2`,
раздел «Эскалация», вопрос 1, вариант «б»): присутствие `__pycache__`
в артефактной ветке после шага — НЕ основание для эскалации
разработчиком; ресинхронизация `acceptance_tests/` с локом — действие
Оператора (мост), не разработчика. Единственное обязательство
разработчика — не добавлять новый дрейф своим шагом.

Этим заходом: код/тесты не менялись (снимок `fc6b2eb` без изменений).
Все прогоны — флагом `-B` (`PYTHONDONTWRITEBYTECODE`), тем же приёмом:
`python3 -B -m unittest tests.test_lease tests.test_pause
tests.test_release` — 56 ok; `python3 -B -m unittest discover -s
tasks/01M1NEEYSP0QWPMXHG0BK591M7/acceptance_tests` — 18 ok (AC-1..AC-8
все зелёные); `python3 -B scripts/guard.py tasks/
01M1NEEYSP0QWPMXHG0BK591M7/PLAN.md tasks/01M1NEEYSP0QWPMXHG0BK591M7/
SPEC.md` — `GUARD: ок (2 файлов)`; `find tasks/
01M1NEEYSP0QWPMXHG0BK591M7 -name __pycache__ -o -name '*.pyc'` — пусто
до и после. `tasks/01M1NEEYSP0QWPMXHG0BK591M7/` в рабочем дереве этой
сессии на старте оказался удалён вне коммита (тот же класс, что
описан `[[feedback_task_dir_deletion_recovery]]`) — восстановлен
`git checkout --`, не переписан. PLAN.md остаётся `status: ready`.

## Предложения системе
- Класс «`escalate` недостижим для роли developer через PLAN.md»
  (`scripts/guard.py::RULES["plan"]["statuses"]` не несёт `escalate`,
  а `fsm_advance.py::in_dev` не читает такой статус) уже трижды
  подтверждён (`tasks/T079`, `tasks/01M1HNNHDMP2C1AJTH5QF1BTN2` дважды)
  — этим заходом эскалация не понадобилась (класс «регрессия A7 №4»
  прецедентно закрыт без неё), но сам структурный пробел остаётся не
  зачинен.
- Класс «регрессия A7 №4» (`__pycache__` в артефактной ветке ломает
  лок `acceptance_tests/`) подтверждён четвёртой независимой задачей
  подряд — фикс `01M1KVG3KSCY47HWXWF5HM0E76` стоит смержить раньше,
  чем эта планка нарастёт до пятого прецедента.
