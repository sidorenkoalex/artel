---
task: 01M5KEYG8G1WXHSR4BDKBSH6JP
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: canary runs — история прошедших прогонов канарейки командой пульта

## Подход
Читающая подкоманда по образцу `canary live`: разбор и все отказы — в
`orchestrator/artel.py` (`_cmd_canary_runs`, ветка `runs` в `_cmd_canary`
рядом с `live`), исполнение — `canary.cmd_canary_runs(since, run_stamp)`.
Строки — одной выборкой `store.all_canary_runs(store.db())`, группировка по
`run_stamp` в Python (порядок `id` внутри группы даёт `ORDER BY id`
читателя), группы — по убыванию `run_stamp` (метка UTC старта, строковый
порядок хронологический). `--since` сравнивает наименьший `created_at` группы
со строкой `<дата> 00:00:00Z` (формат `store.now()`, лексикографически
сопоставим). Причина отказа — `_acceptance_summary(route, refusal, False)`,
каталог диагностики — `_diagnostics_dir(config.ROOT, …)`: те же функции,
что у записи прогона, без копии формулы. Реестр живых, git и сеть не
трогаются. Бюджет SPEC не пересматривается.

## Шаги
1. `orchestrator/canary.py`: `CANARY_RUNS_DEFAULT_COUNT = 10`, помощники
   вывода `_runs_value`, `_runs_money`, `_runs_header`, `_runs_task_lines`,
   `cmd_canary_runs`. `orchestrator/artel.py`: `_CANARY_RUNS_USAGE`,
   `_cmd_canary_runs` (отказы требования 2 до чтения БД), ветка `runs`,
   строка справки сразу под `canary live`. Тест
   `tests/test_canary_runs.py` (пустой отбор `--since`), карта
   `docs/codebase-map.md` регенерирована.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1 |
| 5 | 1 |
| 6 | 1 |
| 7 | 1 |
| 8 | 1 |

Проверено: `python3 -m pytest tests/test_01m5keyg8g1wxhsr4bdkbsh6jp_canary_runs.py
tests/test_canary_runs.py tests/test_01m5fa4nr91pcf47szt6v0q9hs_live_cmd.py
tests/test_01m5c6qa6s3ry9ps4h9zj58wq0_canary_registry.py tests/test_canary_parallel.py
tests/test_canary_parallel_protection.py` — зелёные; `artel.py plank-run
01M5KEYG8G1WXHSR4BDKBSH6JP` — 2 passed. Мутация нового теста (пустой отбор →
`sys.exit`) — тест красный, код возвращён.

## Влияние на систему
Новая ветка `runs` стоит до разбора `--parallel`/`--detach`/`--k` и
срабатывает только на первом аргументе `runs`; прочие аргументы идут прежним
путём (отказ «нужен параметр --k» — AC-13 зелёный). Команда только читает
через `store`; ленивое заведение `store.all_canary_runs` не тронуто. Гейты,
лимиты, существующие тесты не меняются. Откат — revert merge-коммита.

## Риски
`created_at` с `NULL` в группе считается пустой строкой (раньше любой даты) —
такой прогон под `--since` не попадёт; в схеме `created_at` заполняется при
записи, случай гипотетический.

## Предложения системе
