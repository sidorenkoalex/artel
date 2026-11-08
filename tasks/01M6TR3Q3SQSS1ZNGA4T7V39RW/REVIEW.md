---
task: 01M6TR3Q3SQSS1ZNGA4T7V39RW
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Прогоны в контейнере по запросу роли — plank-run и suite-run для проекта с раннером compose

## Фаза A — план

- Таблица покрытия PLAN полна: требования 1–17 сопоставлены шагам; требование 16
  честно помечено «—» с пояснением (отказ `COMPOSE_ROLE_REFUSAL` не тронут, в
  `acceptance.py` только переименование `_compose_call` → `compose_call`, шаг 6).
- Шаги — единицы размера модуля (suite_run / plank_run / artel / runner / карта),
  плюс два возврата из verifying с причиной и прогоном CI. Монолит обоснован SPEC.
- Подход в конвенциях: очередь в хозяйстве `suite-run`, исполнитель — поток в
  `run_agent_once` вокруг `_spawn_and_wait`, агента ждёт прежний единственный
  `proc.wait`; `suite_lock.py` не тронут (ANSWER-1, ответ 6).
- «Влияние на систему» = diff: 5 файлов кода (`acceptance.py`, `artel.py`,
  `plank_run.py`, `runner.py`, `suite_run.py`) + карта + долгоживущий файл задачи;
  все в зонах SPEC; `artel.py` — ровно три правки мандата ANSWER-1 (диспетчер
  `rest[1:]`, строка справки, дополнение основания белого списка);
  `_ROLE_ALLOWED_COMMANDS`/`_ROLE_REFUSED_FLAGS`/`_ROLE_ALLOWED_SUBCOMMANDS` не
  тронуты. Откат описан (revert, файлы очереди — мусор под `prune`).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `plank_run._submitted` / `cmd_suite_run` → `suite_run.request_mode`: `runner.in_role_environment()` и раннер `project_profile.for_task_target(...).profile` (компонент задачи), не проекта; AC-26 (два компонента) зелёный |
| 2 | OK | `submit_request`: ровно `kind/file/task_id/time`, `requests/<n>.json`, атомарно через `os.link` tmp-файла; итог `<n>.result.json` |
| 3 | OK | номер — общий `_next_number` (логи, `run.json`, `result.json`, запросы); без `lease.is_live` — отказ до записи; БД — `suite_run._db()` (fallback только на чтение для Codex) |
| 4 | OK | `wait_request`: итог только своего номера; «в очереди (позиция N), прогон не начат» / «прогон не прерван, повтори»; предел `SUITE_RUN_MAX_WAIT_MIN` в `_wait_minutes` с именем константы и диапазоном |
| 5 | OK | диспетчер `cmd_plank_run(rest[0], *rest[1:])`; лишний аргумент — отказ с его именем; `--wait` — чтение итога; справка обновлена; основание белого списка дополнено, не заменено |
| 6 | OK | отказ разработчику в `cmd_suite_run` идёт раньше `request_mode` (AC-19) |
| 7 | OK | вне режима запроса путь прежний: вынос `_plank_source` с `ref_if_no_draft=False` побайтно даёт прежние ветки и прежний текст отказа «ссылка документов … не прочитана (git не ответил); планка не выложена»; `_new_log` → `_next_number` без смены поведения для задач без запросов. Планка AC-20/AC-24 (сравнение с базой) — зелёная |
| 8 | OK | дочерний прогон — новый интерпретатор пульта (`cwd=config.ROOT`, `-c REQUEST_CHILD`), без `fork`, без `start_new_session`; планка — `cmd_plank_run` целиком, полный набор — `background` в том же процессе; окружение пульта без `ARTEL_ROLE` (HOME пульта — признак роли снят) |
| 9 | OK | `suite_lock.acquire` без ожидания, занят — «прогон не начат: замок занят <describe>»; передача `hand`→`adopt` без гонки (adopt принимает замок и до `hand`: task/run совпадают) |
| 10 | OK | `start()` отказывает всем `pending_requests` по перечню файлов до запуска агента; маркер «принят шагом <session>/<попытка>, <время>»; `stop()` — «не исполнен: шаг роли завершён» |
| 11 | OK | `_refusal`: не-объект, лишний/недостающий ключ, вид, чужой id, раннер профиля задачи ≠ compose, `full` для developer, файл не у `plank`, файл вне планки/долгоживущего (`request_file_refusal`); тексты называют причину |
| 12 | OK | один поток — один запрос за раз; предел очереди 3 при записи с числом в тексте |
| 13 | OK | SIGTERM → `KeyboardInterrupt` в дочернем (finally `_compose_report_run` снимает стенд), ожидание `COMPOSE_TEARDOWN_TIMEOUT_SEC + 15`, затем `killpg` только группы дочернего (`process_group=0`); затем всегда `docker ps …` и `down --remove-orphans` без `-v` по префиксу `artel-<id>-` И метке `artel.run-pid` = `child.pid` объекта процесса; замок за дочерним снимается; всё в `finally` до `_account_step`; дочерний следит за родителем (pause --now/kill) |
| 14 | OK | `_finish` — единственное место записи журнала, `store.journal` автором `orchestrator`, действие «прогон по запросу роли»; `deferrable` не расширен |
| 15 | OK | файлы очереди гейтами не читаются; AC-18 зелёный |
| 16 | OK | `COMPOSE_ROLE_REFUSAL`, место и условие не изменены; переименование `compose_call` — тело и сигнатура прежние, старое имя нигде не осталось (grep по `orchestrator/ tests/ scripts/` — пусто) |
| 17 | OK | итог планки — только `requests/<n>.result.json`; `latest_request` фильтрует по виду; `run.json` с ключом `request` пишется только для `full`/`failed`; `background` `run.json` не переписывает, ключ переживает прогон; AC-23 зелёный |

