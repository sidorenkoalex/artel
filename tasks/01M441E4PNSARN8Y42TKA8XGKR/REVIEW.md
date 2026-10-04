---
task: 01M441E4PNSARN8Y42TKA8XGKR
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: canary-status-sort

## Фаза A — план
- Покрытие: все 4 требования SPEC сведены в таблицу PLAN на шаг 1 — полно.
- Шаг один, размером в MR (флаг + блок + тест углов + карта) — для задачи
  такого объёма адекватно.
- Подход следует допущению ANSWER-1, записанному в SPEC (блок дописан
  после всего прежнего вывода, порядок прежних строк не трогается);
  отказ кодом 2 до вывода задач — разбор в диспетчере до вызова
  `cmd_status`. Конфликта с архитектурой нет: `status` остаётся в белом
  списке роли, `_refuse_if_role_restricted` по аргументам `status` не
  решает (проверено чтением `orchestrator/artel.py:1507-1519`).
- «Влияние на систему» совпадает с diff: тронуты только
  `orchestrator/artel.py`, `orchestrator/catalog.py`, новый
  `tests/test_status_sort_edges.py` и карта; все в зонах SPEC.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `orchestrator/catalog.py:883-884` — `_by_cost_block(rows)` после секции триггеров; строка блока `  <id>  $<spent:.2f>/<budget:.2f>  <title>` начинается с id после пробелов; каждая задача из `rows` ровно один раз. |
| 2 | OK | Ключ `(-spent_usd, id)` (`catalog.py:834`). |
| 3 | OK | При `sort=None` путь вывода не изменён — diff `cmd_status` затрагивает только сигнатуру и хвост после триггеров. |
| 4 | OK | `orchestrator/artel.py:1522-1536`: неизвестное и пропущенное значение — stderr с переданным значением и `допустимо: cost`, `sys.exit(2)`; вызывается в лямбде как аргумент `cmd_status`, т.е. до печати задач. Наблюдение: форма `--sort=xxx` не распознаётся как `--sort` и ведёт себя как прочие лишние аргументы (игнор) — в CLI пульта нигде не используется форма `=`, SPEC её не называет; замечанием не оформляю. |

## Замечания
Блокеров и major нет.

Тесты:
- `tests/test_status_sort_edges.py` — оба метода с заявкой «Ловит мутацию»,
  заявки исполнимы и проверены временной мутацией (см. ниже); свойства
  («`--sort` без значения», «нет строк задач при отказе») долгоживущим
  файлом задачи не покрыты — повтора нет.
- Утверждения существующих тестов не менялись (в diff `tests/` только
  новый файл); долгоживущий файл задачи не правлен.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest -q tests/test_01m441e4pnsarn8y42tka8xgkr_status_sort.py tests/test_status_sort_edges.py tests/test_catalog_status_log.py tests/test_catalog_wave_breaker_status.py tests/test_artel_role_restricted_commands.py tests/test_01m3xtf5506gf43hd51ece230t_role_refusal.py` — 44 passed, 123 subtests passed.
- `artel.py plank-run 01M441E4PNSARN8Y42TKA8XGKR` — «планки нет: … нет файлов test_*.py»: у задачи только долгоживущий тест в `tests/`, он прогнан выше.
- `python3 scripts/codebase_map.py` → `git diff -- docs/codebase-map.md` без строки `built_at_sha` пуст — карта свежа (изменение откачено `git checkout`).
- Временные мутации (код возвращён, `git status` чист):
  1. `_status_sort_arg`: `rest[i + 1]` без проверки длины — красный `test_sort_without_value_exits_2_naming_cost`.
  2. Основной вывод печатается до разбора `--sort` (`(cmd_status(), cmd_status(_status_sort_arg(rest)))`) — красный `test_unknown_sort_prints_no_task_lines`.
  3. Ключ `(spent_usd, id)` с `reverse=True` на весь кортеж — красный `test_ac2_equal_spent_ordered_by_id_ascending`.
  4. Ключ без id `(-spent_usd,)` — тесты ЗЕЛЁНЫЕ: `store.all_tasks` отдаёт строки `ORDER BY id` (`orchestrator/store.py:518-520`), устойчивая сортировка сохраняет id по возрастанию, так что мутация поведенчески нейтральна для этого кода (см. «Предложения системе»).

## Предложения системе
- Долгоживущий `tests/test_01m441e4pnsarn8y42tka8xgkr_status_sort.py::test_ac2_…`: первая половина заявки «ключ без id (устойчивая сортировка оставляет равные в порядке вставки)» неисполнима — `store.all_tasks` уже сортирует по id, порядок вставки в БД до блока не доходит. Вторая половина заявки (reverse на кортеж) ловится. Класс: автор теста заявляет мутацию, не сверив источник порядка данных; test_author стоило бы проверять заявку временной мутацией до лока.
- Песочница ревьювера отказывает в составных bash-командах (`sed -i … && pytest`), временные мутации пришлось делать серией Edit/pytest/Edit — приём «временная мутация» из review-checklist стоит снабдить рекомендуемой формой под эту песочницу.
