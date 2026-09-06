---
task: 01M1RFVWV6WWTXRC5F40K61632
type: review
author_role: reviewer
status: approved
iteration: 3
schema_version: 4
---

# REVIEW: Наблюдатель роста карты кодовой базы (часть а): история, самокалибрующийся порог, атрибуция

## Контекст итерации 3 (диагностика перед вердиктом)

Ревью-пакет для этой итерации не показал ни SPEC.md, ни PLAN.md этой
задачи («не показан: в ветке — fatal: path ... does not exist в
ветке; в дереве — файл не найден»), а инкрементальный diff (от
69fad830 до HEAD) состоял целиком из «подтяжки main» (коммит
3f55b862) — содержимого пяти ЧУЖИХ, уже смерженных в main задач
(01M1RA0R9AH9RBAHD4A2Z5SEWQ, 01M1RQ12JVHE3PQYDFV1XPSTQ3,
01M1SAA2AZX3ERQ779QJ5TS9J4, 01M1SD5NZ79MWCEJDJ9JP6EPWS,
01M1SD5RHTJ0H0SR0615SVCJM5), ни строкой не относящегося к предмету
этой задачи. Тот же класс ложного сигнала, что уже фиксировался в
памяти прошлых ревью (01M1SC3Y20YBTTJVQDJBF2NDQW, 01M1SD5RHTJ0H0SR0615SVCJM5
итерация 2, 01M1RQ12JVHE3PQYDFV1XPSTQ3 итерация 2) и в `docs/backlog.md`
(строка про трёхточечный дифф, задача 01M1SG9T96).

Восстановил фактический материал ревью вручную:
- `git merge-base --is-ancestor main HEAD` — main является предком HEAD.
- SPEC.md/PLAN.md/REVIEW.md прочитаны из `artifact/01m1rfvwv6wwtxrc5f40k61632`
  (`git show <ветка>:tasks/01M1RFVWV6WWTXRC5F40K61632/{SPEC,PLAN,REVIEW}.md`).
- `git diff main...HEAD -- <зона SPEC>` — реальный вклад ветки в зону
  задачи: `orchestrator/config.py` (3 новые константы, требование 3),
  `orchestrator/doctor.py`, `orchestrator/fsm_postmerge.py`,
  `scripts/codebase_map.py`, `docs/codebase-map.md`,
  `tests/test_codebase_map.py`, `tests/test_doctor.py`,
  `tests/test_fsm_map_regen.py` — 524 вставки/3 удаления, ровно зона
  SPEC (`orchestrator/doctor.py` крупнее прочих из-за содержательного
  фикса ниже, не разрастания зоны).

**Почему нужна третья итерация.** REVIEW.md итерации 2 (`status:
approved`) закоммичен в артефактную ветку 2026-09-06 01:29:35 (коммит
`0fd9913a`). После этого код ветки получил ещё один содержательный
коммит — `69fad830` (2026-09-06 08:08:29, ПОСЛЕ approve итерации 2):
«убран прямой SQL из doctor.py — только store.py». Причина по
PLAN.md (раздел «Риски», абзац «снят после возврата из verifying,
CI: tests/test_multitarget SqlOnlyInStoreTest»): задача после
одобренного ревью дошла до `verifying`, где полный набор `tests/`
поймал нарушение инварианта «SQL только в store.py» (ADR-0003 3ж) —
`check_map_growth`/`_map_growth_reference_point`/`_map_growth_series`
читали `alerts`/`steps` прямым SQL внутри `orchestrator/doctor.py`,
хотя `store.py` вне зон этой задачи. Задача вернулась в `in_dev`,
разработчик переписал три места на композицию уже существующих
функций `store` (`all_tasks`, `task_steps`, `alerts_older_than`) с
фильтрацией в Python, задокументировал фикс в PLAN.md — код продвинулся
дальше одобренного, поэтому гейт `review -> verifying` справедливо
потребовал новый прогон ревьювера (история отказов advance,
дословно: «вердикт REVIEW.md (status=approved, iteration=2) уже
учтён — жду новый прогон ревьювера с iteration: 3»). Ревью ниже
целиком сосредоточено на этом единственном реальном приросте —
остальное содержимое SPEC/PLAN/кода, одобренное итерацией 2, повторно
не пересматривается по существу (кроме сверки, что оно не изменилось).

