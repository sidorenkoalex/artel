---
task: 01M5MVG2B1YGVPTZWKB18EVGHZ
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: canary --parallel: строка «оборвана сигналом» не теряется у дочернего, тесты гонки говорят причину, GroupSignalTest не виснет

## Фаза A — план
- Таблица покрытия PLAN полна: требования 1–7 сопоставлены шагам 1–3 и разделу «Риски».
- Шаги размера MR, не микрооперации.
- Требование 4 закрыто: в «Рисках» есть остаточный риск SIGHUP во время повторов, ограничение потока, который не дошёл до открытия канала, и допущение модели срока со ссылками `store.py:409`, `:431`, `:1620–1623`, `schema.py:291–400`.
- Подход не конфликтует с архитектурой: родитель не тронут, вынесена одна закрытая функция.
- «Влияние на систему» = diff: меняются `canary.py` (ветка `except CanaryInterrupted`), два тестовых файла (сообщения и помощники) и новый тестовый файл.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `tests/test_canary_parallel_protection.py:507` — `run.out`; `tests/test_canary_parallel.py:384` — `out`. Добавлен только третий аргумент, литералы прежние. |
| 2 | OK | `canary._insert_interrupted_row`: `store.db()` внутри `try` каждой попытки, повтор только при `sqlite3.OperationalError`, `CHILD_ROW_WRITE_ATTEMPTS = 3`, без `sleep`. В ветке `except CanaryInterrupted` при любом `Exception` в stderr идут «строка прогона не записана:» и `traceback.format_exc()`, выход `128 + signum` в обоих исходах. |
| 3 | OK | `_finish_child` и `_report_child_failure` не тронуты. Строка доходит до родителя через журнал дочернего (`ParentReportsUnwrittenRowTest`). |
| 4 | OK | Записано в PLAN, раздел «Риски». |
| 5 | OK | `run_cli`: дескриптор на запись `os.close(os.open(...))` закрывается до `join`. `read_grandchild_pid` при пустых данных бросает `AssertionError("внук не появился")`. |
| 6 | OK | Новый `tests/test_canary_child_row_write.py`: 5 тестов, у каждого есть «Ловит мутацию:», нагрузки и серий нет. |
| 7 | OK | Другие методы обоих файлов не тронуты, ни одно утверждение не удалено и не ослаблено. Сверено по diff с базой b27df084. |

Тесты: заявки мутаций сверены и наблюдаемы. «`store.db()` вне цикла»: `db.call_count == 3` и `test_failed_connection_open_is_retried`. «`except Exception` в цикле»: `insert.call_count == 1`. «sleep между попытками»: шпион `patch_sleep`. Две последние заявки подтверждены временной мутацией, см. ниже. Тест AC-4 повторяет свойство, которое планка держит только до мержа; в `tests/` оно нужно как долгоживущее, поэтому это не повтор долгоживущего файла задачи. Долгоживущий `tests/test_01m5mvg2b1ygvptzwkb18evghz_row_write_deadline.py` держит только границу срока, и новые тесты её не дублируют.

## Замечания
Нет blocker/major/minor.

Наблюдение без замечания: соединение неудачной попытки не закрывается явно, его собирает сборщик мусора. Так было и в прежнем коде, и вне зоны SPEC это ни на что не влияет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest tests/test_canary_child_row_write.py tests/test_01m5mvg2b1ygvptzwkb18evghz_row_write_deadline.py tests/test_canary_parallel_protection.py tests/test_canary_parallel.py tests/test_01m443hpzbmjgchvgv4jqn88rs_sleep_guard.py -p no:cacheprovider -q`: 36 passed, 47 subtests passed.
- `artel.py plank-run 01M5MVG2B1YGVPTZWKB18EVGHZ`: 8 passed, код выхода pytest 0.
- Временная мутация 1: `time.sleep(0)` после неудачной попытки в `_insert_interrupted_row`. Красные `test_locked_write_is_retried_without_sleep_and_row_written` и `test_persistent_lock_exhausts_attempts_and_reports_stack`. Код возвращён через `git checkout`.
- Временная мутация 2: `except sqlite3.OperationalError` заменён на `except Exception`. Красный `test_other_error_is_not_retried_and_reported`. Код возвращён.
- `python3 scripts/codebase_map.py` и `git diff -- docs/codebase-map.md` без строки `built_at_sha`: расхождений нет, карта свежая. Файл возвращён, `git status` чист.

## Предложения системе
- Планка `acceptance_tests/test_ac2_ac3_ac8_ac9_child_row_write.py` подменяет `canary.time.sleep` глобально и ловит паузы `subprocess.run(timeout=…)`, поэтому может ложно краснеть. Об этом пишет PLAN, раздел «Риски». Аналитику стоит правило в skills/test-authoring.md: шпион sleep в планке — только `tests.sandbox.patch_sleep`.
