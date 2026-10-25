---
task: 01M5TB6VDVV6AM8DWPGVQE8CDW
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Эпики Э0 — деление доводится до конца

## Подход
Все проверки деления собраны в одном месте `approve` гейта SPEC
(`orchestrator/fsm.py::_approve_spec_gate`): последним из мягких отказов и
до первой записи (журнал «Меняемое поведение», принятие `fail` аудита,
`zones`/`merge_after`, потолок). Отказ — одна запись «approve отклонён».

- Порядок частей — `merge_after.division_order`: разбор «Порядок: после …»
  теми же правилами, что строка ТЗ (`_ORDER_LIST_END`, `guard.merge_after_items`);
  «части N» — индекс части; id — через существующий `merge_after.check`
  (задача есть, префикс однозначен, не `killed`, тот же проект, без
  повтора) с явным target'ом, как для ещё не заведённой задачи. Сам
  родитель отсекается до `check` (для `check` он ещё жив). Цикл ищется
  существующим `_cycle_path` на виртуальном графе: узлы `#N` частей +
  `merge_after` всех строк БД, где родитель заменён узлом преемника.
  Преемник — `_successor` по графу частей (требование 4).
- Рамка — `guard.division_frame` (снимает `$`, `spend.cli_number`,
  `0 < N <= ROLE_BUDGET_CAP`): одна функция и для guard
  (`division_section_errors`), и для перепроверки на approve.
- После заведения ВСЕХ частей (`catalog.spawn_subtask` не меняется):
  `merge_after.record_declared` для каждой части (канал `new`, запись
  «merge_after заявлен Оператором»), `budget.apply_division_frame` (потолок
  `operator` + запись журнала части), предупреждение о нецепочке, переход
  родителя в `killed` + `closed_as='divided'`, `replace_divided` на
  преемника.
- `closed_as`: колонка в `SCHEMA` и `migrate`; прежние деления
  размечаются в том же проходе миграции, который заводит колонку
  (`schema._mark_past_divisions`) — повторный проход колонку видит и
  ничего не трогает, проверок журнала на каждом `store.db()` нет.
  Отметка `status` — `catalog._division_suffix` по `closed_as`.
- Один список состояний: `fsm.STATES`/`fsm.TERMINAL_STATES` объявлены в
  `fsm.py` ДО импортов модулей пакета. Так `cleanup`, `watch`, `report`
  берут их модульным `from . import fsm` (те же объекты — AC-15), а на
  круговом импорте получают частичный `fsm`, где константы уже есть.
  `models`/`zone_lock`/`prune` — отложенный импорт внутри функции (store →
  models и guard → zone_lock иначе тянули бы весь fsm в лист графа);
  `doctor/*` — `from orchestrator import doctor, fsm`.

Бюджет SPEC ($70) не переоценивается.

## Шаги
1. Константы `fsm.STATES`/`TERMINAL_STATES`, замена перечислений в
   report, cleanup, watch, models, zone_lock, prune, doctor/* (4 файла).
   Проверка: каждый модуль `orchestrator/`/`scripts/` импортирован первым
   в свежем интерпретаторе — падают только `fixation`, `checkpoint`,
   `pause`, и ровно так же на базе (цикл fixation → workspace → lease →
   artifact_branch, не эта задача). Планка AC-15 — зелёная.
2. `closed_as`: `schema.py` (колонка, `_mark_past_divisions`,
   константы), реэкспорт в `store.py`, отметка `catalog._division_suffix`.
3. `guard.division_frame` + ошибка рамки в `division_section_errors`.
4. `merge_after.division_order` (+ `DivisionOrder`, `_part_deps`,
   `_successor`), `budget.apply_division_frame`, в `fsm.py` —
   `_division_check` до записей и новый `_spawn_division_subtasks`.
5. Юнит-тесты `tests/test_division_order_units.py`, карта
   `docs/codebase-map.md`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 2, 4 |
| 2 | 2 |
| 3 | 2 |
| 4 | 4 |
| 5 | 4 |
| 6 | 4 |
| 7 | 4 |
| 8 | 3 |
| 9 | 4 |
| 10 | 4 |
| 11 | 1 |
| 12 | 1 (сторож — долгоживущий файл test_author) |

Прогоны: долгоживущие файлы задачи (`..._division_finish.py`,
`..._closed_as.py`, `..._guard_frame.py`, `..._terminal_literal_guard.py`)
— 38 passed, повторы со случайным зерном зелёные; планка `plank-run` — 1
passed; соседние модули (deleniye, merge_after, guard division, spec gate,
doctor, zone_lock, models, watch, report, prune, kill, invariants, миграции
схемы) — 597 + 337 passed.

## Влияние на систему
- Гейт SPEC становится строже только для SPEC с «## Деление»: новые отказы
  по порядку и рамке; без деления путь approve прежний. Существующие
  отказы и их порядок не тронуты, проверки деления стоят после них.
- Guard: новая ошибка только при заданной и негодной «Рамка:»; поле
  по-прежнему необязательно, «Порядок:» по-прежнему обязателен.
- `catalog.spawn_subtask` не меняется (`merge_after` не пишет —
  `tests/test_01m45d29bqje8fjyja4jqwsyfz_spec_gate_declared.py` зелёный).
- Миграция одноразовая (только при заведении колонки) — нагрузки на
  каждое `store.db()` не добавляет.
- Порядок импортов: `cleanup`/`watch`/`report` теперь импортируют `fsm`
  на уровне модуля; проверено импортом каждого модуля первым.
- Ни тестов, ни гейтов, ни лимитов не ослабляю; существующие тесты не
  правились. Откат — revert merge-коммита; колонка `closed_as` в БД
  останется пустой лишней колонкой и ничего не ломает.

## Риски
- `fsm.STATES` объявлены до импортов: перенос их ниже импортов вернёт
  круговой `AttributeError` при импорте `cleanup`/`watch` первыми —
  комментарий в `fsm.py` это объясняет.
- Элемент «части N» разбирается строго (`части` + число); «часть N» —
  отказ «не той формы», как требует п. 4 SPEC.

## Предложения системе
- Импорт `orchestrator.fixation` (а с ним `checkpoint`, `pause`) первым в
  свежем интерпретаторе падает на main: цикл fixation → workspace → lease
  → artifact_branch читает `fixation.FIXATION_AUTHOR_NAME` на уровне
  модуля. Работает только потому, что обычно первым грузится другой
  модуль; стоит сторожа «каждый модуль импортируется первым».
- Bash-инструмент роли требует подтверждения на `$?`, `for … $x` и
  `cd …;` — проверочные сценарии приходится писать python-heredoc'ом.
