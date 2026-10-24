---
task: 01M5PWFGJQNV8YSAN5MF0CKHVW
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: `mutation-run` — `--wait-lock`, `--copy-table`, `--workers`

## Фаза A — план
- Таблица покрытия PLAN.md охватывает требования 1–20; шаги размера MR (код модуля / тексты artel.py+карта / прогон тестов), не микрооперации.
- Подход согласован с SPEC «Материалы»: своё ожидание вместо `suite_lock.wait_acquire` (опрос 1 с), `-n` в конце `extra`, копия прямым `write_bytes`. Решения ANSWER-2 (В-1 «копии нет» без таблицы, `int(строка)`, `os.cpu_count() or 1`) учтены в плане и в коде.
- «Влияние на систему» совпадает с diff: изменены только `orchestrator/mutation_run.py`, `orchestrator/artel.py` (строка «Команды:» и комментарий `_ROLE_ALLOWED_COMMANDS`), `docs/codebase-map.md`. Откат — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `_lock_minutes` (`mutation_run.py:739`), без флага `lock_minutes = 0` → прежний отказ в `_take_lock` |
| 2 | OK | `_take_lock` (`:864`): строка ожидания с `describe(holder)`, цикл `sleep(10)` → `acquire` до `monotonic()+N·60`; срок кратен 10 с — последняя проверка на сроке, отказ «ожидание N мин истекло» |
| 3 | OK | проигранный `acquire` — просто следующая итерация цикла |
| 4 | OK | `_take_lock` стоит до `_new_log`/`mutation-background.log`; `KeyboardInterrupt` не перехватывается; SIGTERM-обработчика нет |
| 5 | OK | `int(text)` с `ValueError`→-1, диапазон 0…предел; без значения — `_parse_args` «требует одно значение» |
| 6 | OK | сумма с `--wait` проверяется, текст называет предел |
| 7 | OK | `_Run.header`/`_Run.row` → `sync_copy` → `_write_copy` (прямой `write_bytes`) |
| 8 | OK | `run.copy` ставится только при `copy_table`; в отчёте — только при `state["copy_table"]` |
| 9 | OK | `_write_copy` не создаёт каталог, сбой → False; `_show_table` печатает одну строку «копии нет» |
| 10 | OK | git не трогается; AC-12 зелёный |
| 11 | OK | `_show_table` печатает «копия таблицы: <путь>» только при успешной записи |
| 12 | OK | перезапись копии до `_print_table` во всех трёх ветках `_wait`; без основной таблицы копия не пишется |
| 13 | OK | `_RUN_FLAGS` в режиме только отчёта → отказ с форматом |
| 14 | OK | разбор прочих флагов, исходы, пределы прежние; в таблице добавлена одна строка шапки; guard не тронут |
| 15 | OK | `USAGE` и строка «Команды:» `artel.py:187–188` |
| 16 | OK | модульный докстринг переписан (`:13–18`, `:28–36`) |
| 17 | OK | комментарий `artel.py:2186–2192` называет `--copy-table` и сужение требования 10 SPEC 01M5NPKPWFEWTYMBYWVR797AM6 |
| 18 | OK | долгоживущие файлы test_author, pytest-стиль, у каждой функции «Ловит мутацию:», часы и сон подменены |
| 19 | OK | без временного файла и `os.replace`; копия появляется только после записи шапки |
| 20 | OK | `_workers` (`:758`), `-n <n>` последним в `extra` `_Run.suite`, строка шапки «# рабочих процессов: …» |

## Замечания
Блокирующих и major-замечаний нет.

- Тесты: долгоживущие файлы задачи (`tests/test_01m5pwfgjqnv8ysan5mf0ckhvw_*`) — заявки «Ловит мутацию» наблюдаемы и сверены выборочно временной мутацией (см. «Проверено исполнением»). Существующие файлы `tests/` в diff не тронуты, ослаблений нет.
- Мелочь, не замечание: файл `…_mutation_run_flags.py` идёт ~150 с, это выше порога 60 с из пакета. Это файл test_author из перечня лока, а не код разработчика, поэтому в реестр не заношу (см. «Предложения системе»).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Замечаний нет.

## Вердикт
approved

## Проверено исполнением
- `artel.py plank-run 01M5PWFGJQNV8YSAN5MF0CKHVW` — отказ «планки нет: … нет файлов test_*.py» (у задачи только долгоживущие тесты).
- `python3 -m pytest -p no:cacheprovider -q tests/test_01m5pwfgjqnv8ysan5mf0ckhvw_mutation_run_flags.py` — 40 passed за 148.6 с.
- `python3 -m pytest -p no:cacheprovider -q tests/test_01m5pwfgjqnv8ysan5mf0ckhvw_mutation_run_texts.py tests/test_01m5npkpwfewtymbywvr797am6_mutation_run.py tests/test_01m5p2bhx6m16xxm0tsvww9hem_mutation_run_table.py` — 32 passed, 50 subtests passed. Первая попытка с `-n 4` не запустила ни одного теста (рабочие процессы xdist «node down»), поэтому повторил без xdist.
- Временная мутация: `_LOCK_POLL_SEC = 1` → `-k ac3` красный (1 failed). Код возвращён.
- Временная мутация: убран `self.sync_copy()` из `_Run.row` → `-k ac9` красные оба варианта (2 failed). Код возвращён, `git status` чистый.
- Свежесть карты: `python3 scripts/codebase_map.py` → `git diff` показал расхождение только в строке `built_at_sha`; карта на ветке свежая. Регенерация откачена `git checkout -- docs/codebase-map.md`.

## Предложения системе
- Долгоживущий файл `tests/test_01m5pwfgjqnv8ysan5mf0ckhvw_mutation_run_flags.py` идёт ~150 с при пороге 60 с: каждый тест поднимает свою песочницу с git и настоящим pytest. Пульт это лишь предупреждает; стоит дать skills/test-authoring.md указание о бюджете времени файла, например общий стенд на модуль.
