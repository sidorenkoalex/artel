---
task: 01M5TB6VDVV6AM8DWPGVQE8CDW
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Эпики Э0: деление доводится до конца — признак поделённого родителя, порядок и рамка частей, один список состояний

# Эпики, шаг Э0: деление задачи доводится до конца — признак поделённого родителя, порядок и рамка частей, один список состояний

## Факты

ADR-0028 (принят 25.10.2026), уровень 0, п. 1–3 и п. 17; порядок исполнения — шаг Э0 перед Э1.

1. Деление на гейте SPEC: `orchestrator/fsm.py:958` `_spawn_division_subtasks` заводит части `catalog.spawn_subtask` (`orchestrator/catalog.py:735`) и переводит родителя в `killed` с записью «поделена на: <ids>» (`fsm.py:979`); зависящие от родителя задачи переходят на последнюю часть (`merge_after.replace_divided`, `orchestrator/merge_after.py:299`). Признака «поделена», отличного от «ликвидирована», в БД нет — только текст журнала.
2. Поля части `Зоны:`/`Порядок:`/`Рамка:` разбираются построчно (`scripts/guard.py:5984` `_DIVISION_FIELD_LINE`, `:6023` — `budget` из «Рамка»). «Порядок: после части N» не разрешается в идентификатор части: разбор строки ТЗ `merge_after._ORDER_LINE_RE` (`orchestrator/merge_after.py:65`) ждёт идентификаторы задач. Рамка части не становится потолком части: SPEC части перезаписывает потолок (`orchestrator/budget.py:145-190`, `budget_source`).
3. Окончательные состояния и порядок показа перечислены в нескольких местах по-разному: `orchestrator/report.py:46` `STATE_ORDER`, `orchestrator/cleanup.py:543` `TERMINAL_STATES`, `orchestrator/watch.py:41` `_TERMINAL_STATES`, перечисления `("done", "killed")` в `zone_lock.py`, `prune.py`, `doctor/branch_freshness.py`, `doctor/ignored_artifacts.py`, `doctor/orphans.py`, `doctor/artifact_branches.py` и др.; `tests/test_invariants.py` `FSM_STATES` (защищённый путь) — 11 состояний без `verifying`.

## Требуется

1. **Признак поделённого родителя.** Колонка `tasks.closed_as` (текст, пусто по умолчанию; миграция схемы `orchestrator/schema.py`). `_spawn_division_subtasks` тем же переходом в `killed` пишет `closed_as='divided'`. Миграция заполняет `closed_as='divided'` у существующих строк `killed`, в журнале которых есть запись «поделена на: …», и пишет запись журнала на каждую заполненную строку. Состояние FSM родителя остаётся `killed`; новых состояний нет. `status` показывает у поделённого родителя «поделена: части слиты N/M» (вычисляемая отметка по состояниям частей).
2. **«Порядок: после части N».** После заведения ВСЕХ частей поле «Порядок:» каждой части разбирается: «после части N» → идентификатор N-й части этого деления; «после <id задачи>» — как есть; каждая запись проходит `merge_after.check` (существование, проект, цикл). Номер вне 1..M или ссылка на саму себя — отказ `approve` деления до заведения частей (части не заводятся). `replace_divided` сохраняется. Если части не выстроены цепочкой (есть часть без «Порядок:» кроме первой), `approve` деления печатает предупреждение.
3. **«Рамка: $N» — потолок части.** guard проверяет значение рамки части тем же разбором чисел, что `budget` (`orchestrator/spend.py:22` `cli_number`), и не выше `config.ROLE_BUDGET_CAP`; ошибка — отказ гейта SPEC родителя. Рамка, утверждённая на гейте SPEC родителя, записывается потолком части с источником `operator` (`budget_source`): SPEC части её не перезаписывает; поднять — командой `budget`.
4. **Один список состояний.** В `orchestrator/fsm.py` — константы `STATES` (порядок показа, включая `verifying`) и `TERMINAL_STATES`; `report.STATE_ORDER`, `cleanup.TERMINAL_STATES`, `watch._TERMINAL_STATES` и перечисления окончательных состояний в модулях пакета пульта заменяются ими (значения не меняются). Новый долгоживущий тест-сторож: в модулях пакета пульта нет литеральных перечислений окончательных состояний вне `fsm.py` (по образцу сторожей `tests/test_invariants.py`, отдельным файлом задачи).

Критерии приёмки:
- деление на гейте SPEC: у родителя `state='killed'`, `closed_as='divided'`; у ликвидированной командой `kill` задачи `closed_as` пусто;
- миграция на копии БД с двумя `killed` (одна с записью «поделена на: …», одна без): `closed_as='divided'` только у первой, по записи журнала на заполненную строку; повторный запуск миграции ничего не меняет;
- части «1» без порядка, «2: после части 1», «3: после части 2» → `merge_after` части 2 = id части 1, части 3 = id части 2; «после части 4» при трёх частях — отказ, частей нет; цикл — отказ;
- «Рамка: $30» части → потолок части $30 с `budget_source=operator`; SPEC части с `budget_usd: 50` потолок не меняет; «Рамка: $150» или «Рамка: тридцать» — отказ гейта SPEC родителя;
- `fsm.STATES` содержит `verifying`; `report`, `cleanup`, `watch` берут состояния из `fsm`; сторож красный при литерале `("done", "killed")` в модуле пакета пульта вне `fsm.py`;
- `status` у поделённого родителя показывает «части слиты N/M».

Зоны: `orchestrator/fsm.py`, `orchestrator/schema.py`, `orchestrator/store.py`, `orchestrator/catalog.py`, `orchestrator/merge_after.py`, `orchestrator/budget.py`, `orchestrator/report.py`, `orchestrator/cleanup.py`, `orchestrator/watch.py`, `orchestrator/zone_lock.py`, `orchestrator/prune.py`, `orchestrator/doctor/` (только замена перечислений состояний), `scripts/guard.py`, `tests/` (долгоживущие файлы задачи). Аналитик сверяет по коду все места перечисления окончательных состояний и вносит их файлы в зоны SPEC поимённо.

Только чтение: `orchestrator/spend.py`, `orchestrator/config.py`, `docs/invariants.md`, `tests/test_invariants.py`, `docs/adr/0028-epics-and-board-projection.md`.

Существующие тесты: правка любого существующего теста — эскалация до SPEC с перечнем и предлагаемой правкой; мандат — только Оператор.

Не входит: сущность эпика и команды `epic …` (шаг Э1); `FSM_STATES` в `tests/test_invariants.py` и строка инварианта 10 в `docs/invariants.md` — операторским коммитом после мержа этой задачи; новые состояния FSM.

Рамка: $45. Набор моделей — по умолчанию.
