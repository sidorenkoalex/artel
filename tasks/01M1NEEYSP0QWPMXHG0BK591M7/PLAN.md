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

Отдельно — подтяжка main (см. «Контекст» ниже) принесла фикс задачи
01M1KVG3KSCY47HWXWF5HM0E76 (`orchestrator/gitcmd.py::check_ignore`,
`checkpoint.py`, `fsm_advance.py`) и регенерацию `docs/codebase-map.md`
по итогам слияния — эти файлы вне зоны текущего SPEC, правка пришла
подтяжкой, не Edit (conventions-core, правило про регенерацию карты
после подтяжки main).

## Риски
Строка предупреждения на русском и содержит structured-данные
(session_id/pid/hostname/возраст) через f-string — не через журнальный
detail напрямую, поэтому инъекции в SQL/журнал нет (тот же
`store.journal`, что и у прочих событий).

## Предложения системе
Класс «локed acceptance_tests/ содержит __pycache__/*.pyc, которых нет
на кодовой ветке» (ложный «лок изменён» на `in_dev -> review`) —
устранён на уровне пульта задачей 01M1KVG3KSCY47HWXWF5HM0E76 (смержена
в main 04.09.2026): `orchestrator/gitcmd.py::check_ignore`,
`checkpoint._commit_external_step_artifacts` и сверка лока в
`fsm_advance.py::in_dev` теперь единообразно учитывают `.gitignore`
пульта. Эта задача столкнулась с классом до фикса (см. «Эскалация» ниже)
и подтвердила его закрытие подтяжкой main.

ANSWER-2 (эта задача) велит впредь подавать developer-эскалацию через
PLAN.md статусом `escalate` во frontmatter, а не `status: draft` +
текстовая секция «## Эскалация». Но `scripts/guard.py::RULES["plan"]
["statuses"]` по-прежнему `{"draft", "ready", "approved"}` —
`"escalate"` туда не входит (проверено после подтяжки main в этой
задаче: строка не поменялась). Указание ANSWER-2 разошлось с текущей
guard-схемой; либо guard.py нужно расширить до `escalate` для `type:
plan`, либо формулировку ANSWER-2 стоит уточнить. Эта задача
эскалацию уже сняла (см. ниже) и следует прежней схеме (`draft` +
текст) — противоречие адресую здесь, чтобы не потерялось для
следующей задачи, которой придётся эскалировать через PLAN.md.

## Эскалация: снята (ANSWER-2)

Предыдущая итерация этого PLAN.md эскалировала блокировку перехода
`in_dev -> review`: гейт лока `acceptance_tests/`
(`orchestrator/fsm_advance.py::in_dev`) сравнивал `tests_locked_sha`
(`9f61cb51b1b8d8dee9dc81e05a487b238b8fe26b`) с текущей головой ветки и
находил непустой диф — но НЕ по содержимому тестов: `git diff --numstat
9f61cb51... HEAD -- tasks/01M1NEEYSP0QWPMXHG0BK591M7/acceptance_tests`
называл только семь бинарных `__pycache__/*.pyc` (автокоммит лока
test_author'а утащил их в снимок, `.gitignore` их на кодовой ветке не
пропускает). Ни один `*.py`-файл не расходился ни байтом.

Оператор ответил (`tasks/01M1NEEYSP0QWPMXHG0BK591M7/ANSWER-2.md`):
класс дефекта уже устранён на уровне пульта задачей
01M1KVG3KSCY47HWXWF5HM0E76 (смержена в main 04.09.2026, запущенная
версия обновлена) — сверка лока теперь не учитывает игнорируемые файлы,
`amend-tests` для пересчёта `tests_locked_sha` не требуется. Единственное
действие разработчика — подтянуть main и сдать шаг статусом `ready`.

### Контекст

- Реализация SPEC 01M1NEEYSP0QWPMXHG0BK591M7 завершена и корректна
  сама по себе: `orchestrator/lease.py::foreign_live_lease`/
  `warn_foreign_live`, подключение в `orchestrator/pause.py::cmd_pause`
  и `orchestrator/release.py::cmd_release` — по коммиту `fc6b2eb`.
- Подтянут main (`git merge main`) — единственный конфликт был в
  сгенерированном `docs/codebase-map.md`, разрешён регенерацией
  (`python3 scripts/codebase_map.py`); прочие файлы смержены без
  конфликтов. Подтяжка принесла фикс 01M1KVG3KSCY47HWXWF5HM0E76.
- Диф лока проверен напрямую после подтяжки (`orchestrator.gitcmd.
  diff_names` + `check_ignore`, тем же кодом, что вызывает
  `fsm_advance.py::in_dev`): между `tests_locked_sha` и текущим HEAD
  по-прежнему называются те же семь `__pycache__/*.pyc`, но
  `check_ignore` относит все семь к игнорируемым — после фильтра список
  пуст. Гейт лока `in_dev -> review` пройдёт.
- `tasks/01M1NEEYSP0QWPMXHG0BK591M7/acceptance_tests/` (локed
  test_author'ом) — 18/18 зелёных без единой правки: `python3 -m
  pytest tasks/01M1NEEYSP0QWPMXHG0BK591M7/acceptance_tests/ -q`.
- Полный набор `tests/` после подтяжки: 1400 passed, 417 subtests
  passed, 0 ошибок, 0 регрессов (`python3 -m pytest tests/ -q`).
- `python3 scripts/guard.py tasks/01M1NEEYSP0QWPMXHG0BK591M7/SPEC.md
  tasks/01M1NEEYSP0QWPMXHG0BK591M7/PLAN.md` — ок.
- Рабочее дерево этого запуска в какой-то момент теряло
  `tasks/01M1NEEYSP0QWPMXHG0BK591M7/` целиком (git status показывал
  все файлы задачи как `deleted` без staged-изменений) — восстановлено
  `git checkout -- tasks/01M1NEEYSP0QWPMXHG0BK591M7/` из HEAD, руками
  ничего не переписывалось; упомянуто на случай, если это системный
  симптом, а не разовая случайность.

## Замечания REVIEW.md итерации 3 закрыты (ANSWER-3)

REVIEW.md (итерация 3, `changes_requested`) держал реестр R1-F1..R1-F4
без единого коммита с итерации 1: `foreign_live_lease` не сверяла
`hostname` перед `_pid_alive` (major, R1-F1), предупреждение не несло
роль/шаг (minor, R1-F2), грамматика формулировки (minor, R1-F3), 13
юнит-тестов без докстринга «Ловит мутацию: …» и ни одного теста с
чужим hostname (major, R1-F4). Оператор (ANSWER-3): исправить все
четыре, реестр закрыть по леджеру, ничего сверх замечаний не менять,
бюджет поднят до 70.

- **R1-F1** — `orchestrator/lease.py::foreign_live_lease` (строка 150)
  теперь сравнивает `row["hostname"] == socket.gethostname()` ПЕРЕД
  `_pid_alive` — тот же приём, что уже применяют `lease.acquire`
  (строка 73), `catalog._lease_holder_suffix` и `pause.cmd_pause_now`:
  для СВОЕГО host мёртвый pid по-прежнему даёт `None` (живость
  проверяема и опровергнута), для ЧУЖОГО host pid не проверяется вовсе
  — heartbeat остаётся единственным критерием (адрес непроверяем
  локальной таблицей процессов, поэтому не трактуется ни как «жив
  ложно», ни как «мёртв ложно»). Докстринг `foreign_live_lease`
  переписан под новое поведение.
- **R1-F2** — `warn_foreign_live` резолвит `role = runner.step_role(t)`
  и `step = t["state"]` (отложенный импорт `runner` — тот же приём, что
  `pause.cmd_pause_now` уже применяет по той же причине цикла
  импортов), подмешивает `role=…, step=…` в `detail`, только когда
  `role is not None`.
- **R1-F3** — текст предупреждения переформулирован: «она может
  активно работать над задачей; предупреждение не блокирует
  выполнение» — грамматически корректно, состав `detail` не менялся.
- **R1-F4** — всем 13 методам (`tests/test_lease.py` — 9,
  `tests/test_pause.py` — 2, `tests/test_release.py` — 2) добавлен
  докстринг с конкретной заявкой «Ловит мутацию: …»; добавлены два
  новых теста: `tests/test_lease.py::
  test_foreign_host_live_heartbeat_unaddressable_pid_returns_the_row`
  (чужой host + заведомо мёртвый локально `_dead_pid()` + свежий
  heartbeat -> живая строка — фиксирует R1-F1 регрессом на будущее) и
  `tests/test_lease.py::test_warn_foreign_live_includes_role_and_step_when_known`
  (T001 в `in_dev` -> `role=developer`, `step=in_dev` — фиксирует
  R1-F2).

Побочный эффект исправления R1-F1 (ожидаемый, не дефект): до фикса
lease на ЧУЖОМ host с непроверяемым локально pid молча трактовался как
«не жив» — два существующих теста T062-эпохи (`tests/test_release.py::
test_journals_former_holder_with_numeric_heartbeat_age`,
`::test_row_replaced_between_read_and_delete_is_not_removed`),
использующие `HOLDER_HOST` («chужой» hostname) со свежим heartbeat,
раньше не видели предупреждения вовсе. После фикса `warn_foreign_live`
на этих сценариях честно печатает и журналирует предупреждение — оба
теста адаптированы читать запись САМОГО снятия по `action == "lease
снят Оператором"`, а не первую/единственную запись журнала; поведение,
которое они изначально проверяли (гонка «строка сменилась между
чтением и удалением»), не изменилось. Комментарий-обоснование выбора
`HOLDER_HOST` в `tests/test_release.py` (строки перед
`test_release_warns_on_foreign_live_lease`) обновлён — прежний текст
объяснял выбор «своего» host предположением, ставшим неверным после
R1-F1.

Реестр REVIEW.md отмечен по каждой из четырёх записей `fixed` с
описанием правки в колонке «решение» (коротко) — закрытие в `accepted`
остаётся за ревьювером следующей итерации.

### Проверено исполнением (итерация после ANSWER-3)

- `python3 -m pytest tests/test_lease.py tests/test_pause.py
  tests/test_release.py -q` — 58 passed (было 56 — R1-F4 добавил два
  новых теста).
- `python3 -m pytest tasks/01M1NEEYSP0QWPMXHG0BK591M7/acceptance_tests/
  -q` — 18 passed, без единой правки состава (лок не тронут).
- `python3 -m pytest tests/ -q` — 1402 passed, 417 subtests passed, 0
  ошибок, 0 регрессов (было 1400 — прирост ровно на два новых теста
  R1-F4).
- `python3 scripts/guard.py tasks/01M1NEEYSP0QWPMXHG0BK591M7/SPEC.md
  tasks/01M1NEEYSP0QWPMXHG0BK591M7/PLAN.md
  tasks/01M1NEEYSP0QWPMXHG0BK591M7/REVIEW.md` — «GUARD: ок (3 файлов)».
- `python3 scripts/codebase_map.py` — перегенерирован тем же коммитом
  (правка `orchestrator/lease.py`): новая запись `lease.py` ->
  `orchestrator/runner.py` в «Импортирует» (отложенный импорт внутри
  `warn_foreign_live` тоже учитывается статическим разбором).
- `git diff --stat` затрагивает только `orchestrator/lease.py`,
  `tests/test_lease.py`, `tests/test_pause.py`, `tests/test_release.py`,
  `docs/codebase-map.md`, `tasks/01M1NEEYSP0QWPMXHG0BK591M7/{PLAN,
  REVIEW}.md` — ничего сверх замечаний реестра не менялось
  (ANSWER-3).

## R4-F1 закрыт (ANSWER-4)

REVIEW.md итерации 4 (`changes_requested`) держал единственный открытый
блокер R4-F1: `python3 scripts/guard.py --all` падал на
`tasks/01M1NEEYSP0QWPMXHG0BK591M7/SPEC.md` — обязательная секция
«## Оценка объёма и деление» (новое правило `scripts/guard.py::
split_assessment_errors`, принесено подтяжкой main задачи
01M1KS8K9RXWHX2PW3ZKB0P903) отсутствовала. Правка SPEC.md — не зона
developer; Оператор (ANSWER-4) внёс секцию сам (обоснование монолита,
«монолит принят Оператором 04.09») в SPEC артефактной и кодовой ветки
коммитом `0dbe7969`. Действие разработчика по ANSWER-4: подтянуть
актуальный SPEC, убедиться, что `guard.py --all` зелёный, реестр
REVIEW.md разметить `fixed` по R4-F1, PLAN в `ready`, сдать шаг —
больше ничего.

### Проверено исполнением (после ANSWER-4)

- HEAD = `0dbe7969` — включает правку SPEC.md Оператором поверх
  `383782d9` (REVIEW.md итерации 4).
- `git diff artifact/01m1neeysp0qwpmxhg0bk591m7:tasks/01M1NEEYSP0QWPMXHG0BK591M7/SPEC.md
  tasks/01M1NEEYSP0QWPMXHG0BK591M7/SPEC.md` — пусто: артефактная и
  кодовая копии SPEC совпадают дословно.
- `python3 scripts/guard.py --all` — «GUARD: ок (429 файлов)» — CI-джоб
  «guard.py по всем артефактам задач» больше не падает.
- `python3 -m pytest tasks/01M1NEEYSP0QWPMXHG0BK591M7/acceptance_tests/
  -q` — 18 passed, состав не менялся (лок не тронут).
- `python3 -m pytest tests/ -q` — полный набор без регрессов (см. REVIEW.md
  «Проверено исполнением» для полного вывода прогона той же итерации).
- Код фичи (`orchestrator/lease.py`/`pause.py`/`release.py` и их тесты)
  этой правкой не тронут — диф ограничен SPEC.md, PLAN.md, REVIEW.md.
