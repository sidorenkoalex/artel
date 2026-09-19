---
task: 01M2XFSE8G3MBRHHQR38H53J1M
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Мьютекс merge держит процесс, не сессия: очередь для параллельных approve одного пульта и повтор подтяжки при сдвиге main

## Подход

Ключ владения мьютексом merge-окна и записью очереди `merge_queue`
меняется с «сессия» на «процесс» = пара (session_id, pid); pid
вызывающего процесса берётся внутри `merge_lock`/`merge_queue` через
`os.getpid()` — так же, как он уже пишется в строку при `set_merge_lock`/
`enqueue_merge_wait`. Публичные сигнатуры `merge_lock.acquire(conn,
task_id, session_id)`, `merge_lock.release(conn, session_id)`,
`merge_queue.wait_for_window(conn, task_id, sid)` НЕ меняются: их мокают
`tests/test_merge_gate_ci_wait.py` и приёмочные тесты задачи
(`fake_acquire(conn, task_id, sid)`, `fake_release(conn, sid)`,
`fake_wait_for_window(conn, task_id, sid)`), а `_cmd_approve_merge_gate_
cycle` зовёт их как сегодня (AC-1 третий тест требует, чтобы цикл гейта
не менялся и уходил в очередь тем же путём).

Опорные функции `store.py` получают pid явным параметром (не скрытым
`os.getpid()` внутри store — store остаётся тонким CRUD, pid держателя
для `set_merge_lock`/`enqueue_merge_wait` и так приходит снаружи):
`release_merge_lock(conn, session_id, pid)`, `touch_merge_queue_heartbeat(
conn, session_id, pid, ts)`, `dequeue_merge_wait(conn, session_id, pid)`
— `WHERE session_id=? AND pid=?`. Приёмочный тест AC-9 прямо называет
ожидаемую форму: «`store.release_merge_lock` с обязательным pid».

`merge_lock.acquire`: ветка «свой» — `row["session_id"] == session_id and
row["pid"] == os.getpid()`; проверка живости (`_holder_is_dead`) идёт
ПОСЛЕ неё и не меняется — мёртвый держатель своей сессии (неживой pid на
своём host) перехватывается прежней записью «мьютекс merge перехвачен»
(AC-3, отдельный файл планки). Живой чужой процесс — тот же текст отказа,
что и чужой сессии, с добавленным pid держателя (AC-1: тексты сравниваются
после нормализации session_id, так что путь и f-строка одна).

`merge_queue`: `_current_holder_id` остаётся как есть (его контракт
проверяет `tests/test_merge_queue.py::CurrentHolderIdTest`), рядом
заводится `_current_holder_label` — «<task_id> (pid <pid>)» либо «?» без
держателя; им пользуются журнальная запись «ждёт merge-окна: держит …» и
`wait_suffix` (требования 6-7, AC-6). Продление heartbeat/снятие записи в
`wait_for_window` — по (sid, os.getpid()).

`fsm_merge_gate._push_merged_main`: отказ push классифицируется по
подстрокам stderr «cannot lock ref» / «non-fast-forward» / «fetch first»
(тексты git на движущийся main; НЕ голое «rejected» — «[remote rejected]
… hook declined» это отказ прав, требование 9). Класс «main сдвинулся» —
запись журнала «main сдвинулся во время окна — повтор подтяжки» и возврат
`"moved"`; тело гейта на `"moved"` возвращает `("moved", branch)` —
отдельный тег, который цикл `_cmd_approve_merge_gate_cycle` ведёт тем же
путём, что и `("wait", branch)`: ставит `deadline` только если он ещё не
задан (не сбрасывается, требование 9/AC-8), ждёт CI ветки (голова не
менялась — статус подтверждается быстро) и заходит в тело заново:
подтяжка увидит сдвинутый main -> `("wait", branch)` -> CI -> merge ->
push. Иные отказы push — прежние «merge FAILED» + `sys.exit`.

Итерация 2 (REVIEW R1-F1). Первая сдача возвращала на «moved» тот же
`("wait", branch)` и полагалась на паузу/потолок цикла ожидания CI, но
`_wait_for_branch_ci_green` при уже зелёном CI возвращается на первой
итерации ДО сверки `deadline` и без `sleep` — устойчиво отвергаемый push
крутил тело гейта горячим бесконечным циклом (пробник ревьювера: 26
заходов, 0 пауз). Поэтому тег отдельный, и ТОЛЬКО на пути «moved» цикл
перед новым заходом делает два шага: продлевает heartbeat мьютекса и
паузит `MERGE_GATE_CI_WAIT_POLL_SEC`, затем сверяет общий `deadline` —
истёк -> `_exit_moved_main_ceiling`: запись «merge FAILED» («main
сдвигался всё окно: потолок ожидания истёк после N повтор(ов) подтяжки»)
и `sys.exit` тем же стилем, что отказ по потолку в цикле ожидания CI;
задача остаётся на `merge_gate`, мьютекс снимает `finally`. Путь
`("wait", branch)` паузы не получает — после зелёного CI тело заходит
заново сразу, как и раньше. Итог: повтор ограничен `CEILING / POLL` (40
при текущих константах) заходами, потолок один на оба исхода.

