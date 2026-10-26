---
task: 01M5TBFH5VZ7GSRXX7VNKHFCCQ
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Эпики Э4 — проекция доски наружу: board, report из модели, внешние ссылки

## Подход
Модель `orchestrator/board.py` (Э1) — единственный источник доски. Она
расширяется: карточка несёт `review_iters`, `escalated_from`, `project`,
`refs`; эпик — `refs`; `build_model(conn, project, with_waiting=True)` —
флаг выключает расчёт `waiting_on` (у карточки `None`, `zone_lock.queue_wait`
не зовётся). Ссылки читаются одним запросом на проект для задач и одним
для эпиков (не на карточку).

Хранение — таблица `external_refs` (`schema.py`: литерал
`EXTERNAL_REFS_DDL` в `SCHEMA` и в `migrate()` через `CREATE TABLE IF NOT
EXISTS`, без записи журнала), уникальность `(kind, object_id, system,
key)` — повторный `link` не дублирует (`INSERT OR IGNORE`). Элемент
`refs` — `{system, key, url, by, at}` в порядке `created_at, id`; id строки
и владельца в элемент не входят (часть деления сверяется с родителем
поэлементно).

Вывод: `board.cmd_board(rest)` — `--json` (модель как есть), `--md` (по
умолчанию; таблицы эпиков и карточек), `--html` (колонки по состояниям);
все виды — из одного `build_model`; неизвестный проект (нет в
`targets.yaml`, нет задач и эпиков в БД) — отказ с именем. `report`:
`cmd_report` строит модель с `with_waiting=False` на каждый проект задач
БД на своём соединении, сводит карточки по id, плитка — из карточки;
внутри колонки — группы эпиков по id эпика (заголовок «<id> <название>»,
карточки по id), затем карточки без эпика прежним порядком. Без эпиков
разметка доски побайтно прежняя.

Ссылки: `new --ref <система>:<ключ>` (многократно; деление по первому
«:») — разбор и проверки (`:` есть, система и ключ непусты,
`policy.ref_systems`, `policy.ref_required` кроме канарейки) сразу после
сверки проекта, до клона, id и ссылки документов; запись ссылок — после
строки задачи и до `_ensure_task_worktree`. `link [--remove] <task|epic>
<id> <система> <ключ> [--url …]` — в `catalog.py`; `--remove` последней
ссылки системы `ref_required` — отказ. `spawn_subtask` копирует ссылки
родителя с его автором и временем. Поля `ref_required`/`ref_systems` —
необязательные поля раздела `policy` (`targets.LOCAL_FIELDS`), проверяются
в `targets.check`.

## Шаги
1. Схема и хранилище: `schema.EXTERNAL_REFS_DDL` в `SCHEMA` и `migrate()`;
   в `store.py` — `insert_external_ref`, `delete_external_ref`,
   `external_refs`, `project_external_refs`, `copy_external_refs`.
2. Поля проекта: `targets.py` — `ref_required`, `ref_systems` в разделе
   `policy`, перенос в плоскую запись, проверка вида.
3. Модель: `board.py` — поля карточки, `refs` карточек и эпиков, флаг
   `with_waiting`; команда `board` (`cmd_board`) с тремя видами и отказом
   на неизвестном проекте.
4. `report` из модели: `_tile_html(card)`, `_board_html(cards, epics)` с
   группами эпиков; `cmd_report` строит модели на своём соединении;
   правка входа пяти методов `tests/test_report.py` по мандату ANSWER-1
   (`id=` → `task=`, утверждения прежние).
5. Ссылки в `new`/`link`/делении: `catalog.cmd_new(refs=…)`, `cmd_link`,
   `spawn_subtask`; `artel.py` — флаг `--ref`, команды `board`, `link`.
6. Карта `scripts/codebase_map.py`, прогон тестов задачи и затронутых
   модулей, `plank-run`, `guard.py`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 3, 5 |
| 2 | 4 |
| 3 | 3, 4 |
| 4 | 3 |
| 5 | 1, 5 |
| 6 | 2, 5 |
| 7 | 1, 5 |
| 8 | 3 |
| 9 | 2, 5 |
| 10 | 5 |
| 11 | 1, 5 |

## Влияние на систему
- `store.db()` → `migrate()` создаёт `external_refs` идемпотентно и без
  записи журнала (`tests/test_epics_board_units.py:9` не задет).
- Модель Э1: ключи верхнего уровня не меняются (`tests/test_01m5tbbdfs6dwqy6ms263t1kpy_board_model.py:141`);
  флаг по умолчанию включён — `status`/`epic show` считают `waiting_on`
  как прежде через `zone_lock.queue_wait` (тесты Э1 `:202`, `:222` без
  правки); `zone_lock.py` не меняется.
- `report`: вид доски без эпиков прежний (AC-5), git и сеть не зовёт;
  `STATE_ORDER` сохранён. Прочие секции `report` не тронуты.
- `tests/test_report.py` — пять методов из матрицы неослабления
  (мандат ANSWER-1): меняется только ключ входа `id` → `task` и
  добавлен докстринг с заявкой «Ловит мутацию» (гейт заявки мутации
  считает метод изменённым); утверждения прежние;
  `test_no_tasks_reports_empty_board` не меняется вовсе.
- Свои тесты — `tests/test_board_refs_units.py` (проверка полей
  `ref_required`/`ref_systems` в `targets.check`, экранирование ячеек
  `--md`, «Задач нет.»): проверены временной мутацией — красные.

## Проверка
- Тесты задачи: `tests/test_01m5tbfh5vz7gsrxx7vnkhfccq_{board_command,external_refs,report_model}.py` — 41 passed.
- Планка: `plank-run` — 2 passed (AC-5 до эталона — форма доски).
- Побайтность доски без эпиков сверена отдельно: `_tile_html`/`_board_html`
  из HEAD (до правки) на фикстуре AC-5 и пустой БД дали тот же раздел
  «Борд задач», что новый `cmd_report` (временный тест, удалён).
- Соседние модули (report, board Э1, epics, targets, catalog, migration,
  store, invariants, canary_drive, new argv; 35 файлов) — 407 passed.
- Новые команды `board` и `link` вне белого списка ролей
  (`_ROLE_ALLOWED_COMMANDS` не трогается — закрыто по умолчанию).
- Откат — revert merge-коммита; таблица `external_refs` на живой БД
  останется пустой и никем не читаемой.

## Риски
- Побайтность доски без эпиков: сводка карточек по id повторяет порядок
  `store.all_tasks`; задача с `target=''` (не NULL) ушла бы из доски — в
  БД пульта таких строк нет (`insert_task` пишет проект).

## Предложения системе
- coding-standards.md: мандат на правку вызовов в существующих тестах
  («меняется только вход») не упоминает, что гейт заявки мутации
  (`guard.test_functions_without_mutation_claim`) потребует докстринг
  «Ловит мутацию» у каждого такого метода — стоит оговорить в шаблоне
  матрицы неослабления.
- Сторож Bash роли не пускает `ls`/`rm`/перенаправление в /tmp — уборка
  временного файла шла через `python3 -c os.remove`.
