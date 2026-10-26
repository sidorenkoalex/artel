---
task: 01M5TBFH5VZ7GSRXX7VNKHFCCQ
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Эпики Э4 — проекция доски наружу: board, report из модели, внешние ссылки

## Фаза A: план
- Таблица покрытия PLAN.md полна: требования 1–11 разнесены по шагам 1–5, шаги — проверяемые единицы (схема/хранилище, поля проекта, модель+`board`, `report`, `new`/`link`/деление).
- Подход не конфликтует с архитектурой: таблица — тем же литералом в `SCHEMA` и `migrate()` (приём `MODEL_TARIFFS_DDL`), модель Э1 расширяется без смены ключей верхнего уровня, `zone_lock.py` не тронут.
- «Влияние на систему» совпадает с diff: 7 модулей зоны, `tests/test_report.py` (пять методов мандата, утверждения прежние), новый `tests/test_board_refs_units.py`. Защищённые пути не тронуты.
- Одна неточность плана, не дефект: в «Влиянии» сказано «пять методов» — так и есть, шестой (`test_no_tasks_reports_empty_board`) не менялся, его вызов `_board_html([])` совместим с новой сигнатурой.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `board.cmd_board`: `--json`/`--md`/`--html`, по умолчанию `--md` (`DEFAULT_VIEW`), все из одного `build_model`; `_known_project` — `targets.load()` либо задачи/эпики в БД, отказ называет проект. Запись в БД и сеть не зовутся (AC-3 зелёный в обеих песочницах). |
| 2 | OK | `cmd_report` строит модель на `sorted({_project(row) for row in tasks})` — все проекты задач БД, включая незаявленные; `_render` сводит карточки по id (как `store.all_tasks ORDER BY id`); `_column_tiles_html` — группы эпиков по id эпика, заголовок «<id> <название>», карточки по id задачи, затем без эпика. Без эпиков разметка прежняя (сверено: `_usd` терпит `None`, `spent_usd or 0.0` вывод не меняет). |
| 3 | OK | `build_model(..., with_waiting=True)`; `report` — `with_waiting=False` на своём `conn`, `queue_wait` не зовётся; ссылки читаются одним запросом на вид объекта. |
| 4 | OK | `_card`: `review_iters`, `escalated_from`, `project` (`target or DEFAULT_TARGET`). |
| 5 | OK | `schema.EXTERNAL_REFS_DDL` в `SCHEMA` и `migrate()`, без журнала; автор `operator` (`catalog.REF_AUTHOR`), копия деления — автор/время родителя (`store.copy_external_refs`). |
| 6 | OK | `_ref_reason`: пустая система/ключ, `ref_systems`; поля проверяются в `targets.check`. |
| 7 | OK | `_new_ref_args` (многократный `--ref`), `split(":", 1)`, `cmd_link` с `INSERT OR IGNORE` по `UNIQUE (kind, object_id, system, key)`, `--remove` отсутствующей и последней требуемой — отказ, несуществующий объект — отказ. |
| 8 | OK | `_ref_item` `{system,key,url,by,at}`, `ORDER BY created_at, id`; трекер не вызывается. |
| 9 | OK | `_new_refs`: `required and not canary`. |
| 10 | OK | `_new_refs` зовётся сразу после `_checked_target`, до `store.db()`/клона/id/ссылки документов; запись ссылок — после строки задачи и до `_ensure_task_worktree`. |
| 11 | OK | `spawn_subtask` → `store.copy_external_refs(conn, parent_id, task_id)`. |

## Замечания
Замечаний blocker/major/minor к diff нет.

Наблюдение вне SPEC (не замечание, в реестр не заносится): `epics.cmd_draft_promote` (`orchestrator/epics.py:796`) заводит задачу через `catalog.cmd_new` без `refs` и флага `--ref` не имеет — в проекте с `policy.ref_required` черновик эпика перевести в задачу нельзя никак (отказ `new` советует `--ref`, которого у `promote` нет). SPEC о `promote` молчит, поле `ref_required` пока нигде не задано, поведение буквально следует требованию 9 — вынесено в «Предложения системе».

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved — все 11 требований реализованы, мандат ANSWER-1 соблюдён (в `tests/test_report.py` меняется только ключ входа `id`→`task` и добавлены докстринги с заявками; утверждения, их вид и значения прежние; `:1018`, `command_report.py:524,550` не тронуты), ANSWER-2 (новая формулировка AC-14) учтён тестом задачи. Тесты задачи держат долгоживущие свойства в `tests/`.

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider` по 11 файлам: три долгоживущих теста задачи, `tests/test_board_refs_units.py`, `tests/test_report.py`, `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_board_model.py`, `tests/test_epics_board_units.py`, `tests/test_report_project_label.py`, `tests/test_01m563e1sh9sb63s2mw4a9b82n_project_label.py`, `tests/test_01m4rzayh3swjw4wfbw4qw15fp_command_report.py`, `tests/test_01m4nz5w9ztkgtw7dgzqgmp2gp_test_author_report.py` — 142 passed, 35 subtests passed.
- `artel.py plank-run 01M5TBFH5VZ7GSRXX7VNKHFCCQ` — 2 passed, код выхода 0 (AC-5 в форме «до эталона»).
- Временная мутация 1: в `targets.check` убрал `item.strip()` у `ref_systems` → `tests/test_board_refs_units.py::test_ref_systems_with_empty_item_refused_naming_field` красный; код возвращён `git checkout`.
- Временная мутация 2: `report.cmd_report` строит модель без `with_waiting=False` → `test_ac14_report_steps_queries_do_not_grow_with_tasks` красный; код возвращён.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` без строки `built_at_sha` — расхождений нет (карта свежая); файл возвращён.
- `git status --short` после всех прогонов — чисто.

## Предложения системе
- `orchestrator/epics.py::cmd_draft_promote` и любые будущие обёртки над `catalog.cmd_new`: новое обязательное условие `new` (здесь `policy.ref_required`) не доходит до обёрток — SPEC стоит спрашивать «кто ещё зовёт `cmd_new`» при добавлении проверки в `new`.
