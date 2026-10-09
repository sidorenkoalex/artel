---
task: 01M4FYTB8QWJNHYCP35K8QC4E3
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Лишняя база в рабочей копии задачи — изоляция тестов, проверка перед полным прогоном, кэш итога

## Фаза A — план
- Таблица покрытия PLAN полна: требования 1–8 → шаги 1–5; шаг 6 — свои тесты вне долгоживущих.
- Шаги размером с MR, не микрооперации. Подход (одна проверка `store.db_usable`, один перечень `store.TREE_DB_FILES`/`tree_db_files`, отказ исходом `FULL_SUITE_NOT_STARTED`) укладывается в существующую архитектуру узла `acceptance.full_suite`. `fsm.py` (вне зон) не тронут.
- «Влияние на систему» соответствует diff: 15 файлов, все в зонах SPEC; защищённые пути (`skills/`, `templates/`, `gates.yaml`, `roles.yaml`, `.github/`) не тронуты.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `store.db_usable()` (`orchestrator/store.py`): `mode=ro`, ищет `tasks` в `sqlite_master`, любая `sqlite3.Error` → False. Используется всеми семью читателями перечня: `artifact_branch.task_repo`, `workspace.task_target`, `acceptance.journal_suite_metrics`, `_plank_helper_text`, `full_suite` (target + `recordable`), `models.live_task_set_providers`, `models._set_pair_withdrawn`. Отдельно проверил на БД в режиме WAL (так работает пульт) без открытых соединений и при открытой пишущей транзакции: `db_usable()` → True, лишних файлов не появилось. |
| 2 | OK | Проверка не зовёт `store.db()`, а `mode=ro` не создаёт файл. Это держит AC-2 (`test_ac2_readers_do_not_create_or_change_db`). |
| 3 | OK | `tests/sandbox.isolate_pult_db` вызывается в `setUp` у `MaterializeFromBranchGitFailureTest`, у `_AutogateConditionsUnitTest` (база трёх названных классов autogate) и у `ChecklistNamesRealChecksTest`. Ассерты не тронуты: diff `tests/test_acceptance.py` и `tests/test_fsm_autogate.py` — только импорт и `setUp`. Поиск по `tests/` подтверждается исполнением (AC-11): после моих прогонов семи модулей в рабочей копии нет `.artel/state.db`. |
| 4 | OK | Отказ в `full_suite` стоит до кэша и замка, исход `FULL_SUITE_NOT_STARTED`. Текст `_db_in_tree_note` называет «не проверен», путь каждого файла и `artel.py worktree-db-clean <id>`. После прогона `_journal_db_files_created` пишет запись с пометкой из SPEC, на исход она не влияет. Гейт мержа получил отдельный совет. Проверка смотрит на дерево самого прогона: при временном дереве прогона файл в рабочей копии ему не страшен, такой файл показывает `doctor`. Это разумное прочтение «рабочей копии задачи»: опасна именно БД в дереве прогона. |
| 5 | OK | `_with_tree_db_files` учитывает наличие и sha256 каждого из четырёх файлов. Для чистого дерева sha прежний, накопленный кэш не теряется. Итог базы и дерево коммита файлы не учитывают — обоснование в PLAN верное. Текст повторного итога называет `--fresh-suite`, фраза «использован повторно» сохранена. |
| 6 | OK | `workspace.cmd_worktree_db_clean`: `shutil.move` в `config.LOGS` под именем `<id>-worktree-<метка>-<имя>`, без перезаписи (суффикс `.N`). Без файлов — сообщение и успешный выход. `doctor` выдаёт строку `worktree-db-files` со статусом `warn` или `ok`. |
| 7 | OK | `docs/operator-session.md`, пункт «Красный набор не по вине задачи», содержит строку требования дословно. Планка зелёная. |
| 8 | OK | Команды нет в `_ROLE_ALLOWED_COMMANDS`, работает штатный `_refuse_if_role_restricted`. AC-12 зелёный. |

## Замечания
Блокирующих и major-замечаний нет. Ниже два наблюдения уровня вкуса — они не заведены в реестр, мержу не мешают:
- `orchestrator/fsm_merge_gate.py:948` — совет выбирается по подстроке `"worktree-db-clean" in run.detail`. Это связь через текст: если формулировка `_db_in_tree_note` изменится, совет молча вернётся к «машина освободится». Сторожем служит `tests/test_worktree_db_files.py::MergeGateDbAdviceTest`, поэтому оставляю как вкус.
- `orchestrator/doctor/worktree_db.py:21` — `root.glob("*/worktrees")` вернёт и файл с именем `worktrees`; тогда `iterdir()` поднимет `NotADirectoryError` и уронит `doctor`. Сценарий маловероятный (каталог раскладывает пульт).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: замечаний уровня blocker/major в итерации 1 нет.

## Вердикт
approved

## Проверено исполнением
- Все команды ниже запускал из рабочей копии.
- `python3 -m pytest -q tests/test_01m4fytb8qwjnhycp35k8qc4e3_db_readers.py tests/test_01m4fytb8qwjnhycp35k8qc4e3_suite_db_files.py tests/test_01m4fytb8qwjnhycp35k8qc4e3_worktree_db_clean.py tests/test_worktree_db_files.py tests/test_fsm_autogate.py tests/test_full_suite_reuse.py tests/test_doctor.py` — 155 passed, 76 subtests passed (61 с).
- `python3 -m pytest -q tests/test_acceptance.py tests/test_models.py tests/test_workspace.py` — 84 passed, 21 subtests passed.
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M4FYTB8QWJNHYCP35K8QC4E3` — 1 passed, код выхода pytest 0.
- Пробный скрипт: БД пульта в режиме WAL во временном каталоге (`store.db()` + `create_schema`). `store.db_usable()` → True и без открытых соединений, и при открытой транзакции `BEGIN IMMEDIATE`; состав каталога `.artel/` до и после вызова одинаковый. SQLite 3.51.0.
- После всех прогонов в `.artel/` рабочей копии лежат только `logs/` и `session-id`, файла `state.db*` нет. Это подкрепляет AC-11 для прогнанных модулей.
- Сверка `tests/` по diff: в `tests/test_acceptance.py` и `tests/test_fsm_autogate.py` изменились только импорты и `setUp`. Удалённых или изменённых ассертов нет.
- Полный набор `tests/` не запускал (решение Оператора 05.09): CI коммита 259bd7e5 зелёный, 16 проверок.

## Предложения системе
- `.artel/session-id` появляется в корне рабочей копии после прогонов тестов — разработчик уже отметил это в PLAN, я воспроизвёл. Это тот же класс «тест пишет в корень дерева, из которого импортирован пакет», что и лишняя `state.db`; стоит завести отдельную задачу на изоляцию `session`.
- `fsm.py::_approve_acceptance_suite` печатает к `FULL_SUITE_NOT_STARTED` совет «повтори, когда машина освободится» и для отказа из-за файлов БД. Поддерживаю предложение PLAN развести советы, как сделано в `fsm_merge_gate`, — лучше по признаку исхода, а не по подстроке.