Сверено `git diff dfa62d0e HEAD` (dfa62d0e — коммит, закрывший
замечания итерации 1, код на момент approve итерации 2) по всей зоне
SPEC: единственные файлы с отличием — `orchestrator/doctor.py` (сам
фикс SQL, коммит `69fad830`) и `orchestrator/config.py` (две строки —
`PROGRAM_STOP_LOSS_USD` 2000→3000 и `MAX_PARALLEL_TASKS` 10→20,
подтверждено построчно как решения Оператора 06.09, попавшие через
подтяжку main, а не работа этой задачи — уже отмечалось итерацией 2
для более ранних значений тех же констант). `tests/test_doctor.py`
получил два не относящихся к задаче изменения тем же путём подтяжки
main (маркер PLAN.md для `PreflightBlocksMissingTokenTest` — задача
01M1RQ12JVHE3PQYDFV1XPSTQ3; класс `RoleHomeReferenceSettingsAutoMemoryTest`
— задача 01M1SG9YKBFG2G5YQDVBR6BVC8) — оба вне предмета этой задачи,
отсюда прирост числа тестов файла со 153 до 154. `scripts/codebase_map.py`,
`orchestrator/fsm_postmerge.py`, `tests/test_codebase_map.py`,
`tests/test_fsm_map_regen.py` — не изменились ни байтом с момента
approve итерации 2.

## Фаза A: проверка плана

PLAN.md обновлён единственным новым абзацем в разделе «Риски»,
описывающим фикс SQL после возврата из `verifying` (см. «Контекст»
выше) — описание соответствует фактическому диффу построчно. Остальное
содержимое плана не менялось с итерации 1/2 (подход, шаги, покрытие
требований, влияние на систему — без изменений). Замечаний к плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (`map_stats`, AC-1..AC-4) | OK | Без изменений с итерации 2. |
| 2 (запись журнала на мерже, AC-5..AC-7) | OK | Без изменений с итерации 2. |
| 3 (`check_map_growth`, AC-8..AC-16, константы AC-18) | OK | Наблюдаемое поведение не изменилось (сверено прогоном планки AC-8..AC-16 и юнитов `MapGrowthCheckTest`/`CrossTargetIndependenceTest` — все зелёные), изменилась только реализация: `_map_growth_reference_point`/`_map_growth_series`/`check_map_growth` (`orchestrator/doctor.py`) больше не читают `alerts`/`steps` прямым SQL — заменены на `_all_map_size_steps` (композиция `store.all_tasks`+`store.task_steps`, фильтрация в Python по `action`/`target`/`ts`) и `store.alerts_older_than` с sentinel-датой `9999-12-31 23:59:59Z` (лексикографически позже любого реального `ts` в формате `store.now()`, что даёт «взять все алерты» без новой SQL). `grep -nE 'conn.execute|conn.cursor'` по `orchestrator/doctor.py` — пусто, `tests/test_multitarget.py::SqlOnlyInStoreTest` зелёный (было бы красным на коде ДО фикса — проверил на `dfa62d0e`, 4 совпадения `SELECT` в `doctor.py`). `store.all_tasks(conn)` — `SELECT * FROM tasks` без фильтра по состоянию, `DELETE FROM tasks`/`DELETE FROM steps` в кодовой базе не встречается (grep) — строки `tasks`/`steps` не удаляются, поэтому переход на итерацию по `store.all_tasks` не теряет данные закрытых (`done`/`killed`) задач, которых в проде подавляющее большинство среди источников записи «карта: размер». Кросс-таргетная изоляция (AC-16) подтверждена прогоном `CrossTargetIndependenceTest` (два реальных `store.insert_task` с разными `target`) на исправленном коде. |
| 4 (внешний target) | OK | Без изменений с итерации 2. |
| 5 (тесты, AC-17/AC-18) | OK | Планка `tests/test_fsm_map_regen.py`/`test_doctor.py`/`test_codebase_map.py` зелёная без правки существующих ассертов (сверено диффом `dfa62d0e..HEAD` — единственные добавленные строки в `tests/` из этого диапазона относятся к ДРУГИМ задачам, пришедшим подтяжкой main, не к этой правке; сама SQL-правка не добавила и не тронула ни одного теста, что не ослабляет требование 5 — существующая планка уже покрывала наблюдаемое поведение `check_map_growth`, включая кросс-таргетный случай, до и после смены реализации). |

