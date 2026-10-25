---
task: 01M5TB6VDVV6AM8DWPGVQE8CDW
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Эпики Э0 — деление доводится до конца: признак поделённого родителя, порядок и рамка частей, один список состояний

## Фаза A: план
- Таблица покрытия PLAN полна: требования 1–12 привязаны к шагам 1–5.
  Требование 12 (сторож) отдано долгоживущему файлу test_author, и это
  верно: `tests/test_01m5tb6vdvv6am8dwpgvqe8cdw_terminal_literal_guard.py`.
- Шаги по размеру — единицы MR: константы, `closed_as`, рамка в guard,
  порядок и рамка на approve, тесты и карта.
- Подход с конвенциями не конфликтует. Проверки деления стоят последним
  мягким отказом в `_approve_spec_gate` (`orchestrator/fsm.py:1347-1354`),
  то есть до первой записи (журнал «Меняемое поведение», `fsm.py:1355`).
  `catalog.spawn_subtask` не тронут. Цикл импортов развязан тем, что
  константы объявлены до импортов в `fsm.py`, а в `models`/`zone_lock`/
  `prune` импорт отложен. Это описано в «Рисках».
- Раздел «Влияние на систему» сходится с diff: 18 файлов, все в `zones`
  SPEC, плюс новый `tests/test_division_order_units.py` и карта.
  Защищённых путей и существующих тестов diff не трогает. Путь отката
  описан.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Колонка в `SCHEMA` и `migrate` (`schema.py:123`, `:326-328`). Деление пишет `closed_as='divided'` (`fsm.py` `_spawn_division_subtasks`), `kill` колонку не трогает (AC-1 зелёный). Запись идёт отдельным `update_task` сразу после `set_state`, а не одним UPDATE; на поведение это не влияет. |
| 2 | OK | `_mark_past_divisions` выполняется только в том проходе, который заводит колонку; отбор — по `action='state -> killed'` и `detail LIKE 'поделена на:%'`, одна запись журнала на строку. Колонки `steps`, которые пишет `store.journal`, к этому моменту уже добавлены (`schema.py:232` стоит раньше `:326`). |
| 3 | OK | `catalog._division_suffix` строит отметку по `closed_as`; N — части в `done`, ids в порядке `rows`. Прежней добавки нет. |
| 4 | OK | `merge_after.division_order` / `_part_deps`. «части N» → индекс части, id разрешает `check` с явным `target`. `record_declared` — тот же канал, что у `new`; пустой перечень не пишется. Записи делаются после заведения всех частей. Преемник — `_successor`. |
| 5 | OK | Граница 1..M, ссылка на себя, повтор, форма — через `merge_after_form_errors` внутри `check`. Родитель (полный id или префикс) — «мёртвая зависимость». Цикл ищется на виртуальном графе, в котором ребро зависимой задачи на родителя заменено ребром на `#преемник`. |
| 6 | OK | Проверки стоят до первой записи, отказ пишет одну запись «approve отклонён». AC-10 (11 параметров, с `fail` аудита и SPEC родителя с `zones`/`merge_after`/`budget_usd`) зелёный. |
| 7 | OK | `order.loose` — части с номером > 1 и «Порядок:» без «после»; печатается «ВНИМАНИЕ…» с именами частей. |
| 8 | OK | `guard.division_frame`: `$` снимается, разбор через `spend.cli_number` (он отсекает nan/inf), условие `0 < v <= ROLE_BUDGET_CAP`. В ошибке названа часть. |
| 9 | OK | `_division_check` перепроверяет рамку той же `division_frame` на тексте, прочитанном approve. |
| 10 | OK | `budget.apply_division_frame`: источник `operator`, запись журнала части. `apply_spec_budget` потолок `operator` не перебивает (AC-12 зелёный). Часть без рамки остаётся с сегодняшним потолком (AC-18). |
| 11 | OK | `fsm.STATES` / `fsm.TERMINAL_STATES`. `report.STATE_ORDER`, `cleanup.TERMINAL_STATES`, `watch._TERMINAL_STATES` — те же объекты (проверено `is`). Литералы в `models`, `zone_lock`, `prune` и четырёх `doctor/*` заменены. |
| 12 | OK | Сторож-долгоживущий зелёный, литерал в модуле верхнего уровня и в `doctor/` находит. |

## Замечания
Блокеров и major нет. Две мелочи, обе без сценария поломки, поэтому
формальными замечаниями не заведены (см. «Предложения системе»):
- `tests/test_division_order_units.py::test_division_frame_accepts`: случаи
  `"$30"` и ровно `ROLE_BUDGET_CAP` повторяют свойство, которое уже держит
  долгоживущий `..._guard_frame.py::test_ac13_frame_at_cap_or_absent_is_not_error`
  (`$` снимается, граница включительная). Новые случаи — `"30,5"`, `None`
  и отказы `""`/`"$"`/`-5`/`$nan`. Повтор безвреден, но при следующей
  правке файла его стоит убрать.
- `orchestrator/fsm.py` `_spawn_division_subtasks`: `closed_as` пишется
  отдельным `update_task` после `store.set_state(... "killed")`. Если
  процесс оборвётся между этими двумя вызовами, родитель останется
  `killed` без признака, а миграция его не доразметит: она работает один
  раз, на заведении колонки. Окно — два соседних вызова в одном процессе.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт
approved. Все 12 требований реализованы, и как требует SPEC. Отказ
деления ничего не записывает, преемник выбирается по графу частей,
сторож одного списка зелёный и чувствителен к нарушению.

## Проверено исполнением
- `artel.py plank-run 01M5TB6VDVV6AM8DWPGVQE8CDW` — `test_ac15_state_constants.py`: 1 passed, код выхода 0.
- `python3 -m pytest -q -p no:cacheprovider`: четыре долгоживущих файла задачи, `tests/test_division_order_units.py`, `test_01m45d29bqje8fjyja4jqwsyfz_spec_gate_declared.py`, `test_merge_after_module.py`, `test_division_parent_cleanup.py`, `test_parent_task_division.py`, `test_guard_division_section.py`, `test_01m4mqagrwmwr0gfdm9086p3td_spec_audit_units.py` — 142 passed, 19 subtests passed.
- Импорт каждого изменённого модуля первым в свежем интерпретаторе (`cleanup`, `watch`, `report`, `models`, `zone_lock`, `prune`, `store`, `catalog`, `merge_after`, `schema`, `budget`, 4×`doctor/*`, `scripts.guard`, `fsm`) — все ok. `report.STATE_ORDER is fsm.STATES`, `cleanup.TERMINAL_STATES is fsm.TERMINAL_STATES`, `watch._TERMINAL_STATES is fsm.TERMINAL_STATES` — True ×3.
- Временные мутации `orchestrator/merge_after.py` (файл после каждой восстановлен, `git status` чист):
  - `_successor` всегда возвращает последнюю часть — AC-19 и юнит-тест красные (2 failed);
  - `max(tops)` → `min(tops)` — юнит-тест красный;
  - в виртуальном графе нет замены родителя преемником — AC-8 красный;
  - повтор «части N» не отсеивается — юнит-тест красный.

## Предложения системе
- Форма REVIEW: мелочь без сценария поломки нельзя записать в реестр, не
  заблокировав `approved` (гейт требует, чтобы все записи были `accepted`).
  Стоит завести статус «к сведению» или отдельную секцию «Наблюдения»,
  иначе minor-находки при аппруве живут только в свободном тексте.
