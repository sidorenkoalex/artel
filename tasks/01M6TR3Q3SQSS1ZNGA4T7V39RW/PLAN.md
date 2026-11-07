---
task: 01M6TR3Q3SQSS1ZNGA4T7V39RW
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Прогоны в контейнере по запросу роли — plank-run и suite-run для проекта с раннером compose

## Подход

Одна атомарная смена механики (SPEC, «Обоснование монолита»): запрос пишет
команда роли, исполняет его процесс пульта, ведущий шаг роли.

- **Очередь и запрос** — в `orchestrator/suite_run.py` (хозяйство каталога
  `suite-run`): `suite_lock.directory()/<id>/requests/<n>.json` — объект ровно
  с ключами `kind`/`file`/`task_id`/`time`; итог — `<n>.result.json`; взятие
  исполнителем — маркер `<n>.taken.json` (по нему `--wait` отличает «в
  очереди» от «прогон идёт»). Номер запроса — общий с нумерацией прогонов
  `suite-run` задачи (`_next_number`: логи, `run.json`, `result.json`, файлы
  очереди), файл создаётся `O_EXCL`. Режим запроса включает
  `request_mode(conn, task_id, target)`: `runner.in_role_environment()` и
  раннер профиля задачи (`project_profile.for_task_target(...).profile`,
  у записи из компонентов — компонент задачи) равен `compose`. Без живого
  lease (`lease.is_live`) — отказ; в очереди уже 3 невзятых-неисполненных —
  отказ, называющий предел 3.
- **suite-run**: в режиме запроса после прежних проверок (профиль, рабочая
  копия, перечень упавших для `--failed`) вместо замка и отвязанного фона —
  запрос; `run.json` получает номер запроса и ключ `request` (pid нет).
  `_wait` на `run.json` с `request` ждёт итог запроса этого номера
  (`wait_request`); отказ разработчику нового полного прогона — прежний,
  раньше всего (требование 6).
- **plank-run**: сигнатура `cmd_plank_run(task_id, file_arg=None, *extra)`
  — диспетчер передаёт весь `rest`; `--wait <минуты>` — чтение итога
  последнего запроса планки (`wait_request`, предел
  `SUITE_RUN_MAX_WAIT_MIN`), неизвестный третий аргумент — отказ с его
  именем. Режим запроса — до прежнего пути; вне его путь прежний побайтно.
- **Исполнитель** — класс `RoleRequestExecutor` в `orchestrator/runner.py`,
  в отдельном потоке процесса пульта: стартует в `run_agent_once` до
  запуска агента (сразу отказывает всем лежащим запросам итогом «запрос без
  шага роли этой задачи в полёте»), останавливается до `_account_step`
  (`try/finally` вокруг `_spawn_and_wait`) — агента по-прежнему ждёт
  единственный `proc.wait`. Проверки запроса: читаемость, ровно четыре
  ключа, вид, `task_id`, раннер `compose` профиля задачи, вид для роли шага
  (разработчику `full` — отказ), файл планки — файл планки задачи
  (`plank_run.request_file_refusal`: черновик в `tests_writing`, иначе
  ссылка документов) или её долгоживущий файл. Принятый запрос — маркер
  «принят шагом <session_id lease>/<попытка>, <время>», дочерний прогон —
  новый интерпретатор пульта (`cwd=config.ROOT`, окружение пульта без
  `ARTEL_ROLE`, `process_group=0`, без `start_new_session`): планка —
  `cmd_plank_run` целиком, полный набор/повтор — `suite_run.background`
  в этом же процессе (планка — с `ref_if_no_draft=True`: нет каталога
  черновика на диске — зафиксированная планка ссылки); замок полных прогонов берёт исполнитель без ожидания
  (занят — итог «прогон не начат: замок занят <держатель>») и передаёт
  дочернему (`suite_lock.hand`), тот принимает его `adopt`.
- **Конец шага до итога**: `SIGTERM` дочернему прогону (он превращает его в
  `KeyboardInterrupt`, так что `finally` `_compose_report_run` снимает стенд
  прежним `_compose_teardown`; дочерний прогон ещё и следит за родителем —
  на случай `pause --now`/`kill` процесса пульта), ожидание выхода
  `COMPOSE_TEARDOWN_TIMEOUT_SEC + REQUEST_TEARDOWN_MARGIN_SEC`, при невыходе
  — `killpg` только группы дочернего прогона; затем всегда `docker ps -a
  --filter label=com.docker.compose.project --format {{json .}}` и явный
  `docker compose --project-name <p> down --remove-orphans` (без `-v`)
  проектам с префиксом `artel-<id строчными>-` и меткой `artel.run-pid`,
  равной pid объекта дочернего процесса; замок, оставшийся за дочерним
  прогоном, снимается; итог «прерван: шаг роли завершён». Оставшимся
  невзятым — «не исполнен: шаг роли завершён».