## Замечания

Нет.

## Реестр замечаний

Записи `R1-F1`/`R1-F2`/`R1-F3` (итерация 1) уже в статусе `accepted`
(закрыты итерацией 2) — не повторяю по правилу кумулятивности (уже
`accepted` восстановимы из git-истории файла). Новых записей эта
итерация не заводит.

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт

approved

## Проверено исполнением

- `git merge-base --is-ancestor main HEAD` — main является предком HEAD (69fad830/3f55b862 действительно продолжают ветку задачи, не расходятся с main).
- `git diff main...HEAD --stat` — 8 файлов, ровно зона SPEC (`orchestrator/config.py, orchestrator/doctor.py, orchestrator/fsm_postmerge.py, scripts/codebase_map.py, docs/codebase-map.md, tests/test_codebase_map.py, tests/test_doctor.py, tests/test_fsm_map_regen.py`), 524 вставки/3 удаления.
- `git diff dfa62d0e HEAD -- <зона SPEC>` — построчно сверен: единственный содержательный прирост со времени approve итерации 2 — `orchestrator/doctor.py` (фикс SQL, коммит `69fad830`); `orchestrator/config.py` (2 строки — решения Оператора на main, не работа задачи, тот же класс уже отмечен итерацией 2); `tests/test_doctor.py` (2 несвязанных изменения из подтянутых задач 01M1RQ12JVHE3PQYDFV1XPSTQ3/01M1SG9YKBFG2G5YQDVBR6BVC8); `scripts/codebase_map.py`/`orchestrator/fsm_postmerge.py`/`tests/test_codebase_map.py`/`tests/test_fsm_map_regen.py` — без изменений.
- `git show dfa62d0e:orchestrator/doctor.py | grep -nE '\bSELECT\b'` — 4 совпадения (подтверждён факт нарушения ДО фикса); `grep -nE 'conn.execute|conn.cursor' orchestrator/doctor.py` на HEAD — пусто (подтверждён факт устранения).
- `python3 -m pytest tests/test_codebase_map.py tests/test_doctor.py tests/test_fsm_map_regen.py -q` — 154 passed, 3 subtests passed.
- `python3 -m pytest tests/test_multitarget.py::SqlOnlyInStoreTest -q` — 1 passed (красный на коде `dfa62d0e`, зелёный на HEAD — проверено раздельно).
- `python3 -m pytest tasks/01M1RFVWV6WWTXRC5F40K61632/acceptance_tests/ -q` — 32 passed (полная планка задачи, включая `CrossTargetIndependenceTest`, AC-16).
- `python3 -m pytest tests/test_multitarget_invariants.py -q` — 12 passed (инвариант 22, независимость данных per-target на уровне БД в целом).
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md` — расхождение только в строке `built_at_sha` (не дефект, review-checklist.md); откачено `git checkout -- docs/codebase-map.md`, `git status --short` — чисто (кроме материализованного `tasks/01M1RFVWV6WWTXRC5F40K61632/`).
- Полный набор `tests/` не гонял (решение Оператора 05.09 — гоняет CI на каждый пуш) — прогнаны планка задачи и все файлы, реально пересекающиеся с диффом со времени предыдущего вердикта.

## Предложения системе

- Ревью-пакет этой итерации не показал SPEC.md/PLAN.md задачи вовсе и
  построил инкрементальный diff, целиком состоящий из содержимого пяти
  чужих задач, пришедших подтяжкой main, — предыдущий вердикт (sha
  `69fad830`) технически был последним commit'ом ЭТОЙ задачи перед
  merge-коммитом подтяжки, но генератор пакета не проверил, что diff от
  этой точки идёт ЧЕРЕЗ merge и приносит целиком чужую историю. Тот же
  класс уже фиксировали независимо минимум три предыдущих ревью (см.
  «Контекст» выше) — стоит явно включить в фикс задачи о трёхточечном
  диффе (01M1SG9T96, в работе) сценарий «predecessor sha — предпоследний
  коммит перед merge подтяжки main», а не только «sha совпал с текущим
  HEAD»/«sha указывает на автокоммит роли», которые уже описаны в
  skills/review-checklist.md.
