---
task: 01M5MJFSYW6MH0WD05CY8V75TX
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: suite-run записывает время каждого теста полного прогона по отметкам времени строк хода

## Фаза A — план
- Таблица покрытия PLAN полна: требования 1–7 привязаны к шагам и именам
  (`Reader._read`, `_Tracker`/`durations`, `_durations_reader`/`Reader.stop`,
  `path_for`, `write_slowest`, условие `profile is None`, тесты).
- Шаги размера MR; итерация 2 оформлена отдельным шагом под ANSWER-1/2.
- Подход в архитектуре: поток — контекст-менеджер внутри того же `with`, ленивый
  импорт против цикла `suite_durations -> suite_run -> acceptance`;
  `parse`/`_progress`/`render` не тронуты. «Влияние на систему» совпадает с diff
  (4 файла кода + карта; долгоживущий файл — по мандату ANSWER-2).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `Reader._loop` опрашивает раз в `POLL_SEC=0.25` с; `_read` держит `pending_at` — время чтения первых байтов неполной строки (suite_durations.py `_read`), полная строка разбирается по `\n`; `_Tracker.in_report` по `suite_run._REPORT_SECTION`. Временная мутация «отметка по приходу `\n`» ловится AC-2 (см. ниже). |
| 2 | OK | `_Tracker.feed`: разница с `last[worker]`, отсчёт от `_WORKERS` (`workers?`/`items?`) или `start`; `durations` склеивает (id, процесс), исход худший через `_worse`. |
| 3 | OK | `_durations_reader` — третий контекст `with` в `_run_full_suite_to_log` (acceptance.py:2891–2892): выход из него после `proc.wait`/`_kill_group` и после присвоения `_last_run_completed_at` в обеих ветках (2903, 2912) — ожидание потока в длительность под наблюдением не входит; без наблюдения +≤`JOIN_SEC`=2 с. Хвост без `\n` при дочитывании эмитится. Поток daemon, лог `rb`, `subprocess` не зовёт; исключения потока и запуска потока гасятся. |
| 4 | OK | `path_for` → `<лог без .log>.durations.tsv`, строка `id\tgw\tисход\tсек` + `flush` на каждую запись; повтор id — повторная строка, `_read_file` суммирует. |
| 5 | OK (по ANSWER-2) | Блок пишется в `<лог>.slowest.txt` (`write_slowest`), в `report` — одна строка-ссылка после `render`/`suite_load_line` (suite_run.py:698–701), только по логу ветки (в `--failed` — лог повтора); без строк — ни файла, ни строки. Лог pytest/`output`/`result.json` не задеты. |
| 6 | OK | argv/env не меняются (AC-6 зелёный); `log=None` идёт мимо `_run_full_suite_to_log`; `pytest-own` (`profile` не `None`) — `_durations_reader` сразу `yield`; профиль с отчётом уходит в `_run_full_suite_reported` до `_run_full_suite_now` (acceptance.py:2569–2571). |
| 7 | OK | Долгоживущий файл test_author + `tests/test_suite_durations.py` (два теста с заявками «Ловит мутацию», заявки наблюдаемы: состав/порядок строк блока, путь вместо `None`). |

AC-4 (имя `.durations.tsv`/`.slowest.txt` не `*.log`) и AC-7 держит планка — по разделу SPEC «Не входит», замечанием не считаю.

Правка долгоживущего `test_ac5_…` авторизована ANSWER-2 («Ослабление тестов
разрешено: …::SuiteRunSlowestBlockTest::test_ac5_…»). Сверил текущий метод с
матрицей неослабления ANSWER-2: 30/15, убывание, суммы теста и файла, повтор
id, «самые медленные», нет блока у базы — проверяются на содержимом
`.slowest.txt` (`check_block`); к отчёту — ровно одна строка-ссылка
(`assertEqual` хвоста) и ни одного id/имени файла из файла времени; сценарии
(4 прогона × без файла/с файлом/пустой) прежние; лог, `failed.json`, ключи
`result.json`, итог базы — `check_same`. Ослабления сверх мандата не вижу.

Существующие тесты `tests/` в diff не изменены (изменены только новые файлы).
Карта `docs/codebase-map.md` свежа: перегенерация дала разницу только в
`built_at_sha` (файл после проверки возвращён `git checkout`).

## Замечания

Нет замечаний blocker/major/minor.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: прошлых итераций ревью нет, в этой замечаний не заведено.

## Вердикт
approved

## Проверено исполнением
- `python3 orchestrator/artel.py plank-run 01M5MJFSYW6MH0WD05CY8V75TX` — 3 passed
  in 18.49s, код выхода pytest 0.
- `python3 -m pytest -p no:cacheprovider -q tests/test_suite_durations.py
  tests/test_01m5mjfsyw6mh0wd05cy8v75tx_suite_durations.py tests/test_suite_run.py`
  — 26 passed, 21 subtests passed.
- `python3 -m pytest -p no:cacheprovider -q
  tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py` (тесты, ронявшие CI
  9e993cb6) — 26 passed, 6 subtests passed.
- Временная мутация в `suite_durations.Reader._read`: `self._emit(now, …)`
  вместо `self._emit(self.pending_at, …)` (отметка по приходу `\n`) —
  `-k ac2` красный (1 failed); код возвращён, `git status` чистый.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` —
  изменилась только строка `built_at_sha`; файл возвращён.

## Предложения системе
- `scripts/codebase_map.py --help` не печатает справку, а молча перегенерирует
  карту — в шаге ревью это правка рабочей копии; стоит разобрать `argparse`
  или отказ на неизвестный флаг.
- Сторож роли отказывает `pytest <абсолютный путь к одному файлу tests/>` как
  «полный прогон набора» — относительный путь проходит; ложный отказ стоит
  времени шага.
