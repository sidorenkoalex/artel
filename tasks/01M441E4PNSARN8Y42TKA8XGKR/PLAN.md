---
task: 01M441E4PNSARN8Y42TKA8XGKR
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: canary-status-sort

## Подход
По допущению SPEC (ANSWER-1): `status --sort cost` печатает прежний вывод
`cmd_status` без изменений, а затем отдельный блок «По расходу:».

- `orchestrator/catalog.py`: `cmd_status(sort: str | None = None)` —
  параметр по умолчанию сохраняет прежний вызов; после секции триггеров
  при `sort == "cost"` печатается `_by_cost_block(rows)`: пустая строка,
  `По расходу:`, затем по строке `  <id>  $<spent>/<budget>  <title>` в
  порядке ключа `(-spent_usd, id)`. Допустимые ключи —
  `STATUS_SORT_KEYS = ("cost",)`.
- `orchestrator/artel.py`: `_status_sort_arg(rest)` разбирает `--sort` ДО
  вызова `cmd_status`; неизвестное или пропущенное значение — текст в
  stderr с переданным значением и `допустимо: cost`, `sys.exit(2)` (идиома
  `_refuse_unsupported_interpreter`). Строка справки модуля дополнена
  `status [--sort cost]`.
- Источник расхода — `spent_usd` строки задачи, без
  `budget.spent_with_estimate` (SPEC, «Не входит»).

## Шаги
1. Блок «По расходу:» в `catalog.cmd_status` + разбор `--sort` в
   диспетчере `artel.py`; свой тест углов `tests/test_status_sort_edges.py`;
   регенерация `docs/codebase-map.md`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 (`_by_cost_block` после всего прежнего вывода) |
| 2 | 1 (ключ `(-spent_usd, id)`) |
| 3 | 1 (без флага `sort=None`, код пути не меняется) |
| 4 | 1 (`_status_sort_arg`, код 2 до вывода задач) |

Проверка (передний план, таймаут 120 с на тест):
- `tests/test_01m441e4pnsarn8y42tka8xgkr_status_sort.py` (долгоживущий,
  не правился) — зелёный;
- `tests/test_status_sort_edges.py`, `tests/test_catalog_status_log.py`,
  `tests/test_catalog_wave_breaker_status.py`,
  `tests/test_catalog_zone_overlap.py`,
  `tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py`,
  `tests/test_artel_role_restricted_commands.py`, `tests/test_codebase_map.py`,
  `tests/test_invariants.py` — все зелёные (113 passed).
- Мутации своих тестов проверены: `rest[i + 1]` без проверки длины и
  печать основного вывода до разбора `--sort` — оба теста красные; код
  возвращён.

## Влияние на систему
- Вывод `status` без флага не меняется (AC-3 долгоживущего теста сверяет
  строки и порядок). `status` остаётся в белом списке команд роли; новый
  флаг — только чтение.
- Прежде лишние аргументы `status` игнорировались; теперь отказывает лишь
  `--sort` с недопустимым значением, прочие аргументы игнорируются как
  раньше.
- Гейты, лимиты, тесты не ослабляются. Откат — revert merge-коммита.

## Риски
- Допущение ANSWER-1 (из SPEC): блок по расходу дописан после прежнего
  вывода, а не переупорядочивает его — может оказаться не тем видом,
  которого ждал Оператор, но номера прежних строк сохранены, скрипты
  сводки не ломаются.
- `status --sort cost` при пустом каталоге печатает «Задач нет…» и пустой
  заголовок блока — сохраняет форму «прежний вывод + блок».

## Предложения системе
- Песочница роли отказывает в `ls` и в составных bash-командах с `cd`/
  присваиванием переменных из-за deny-правила Read — простые шаги
  (листинг каталога документов) требуют обходов через Read/grep.
