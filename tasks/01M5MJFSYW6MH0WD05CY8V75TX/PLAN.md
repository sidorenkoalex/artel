---
task: 01M5MJFSYW6MH0WD05CY8V75TX
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: suite-run записывает время каждого теста полного прогона по отметкам времени строк хода

## Подход
Новый модуль `orchestrator/suite_durations.py`:
- `_Tracker` — разбор одной полной строки: строка рабочих
  (`^\d+ workers? \[\d+ items?\]`) задаёт отсчёт первой строки процесса
  (без неё — `start`); строка хода xdist распознаётся `suite_run._PROGRESS`
  (форма `[gwN] …`, группа `n1`) плюс имя процесса; после первой
  `suite_run._REPORT_SECTION` строки не разбираются. Время — разница с прошлой
  строкой хода своего процесса.
- `durations(marks, start)` — чистая функция поверх `_Tracker`: одна запись
  `Record(node, worker, outcome, seconds)` на (id, процесс) в порядке первого
  появления, повтор суммирует время, исход худший (как в `_progress`).
- `Reader` — фоновый daemon-поток: раз в 0,25 с читает прирост лога (лог
  открыт `rb`), время строки — момент чтения, в котором пришли её первые
  байты; полная строка (пришёл `\n`) даёт строку
  `<id>\t<gwN>\t<исход>\t<секунды>` в `<лог без .log>.durations.tsv` с `flush`
  (повтор id — повторная строка). `stop()` ставит событие, поток один раз
  дочитывает остаток, хвост без `\n` разбирает как полную строку; ожидание —
  `join(2.0)`. Любое исключение в потоке (в т.ч. файл времени не открывается)
  просто завершает поток.
- `slowest_block(log)` — 30 тестов и 15 файлов по убыванию секунд (сумма
  строк одного id; файл — сумма его тестов), строки `  <секунды> с  <имя>`;
  нет файла/строк — пустая строка.

`acceptance._run_full_suite_to_log`: третий контекст в том же `with` —
`_durations_reader(log, profile)`; при `profile is None` он запускает
`Reader` до `_launch` (начало прогона) и останавливает на выходе из тела, т.е.
после отметки `_last_run_completed_at` и после `proc.wait`/снятия группы.
argv, окружение, лог и вывод не меняются. Импорт `suite_durations` ленивый
(цикл `suite_durations -> suite_run -> acceptance`).

`suite_run._run`: после `render` и `suite_load_line` дописывается
`suite_durations.slowest_block(log)` — только по логу ветки (база в блок не
идёт), в лог и `output` блок не попадает.

## Шаги
1. `orchestrator/suite_durations.py` + поток в `_run_full_suite_to_log` +
   блок в `suite_run._run`; новый тест `tests/test_suite_durations.py`
   (блок меньше среза); регенерация `docs/codebase-map.md`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 (`Reader._read`, время по первым байтам, неполная строка ждёт) |
| 2 | 1 (`_Tracker`, `durations`) |
| 3 | 1 (`_durations_reader`, `Reader.stop`, дочитывание хвоста) |
| 4 | 1 (`path_for`, запись с `flush`) |
| 5 | 1 (`slowest_block`, `suite_run._run`) |
| 6 | 1 (поток только при `profile is None` и только в прогоне в файл) |
| 7 | долгоживущий файл test_author + `tests/test_suite_durations.py` |

Проверено: `tests/test_01m5mjfsyw6mh0wd05cy8v75tx_suite_durations.py` — 5
passed; планка `plank-run` — 3 passed; tests/test_suite_run.py,
pult_pytest_unchanged, launch_places, approve_acceptance_full_suite,
fsm_merge_gate_remote_branch_cleanup, doc_commit_suite_gate, own_run_path,
profile_callers, base_reuse, missing_command, subtest_failures,
developer_suite_run, pytest_own_places, suite_observation, suite_near_limit —
160 passed. Мутация нового теста (срез `[:len-1]`) — красный, код возвращён.

## Влияние на систему
Гейты (автогейт, мерж, `notes`) идут без лога — `_run_full_suite_now` до
`_run_full_suite_to_log` не доходит, их прогон не меняется. Поток не зовёт
`subprocess`, лог только читает; ожидание потока не входит в длительность
под наблюдением (после отметки), без наблюдения добавляет ≤ 2 с. Новых ключей
`result.json` нет, `parse`/`_progress`/`render` не тронуты. Имя `.tsv` не
подпадает под `*.log` шаблоны номеров. Откат — revert merge-коммита.

## Риски
- Время зависит от периода опроса (0,25 с) — точность порядка опроса; для
  поиска медленных тестов достаточно.
- Если поток не уложился в 2 с (диск завис), он остаётся daemon и файл
  времени может быть неполон — прогон и итог от этого не зависят.

## Предложения системе
- Bash роли: `cd … && …` и `ls`/`sed` в конвейере требуют подтверждения —
  рабочий приём только абсолютные пути и одиночные команды (повтор наблюдения
  test_author этой же задачи).
