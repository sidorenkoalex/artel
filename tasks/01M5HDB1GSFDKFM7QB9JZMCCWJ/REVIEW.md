---
task: 01M5HDB1GSFDKFM7QB9JZMCCWJ
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: suite-run отказывает новому полному прогону из шага developer

## Фаза A — план

- Таблица покрытия полна: требования 1–6 → шаг 1 (`suite_run.py`), 7 → шаг 2
  (`role_prompt.py`), 8 → шаг 3 (`ROLES`), 9 → долгоживущий файл test_author.
- Шаги размера MR, не микрооперации. Подход (ранняя ветка в `cmd_suite_run`
  до `_db()`/`deliver_journal`, чтение `mode=ro`) соответствует ADR-0024 с
  поправкой 22.10.2026 и SPEC.
- Матрица неослабления — строка на каждый из пяти методов `readonly_db`,
  совпадает по смыслу с матрицей ANSWER-1 (оба условия «ок при условии» —
  `--failed` с общим замком и `--wait 0` под БД только на чтение — закрыты
  `KeptFlagsTest::test_ac4_developer_wait_and_failed_under_readonly_db`).
- «Влияние на систему» = фактический diff: `suite_run.py`, `role_prompt.py`,
  одна строка `readonly_db`, карта. Откат — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `cmd_suite_run`: `if minutes is None and not failed and _developer()` стоит до `_db()` и `deliver_journal`; `_refuse_developer_full_run` разрешает id `store.get_task` (→ `resolve_task_id`, префикс) на `_readonly_db()` (`mode=ro`, `uri=True`), закрывает соединение; `_running` только читает файлы. Записей нет — держит `RefusalTest::test_ac1` (снимок БД+WAL+хозяйства, счётчики `store.db`/`deliver_journal`/`Popen`). |
| 2 | OK | Текст: `[<id>] suite-run: отказ — … роли developer (ARTEL_ROLE=developer), задача <id>; полный набор прогонят CI и автопроверка приёмки; свои файлы — python3 -m pytest tests/<файлы> … в переднем плане; планка — … plank-run <id> [файл]; повтор упавших — … suite-run <id> --failed`. Голого `suite-run <id>` и `<id> <файлы>` нет. |
| 3 | OK | Идущий прогон — `_running_text` (общий с прежней веткой, текст дословно прежний), `return` без кода. |
| 4 | OK | `--wait`/`--failed` под маркером идут прежним путём (досыл, замок, отказы); `--wait 0` даёт `minutes == 0`, не `None` — ветка отказа не срабатывает. |
| 5 | OK | Развилки `_developer()` в четырёх местах (`_wait` «нет прогона», «оборван», `--failed` «нет прошлого», «упавших нет»); у прочих текст дословно прежний (сверил diff: склейка `; {hint}` даёт ту же строку; `HintsTest` сравнивает дословно). |
| 6 | OK | Признак — строгое равенство `ARTEL_ROLE == STATE_ROLE["in_dev"]`; HOME, пустой маркер, иные роли — прежний путь. |
| 7 | OK | `suite_run_note`: CI и гейт приёмки, `--failed` (только после прогона Оператора или ревьювера) и `--wait <минуты, не больше …>` с полным путём пульта; `test_ac25_…` зелёный без правки; миссия ревьювера внешнего проекта не тронута. |
| 8 | OK | Diff файла `readonly_db` — ровно строка `ROLES`; пять методов не тронуты; мандат ANSWER-1. |
| 9 | OK | Долгоживущий файл test_author покрывает AC-1–AC-7; заявки «Ловит мутацию» у всех семи методов называют наблюдаемое расхождение; зерно печатается; `--wait` только с `0`, `Popen` подменён. |

## Замечания

- Блокеров и major нет.
- (не заводится в реестр, вкус) `orchestrator/suite_run.py::_refuse_developer_full_run` — при отсутствующем файле БД developer получит необработанное `sqlite3.OperationalError` вместо текстового отказа; PLAN честно записал это в «Риски», для шага роли пульта БД всегда есть.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

(Замечаний blocker/major/minor, требующих работы, нет — реестр пуст.)

## Вердикт

approved

## Проверено исполнением

- `python3 orchestrator/artel.py plank-run 01M5HDB1GSFDKFM7QB9JZMCCWJ` — 4 passed, код 0.
- `python3 -m pytest tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py -p no:cacheprovider -q` — 39 passed, 38 subtests passed (3 мин 56 с).
- `python3 scripts/codebase_map.py` + `git diff docs/codebase-map.md` — расхождение только в `built_at_sha`, карта свежа (изменение откатил `git checkout`).
- `store.get_task` → `resolve_task_id` (orchestrator/store.py:1074) — прочитал, чтобы подтвердить разрешение префикса в ветке отказа.
- Временную мутацию `_developer` («любая непустая роль») запустить не удалось — составная команда не получила разрешения; чувствительность AC-6 к ней заявлена докстрингом и подтверждена автором теста стабом.

## Предложения системе

- CI ветки уже зелёный на 85594c3e, а прогон трёх файлов suite-run занимает ~4 минуты в шаге ревью — стоит в пакете ревьювера указывать, какие из затронутых модулей CI уже прогнал на этом sha, чтобы не дублировать.
