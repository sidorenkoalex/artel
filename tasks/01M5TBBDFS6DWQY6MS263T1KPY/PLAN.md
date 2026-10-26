---
task: 01M5TBBDFS6DWQY6MS263T1KPY
type: plan
author_role: developer
status: escalate
schema_version: 5
---

# PLAN: Эпики Э1 — эпик как сущность пульта, команды эпика и модель доски

## Подход
Эпик — строка новой таблицы `epics` и колонка `tasks.epic_id`. Весь SQL — в
`orchestrator/store.py` (правило `SqlOnlyInStoreTest`): некоммитящие
помощники `begin_immediate`, `get_epic`, `insert_epic`, `update_epic`,
`set_task_epic`, `epic_tasks`, `project_epics`, `project_tasks`,
`last_step_times`; `store.insert_task` получает keyword `epic_id`.

- Миграция (`schema._migrate_epics`): быстрая проверка «нет колонки
  `tasks.epic_id`» вне транзакции; при догоне — `BEGIN IMMEDIATE`,
  повторная проверка, `CREATE TABLE epics`, `ALTER TABLE tasks ADD COLUMN
  epic_id`, индекс, запись журнала с `task_id = config.EPICS_MIGRATION_JOURNAL_TASK_ID`
  последней (её `commit` закрывает транзакцию); БД без `steps` — без записи,
  явный `commit`. Свежая схема `SCHEMA` несёт ту же DDL тем же литералом.
- Модуль `orchestrator/epics.py` — команды `epic new|show|edit|close|add|remove`
  и общий узел проверки привязки `binding_refusal(conn, epic_id, project)`.
  Команды эпика — одна транзакция `BEGIN IMMEDIATE` без lease;
  `add`/`remove` — `lease.run_locked` по id задачи, транзакция внутри;
  существование эпика проверяется до lease и транзакции
  («эпик <id> не найден»).
- Привязка при заведении (`new --epic`, части деления): `_new_task_row`
  проверяет эпик в транзакции `BEGIN IMMEDIATE` и вставляет строку с
  `epic_id` той же транзакцией; `cmd_new` проверяет эпик заранее, до ТЗ,
  клона и ссылки документов.
- `--after`: `merge_after.declared_for_new` объединяет элементы строки ТЗ и
  `--after` с дедупликацией по полному id до `merge_after.check` и
  проверяет объединённый перечень.
- `approve --as-epic`: предварительная проверка в `fsm.cmd_approve` до
  `lease.run_locked` без записей (уже в эпике, не `spec_gate`, SPEC не
  прочитан, нет деления); эпик заводится в `_spawn_division_subtasks`
  перед частями — значит только вместе с ними (мягкие отказы гейта до него
  не доходят). Цель — первый абзац «Контекст».
- Модель доски `orchestrator/board.py::build_model(conn, project)` — только
  чтение, порядок детерминирован (карточки по id, рёбра отсортированы);
  `pin` — `watch._pin_head()`. Порядок задач эпика `ordered_nodes` — Кан
  с кучей по id. `waiting_on`: operator → ci → dependency
  (`zone_lock.queue_wait`) → role.
- `status`: строка задачи вынесена в `_status_line` без изменения текста;
  при хотя бы одной задаче с эпиком — блоки проектов по имени, в блоке
  группы эпиков (заголовок и порядок из модели), затем задачи без эпика.
  `epic show` — из той же модели.

Бюджет: оценка SPEC $75 держится, переоценка не нужна.

## Шаги
1. Схема и store: `epics`, `tasks.epic_id`, миграция с журналом, помощники
   store, `config.PROJECT_DIRS` + `epics`, константа журнала миграции;
   правка литерала `tests/test_multitarget.py:288-289` по мандату ANSWER-1.
2. `orchestrator/board.py` — модель доски, порядок задач эпика,
   готовность к закрытию.
3. `orchestrator/epics.py` — команды эпика; CLI `epic` в `artel.py`.
4. `new --epic/--after`: `catalog.cmd_new`/`_new_task_row`/`spawn_subtask`,
   `merge_after.declared_for_new`, разбор флагов в `artel._cmd_new`.
5. `approve --as-epic`: `fsm.cmd_approve`, `_spawn_division_subtasks`,
   `artel._approve_sha_arg`.
6. `status` с блоками проектов и группами эпиков.
7. Юнит-тесты сверх долгоживущих файлов задачи —
   `tests/test_epics_board_units.py` (миграция эпиков на БД, где `steps`
   ещё без `target`/`session_id`; порядок задач эпика при цикле
   `merge_after`), каждый проверен временной мутацией (покраснел, код
   возвращён). Карта `scripts/codebase_map.py`, прогон тестов задачи и
   затронутых модулей.

