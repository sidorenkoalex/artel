---
task: 01M5MHVFQ9SC6EDRH34F8THNQ3
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Одна функция открытия БД пульта только на чтение вместо пяти копий

# Одна функция открытия БД пульта только на чтение вместо пяти копий

## Факты

Находка ревизии кода 22.10 CR-2026-10-22-13 (`docs/audits/code-revision-2026-10-22.md`, раздел «Находки»). Сверено с пином 870aa7e9 (`origin/main` edbbc059, затронутые файлы совпадают).

Пять мест сами собирают соединение с БД пульта в режиме «только чтение» — `sqlite3.connect(f"{<путь>.resolve().as_uri()}?mode=ro", uri=True)`; timeout и pragma нигде не задаются:

| Место | Функция | row_factory | Файла нет |
|---|---|---|---|
| `orchestrator/store.py:325` | `db_usable() -> bool` | нет | `config.DB.is_file()` ложно → `False`; `sqlite3.Error` при открытии → `False` |
| `orchestrator/knowledge_cards.py:761` | `_open_db_readonly(arg)` | `sqlite3.Row` | `sys.exit(f"knowledge: БД пульта {config.DB} не найдена")` |
| `orchestrator/suite_run.py:178` | `_readonly_db()` (запасной путь `_db()` после отказа `store.db()`) | `sqlite3.Row` | проверки нет: `sqlite3.OperationalError` от `connect` |
| `orchestrator/preflight.py:80` | `_open_db_readonly()` | `sqlite3.Row` | `None`; `_task_row` печатает «БД пульта … не найдена» и выходит с кодом 2 |
| `scripts/test_rule_stats.py:66` | `journal(db_path, since)` (путь — параметр, не `config.DB`) | нет (кортежи) | `StatsError("нет БД пульта …")`; `sqlite3.Error` → `StatsError("БД пульта … не прочитана: …")` |

В `orchestrator/store.py` функции открытия только на чтение нет: есть `db()` (`:387`, открывает на запись, включает WAL и миграцию) и `db_usable()`. `scripts/test_rule_stats.py` уже импортирует модули `orchestrator` (`sys.path.insert` на строке 41); `scripts/` и `orchestrator/` не входят в защищённые пути.

Тесты, которые держат нынешнее поведение и не правятся:
- `tests/test_01m5keyg8g1wxhsr4bdkbsh6jp_canary_runs.py::test_ac11_sqlite_connect_only_from_store` — во время `canary runs` `sqlite3.connect` допускается только из `orchestrator.store` (`db_readonly` в `store` это сохраняет);
- `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_command.py::test_ac5_reads_db_with_read_only_connection` и `tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py::test_ac1_developer_full_run_refused_before_any_write` — подменяют атрибут `sqlite3.connect` и ищут `mode=ro` в первом аргументе и `uri=True` именованным аргументом;
- `tests/test_preflight.py::test_missing_db_exits_2_and_creates_no_db`, `tests/test_test_rule_stats.py::FailClosedTest::test_missing_db_is_exit_2_without_summary`, `tests/test_01m3xr84299td6v6e16d2pnxh4_rule_stats.py::test_ac9_run_leaves_db_unchanged_and_connection_is_read_only`, `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py`, `tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py::test_ac8_readonly_db_file_same_output_and_code`, `tests/test_reference_command.py` (подмена `store.db_usable`).

Прямые SELECT в `orchestrator/doctor/observations.py` и `orchestrator/doctor/stale_cycles.py` получают готовое соединение из `store.db()` (`doctor/cli.py`), отдельного соединения на чтение не открывают — в задачу не входят.

## Требования

1. В `orchestrator/store.py` появляется функция `db_readonly(path=None, *, rows=True) -> sqlite3.Connection`: открывает `path` (`pathlib.Path` или `None`; `None` — `config.DB`, прочитанный в момент вызова, а не при импорте) вызовом `sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)` — через атрибут модуля `sqlite3`, с `uri` именованным аргументом; при `rows=True` ставит `row_factory = sqlite3.Row`. Существование файла функция не проверяет и исключения `sqlite3` не перехватывает: на отсутствующем файле наружу выходит то же `sqlite3.OperationalError`, что сегодня у `connect`. Файл БД она не создаёт, `store.db()` не зовёт, режим журнала не меняет.
2. Пять мест таблицы открывают соединение через `store.db_readonly`: `db_usable` (`rows=False`), `knowledge_cards._open_db_readonly`, `suite_run._readonly_db`, `preflight._open_db_readonly`, `scripts/test_rule_stats.journal` (`path=db_path`, `rows=False`). Проверки существования файла, тексты отказов, коды выхода и перехват исключений остаются у вызывающих в нынешнем виде.
3. После правки `grep -rn "?mode=ro" orchestrator scripts` находит ровно одну строку — в `store.db_readonly`.
4. Тест (новый файл в `tests/`): (а) `db_readonly` на существующей БД с таблицей отдаёт соединение, запись через которое отказывает (`sqlite3.OperationalError` с «readonly»), а `row_factory` — `sqlite3.Row` при `rows=True` и `None` при `rows=False`; (б) на отсутствующем файле — `sqlite3.OperationalError`, файл не появляется; (в) подменой атрибута `sqlite3.connect` шпионом: первый аргумент оканчивается на `?mode=ro`, `uri=True` передан именованным аргументом, путь — `as_uri()` переданного пути; (г) разбор AST всех `.py` в `orchestrator/` и `scripts/`: строковая константа или часть f-строки, содержащая `?mode=ro` (докстринги модулей, классов и функций не считаются), встречается только внутри `store.db_readonly`; (д) при подменённом `config.DB` вызов `db_readonly()` без аргументов открывает подменённый путь (шпион `sqlite3.connect` видит его `as_uri()`). На текущем коде (а)–(в) и (д) красные (функции нет), (г) красный (пять мест, включая `scripts/test_rule_stats.py:72`). Проверка (г) — линтер требования 3; в её докстринге — «Ловит мутацию: возвращена своя копия открытия `?mode=ro` мимо `store.db_readonly`».
5. Поведение команд `knowledge`, `suite-run`, `preflight`, `scripts/test_rule_stats.py` и функции `db_usable` не меняется. Существующие тесты не правятся и остаются зелёными.

Зоны: orchestrator/store.py, orchestrator/knowledge_cards.py, orchestrator/suite_run.py, orchestrator/preflight.py, scripts/test_rule_stats.py, docs/codebase-map.md, tests/

Ограничение зон по смыслу: в `knowledge_cards.py`, `suite_run.py`, `preflight.py`, `scripts/test_rule_stats.py` меняется только строка открытия соединения (и ставший лишним импорт `sqlite3`, если он больше не нужен).

Только чтение: orchestrator/ и scripts/ (каталоги обхода AST в тесте; меняются только файлы Зон), orchestrator/doctor/observations.py, orchestrator/doctor/stale_cycles.py (соединение из `store.db()` — не меняются).

Не входит: соединения `mode=ro`, которые открывают сами тесты; прямые SELECT в `orchestrator/doctor/*` (соединение — `store.db()`); единый текст отказа «БД не найдена» для всех команд — тексты разные намеренно и держатся тестами.

Бюджет: $25.
