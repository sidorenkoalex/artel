---
task: 01M5MHVM25KH83WGZ5K256WN9Q
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Свежесть связи наблюдения — одна функция вместо трёх копий

## Подход
В `orchestrator/watch.py` добавлены `observation_age(row)` (единственный
разбор `last_seen_at`; `None` при `None` и `""`; «сейчас» — один вызов
`datetime.now(timezone.utc)` через имя `datetime` модуля `watch`) и
`observation_link_fresh(row)` (`age is not None and age <= порог`). Три
копии заменены вызовами:
- `artel.py::_launch_observation` — `age = watch.observation_age(observer)`;
  `None` → прежний отказ «связи с watch ещё нет …», `age > порог` → прежний
  отказ с `age:.0f`; `now` берётся один раз;
- `artel.py::_observation_fresh` — `state != "active"` → `False`, иначе
  `watch.observation_link_fresh(row)`;
- `watch.py::observation_process_state`, ветка `pid is None` — `unstarted`
  при пустом `last_seen_at`, иначе `fresh`/`stale` по `observation_link_fresh`.
Пустая строка в `artel.py` теперь трактуется как «связи нет» (намеренно, SPEC
требование 2). Импорт `datetime` в `artel.py` остаётся — он нужен в других
местах модуля (строки ~1726, ~1742).

## Шаги
1. Функции `observation_age`/`observation_link_fresh` в `watch.py` и замена
   ветки `pid is None`; замена двух копий в `artel.py`; регенерация
   `docs/codebase-map.md`. Тесты — долгоживущий файл test_author
   `tests/test_01m5mhvm25kh83wgz5k256wn9q_observation_freshness.py` (AC-1..AC-6,
   включая AST-линтер требования 3) и планка AC-7; своих тестов не добавлял —
   свойств, не покрытых долгоживущим файлом, нет.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1 (долгоживущий файл test_author) |
| 5 | 1 (store.py/config.py и существующие тесты не тронуты) |

## Влияние на систему
Поведение сохраняется, кроме намеренного: пустая строка `last_seen_at` в
`artel.py` больше не роняет `ValueError`. Тексты отказов, коды выхода, порядок
проверок не менялись. Формат хранения в `observations` и `store.py` не тронуты.
Прогнаны: долгоживущий файл задачи, `test_01m4fz6qyppkyqzfex14qh8xt6_launch`,
`test_observation_edges`, `test_observation_acceptance_return`, `test_cycle_hint`
и прочие файлы tests/, упоминающие `last_seen_at`/функции свежести (88 passed);
`plank-run` — 1 passed. Откат — revert коммита задачи.

## Риски
Минимальные: правка локальна, три места и две новые функции.

## Предложения системе
