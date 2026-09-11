---
task: 01M1TNMBY8G3AH3MYCB07RW14N
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Циклы run/auto отвязаны от процесса сессии Оператора (второй заход)

## Подход

Реализация перенесена готовым диффом из ветки `keep/01m1nwchvt-code`
(закрытая задача 01M1NWCHVTYQ0M8PCJ1YJ2N78P), как и предписывает SPEC —
не переписана заново. Перенос сделан трёхсторонним слиянием
(`git apply --3way` на диф `HEAD...keep/01m1nwchvt-code` по зонам этой
задачи), потому что main с момента `keep/01m1nwchvt-code` успел
разойтись в тех же файлах двумя чужими, уже смерженными задачами:
`auto --wait-zone` (01M1VBEAWZW4EBZHKMGNBBK648, `orchestrator/auto.py`/
`docs/operator-session.md`) и `same_host_ok` у lease
(01M1VBEDGMEXHVGWAH42FTDZ4X, `orchestrator/lease.py`). Оба перекрытия
разрешены вручную, содержательно объединяя обе стороны (не выбором
одной), без потери ни одной из механик:

- `orchestrator/lease.py::acquire`/`run_locked` несёт ТЕПЕРЬ оба
  keyword-only параметра, `same_host_ok` и `force`, независимых друг от
  друга (разные вызыватели: `budget` — первый, `kill` — второй; порядок
  проверки — `force` даёт приоритет, `same_host_ok` внутри ветки «не
  force»).
- `orchestrator/auto.py::cmd_auto` держит и параметр `wait_zone`
  (сигнатура и вызов `_cmd_auto(conn, task_id, sid, wait_zone)`), и
  новую обёртку `try/except BaseException` вокруг `lease.run_locked`
  (требование 7, журналирование обрыва) — оба поверх одного и того же
  тела функции.
- `orchestrator/artel.py` — таблица импортов и диспетчер команд собраны
  из обеих сторон (`liveness`/`store`/`config` для детача, `notes`/
  `watch` для уже смерженных команд).
- `docs/operator-session.md` — оба абзаца раздела «Запуски и рабочие
  копии» (zone-wait и детач) сохранены, последняя строка про
  «`run`/`auto` — только фоновыми процессами» заменена абзацем про
  детач/`stop` (тем же смыслом, точнее).

`tests/test_git_fixation.py` (диф применился с конфликтами по тем же
причинам — соседние правки чужих задач сдвинули контекст) объединён тем
же способом: венв-заглушка (`_provision_stub_venv`) и REVIEW.md-заглушка
+ ленивое заведение ветки кода в `enter_in_dev` — из `keep`, остальное
содержимое файла (в т.ч. подключение `stat`) не тронуто мимо самого
дифа.

Помимо трёхстороннего слияния кода, эта задача добавляет две вещи,
которых не было в `keep`-диффе, но которые уместны без выхода за
зону/требования SPEC:

1. Краткое описание команды `stop` и флага `--attach` в модульном
   докстринге `orchestrator/artel.py` (строка «Команды:» и абзац после
   `auto <id>`) — сам `keep`-дифф этот докстринг не трогал вовсе (гэп
   подтверждён прямым сравнением `git show keep/01m1nwchvt-code:
   orchestrator/artel.py`), а Команды: — единственное описание CLI,
   которое видит Оператор по `--help`; без строки про `stop`/`--attach`
   они были бы «невидимой» командой в собственной документации модуля.
2. `tests/test_detached_cycle.py` и правка `tests/test_git_fixation.py`
   перенесены байт-в-байт из `keep` (test_author их не трогает — они
   не под `tasks/<id>/acceptance_tests/`), синтаксис и прогон
   проверены на этом рабочем месте отдельно.

`orchestrator/doctor/` (требования 4 и 8) не входит в зоны задачи и не
менялся: как и предсказывал SPEC «Обоснование монолита», различение
живости и трёх состояний цикла — прямое следствие того, что теперь
именно отвязанный процесс несёт `leases.pid`/`leases.session_id`
(следствие шага 1) и что его штатный выход снимает lease через тот же
`finally` в `lease.run_locked` (следствие шагов 2-3) — существующий
`doctor.check_leases`/`catalog._lease_holder_suffix` уже читает именно
эти два факта, без единой новой строки кода. Подтверждено полными
прогонами `tests/test_doctor.py` (126 тестов, зелены без изменений) и
приёмочными AC-8/AC-12 (см. «Влияние на систему»).

`--wait-zone` как CLI-флаг `artel.py auto` по-прежнему не существует
(подтверждено `docs/operator-session.md`, абзац zone-wait: «отдельного
флага командной строки на каждый вызов эта задача не заводит» —
намеренно, `orchestrator/artel.py` вне зоны ТОЙ задачи). Моя обёртка
`_cmd_auto_or_detach` парсит только `--attach`, любой другой токен
(включая `--wait-zone`) молча остаётся в позиционных аргументах и
игнорируется — байт-в-байт то же поведение, что было у диспетчера ДО
этой задачи (`auto.cmd_auto(rest[0])`), не регрессия.