Итог прогонов шага: 56 долгоживущих тестов задачи — зелёные; планка
(`plank-run`, AC-29) — 1 passed; затронутые модули (status, new, approve,
деление, merge_after, схема, мультитаргет, канарейка, карта, help-реестр —
около 45 файлов `tests/`) — зелёные. Найденный по пути регресс
(`tests/test_merge_after_module.py::test_ac6_invalid_dependency_refused_without_traces`:
дедупликация схлопывала повтор внутри самой строки ТЗ) исправлен —
схлопываются только элементы `--after`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 3 (id `E`+ULID), 4 (`--after` отказ формы) |
| 3 | 3, 4 |
| 4 | 3 |
| 5 | 4 |
| 6 | 3, 4 |
| 7 | 5 |
| 8 | 2 |
| 9 | 2, 3, 6 |
| 10 | 2 |
| 11 | 2 |
| 12 | 3 |
| 13 | 6 |
| 14 | 1, 2, 3 |

## Влияние на систему
- Схема: новая таблица и колонка, миграция идёт на каждом `store.db()` —
  догнанная БД заканчивает на одной проверке `PRAGMA table_info` без
  блокировки; БД без `steps` не падает (`tests/test_agent_failure.py:355`).
- `status` без эпиков печатает прежний текст: строка задачи вынесена в
  функцию дословно, группировка включается только при эпике у задачи.
- `approve` без `--as-epic` и `new` без новых флагов — прежние пути;
  `insert_task` получил необязательный keyword.
- Существующий тест меняется ровно в одном утверждении
  (`tests/test_multitarget.py::TargetInitTest::test_structure_is_created`,
  литерал `PROJECT_DIRS` + `epics`) — мандат ANSWER-1, вид `assertEqual`
  сохранён; иных правок тестов нет.
- Lease по id эпика не берётся; `lease.py`, `watch.py` только читаются.
- Откат — revert merge-коммита; колонка и таблица в БД остаются
  безвредными (старый код их не читает).

## Риски
- Перемежение транзакций (AC-34/AC-39): проверка и запись строго после
  `BEGIN IMMEDIATE`; повторная проверка в транзакции миграции.
- Таймаут занятости БД у `store.db()` — штатные 5 с.

## Предложения системе
- `store.journal`/`insert_task`/`update_task` сами делают `commit` — любая
  транзакция `BEGIN IMMEDIATE` с ними вынуждена ставить запись журнала
  последней и заводить некоммитящие двойники (`store.set_task_epic`,
  `update_epic`); класс «помощник store закрывает чужую транзакцию»
  стоит одного параметра `commit=False` у этих функций (store.py).
- Линт «формат id вне idgen» (`scripts/id_format_patterns.txt`) не входит в
  preflight `tests_writing`: test_author заложил нарушение в долгоживущий
  файл, его поймал только CI на `verifying`, а чинить его разработчику
  запрещает замок сумм — круг через эскалацию и `amend-tests`.
  Предложение: гнать тот же grep в `preflight`/гейте выхода из `tests_writing`.

## Эскалация
Код причины: `правка-зафиксированного-теста`.

**Вопросы** (один батч):
1. (блокирующий) Причина возврата из `verifying` требует убрать
   `TASK_ID = re.compile(r"[0-9A-HJKMNP-TV-Z]{26}")` из
   `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_views.py:37`. Это долгоживущий
   файл задачи под замком сумм
   (`acceptance_tests/long_lived.sha256.txt`, строка 5, `dc342c1c…3138`):
   правка разработчиком запрещена и будет отказана гейтом замка на выходе
   из `in_dev`. Варианты:
   (а) Оператор применяет готовый патч `amend-views-task-id.diff` (каталог
   документов задачи) командой `amend-tests`; затем задача идёт в
   `verifying` без нового шага разработчика — код менять не нужно;
   (б) мандат разработчику на правку этого файла в ANSWER (тогда я применю
   тот же патч, больше ничего не меняя).
   Дефолт при молчании: (а).

**Контекст**:
- Линт на чистой ветке (`git diff origin/main...HEAD -- '*.py'
  ':!orchestrator/idgen.py' | grep -E '^\+' | grep -Ef
  scripts/id_format_patterns.txt`) находит ровно одну строку — эту; код
  задачи (`orchestrator/`, мои тесты) линт не нарушает.
- Патч `amend-views-task-id.diff`: удаляет регулярное выражение и заводит
  помощник `carries_id(line)` — id берутся из фикстуры (`store.all_tasks`
  + таблица `epics`), не из формата; две точки использования
  (`block_header`, отбор `later` в `test_ac28_status_project_blocks`)
  переходят на него. Прежнее выражение ловило и id эпика (`E` + 26 знаков),
  поэтому эпики включены в перечень — поведение теста то же. Утверждения
  тестов не меняются.
- Проверено: `git apply --check` на чистом дереве — применяется; с
  временно применённым патчем `python3 -m pytest
  tests/test_01m5tbbdfs6dwqy6ms263t1kpy_views.py` — 7 passed, линт
  пуст; файл затем возвращён `git checkout --` к зафиксированным байтам,
  дерево чистое.

**Блокирует**: повторный вход в `verifying` (джоб CI «Линт — новый парсинг
формата id задачи вне генератора» красный, пока строка в файле).