- **Журнал**: действие `прогон по запросу роли` (константа
  `suite_run.REQUEST_ACTION`), текст «№n: <вид>, итог <…>», автор
  `orchestrator`, напрямую `store.journal` из потока исполнителя своим
  соединением; `suite_lock.deferrable` не трогается.

## Шаги

1. `suite_run.py`: очередь запросов, нумерация, `request_mode`,
   `submit_request`, `wait_request`, дочерний прогон (`_REQUEST_CHILD`,
   `request_child`), режим запроса в `cmd_suite_run` и `_wait`.
2. `plank_run.py`: разбор `--wait`/лишнего аргумента, режим запроса,
   `request_file_refusal`.
3. `artel.py`: диспетчер `plank-run` (весь `rest`), строка справки,
   дополнение основания белого списка.
4. `runner.py`: `RoleRequestExecutor` и его вызов в `run_agent_once`.
5. Регенерация `docs/codebase-map.md`; прогоны тестов затронутых модулей и
   долгоживущего файла задачи, планки (`plank-run`).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 2 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1, 2 |
| 5 | 2, 3 |
| 6 | 1, 4 |
| 7 | 1, 2 |
| 8 | 1, 4 |
| 9 | 4 |
| 10 | 4 |
| 11 | 2, 4 |
| 12 | 1, 4 |
| 13 | 4 |
| 14 | 4 |
| 15 | 1 (гейты файл итога не читают) |
| 16 | — (`acceptance.py` не меняется) |
| 17 | 1 |

## Влияние на систему

- Отказ `COMPOSE_ROLE_REFUSAL` и `acceptance.py` не меняются: исполнитель
  зовёт прежние узлы вне окружения роли.
- `suite_lock.deferrable` не расширяется, журнал пишет только исполнитель.
- Существующие тесты `run_agent_once` с `FakeProc`: исполнитель на пустой
  очереди не создаёт файлов, не открывает БД и не пишет журнал; ожидание
  агента — прежний единственный `proc.wait`.
- Гейты свой итог берут собственным прогоном; файл итога запроса никем из
  них не читается (AC-18).
- Откат — revert коммита задачи: файлы очереди в каталоге `suite-run`
  остаются безвредным мусором, их уберёт `prune` по общему правилу каталога.

## Риски

- Ожидание конца шага до `COMPOSE_TEARDOWN_TIMEOUT_SEC + запас` (≈135 с)
  при оборванном прогоне — плата за честное снятие стенда.
- `process_group=` требует Python ≥ 3.11.

## Проверка

- `tests/test_01m6tr3q3sqss1znga4t7v39rw_role_requests.py` — 32 passed.
- Планка (`artel.py plank-run 01M6TR3Q3SQSS1ZNGA4T7V39RW`) — 6 passed, код 0.
- Тесты затронутых модулей, пачками в переднем плане (`-o timeout=120`):
  plank_run (6 файлов) + suite_run/developer/readonly_db/deferred_journal +
  `test_cmd_approve_dispatch.py` — 75 passed; `test_agent_failure.py`,
  `test_step_cost.py`, `test_agent_failure_cli_isolation.py`, compose_run/
  compose_docker/role_env_compose, `test_doctor_compose_stands.py` — 175
  passed, 1 skipped.
- `tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py` и
  `tests/test_01m46c776szemypbqgpnjn1txy_suite_run_appendix.py` в шаге роли
  не проходят: отвязанный фон `suite_run.background` копии пульта виснет на
  `git show refs/artifacts/…:PLAN.md` через обёртку `role_bin/role_git.py`,
  унаследованную из PATH процесса роли (`/bin/ps`: фон → `python3 -I -S
  …/role_bin/../role_git.py … show …`, лог прогона пуст 4 мин). Путь
  `background`/`appendix_tree` этой задачей не меняется (в `suite_run.py`
  вне режима запроса тронут только номер `_new_log` → `_next_number`);
  вердикт по ним — CI и гейт приёмки, вне окружения роли.

## Предложения системе

- Прогон 28 файлов тестов затронутых модулей в шаге разработчика идёт
  дольше 10 минут последовательно, а `-n` в шаге рубит `conftest.py`
  (все воркеры «node down»): нужен штатный путь параллельного прогона
  выбранных файлов для роли (класс «нет команды пульта»).
- Тесты, запускающие копию пульта с отвязанным фоном `suite-run`
  (`tests/test_01m462…_suite_run.py`, `tests/test_01m46c…_suite_run_appendix.py`),
  в шаге роли виснут на обёртке `role_git` из PATH роли и оставляют
  осиротевшие фоны в `$TMPDIR` (у меня их набралось шесть, старшему —
  1,5 ч); `cli()` таких тестов снимает только свою группу. Нужна либо
  очистка PATH роли в песочнице теста, либо пометка «не для шага роли».
