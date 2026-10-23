---
task: 01M5MHVFQ9SC6EDRH34F8THNQ3
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/store.py, orchestrator/knowledge_cards.py, orchestrator/suite_run.py, orchestrator/preflight.py, scripts/test_rule_stats.py, docs/codebase-map.md, tests/
budget_usd: 25
---

# SPEC: Одна функция открытия БД пульта только на чтение вместо пяти копий

## Контекст
Находка ревизии кода 22.10 CR-2026-10-22-13 (`docs/audits/code-revision-2026-10-22.md`).
Пять мест сами собирают соединение с БД пульта «только на чтение» строкой
`sqlite3.connect(f"{<путь>.resolve().as_uri()}?mode=ro", uri=True)`:
`orchestrator/store.py:337` (`db_usable`), `orchestrator/knowledge_cards.py:767`
(`_open_db_readonly`), `orchestrator/suite_run.py:179` (`_readonly_db`),
`orchestrator/preflight.py:84` (`_open_db_readonly`), `scripts/test_rule_stats.py:72`
(`journal`). Общей функции открытия на чтение в `store.py` нет — есть только
`db()` (на запись, WAL, миграция). Задача сводит пять копий к одной функции
`store.db_readonly`, не меняя поведения вызывающих.

## Требования

1. В `orchestrator/store.py` появляется функция `db_readonly(path=None, *, rows=True) -> sqlite3.Connection`:
   открывает `path` (`pathlib.Path` или `None`; `None` — `config.DB`, прочитанный
   в момент вызова, а не при импорте) вызовом
   `sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)` — через
   атрибут модуля `sqlite3`, с `uri` именованным аргументом; при `rows=True`
   ставит `row_factory = sqlite3.Row`. Существование файла функция не проверяет
   и исключения `sqlite3` не перехватывает: на отсутствующем файле наружу
   выходит то же `sqlite3.OperationalError`, что сегодня у `connect`. Файл БД
   она не создаёт, `store.db()` не зовёт, режим журнала не меняет.
2. Пять мест открывают соединение через `store.db_readonly`: `store.db_usable`
   (`rows=False`), `knowledge_cards._open_db_readonly`, `suite_run._readonly_db`,
   `preflight._open_db_readonly`, `scripts/test_rule_stats.journal`
   (`path=db_path`, `rows=False`). Проверки существования файла, тексты
   отказов, коды выхода и перехват исключений остаются у вызывающих в нынешнем
   виде.
3. Вне `store.db_readonly` подстрока `?mode=ro` не встречается ни в строковых
   константах, ни в частях f-строк кода `orchestrator/` и `scripts/`;
   докстринги и комментарии не считаются.
4. Новый тестовый файл в `tests/` держит свойства критериев AC-1…AC-5;
   проверка AC-4 — линтер требования 3, в её докстринге — «Ловит мутацию:
   возвращена своя копия открытия `?mode=ro` мимо `store.db_readonly`». На
   текущем коде все эти проверки красные (функции нет; копий пять, включая
   `scripts/test_rule_stats.py:72`).
5. Поведение команд `knowledge`, `suite-run`, `preflight`,
   `scripts/test_rule_stats.py` и функции `db_usable` не меняется.
   Существующие тесты не правятся.

## Критерии приёмки

AC-1. `store.db_readonly` на существующей БД с таблицей отдаёт соединение, запись через которое отказывает `sqlite3.OperationalError` с «readonly» в тексте; `row_factory` соединения — `sqlite3.Row` при `rows=True` (и по умолчанию) и `None` при `rows=False`.

AC-2. `store.db_readonly` на отсутствующем файле поднимает `sqlite3.OperationalError`, и файл после вызова не появляется.

AC-3. При подменённом шпионом атрибуте `sqlite3.connect` вызов `store.db_readonly(path)` передаёт первым аргументом строку, равную `path.resolve().as_uri()` с суффиксом `?mode=ro`, а `uri=True` — именованным аргументом; `path` в проверке содержит компонент, который `resolve()` меняет (символическая ссылка на каталог или `..`), так что строка от неразрешённого пути с ожидаемой не совпадает.

AC-4. Разбор AST всех `.py` в `orchestrator/` и `scripts/`: строковая константа или часть f-строки, содержащая `?mode=ro` (докстринги модулей, классов и функций не считаются; комментарии в AST не попадают), встречается только внутри функции `db_readonly` модуля `orchestrator/store.py`.