Расхождения с оценкой SPEC по бюджету нет — четыре модуля и тесты, как и
оценено.

## Шаги

1. `orchestrator/store.py`: `release_merge_lock(conn, session_id, pid)`,
   `touch_merge_queue_heartbeat(conn, session_id, pid, ts)`,
   `dequeue_merge_wait(conn, session_id, pid)` — адресация процессом;
   докстринги про ключ владения.
2. `orchestrator/merge_lock.py`: `acquire` — условие «свой» по session_id
   И pid, текст отказа с pid держателя; `release` передаёт `os.getpid()`;
   модульный докстринг: держатель — процесс.
3. `orchestrator/merge_queue.py`: `_current_holder_label`, запись журнала
   и `wait_suffix` с pid держателя; `wait_for_window` продлевает/снимает
   свою запись по (sid, pid).
4. `orchestrator/fsm_merge_gate.py`: `_push_rejected_by_moved_main(stderr)`
   + `_push_merged_main` возвращает `"moved"` с именованной записью
   журнала; `_cmd_approve_merge_gate` на `"moved"` возвращает
   `("moved", branch)`; `_cmd_approve_merge_gate_cycle` на этом исходе —
   heartbeat, пауза `MERGE_GATE_CI_WAIT_POLL_SEC`, сверка общего
   `deadline` (`_exit_moved_main_ceiling` — «merge FAILED» + `sys.exit`),
   затем прежний путь ожидания CI и нового захода (итерация 2, R1-F1).
5. Тесты: `tests/test_merge_lock.py` (владение процессом, отказ с pid,
   одинаковый текст, перехват мёртвого своей сессии, release только
   держателем), `tests/test_merge_queue.py` (две записи одной сессии,
   heartbeat/снятие адресно, label с pid в журнале и суффиксе; ОДНА
   существующая точная сверка суффикса обновлена под новый формат с pid —
   см. «Риски»), `tests/test_merge_gate_ci_wait.py` (классификация отказа
   push, `"moved"` -> `("moved", branch)`, повтор без сброса потолка, иной
   отказ — «merge FAILED» + `SystemExit`; итерация 2: пауза на пути
   «moved», отсутствие паузы на пути `("wait", …)`, конечность повтора с
   РЕАЛЬНЫМ `_wait_for_branch_ci_green`, зелёным CI и вечно отвергаемым
   push — ровно `CEILING / POLL` заходов и `SystemExit`; общий потолок —
   отказ на первом «moved» после съеденного ожиданием CI потолка),
   `tests/test_doctor.py` — один вызов `store.release_merge_lock` получает
   pid (сигнатура).
6. `python3 scripts/codebase_map.py` тем же коммитом; прогон планки
   задачи и трёх затронутых модулей `tests/` с явным таймаутом.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (свой = session_id И живой pid) | 2, 5 |
| 2 (живой процесс той же сессии — тот же отказ с pid, уход в очередь) | 2, 5 |
| 3 (перехват мёртвого и повторный вход не меняются) | 2, 5 |
| 4 (release только своим процессом, store тем же образом) | 1, 2, 5 |
| 5 (очередь адресуется процессом, FIFO прежний) | 1, 3, 5 |
| 6 (журнал «ждёт merge-окна: держит …» с pid) | 3, 5 |
| 7 (суффикс status с pid, новых выводов нет) | 3, 5 |
| 8 (сдвиг main -> запись + повтор тела в том же approve) | 4, 5 |
| 9 (потолок CI не сбрасывается; иные отказы как раньше) | 4, 5 |
| 10 (тесты; три существующих модуля зелёные) | 5, 6 |

## Влияние на систему

