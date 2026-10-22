---
task: 01M5HDB1GSFDKFM7QB9JZMCCWJ
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: suite-run отказывает новому полному прогону из шага developer

## Подход

Признак developer — маркер `ARTEL_ROLE`, равный `config.STATE_ROLE["in_dev"]`
(ADR-0024, поправка 22.10.2026); `HOME` роли, пустой маркер и любая иная роль
признаком не считаются (`suite_run._developer`).

В `orchestrator/suite_run.py::cmd_suite_run` сразу после разбора аргументов,
до `_db()` и `suite_lock.deliver_journal`, вызов без `--wait` и без
`--failed` под маркером developer уходит в `_refuse_developer_full_run`:
задача разрешается `store.get_task` на соединении `_readonly_db()`
(`sqlite3.connect(<uri>?mode=ro, uri=True)`, вынесено из прежнего запасного
пути `_db`), соединение закрывается; идущий прогон задачи (`_running`, только
чтение файлов) — прежний ответ «уже идёт … второй не запускаю», код 0 (текст
вынесен в `_running_text`, общий с прежней веткой); иначе `sys.exit` с
отказом. Отказ называет `suite-run`, роль developer, полный id и подсказку
`_developer_hint`: CI и автопроверка приёмки, `python3 -m pytest tests/<файлы> …`
в переднем плане, `plank-run <полный id> [файл]`, `suite-run <полный id> --failed`.

Подсказки под маркером developer (`--wait` «прогона нет», `--wait` «оборван»,
`--failed` «упавших нет») берут `_developer_hint` вместо совета полного
прогона; `--failed` «прошлого прогона нет» у developer говорит, что перечень
пишет только прогон Оператора или ревьювера, и называет запуск упавших тестов
CI или гейта по именам. Без маркера тексты прежние дословно.

`orchestrator/role_prompt.py::suite_run_note` — миссия: полный набор гоняют
CI и гейт приёмки; `--failed` (только после прогона Оператора или ревьювера)
и `--wait <минуты…>` с полным путём пульта. Миссия ревьювера внешнего
проекта не тронута.

`tests/test_01m4kg7vhhxtvtw5ttx2pgy5ry_suite_run_readonly_db.py`: `ROLES`
без `developer` по мандату ANSWER-1; остальное в файле не менялось.

Новые тесты — долгоживущий файл test_author
`tests/test_01m5hdb1gsfdkfm7qb9jzmccwj_developer_suite_run.py` (ADR-0020);
своих тестов сверх него не добавлял — свойства SPEC им покрыты.

## Шаги

1. `suite_run.py`: `_readonly_db`, `_developer`, `_developer_hint`,
   `_refuse_developer_full_run`, `_running_text`; ветка developer в
   `cmd_suite_run`; развилки подсказок в `_wait` и `--failed`.
2. `role_prompt.py::suite_run_note` — новая миссия.
3. `ROLES` в `readonly_db` без developer.
4. Карта кодовой базы (`scripts/codebase_map.py`), тесты затронутых модулей,
   планка `plank-run`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1 |
| 5 | 1 |
| 6 | 1 |
| 7 | 2 |
| 8 | 3 |
| 9 | долгоживущий файл test_author; прогон — 4 |

## Матрица неослабления

| Метод | Свойство | Чем держится после |
|---|---|---|
| ReadonlyDbOutcomeTest::test_ac4_readonly_db_run_reaches_same_outcome_and_report | итог и отчёт прогона роли при БД только на чтение | тот же метод и утверждения для test_author/reviewer; `--wait 0` developer под БД только на чтение — `KeptFlagsTest::test_ac4_developer_wait_and_failed_under_readonly_db`; отказ developer под БД только на чтение — `RefusalTest::test_ac1_developer_full_run_refused_before_any_write` |
| JournalRedeliveryTest::test_ac5_pult_process_delivers_journal_record | отложенная запись журнала и её досыл процессом пульта | тот же метод; отказ developer не досылает и не трогает отложенную запись — `RefusalTest::test_ac1_…`; досыл у `--wait`/`--failed` developer — `KeptFlagsTest::test_ac4_…`; досыл у прочих вызывающих — `OtherCallersTest::test_ac6_other_callers_start_full_run_as_before` |
| SharedLockTest::test_ac6_role_suite_run_and_gate_share_one_lock_file | один файл замка у роли и гейта | тот же метод для test_author/reviewer; developer `--failed` под БД только на чтение берёт общий замок, при замке гейта отказ называет задачу гейта — `KeptFlagsTest::test_ac4_…` |
| LimitUnchangedTest::test_ac8_readonly_db_run_keeps_profile_limit_and_timeout_outcome | предел профиля и исход «не уложился» | тот же метод и утверждения для test_author/reviewer (у developer полного прогона больше нет) |
| LogPlacementTest::test_ac9_suite_run_logs_live_under_suite_run_dir | логи ветки и базы под `suite-run/` | тот же метод; отказ developer не создаёт лог (снимок хозяйства) — `RefusalTest::test_ac1_…` |

## Влияние на систему

Меняется только поведение `suite-run` под маркером `ARTEL_ROLE=developer`:
полный прогон из шага разработчика больше не берёт общий замок полных
прогонов и не задерживает гейты. Оператор, прочие роли, HOME роли без
маркера, пустой маркер — путь прежний (снятие маркера в окружении фона,
досыл журнала, замок). Гейты, лимиты, `suite_lock`, `acceptance`,
`artel.py`, `conftest.py` не тронуты. Пять методов `readonly_db` сохраняют
имена и утверждения; исключение developer из `ROLES` — по мандату ANSWER-1,
покрытие — матрица выше. Откат — revert merge-коммита задачи.

## Риски

- Отказ стоит на маркере окружения, обойти его намеренно легко — это
  уровень защиты по ADR-0024 (отсечение ошибочного вызова).
- Несуществующий id под маркером developer — прежний отказ `get_task`
  «не найдена» (чтение `mode=ro`); отсутствующая БД — исключение sqlite.

## Предложения системе

- `templates/PLAN.md`/миссия: планка AC-8 читает PLAN из ссылки документов,
  поэтому локальный `plank-run` до автокоммита шага красен на ней — шаг
  видит ложный красный и не может проверить свою матрицу сам.
