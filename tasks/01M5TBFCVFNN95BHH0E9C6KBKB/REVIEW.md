---
task: 01M5TBFCVFNN95BHH0E9C6KBKB
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Эпики Э3 — черновики и решения эпика, копия эпика в `refs/artifacts/epic-<id>`

## Фаза A — план
- Таблица покрытия полна: требования 1–17, у каждого есть шаг.
- Шаги размером с MR (схема/store; artifact_branch и фильтры перебора; команды epics; справка/карта). Микроопераций и пункта «сделать всё» нет.
- Подход совпадает с архитектурой: плотницкая запись через `artifact_branch.commit_files` (ключ `epic-<id>`, `target` — проект эпика), область `deferred_sends` вокруг всей подкоманды `cmd_epic`, путь `new` через keyword `tz_text`, рамка через общее ядро `apply_operator_frame`.
- «Влияние на систему» сходится с diff. Отступление одно: `orchestrator/config.py` (константа `EPIC_REF_NAME_PREFIX`, `config.py:319-323`) не входит в `zones:` SPEC. Правка — одна аддитивная константа, без побочных эффектов, CI зелёный. Записываю как наблюдение, не как замечание.
- Риск гонки двух `promote` названен в PLAN. Код ловит его повторной проверкой состояния в транзакции (`epics.py`, `cmd_draft_promote::body`), отказ называет уже заведённую задачу. SPEC lease по эпику не требует, поэтому это не дефект.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `schema.EPIC_DRAFTS_DDL`: один литерал в `SCHEMA` и в `migrate`, `IF NOT EXISTS`, ключ `(epic_id, number)`. AC-15 проверен тестом migration. |
| 2 | OK | `_ADDRESS_RE`, `store._next_epic_number` = MAX+1: номер после `drop` не переиспользуется (AC-18). |
| 3 | OK | `_read_tz` читает с `newline=""`, текст дословно, название — первый `# `. Закрытый или несуществующий эпик — отказ. `_list_value` собирает все негодные элементы и отказывает их перечнем (AC-16). |
| 4 | OK | `cmd_draft_edit` меняет только названные поля; `--tz` меняет и текст, и название. Ссылка черновика на себя — отказ (свой тест). |
| 5 | OK | `cmd_draft_drop`. |
| 6 | OK | `catalog.cmd_new(tz_text=…, epic_id, after, start_after, target=проект эпика)`: `tz_check`, зоны и «Порядок:» — тем же путём. Рамка → `apply_operator_frame` с источником `operator` (AC-19). Адреса разрешаются `_resolved_list`. |
| 7 | OK | Незаведённые черновики дают отказ перечнем до `new`. Отказ `new` — это `sys.exit` до записи черновика, черновик остаётся `draft` (AC-3, AC-4). |
| 8 | OK | `_state_refusal` срабатывает до транзакции и повторно внутри неё. |
| 9 | OK | `epic_decisions` с `for_kind`/`for_ref`; текст пишется как есть. `--for` проверяет черновик своего эпика и задачу БД (AC-6, AC-17). |
| 10 | OK | `ref_files`: `EPIC.md` (все поля строки + задачи с `closed_as`), `drafts/<n>.md`, `DECISIONS.md`. Первая строка — JSON, `>` экранирован. |
| 11 | OK | `_write_ref` стоит после успешной транзакции во всех меняющих командах, включая `envelope` и `add/remove` внутри lease. Если запись не удалась — предупреждение и журнал `REF_WRITE_FAILED_ACTION` под `E…` (AC-22). `show`/`export` ссылку не пишут. |
| 12 | OK | `cmd_epic` открывает `deferred_sends`, внутри lease область вложенная, отправка одна. `_journal_identity` пишет исход под id эпика с `target` проекта, `_last_send_failed` смотрит туда же: после восстановления origin успех записывается и досылается (AC-9, AC-21). |
| 13 | OK | `cmd_export` печатает файлы ссылки в порядке `_read_ref` (числовая сортировка `drafts`). Если ссылки нет — рендер по БД с предупреждением в stderr. |
| 14 | OK | `fetch_all_from_origin` сдвигает и `epic-…` тем же `_sync_local_ref` (вперёд, со сверкой). |
| 15 | OK | Фильтры стоят в `fetch_all_from_origin` (исходы), `artifact_cleanup._inventory`, `doctor._origin_artifact_refs`, `retro_corpus._local_artifact_refs`, `snapshot._history_pass`, `plan_appendix_ci.remote_docs_refs`. Литерал CI равен литералу config: это держит `test_ci_script_epic_prefix_matches_config`. |
| 16 | OK | `_restore_plan` сверяет по ключу и каждому полю, лишние строки БД тоже считаются расхождением. Есть отказ при чужом проекте ссылки, ссылки нет — отказ (AC-12–14). |
| 17 | OK | `board._epic_item.ready_to_close` учитывает черновики `draft`. `epic close` отказывает перечнем «адрес «название»» (AC-20). |