- Затронуто: `merge_lock.acquire`/`release`, три функции `store.py`,
  `merge_queue.wait_for_window`/`wait_suffix`, `_push_merged_main`,
  одна строка `_cmd_approve_merge_gate` и ветка «moved» в цикле
  `_cmd_approve_merge_gate_cycle` плюс `_exit_moved_main_ceiling`
  (итерация 2). `merge_lock.touch_heartbeat` (только зовётся на новом
  пути), `_holder_is_dead`, `run_window`, `_wait_for_branch_ci_green`,
  `doctor`, `notes._silence_window_reason`, `session.py`, `liveness.py`,
  схема БД — не трогаются.
- Гейты/лимиты не ослабляются: мьютекс становится СТРОЖЕ (второй процесс
  своей сессии больше не проходит «как свой»), `release`/`dequeue`
  перестают снимать чужую строку; потолки `MERGE_GATE_CI_WAIT_CEILING_SEC`
  и `MERGE_QUEUE_WAIT_CEILING_SEC` прежние, повтор подтяжки не
  сбрасывает первый. Классификатор отказа push узкий (три подстроки),
  всё остальное — прежний `sys.exit`.
- Инварианты `docs/invariants.md` про мьютекс merge не упоминают
  сессию как ключ (grep пуст) — не задеты.
- Приёмочные планки ДРУГИХ (закрытых) задач, зовущие `store.release_
  merge_lock(conn, sid)` двумя аргументами и золотой снимок сигнатур
  `tasks/01M1SD5NZ79MWCEJDJ9JP6EPWS/acceptance_tests/test_ac4_public_
  signatures_unchanged.py` (`release_merge_lock: ("conn", "session_id")`)
  после задачи устареют. Они не гоняются ни CI (`pytest tests`), ни
  пультом (`acceptance.run` — только `tasks/<своя id>/acceptance_tests/`)
  — это исторические планки, править их роль не вправе; изменение
  сигнатуры требует SPEC (требование 4) и ожидается приёмочным AC-9 этой
  задачи.
- Откат — revert одного merge-коммита: схема БД не меняется, строки
  `merge_locks`/`merge_queue` прежнего формата.

## Риски

- `tests/test_merge_queue.py::test_queued_reports_minutes_waited_and_the_
  current_holder` сверяет суффикс `status` ТОЧНОЙ строкой без pid, а
  требование 7 дополняет тот же суффикс pid держателя — совместить
  нельзя. Ожидаемая строка теста обновлена под новый формат (сверка
  остаётся точной, ничего не ослаблено); приёмочный AC-9 гоняет модуль
  целиком в его текущем виде. Ревьюверу — проверить именно это место.
- Текст «cannot lock ref» git печатает и при локальном сбое блокировки
  ссылки (не только при сдвиге main) — тогда повтор подтяжки пойдёт
  циклом «пауза 90 с -> сверка потолка -> CI (уже зелёный) -> тело ->
  push»; отказ повторится, и через `CEILING / POLL` = 40 заходов цикл
  завершится `_exit_moved_main_ceiling` («merge FAILED», `sys.exit`)
  вместо немедленного `sys.exit`. Первая сдача утверждала это свойство,
  не имея его в коде (R1-F1); теперь сверка потолка и пауза стоят на
  самом пути «moved» и покрыты тестом с реальным циклом ожидания CI.
  Приемлемо: 40 заходов за час вместо бесконечного горячего цикла, а
  инцидент 13.09 нёс ровно этот текст.
- Легитимный сдвиг main получает лишние 90 секунд паузы перед повтором
  — на фоне ожидания CI в минуты это несущественно, зато число тяжёлых
  заходов (fetch/worktree/merge/карта/RETRO/push) ограничено не только
  временем, но и счётом.
- Ключ владения — (session_id, pid) буквально по SPEC, без hostname:
  совпадение pid на двух host'ах внутри одной session_id требует общей
  рабочей копии на два host'а — вне модели `session.py`.

## Предложения системе

- Золотой снимок сигнатур `store.py` в приёмочной планке закрытой задачи
  (`tasks/01M1SD5NZ79MWCEJDJ9JP6EPWS/acceptance_tests/test_ac4_public_
  signatures_unchanged.py`) переживает свою задачу и молча устаревает при
  каждом следующем изменении сигнатуры store — класс «залоченная планка
  закрытой задачи фиксирует то, что по определению будет меняться»;
  скил test-authoring мог бы просить у таких планок срок жизни (либо
  сверку с явным списком, который правится через SPEC).
- SPEC (требование 10 «существующие тесты остаются зелёными») и
  требование 7 (новый формат суффикса) противоречат друг другу для точной
  строковой сверки в `tests/test_merge_queue.py` — аналитику стоило бы
  называть тесты, которым нужна адаптация, отдельно от тех, что должны
  остаться зелёными без правок.
