---
task: 01M5KEYG8G1WXHSR4BDKBSH6JP
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: canary runs — история прошедших прогонов канарейки командой пульта

## Фаза A: план
- Таблица покрытия полна (требования 1–8 → шаг 1). Один шаг оправдан
  обоснованием монолита SPEC (ветка разбора без функции и наоборот не
  проверяемы); дифф 155 строк — размер одного MR.
- Подход по образцу `canary live` (разбор/отказы в `artel.py`, исполнение в
  `canary.py`), повторное использование `_acceptance_summary` и
  `_diagnostics_dir` вместо копии формулы — согласуется с архитектурой.
- «Влияние на систему» соответствует диффу: изменены только
  `orchestrator/artel.py`, `orchestrator/canary.py`, новый
  `tests/test_canary_runs.py` (+ карта). Существующие тесты, гейты,
  `store.py` не тронуты. Откат — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | ветка `runs` — `orchestrator/artel.py:1577`, `canary.cmd_canary_runs(since, run_stamp)` — `orchestrator/canary.py` (после `cmd_canary_live`) |
| 2 | OK | `_cmd_canary_runs`: `-…`/второй позиционный/повторный `--since`/`--since` последним/значение на `--` → текст использования; `fullmatch` + `strptime` для даты; `RUN_STAMP_RE.fullmatch`; несовместимость. Всё до `canary.cmd_canary_runs`, т.е. до `store.db()` (AC-6 зелёный) |
| 3 | OK | группировка по `run_stamp`, `sorted(reverse=True)`; внутри группы порядок `ORDER BY id` читателя; default — срез `CANARY_RUNS_DEFAULT_COUNT=10`; `--since` — `min(created_at) >= "<дата> 00:00:00Z"`; отсутствующий stamp — `sys.exit` с текстом; пусто — «прогонов канарейки нет», код 0 |
| 4 | OK | заголовок из первой строки группы, `NULL`→`—`, `cost_usd NULL` = 0 в сумме и `$—` в строке; пометки ролей/маркера; причина отказа `_acceptance_summary(..., False).lstrip()` с отступом 4; диагностика по `_diagnostics_dir(config.ROOT, stamp, task_id).is_dir()` (`canary.py:2067` даёт ровно `.artel/canary/<stamp>/<task_id>`) |
| 5 | OK | одно чтение `store.all_canary_runs(store.db())`; ни журнала, ни записи, ни `live_runs`/`_live_dir`, ни subprocess (AC-8, AC-11, AC-12 зелёные) |
| 6 | OK | ветка `runs` только на `rest[0] == "runs"`, прочие пути не тронуты; AC-13 зелёный |
| 7 | OK | строка справки сразу под `canary live` (`artel.py:189`) |
| 8 | OK | долгоживущий файл задачи + `tests/test_canary_runs.py`, детерминированно, песочница; существующие тесты не правятся |

## Замечания
Блокирующих и major нет.

- (наблюдение, не замечание) `tests/test_canary_runs.py` проверяет пустой отбор
  `--since` при непустой таблице — свойство, которого долгоживущий файл задачи
  не держит (там AC-7 — пустая таблица, AC-4 — непустой отбор), повтором не
  является. Заявка «Ловит мутацию» проверена временной мутацией (см. ниже).
- (наблюдение) `\d` в проверке `--since` принимает и не-ASCII цифры
  (`strptime` их тоже примет) — такой ввод даёт пустой отбор, а не отказ.
  Формулировка SPEC (`\d{4}-\d{2}-\d{2}`) выполнена буквально; последствий
  кроме «прогонов канарейки нет» нет — не замечание.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Замечаний нет.

## Вердикт
approved

## Проверено исполнением
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M5KEYG8G1WXHSR4BDKBSH6JP` —
  `2 passed in 1.17s`, код выхода pytest 0.
- `python3 -m pytest -q tests/test_01m5keyg8g1wxhsr4bdkbsh6jp_canary_runs.py tests/test_canary_runs.py tests/test_01m5fa4nr91pcf47szt6v0q9hs_live_cmd.py` —
  `23 passed, 49 subtests passed`.
- Временная мутация заявки `tests/test_canary_runs.py`: в `cmd_canary_runs`
  убрана печать «прогонов канарейки нет» при пустом отборе → тест
  `test_since_after_every_run_prints_single_line` красный (1 failed); код
  возвращён `git checkout -- orchestrator/canary.py`, дерево чистое.
- `python3 scripts/codebase_map.py` → `git diff --stat`: изменена 1 строка
  (`built_at_sha`), содержимое карты свежее; изменение откачено.
- CI коммита 5a10bd5e зелёный (16 проверок, из пакета).

## Предложения системе
- Песочница Bash шага ревью не пропускает `cp` во `/tmp` для бэкапа перед
  временной мутацией; рабочий приём — правка через `python3 -c` и откат
  `git checkout -- <файл>`. Стоит назвать его в review-checklist
  («Сторож — проверен временной мутацией»).