## Замечания

Блокеров и major нет. Ниже — наблюдения minor (вкус/редкий сбой), правка в этой
задаче не требуется; в реестр не внесены, вердикт не держат:

- minor — `orchestrator/runner.py` `RoleRequestExecutor._handle`: между
  `suite_lock.acquire(...)` и `subprocess.Popen` в `_run_child` исключение
  (`store.lease_row`, `mark_taken` — OSError записи) уходит в `_loop` через
  `traceback`, а замок остаётся за живым pid процесса пульта до конца его жизни —
  полные прогоны машины встанут «замок занят». Окно узкое (ошибка ФС/БД); при
  случае — `try/except` с `suite_lock.release()` вокруг этого участка.
- minor — `orchestrator/runner.py` `_run_child`: исключение в `_down_leftovers`
  (например, `task_own_profile` бросает на сломанном профиле) оставит прерванный
  запрос без итога «прерван…» — `stop()` даст ему «не исполнен: шаг роли
  завершён». Сведения роли, на гейты не влияет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

(Замечаний blocker/major нет; наблюдения minor выше в реестр не заводились.)

## Вердикт

approved — все 17 требований реализованы, как сказано в SPEC; существующие тесты не
тронуты (diff `tests/` — только новый долгоживущий файл задачи); защищённые пути не
тронуты; изменения `artel.py` в рамках мандата ANSWER-1.

## Проверено исполнением

- `python3 -m pytest tests/test_01m6tr3q3sqss1znga4t7v39rw_role_requests.py -p no:cacheprovider -q -o timeout=300` — 32 passed за 166 с.
- `artel.py plank-run 01M6TR3Q3SQSS1ZNGA4T7V39RW` — 6 passed, код выхода pytest 0.
- `python3 -m pytest` по 11 файлам затронутых модулей (`test_*plank_run*` ×6,
  `test_suite_run.py`, `test_step_cost.py`, `test_agent_failure.py`,
  `test_01m6paj61d4pyap79adrpa6mwv_compose_run.py`,
  `test_01m5n8asj63zkf3m9etc7a3p5v_plank_layout_names.py`) — 211 passed,
  166 subtests passed.
- `python3 scripts/codebase_map.py` + `git diff docs/codebase-map.md` — расхождение
  только в `built_at_sha`, карта свежа (регенерацию откатил `git checkout`, дерево чистое).
- `grep -rn _compose_call orchestrator tests scripts` — пусто.
- `git diff <база>...HEAD --stat -- tests/` — только новый долгоживущий файл задачи, существующие тесты не меняются.
- Временную мутацию не вносил: заявки «Ловит мутацию» сверены по чтению; CI коммита 2cd3ec6d зелёный.

## Предложения системе

- Долгоживущий файл задачи идёт 166–196 с (порог 60 с) — каждый тест поднимает
  копию пульта и процесс-водитель шага. Стоит ли держать такие e2e-тесты в общем
  наборе или делить их на быстрые проверки исполнителя и одну e2e — решать Оператору
  (класс «долгий долгоживущий тест»).
- Ревьюер в шаге может по привычке запустить `scripts/codebase_map.py` и тем
  изменить рабочую копию; режим «только проверить» (`--check`) у генератора карты
  убрал бы этот риск.