## Шаги

1. `orchestrator/artel.py`: разбор `--attach` (`_task_id_and_attach`),
   самозапуск отвязанным процессом (`_launch_detached`) для `run`/`auto`,
   новая команда `stop` (`_cmd_stop`) — SIGTERM держателю lease с
   разбором «чужой host»/«нет lease»/«pid уже мёртв»; докстринг модуля
   дополнен командой `stop`/флагом `--attach`.
2. `orchestrator/auto.py`: обработчик SIGTERM (`_on_sigterm`,
   `_stop_requested`), установка обработчика в начале `cmd_auto`,
   проверка флага на границе между итерациями цикла со штатным
   `auto_stop(..., alert=False)`, журналирование обрыва
   (`try/except BaseException` вокруг `lease.run_locked`) — совместно с
   уже смерженным `wait_zone`.
3. `orchestrator/lease.py`: параметр `force` у `acquire`/`run_locked` —
   перешагивает отказ «сессия свежая», с особой причиной перехвата
   «kill switch» в журнале, когда lease был свежим — совместно с уже
   смерженным `same_host_ok`.
4. `orchestrator/cleanup.py`: снимок lease ДО `run_locked(force=True)`
   (`holder_before`), SIGKILL прежнему живому держателю на этом host
   (`_cmd_kill`) — до снятия lease и уборки хвостов.
5. `docs/operator-session.md`: абзац в разделе «Запуски и рабочие
   копии» о том, что `run`/`auto` отвязываются от процесса сессии, и о
   команде `stop`.
6. Юнит-тесты `tests/test_detached_cycle.py` (новый файл, 24 теста):
   разбор argv, `_launch_detached` (argv самозапуска, `start_new_session`,
   нумерация логов, резолвинг префикса id), `_cmd_stop` (адресация,
   отказы), `force` у `lease.acquire`, SIGKILL держателя в `cleanup.
   cmd_kill` — все в изоляции (моки), без реального `claude`/сети.
7. `tests/test_git_fixation.py`: венв-заглушка (`_provision_stub_venv`,
   вызывается в `RealPultGitTest.setUp`) и REVIEW.md-заглушка + ленивое
   заведение ветки кода в `enter_in_dev` — иначе приёмочный стенд
   `acceptance_tests/_sandbox.py` (реальный отдельный процесс роли) не
   проходит собственный гейт `runner.role_env`/гейт ёмкости диффа
   раньше, чем успевает проверить предмет задачи.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 (детач по умолчанию, pid/лог/подсказка) | 1 |
| 2 (`--attach` — прежнее поведение) | 1 |
| 3 (lease несёт pid/session_id цикла, heartbeat от цикла) | 1 (следствие архитектуры самозапуска, без отдельного кода) |
| 4 (`status`/`doctor` — живость по циклу) | 1, 3 (следствие корректного `leases.pid`; `catalog._lease_holder_suffix`/`doctor.check_leases` не меняются, SPEC AC-13) |
| 5 (`stop` — штатная остановка между шагами) | 1, 2 |
| 6 (`kill` — немедленное прерывание, включая отвязанный процесс) | 3, 4 |
| 7 (обрыв не через `stop` — запись в журнал) | 2 |
| 8 (`doctor` — три состояния цикла) | следствие шагов 2-4 (см. «Подход»), проверка — существующий `doctor.check_leases`, не новый код |

## Влияние на систему

Механика lease (`orchestrator/lease.py`) — общая точка ВСЕХ мутирующих
команд (`run`, `auto`, `advance`, `approve`, `reject`, `kill`, `budget`,
`workspace`) — новый параметр `force` добавлен со значением по умолчанию
`False` и не меняет поведение существующего `same_host_ok`
(01M1VBEDGMEXHVGWAH42FTDZ4X) — оба флага независимы, `budget` по-прежнему
единственный вызыватель `same_host_ok=True`, `kill` — единственный
вызыватель `force=True`.

`auto.cmd_auto` ставит глобальный обработчик `signal.signal(SIGTERM,
...)` на весь процесс — затрагивает только процессы, реально запущенные
через `auto` (в т.ч. под `--attach`); `run`-процессы (без цикла)
обработчик не ставят, SIGTERM для них ведёт себя как раньше
(неперехваченный сигнал завершает процесс).

Самоперезапуск (`_launch_detached`) резолвит себя через
`Path(__file__).resolve()` и `sys.executable` — не зависит от cwd
вызывающей команды и не расширяет поверхность запуска (тот же
интерпретатор, тот же файл).

