---
task: 01M4S24963R9H18AN2XDP6R15B
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Справочник ядра — генератор, настройка проекта, кэш (К-3а)

## Подход
Три части с одним интерфейсом для К-3б, новый код ни из одной команды
пульта не вызывается (поведение пульта прежнее):

- **Генератор `scripts/core_reference.py`** — только stdlib, только `ast`
  (код проекта не импортируется и не исполняется). `build(...)` — текст;
  `build_report(...)` — текст, число записей и сбои (тексты сбоев без sha,
  времени и размеров — сразу годны в алерт). Дополнительные keyword-параметры
  `unparsed`/`skipped` (файлы, отсеянные до `build`: не UTF-8, ссылки,
  подмодули, крупные/отсутствующие blob) и `deadline` (`time.monotonic`;
  проверка после каждого `ast.parse` и каждого файла обхода —
  `DeadlineExceeded`). Детерминизм: файлы обходятся `sorted(sources)`,
  вызовы в файле — по (строка, столбец). Сигнатура собирается из
  фрагментов исходника (`ast`-смещения), не `ast.unparse` — «как в коде».
  Шапка — строки `ключ: значение` (настройка — JSON одной строкой), тело
  отделено пустой строкой; `reference_sha(text, setting, …)` сверяет
  настройку, `generator_sha256` и sha256 тела и отдаёт `built_at_sha` — формат
  шапки знает один модуль. Умолчание `--min-uses` — литерал 3 с
  комментарием (генератор не импортирует `config`; равенство с
  `config.CORE_REFERENCE_MIN_USES` держит долгоживущий тест CLI).
- **Настройка** — `targets.REFERENCE_FIELD`, проверка `_check_reference`
  в `targets.check` тем же приёмом, что `test_profile`;
  `targets.core_reference(name)` разбирает файл один раз и проверяет
  только запись `name` (`check(name, entry)` — вся запись, чужие не
  смотрятся).
- **Кэш `orchestrator/reference_cache.py`** — `get_reference(conn, task_id,
  *, reason, sha=None)` → `Reference(text, note, state)`. Порядок: `NO_AREA`
  → `off` до всего; настройка (`TargetsError` → `absent`+алерт; нет записи
  или поля → `off`); кэш читается один раз (`open` с `O_NOFOLLOW|O_NONBLOCK`,
  `fstat`: не обычный файл или > 4·`MAX_BLOB_BYTES` — испорчен); sha — переданный
  (форма `[0-9a-f]{40}` до git) или `rev-parse refs/heads/<ветка>^{commit}`
  (не узнан: кэш есть → `unverified`, нет → `absent`). Чтение коммита —
  `ls-tree -r -l -z` потоком через `Popen` с пределом вывода и таймером
  остатка срока, отбор `blob` 100644/100755 `.py`, пределы файлов и объёма
  по размерам `ls-tree` до `cat-file`; затем один `cat-file --batch` по
  уникальным blob с остатком срока, разбор по длине, `missing` — пропуск.
  Запись кэша — `mkstemp` в том же каталоге + `os.replace`, сбой — алерт
  и `fresh` из памяти. Каждая сборка — журнал «справочник ядра: построен»
  (sha, байты, записи, длительность, повод); сбои — журнал «справочник
  ядра: сбой» с подробностью, алерт `incident` с фиксированным текстом по
  проекту задачи, источник от `reason`. Внешний `except Exception` в
  `get_reference` — контракт «не бросает» (требование 6).
- Кэш — `knowledge/derived/` области проекта: карта лежит в git артели и
  коммитится после мержа, для внешнего проекта это была бы запись в чужой
  репозиторий; `knowledge/` вне git (ADR-0003 п.3а), `derived/` отделяет
  пересоздаваемое от карточек К-4а.

Оценка SPEC ($45, 5 файлов кода + тесты) совпадает с объёмом — `budget_usd`
не меняется.

## Шаги
1. `config.CORE_REFERENCE_*` (6 констант требований 2 и 4).
2. `targets`: поле `core_reference` в `check`, `core_reference(name)`.
3. `scripts/core_reference.py`: `build`/`build_report`, шапка и сверка,
   командная строка (`git ls-files` / обход диска).