AC-5. При подменённом `config.DB` вызов `store.db_readonly()` без аргументов открывает подменённый путь: шпион `sqlite3.connect` видит его `as_uri()` с суффиксом `?mode=ro`.

AC-6. `store.db_usable`, `knowledge_cards._open_db_readonly`, `suite_run._readonly_db`, `preflight._open_db_readonly` и `scripts/test_rule_stats.journal` открывают соединение вызовом `store.db_readonly` (у `db_usable` — с `rows=False`; у `journal` — с `path=db_path`, `rows=False`): подмена `store.db_readonly` шпионом фиксирует вызов из каждого из пяти мест с этими аргументами.

AC-7. Тексты отказов и коды выхода на отсутствующей БД остаются прежними: `knowledge` — `sys.exit` с текстом «knowledge: БД пульта … не найдена»; `preflight` — «БД пульта … не найдена» и код 2; `scripts/test_rule_stats.journal` — `StatsError` «нет БД пульта …», а `sqlite3.Error` при открытии — `StatsError` «БД пульта … не прочитана: …»; `db_usable` — `False` и при отсутствии файла, и при `sqlite3.Error` открытия.

## Оценка объёма и деление

Сработавший сигнал: число файлов зоны вне общих зон — 5
(`orchestrator/store.py`, `orchestrator/knowledge_cards.py`,
`orchestrator/suite_run.py`, `orchestrator/preflight.py`,
`scripts/test_rule_stats.py`) при пороге `SPLIT_SIGNAL_ZONE_FILES = 5`.

Материал для решения Оператора — обоснование монолита: правка в четырёх
вызывающих файлах — строки открытия соединения (плюс, где нужно, импорт
`store` и удаление ставшего лишним импорта `sqlite3`), объём всей задачи мал. Деление «функция в `store`
первой, замены второй» оставило бы после первой части красным линтер AC-4
(требование 3: копий `?mode=ro` вне `store.db_readonly` остаётся пять), т.е.
первая часть не мержима с зелёной планкой без отказа от AC-4; деление по
вызывающим без общей функции невозможно — всем им нужна `store.db_readonly`.

## Не входит

- Остальные файлы каталогов `orchestrator/` и `scripts/` (только чтение —
  каталоги обхода AST в тесте AC-4; меняются только файлы зон).
- Соединения `mode=ro`, которые открывают сами тесты.
- Прямые SELECT в `orchestrator/doctor/observations.py` и
  `orchestrator/doctor/stale_cycles.py` (соединение из `store.db()`) — эти
  файлы не меняются.
- Единый текст отказа «БД не найдена» для всех команд — тексты разные
  намеренно и держатся тестами.
- В `knowledge_cards.py`, `suite_run.py`, `preflight.py`,
  `scripts/test_rule_stats.py` — любые правки, кроме замены строк открытия
  соединения (включая промежуточную переменную `uri = …` в
  `scripts/test_rule_stats.py:72`), добавления импорта `store`
  (`from orchestrator import store` в скрипте) и удаления ставшего лишним
  импорта `sqlite3`; прочий код этих файлов не меняется (решение Оператора
  на гейте SPEC 23.10.2026).
- Правка существующих тестов (в том числе
  `tests/test_01m5keyg8g1wxhsr4bdkbsh6jp_canary_runs.py::test_ac11_sqlite_connect_only_from_store`,
  `tests/test_01m4s0k2mjrmvmqwkatame3rhr_knowledge_command.py::test_ac5_reads_db_with_read_only_connection`,
  `tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py::test_ac1_developer_full_run_refused_before_any_write`,
  `tests/test_preflight.py`, `tests/test_test_rule_stats.py`,
  `tests/test_01m3xr84299td6v6e16d2pnxh4_rule_stats.py`,
  `tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py`,
  `tests/test_01m4p4zp37wv81410ytzhkqc8d_preflight.py`,
  `tests/test_reference_command.py`) — их зелёный прогон держит пульт
  (полный набор `tests/`).

## Материалы

- ТЗ: `tasks/01M5MHVFQ9SC6EDRH34F8THNQ3/TZ.md`.
- `docs/audits/code-revision-2026-10-22.md`, находка CR-2026-10-22-13.
