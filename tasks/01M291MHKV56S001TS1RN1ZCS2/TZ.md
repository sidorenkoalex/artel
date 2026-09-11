---
task: 01M291MHKV56S001TS1RN1ZCS2
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: состояние split для поделённого родителя вместо killed: единый список терминальных состояний, RETRO «поделена», связь родитель–подзадачи в БД и status

Источник: решение Оператора 11.09 (сессия при Операторе) после первого
живого деления задачи: 01M28VZ8Q1 «единая очередь мержа» утверждена на
spec_gate с секцией «## Деление» и переведена в `killed` с записью
«поделена на: 01M291EJMA…, 01M291EPQ2…». Задача деления —
01M1SHJZCE0Y4DXAAWQ2W585A7 (секция «## Деление», `fsm.
_spawn_division_subtasks`, `catalog.spawn_subtask`).

Факт: `_spawn_division_subtasks` (`orchestrator/fsm.py`) выбирает
`killed` как «единственное терминальное непродолжаемое состояние,
подходящее по смыслу». Смысл не совпадает: `killed` — задача снята
(отказ, ликвидация, ручной `kill`), а поделённый родитель — задача
ВЫПОЛНЯЕТСЯ подзадачами. Последствия сегодняшнего выбора:
- `status` показывает родителя строкой «killed … $40 потрачено» рядом с
  настоящими снятыми задачами; статистика ревью/бюджета считает деление
  провалом;
- `fsm_postmerge` подбирает `killed`-задачи как «долги» и генерирует
  killed-RETRO при следующем мерже (`retro.build_killed`); `snapshot`
  закрытия пишет исход `killed`;
- `canary` считает `killed` исходом с причиной снятия;
- `doctor` (orphans, artifact_branches, branch_freshness,
  ignored_artifacts), `watch._TERMINAL_STATES`,
  `cleanup.TERMINAL_STATES`, `auto` (список остановки), `report`
  (порядок состояний), `config.AUTO_STOP` — все знают ровно два
  терминальных состояния `done`/`killed` и трактуют родителя как снятого;
- связь родитель → подзадачи живёт только в тексте detail записи журнала
  «поделена на: …» и в строке-ссылке TZ подзадачи; обратной навигации
  из `status` нет.

Требуется:
1. Новое терминальное состояние FSM `split` («поделена»): в него переходит ТОЛЬКО родитель при approve SPEC с секцией «## Деление» (`_spawn_division_subtasks`), detail — «поделена на: <id, id…>» как сейчас; `set_state` принимает его наравне с `done`/`killed`; переходов ИЗ `split` нет; `kill`/`approve`/`advance`/`auto` на задаче в `split` — именованный отказ «задача поделена на …, работать с подзадачами».
2. Единый список терминальных состояний: одна константа `config.TERMINAL_STATES = ("done", "killed", "split")` (и, если нужно, `config.CLOSED_OUTCOMES`), на которую переходят все сегодняшние локальные копии — `cleanup.TERMINAL_STATES`, `watch._TERMINAL_STATES`, список остановки в `auto`, кортежи `("done", "killed")` в `orchestrator/doctor/` (orphans, artifact_branches, branch_freshness, ignored_artifacts), `report` (порядок состояний), `zone_lock` (диапазон занимающих состояний не меняется — `split` вне него), `config.AUTO_STOP` (подсказка «поделена — работай с подзадачами: <ids>»); тест-инвариант «нет локальных кортежей терминальных состояний вне config» (grep-проверка по `orchestrator/`, по образцу существующих инвариантных тестов).
3. Закрытие родителя: `split` — не «долг»: `fsm_postmerge` не генерирует для него killed-RETRO; снапшот закрытия (`snapshot`, T094 требования 12-14) пишет для `split` RETRO вида «поделена» (`retro.build_split`: суть родителя, список подзадач с названиями, стоимость аналитики до деления) — артефактная ветка родителя (SPEC с секцией «Деление», TZ) сохраняется в снапшоте, уборка веток/worktree — как для `done`/`killed` (`cleanup`), логи не трогаются (инвариант 16).
4. Навигация: `status` показывает родителя в `split` добавкой «[поделена: <id1>, <id2>]», а каждую подзадачу — добавкой «[часть N/M родителя <id>]»; связь хранится в БД (колонка `parent_task_id` в `tasks`, миграция в `orchestrator/schema.py`), а не только в тексте журнала; `spawn_subtask` заполняет её. `canary` учитывает `split` как исход «поделена» (не провал и не снятие) в отчёте прогона.
5. Документация в зонах: `docs/invariants.md` — строка о трёх терминальных состояниях и запрете переходов из `split`; ADR `docs/adr/` — короткая запись решения Оператора 11.09 «состояние поделённого родителя — split, не killed» (текст решения — из этого ТЗ, автор роли записывает, не решает).
6. Тесты: approve SPEC с «## Деление» переводит родителя в `split`, а не `killed` (мутация «killed» — красный); `kill`/`advance`/`auto` на `split` — отказ с текстом; `fsm_postmerge` не пишет killed-RETRO для `split`; снапшот `split` несёт RETRO «поделена» со списком подзадач; `status` показывает обе добавки; `doctor` не считает ветки/каталоги `split`-родителя сиротами иначе, чем у `done`; инвариант «терминальные состояния только из config» зелёный; существующие тесты деления (01M1SHJZCE), kill, cleanup, doctor, watch, canary — без ослабления (замена литерала `killed` на `split` в ассертах о поделённом родителе — не ослабление, а следствие требования 1).

Зоны: orchestrator/fsm.py, orchestrator/catalog.py, orchestrator/schema.py, orchestrator/store.py, orchestrator/cleanup.py, orchestrator/fsm_postmerge.py, orchestrator/snapshot.py, orchestrator/retro.py, orchestrator/report.py, orchestrator/watch.py, orchestrator/auto.py, orchestrator/canary.py, orchestrator/doctor/orphans.py, orchestrator/doctor/artifact_branches.py, orchestrator/doctor/branch_freshness.py, orchestrator/doctor/ignored_artifacts.py, docs/invariants.md, docs/adr/, tests/.

Условие старта: после мержа задач волны 1, держащих fsm.py и auto.py (01M290PYPV), watch.py (01M290PP4K), cleanup.py (01M28NX0M2), store.py (01M28NWPS3, 01M291EPQ2) — `auto --wait-zone`.

Не входит: изменение механики самого деления (формат секции, guard, `spawn_subtask` кроме `parent_task_id`); объединение подзадач обратно; переходы из `split`; изменение `done`/`killed`; `orchestrator/zone_lock.py` (диапазон занимающих состояний не меняется).

Рамка: $60.