4. `orchestrator/reference_cache.py`: `get_reference`, чтение коммита,
   кэш, журнал, алерты.
5. Тесты `tests/test_core_reference.py` (свойства вне долгоживущих файлов:
   пояснение многострочной константы, вырезание комментариев из значения,
   отказ CLI на `--constants-module` без `--constants`); карта
   `docs/codebase-map.md` регенерирована.
6. Возврат из verifying (CI красный из-за утечки состояния между тестами,
   не из-за кода задачи): `auto._stop_requested`/`auto._zone_wait_sleeping`
   после настоящего SIGTERM в
   `tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py::CommandHintEndToEndTest`
   доживали до `tests/test_auto_cycle.py`. Правки без изменения проверок:
   `CommandHintEndToEndTest.setUp` возвращает оба флага через `addCleanup`;
   `AutoCycleTest.setUp` выставляет оба в `False` через `patch_object`
   (`mock.patch.object` + `addCleanup(stop)` — прежние значения
   возвращаются). Код задачи не менялся; карта регенерирована.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 3 |
| 2 | 1, 3 |
| 3 | 2 |
| 4 | 1, 4 |
| 5 | 4 |
| 6 | 4 |
| 7 | 4 |
| 8 | 5 (+ долгоживущие файлы задачи) |
| 9 | 5 |

## Влияние на систему
- Новые модули ни из одной команды пульта не вызываются; `targets.check`
  дополнен необязательным полем — существующие записи без поля проверяются
  как прежде (отказ `load()` на сломанном `core_reference` принят
  Оператором 13.10.2026). Гейты, лимиты, guard и существующие тесты не
  тронуты; `orchestrator/gitcmd.py` не меняется (используется только
  `pult_env`).
- Git на чтение объектов клона проекта (`ls-tree`, `cat-file`,
  `rev-parse`), без checkout и записи в клон; пределы и срок — константы
  `config` (класс ADR-0002, меняет Оператор).
- Кэш вне git, только в `<область проектов>/<проект>/knowledge/derived/`;
  при `NO_AREA` ни чтения, ни записи.
- Откат — revert merge-коммита задачи; файлы кэша можно удалить, они
  пересобираемые.

## Проверка
- Шаг 6: `python3 -m pytest
  tests/test_01m3xtfjcc5tg63fhw907gqm4d_launch_hint.py::CommandHintEndToEndTest::test_ac9_auto_stopped_by_stop_hints_observe_add
  tests/test_auto_cycle.py::WaitForZoneTest::test_lease_lost_during_wait_stops_the_cycle_named
  tests/test_auto_cycle.py::ZoneWaitStopTest::test_signal_during_the_poll_sleep_aborts_it_and_stops_the_wait
  -p no:cacheprovider -q` — 3 passed (до правки — 2 failed по причине
  возврата); оба файла целиком — 71 passed, 53 subtests passed.
- `python3 -m pytest tests/test_01m4s24963r9h18an2xdp6r15b_generator.py
  tests/test_01m4s24963r9h18an2xdp6r15b_cli.py
  tests/test_01m4s24963r9h18an2xdp6r15b_targets_field.py
  tests/test_01m4s24963r9h18an2xdp6r15b_cache.py tests/test_core_reference.py`
  — все зелёные; `artel.py plank-run` — 2 passed.
- Мутации своих тестов (временная правка кода, возврат): поиск строкового
  комментария и в `end_lineno` — красный первый тест; без вырезания
  комментариев — второй; без отказа пары `--constants-module`/`--constants` — третий.
- Справочник артели по настройке К-3б: 28 386 байт, 162 строки (замер ТЗ
  без `scripts/guard.py` — 26 656 байт).

## Риски
- Сторож AC-14 краснеет у чужой задачи, переименовавшей одно из шести
  имён, — принятый риск SPEC.
- Многострочные значения констант схлопываются в строку и с комментариями
  внутри теряли бы хвост — вырезание комментариев покрыто своим тестом.

## Предложения системе
- Окружение роли без `cp`/`rm`/`mv` в PATH (bash `command not found`) и с
  отказом на `cd … ; grep` — проверка мутацией потребовала вспомогательный
  сценарий в каталоге документов; скил coding-standards («временно сломай
  код») стоит дополнить штатным способом (команда пульта `mutate`?).