Тесты. Четыре долгоживущих файла задачи лежат в `tests/` — сторож после мержа есть. Каждый метод несёт заявку «Ловит мутацию» с наблюдаемым расхождением. У каждого файла есть строка группы («Группа: долгоживущий»), и метки верные: файлы проверяют свойства кода, не факты задачи. Тест разработчика `tests/test_epic_drafts_units.py` долгоживущие не повторяет: строки данных, ссылки черновика на себя и копии префикса в CI в файлах задачи нет. Его заявки исполнимы (при `-->` без экранирования `count("-->") == 2`). Существующие тесты `tests/` в diff не изменены и не удалены. Защищённых путей (`skills/`, `templates/`, `gates.yaml`, `roles.yaml`, `.github/`) diff не трогает.

## Замечания
Блокирующих, major и minor замечаний нет. Два наблюдения без последствий, которые требовали бы правки:
- Правка `orchestrator/config.py` вне `zones:` SPEC — аддитивная константа (см. Фазу A).
- `board._epic_item` запрашивает `store.epic_drafts` отдельно на каждый эпик (N+1 запросов в `status`). При нынешнем числе эпиков это незаметно.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `artel.py plank-run 01M5TBFCVFNN95BHH0E9C6KBKB` отказал: «планки нет: в источнике … нет файлов test_*.py». У задачи вся планка — долгоживущие файлы в `tests/`, поэтому я прогнал их pytest'ом.
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m5tbfcvfnn95bhh0e9c6kbkb_{drafts,epic_ref,migration,ref_scans}.py tests/test_epic_drafts_units.py` — 40 passed (28.8 с).
- Тесты затронутых модулей: `test_01m5rwnjezt6ya2vp7jk6f3rxs_one_push_per_command.py`, все Э1 (`…5tbbdfs…_board_model/division_epic/epic_commands/migration/views`), Э2а (`…5tbcy7…_epic_view/start_after_write/envelope_run`), `…5tb6vdvv…_division_finish`, `test_doctor_artifact_branch_sync.py`, `test_retro_corpus.py`, `test_snapshot_history.py`, `test_spec_budget.py`, `test_parent_task_division.py` — 202 passed, 31 subtests passed.
- Временная мутация 1: в `board.py` условие `d["state"] == "draft"` заменено на `"XXdraft"` (черновики не учитываются). `-k ac20` покраснел, 2 failed. Код возвращён.
- Временная мутация 2: в `retro_corpus._local_artifact_refs` фильтр `epic-` выключен. `test_ac11_retro_cache_has_no_epic_row` покраснел. Код возвращён; `git status --short` пуст.

## Предложения системе
- Планка задачи целиком состоит из долгоживущих файлов `tests/`, а `plank-run` в этом случае отказывает «планки нет», хотя ревьюверу предписано гонять планку именно им. `plank-run` стоит научить гонять долгоживущие файлы из перечня лока, либо прямо сказать о pytest в `skills/review-checklist.md`.
