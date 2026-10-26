---
task: 01M5TBFCVFNN95BHH0E9C6KBKB
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Эпики Э3 — черновики и решения эпика, копия эпика в `refs/artifacts/epic-<id>`

## Фаза A — план
- Таблица покрытия полна: требования 1–17, у каждого есть шаг. Шаги — размера MR.
- Новый блок PLAN «Сторожа фильтров `epic-` (возврат из merge_gate 26.10)» сходится с diff. Код фильтров не менялся. Добавлен один файл `tests/test_epic_ref_scan_filters.py`, существующие тесты не тронуты, карта перегенерирована (коммит 853f80951: только этот тест и `docs/codebase-map.md`).
- «Влияние на систему» соответствует diff. Наблюдение итерации 1 о `orchestrator/config.py` вне `zones:` (одна аддитивная константа) в силе, замечанием не является.

## Изменения после итерации 1
Пакет пришёл с полным diff от main: базу инкремента пульт не определил. Поэтому инкремент сверен вручную. Записка итерации 1 сохранена в 04:38Z, это позже a05ac778f (07:11 +0300). После неё есть один коммит, 853f80951: в нём `tests/test_epic_ref_scan_filters.py` (+71) и карта. Кода `orchestrator/`/`scripts/` в нём нет.

Новый файл проверен:
- У каждого из трёх методов в докстринге описаны сценарий и наблюдаемое свойство, а заявка «Ловит мутацию» называет видимое расхождение: ссылка эпика в перечне сверки doctor; «со ссылкой 1, без ссылки 1» вместо засчитанного снимка; ветка `artifact/epic-<id>` удалена `--execute`.
- Повтора долгоживущих тестов нет. `…_ref_scans.py` сверяет «вывод со ссылкой эпика = вывод без неё», а этот вход фильтры doctor/snapshot/cleanup не различают (PLAN это объясняет). Новые тесты берут вход, на котором фильтр меняет вывод.
- Фикстура `stand` и помощники импортируются из долгоживущего файла задачи. Сам файл не правлен, лок не нарушен.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Без изменений с итерации 1: `schema.EPIC_DRAFTS_DDL` в `SCHEMA` и `migrate`; AC-15 зелёный. |
| 2 | OK | `_ADDRESS_RE`, `store._next_epic_number` = MAX+1 (AC-18). |
| 3 | OK | `_read_tz` дословно, название — первый `# `, отказ перечнем негодных (AC-1, AC-16). |
| 4 | OK | `cmd_draft_edit` меняет только названные поля. |
| 5 | OK | `cmd_draft_drop`. |
| 6 | OK | `catalog.cmd_new(tz_text=…)`, рамка через `apply_operator_frame` с источником `operator` (AC-2, AC-19). |
| 7 | OK | Незаведённые черновики — отказ до `new`; отказ `new` оставляет черновик в `draft` (AC-3, AC-4). |
| 8 | OK | `_state_refusal` срабатывает до транзакции и внутри неё (AC-5). |
| 9 | OK | `epic_decisions`, текст как есть, `--for` проверяется (AC-6, AC-17). |
| 10 | OK | `ref_files`: `EPIC.md`, `drafts/<n>.md`, `DECISIONS.md`, первая строка — JSON. |
| 11 | OK | `_write_ref` вызывается после транзакции во всех меняющих командах; при неудаче записи — предупреждение и журнал `E…` (AC-7, AC-8, AC-22). |
| 12 | OK | `deferred_sends` вокруг `cmd_epic`; журнал отказа отправки пишется под id эпика с `target` проекта (AC-9, AC-21). |
| 13 | OK | `cmd_export` идёт в порядке `_read_ref` (AC-10). |
| 14 | OK | `fetch_all_from_origin` сдвигает `epic-…`, в исходы задач их не отдаёт. |
| 15 | OK | Шесть фильтров. Сторож после мержа: retro/plan_appendix/fetch — `…_ref_scans.py`; doctor/snapshot/cleanup — `test_epic_ref_scan_filters.py` (проверено мутацией, см. ниже). |
| 16 | OK | `_restore_plan` сверяет по ключу и каждому полю (AC-12–14). |
| 17 | OK | `board._epic_item.ready_to_close` и `epic close` учитывают черновики `draft` (AC-20). |

## Замечания
Blocker, major и minor замечаний нет. Наблюдения без требования правки:
- `tests/test_epic_ref_scan_filters.py::test_history_snapshots_epic_ref_is_no_docs_ref_of_dir` утверждает, что каталог main `tasks/epic-<id>/` числится «без ссылки» и попадает в «были бы созданы `refs/artifacts/epic-<id>`». Вход искусственный: каталогов задач с таким именем в main не бывает (имя каталога — id задачи). Но тест фиксирует поведение, при котором проход snapshot в принципе мог бы попытаться создать ссылку на месте копии эпика. Если когда-нибудь появится защита «каталог `epic-…` — не задача», тест придётся поправить. Сейчас вреда нет.
- Из итерации 1 в силе: правка `config.py` вне `zones:`; `board._epic_item` делает N+1 запросов `epic_drafts`.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `git log --stat`: после вердикта итерации 1 есть только коммит 853f80951 (новый тест и карта), кода в нём нет.
- `python3 -m pytest -q -p no:cacheprovider tests/test_epic_ref_scan_filters.py tests/test_01m5tbfcvfnn95bhh0e9c6kbkb_ref_scans.py tests/test_epic_drafts_units.py` — 13 passed.
- Временная мутация: сняты фильтры `epic-` в трёх местах — `doctor/artifact_branches.py` (`if sha and ref:`), `snapshot._history_pass` (без `is_epic_ref_key`), `artifact_cleanup._inventory` (без проверки префикса). `tests/test_epic_ref_scan_filters.py` — 3 failed. Каждый тест идёт только через свой модуль. Код возвращён `git checkout`, повторный прогон — 3 passed, `git status --short` пуст.
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m5tbfcvfnn95bhh0e9c6kbkb_{drafts,epic_ref,migration,ref_scans}.py tests/test_epic_drafts_units.py tests/test_doctor_artifact_branch_sync.py tests/test_snapshot_history.py` — 50 passed (29.7 с).
- `plank-run` не запускался: у задачи нет планки в `acceptance_tests/`, вся она — долгоживущие файлы `tests/`, их прогнал pytest'ом (в итерации 1 `plank-run` отказал «планки нет»).

## Предложения системе
- Пакет ревью итерации 2 не определил базу инкремента и дал полный diff от main (562 КБ, 12 частей), хотя фактический инкремент — один тестовый файл. Стоит брать базой коммит, на котором была сохранена записка ревьювера прошлой итерации, или sha HEAD из журнала вердикта.