`orchestrator/doctor/`/`catalog._lease_holder_suffix` — существующий код,
эта задача его не меняет (SPEC AC-13, требование явно оговорено):
различение трёх состояний — следствие того, ЧТО кладётся/убирается в
таблицу `leases`, не новой проверки. Откат: убрать `force` у
`lease.acquire`/`run_locked`, `_launch_detached`/`_cmd_stop` из
`artel.py`, обработчик SIGTERM и `try/except` из `auto.py`, снимок
`holder_before` из `cleanup._cmd_kill` — по отдельности, без потери
прежнего (не-детач) поведения `run`/`auto`/`kill` и без потери
`wait_zone`/`same_host_ok` (эти два — не предмет отката, живут своим
кодом).

Прогоны на этом рабочем месте, все зелёные без регрессии (передний
план, с явным таймаутом, по затронутым модулям — полный `tests/` не
гонялся, это дело CI):

- `tests/test_detached_cycle.py` (новый, 24) — изолированные моки.
- `tests/test_lease.py` (не в зоне), `tests/test_lease_pgid_store.py`,
  `tests/test_auto_cycle.py`, `tests/test_git_fixation.py` (41) —
  совместно, 151 тест.
- `tests/test_doctor.py` (126, требования 4/8 — доктор не в зоне,
  контрольный прогон).
- `tests/test_kill_cleanup.py` (не в зоне, AC-13 требует зелёным без
  правок) — зелен.
- Потребители `enter_in_dev`, затронутого шагом 7: `tests/
  test_acceptance_tests_flow.py`, `tests/test_answer.py`, `tests/
  test_amend.py`, `tests/test_gitcmd_branch_reads.py`, `tests/
  test_pause_now.py`, `tests/test_multitarget.py`, `tests/
  test_step_refixation.py`, `tests/test_timeout_checkpoint.py`, `tests/
  test_step_autocommit.py`, `tests/test_workspace.py` — совместно 264
  теста, зелены.
- Приёмочная планка задачи (`tasks/01M1TNMBY8G3AH3MYCB07RW14N/
  acceptance_tests/`, реальные отдельные процессы ОС): 13 из 14 методов
  зелены (AC-1..AC-12 полностью, AC-13 частично — см. «Риски» п.1).

## Риски

1. **AC-13 (`Ac13ExistingSuiteStaysGreenTest`) красный на этом рабочем
   месте по причине ВНЕ зоны задачи.** Планка прогоняет `tests/
   test_liveness.py` отдельным subprocess'ом, и
   `TerminateProcessGroupTest.test_kills_the_leader_and_returns_a_
   positive_count` не проходит: `terminate_process_group` возвращает 0
   вместо ожидаемого `>=1` — `os.killpg`/доставка сигнала процессной
   группе, судя по всему, не работает в песочнице этого рабочего
   места (детали среды исполнения агента вне видимости роли).
   Проверено прямым сравнением: тот же тест тем же способом падает и
   на чистом `HEAD` БЕЗ единого изменения этой задачи (`git stash -u`
   + прогон в изоляции) — `orchestrator/liveness.py` и `tests/
   test_liveness.py` не в зоне задачи и не тронуты ни одной правкой
   этого шага. Класс — не дефект переноса, а ограничение конкретного
   рабочего места; остальные 4 теста того же файла
   (`TerminateProcessGroupTest.*`, `GroupKillDetailTest`) на этом же
   рабочем месте зелены, включая `test_kills_every_member_of_the_
   group_not_just_the_leader`, который логически строже. Отдельные
   прогоны `tests/test_lease.py`, `tests/test_lease_pgid_store.py`,
   `tests/test_auto_cycle.py` (все три модуля, названные тем же
   критерием AC-13) — зелёные.
2. `--wait-zone` не подключён в диспетчер `artel.py` (см. «Подход») —
   это намеренное состояние чужой, уже закрытой задачи
   (01M1VBEAWZW4EBZHKMGNBBK648), не пробел этой; упомянуто здесь
   только чтобы явно снять вопрос «а не должен ли `_cmd_auto_or_
   detach` его парсить» на ревью.

## Предложения системе
- `docs/operator-session.md`, раздел «Обходной сценарий вместо команды
  пульта»: список из пяти задач-обходов (zone-wait, budget, answer,
  note, watch) не включает регистрацию находки «SPEC/PLAN закрытой
  задачи можно переносить трёхсторонним git-слиянием (`git apply
  --3way`), когда main разошёлся тем же файлом с момента `keep`-ветки»
  — на будущее для похожих «второй заход» задач стоило бы явно назвать
  этот приём в скиле coding-standards (класс: перенос готового диффа
  из закрытой/архивной ветки поверх ушедшего вперёд main), а не
  полагаться на то, что каждый разработчик изобретёт его заново.
