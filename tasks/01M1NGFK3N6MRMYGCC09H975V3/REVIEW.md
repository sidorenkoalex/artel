---
task: 01M1NGFK3N6MRMYGCC09H975V3
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 4
---

# REVIEW: Канарейка v2 (часть 2): привязка пина к зелёной канарейке, триггер doctor, откат пина

## Замечание к самому ревью-пакету

Инкрементальный diff пакета (база `9c55cd47` → HEAD `9e1eac9e`) НЕ отражает
фактические изменения этой итерации: `9c55cd47` — это сам коммит-фикс
разработчика («правки по REVIEW итерации 1, R1-F1..R1-F4»), а не sha, на
котором рендерился вердикт итерации 1 (тот стоял на `77378ee2`, ДО фикса).
Взятый пакетом диапазон показывает только последующую подтяжку main
(нёсшую целиком не относящуюся к этой задаче работу — мерж
01M1REVP9WGRHDDNVEVE8BBH0Z, критерий сироты `doctor --fix`) и не
показывает вообще ничего из `orchestrator/pin.py`/`orchestrator/doctor.py`/
`tests/test_pin.py`/`tests/test_canary.py`/`tests/test_gitcmd_branch_reads.py`
— то есть ни одной из строк, которые как раз и являются предметом этой
итерации ревью (реакция на R1-F1..R1-F4). Также не была включена ни
прошлая REVIEW.md (итерации 1), ни PLAN.md (путь на диске поиска был взят
от корня основного репозитория, а не от этого worktree — тот же класс, что
и уже известный «пути в брифе абсолютные от корня пульта»).

Восстановил фактический diff вручную: `git log --oneline` показал
`77378ee2` (исходная реализация разработчика) → `9c55cd47` (фикс R1-F1..
R1-F4) → далее только подтяжки main; прочитал `git show 9c55cd47 --
orchestrator/pin.py orchestrator/doctor.py tests/test_pin.py
tests/test_canary.py tests/test_doctor.py tests/test_gitcmd_branch_reads.py`
целиком, прошлую REVIEW.md — из артефактной ветки (`git show 63a2761a:
tasks/01M1NGFK3N6MRMYGCC09H975V3/REVIEW.md`), PLAN.md — прямым чтением с
диска этого worktree (файл там материализован и совпадает с текущей
головой артефактной ветки). Ниже — вердикт по фактическому содержимому,
не по пакету.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (`pin-update` отказывает без свежего зелёного прогона) | OK | R1-F1 закрыт: гейт (`orchestrator/pin.py:37-57`) теперь стоит ПОСЛЕ `git fetch`, но ДО `git merge --ff-only` — `merges_since_last_green_run` резолвит уже притянутый объект `sha`. Новый регрессионный тест `tests/test_pin.py::PinUpdateGateAfterFetchTest::test_pin_update_succeeds_on_a_sha_not_yet_fetched_locally` воспроизводит ровно сценарий итерации 1 (bare origin + второй клон, sha ещё не локален) и проходит. |
| 2 (`doctor` — триггер `kind=trigger` по тому же порогу) | OK | R1-F2 закрыт: `orchestrator/doctor.py:1402-1420` — текст, идущий в `alerts.raise_alert` (`alert_message`, дедуп-ключ), зафиксирован без переменного числа мержей; конкретный возраст остался только в `Check.detail`/`print`, в дедуп не участвует. Новый тест `tests/test_doctor.py::CanaryTriggerCheckTest::test_growing_age_between_calls_still_dedupes_the_alert` воспроизводит рост `age` между двумя прогонами `check_canary_trigger` и подтверждает ровно 1 открытый алерт. |
| 3 (`pin --to <sha>`/`pin --to` — откат, main не трогается) | OK | Без изменений с итерации 1 (уже была `OK`) — `orchestrator/pin.py:74-108`, `git reset --hard` без fetch/push. |
| 4 (каждый откат — отдельная запись журнала) | OK | Без изменений с итерации 1 (уже была `OK`) — `_refuse_rollback`/успешная ветка `cmd_pin_to` журналируют ровно один раз на вызов. |

## Замечания

Новых замечаний в этой итерации не заведено — см. «Реестр замечаний»
ниже: все четыре записи итерации 1 проверены и закрыты.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/pin.py:37-57 | Гейт `cmd_pin_update` резолвил `sha` до `git fetch`, а `sha` обычно ещё не в локальной базе | `pin-update` отказывал практически при любом реальном вызове (AC-2 не работал вне приёмочной песочницы) | Проверено: гейт переставлен между `fetch` (строки 41-44) и `merge --ff-only` (строка 54); `fetch` не двигает HEAD, отказ по-прежнему не трогает пин (`ANSWER-1` п.4 соблюдён). Прочитан код целиком, прогнан `tests/test_pin.py::PinUpdateGateAfterFetchTest::test_pin_update_succeeds_on_a_sha_not_yet_fetched_locally` — зелёный, эмпирически подтверждает исчезновение дефекта на том же сценарии, что воспроизвёл ревьювер итерации 1 (bare origin + отдельный клон с непритянутым коммитом). Закрываю `accepted`. |
| R1-F2 | accepted | orchestrator/doctor.py:1386-1420 | Дедуп-сообщение алерта триггера несло меняющееся число мержей | Каждый новый мерж main после срабатывания порога заводил новый алерт вместо одного открытого | Проверено: `alert_message` (идёт в `alerts.raise_alert`, участвует в дедупе через `store.open_alert_exists`) зафиксирован текстом без `age`; `age` остаётся только в `detail` (`Check.detail`, в алерт не идёт) — прочитан код (строки 1402-1420) построчно. Прогнан `tests/test_doctor.py::CanaryTriggerCheckTest::test_growing_age_between_calls_still_dedupes_the_alert` (мерж между двумя вызовами `check_canary_trigger`) — зелёный, 1 открытый алерт вместо 2. Закрываю `accepted`. |
| R1-F3 | accepted | tests/test_pin.py, tests/test_canary.py, tests/test_doctor.py, tests/test_gitcmd_branch_reads.py | 23 новых/изменённых тестовых метода без докстринга «Ловит мутацию: …» | Ревьювер не мог сверить тест с заявленной чувствительностью | Проверено: перечитаны все классы, названные в итерации 1 (`PinUpdateGateOrderTest`, `PinToResetFailureTest`, `GreenCanaryRunsTest`, `DriveTaskEscalationCapTest`, `DriveTaskStallCapTest`, `MergesSinceLastGreenRunTest`, `DriveTaskReachedGateMarkerTest`, `CanaryTriggerCheckTest`, `IsAncestorTest`, `MergesBetweenTest`) — у каждого метода теперь есть докстринг с конкретной, правдоподобной мутацией реализации (не пересказ имени метода), плюс два новых регрессионных теста (R1-F1/R1-F2) тоже с заявкой. Единственное расхождение с итерацией 1 — `GreenCanaryRunsTest` фактически несёт 3 метода, не 4 (видимо, ошибка счёта в прошлой итерации) — не влияет на вывод: все 3 существующих докстринг несут. Закрываю `accepted`. |
| R1-F4 | accepted | orchestrator/pin.py:19 | Опечатка `ANСВЕР-1` (кириллица) вместо `ANSWER-1` | Косметика, затрудняет grep | Проверено чтением файла — на месте `ANSWER-1` (латиница), `grep -rn "ANСВЕР" orchestrator/` не находит совпадений. Закрываю `accepted`. |

## Вердикт

approved — все четыре замечания итерации 1 (R1-F1 blocker, R1-F2/R1-F3
major, R1-F4 minor) исправлены по существу и закрыты `accepted` выше,
новых blocker/major в этой итерации не найдено. Фаза A (PLAN) повторно не
пересматривалась содержательно — подход и разбивка на шаги не менялись с
итерации 1, где вопросов не было.

## Проверено исполнением

- Реконструкция фактического diff вручную (пакет дал нерепрезентативный
  диапазон, см. выше): `git log --oneline` по коду-ветке;
  `git show 9c55cd47 -- orchestrator/pin.py orchestrator/doctor.py
  tests/test_pin.py tests/test_canary.py tests/test_doctor.py
  tests/test_gitcmd_branch_reads.py` — полный текст фикс-коммита прочитан
  целиком; `git show 77378ee2 --stat` и построчно
  `-- orchestrator/canary.py orchestrator/store.py orchestrator/gitcmd.py
  orchestrator/artel.py orchestrator/config.py` — независимая проверка
  исходной реализации (не только диффа фикса).
- `git show 63a2761a:tasks/01M1NGFK3N6MRMYGCC09H975V3/REVIEW.md` — прошлый
  вердикт (итерация 1, `changes_requested`, R1-F1..R1-F4) прочитан из
  артефактной ветки, т.к. пакет его не включил.
- `python3 -m pytest tests/test_pin.py tests/test_canary.py
  tests/test_doctor.py tests/test_gitcmd_branch_reads.py -q` — 205 тестов
  пройдено, 3 subtests пройдено, 0 отказов (затронутые модули).
- `cd tasks/01M1NGFK3N6MRMYGCC09H975V3/acceptance_tests && python3 -m
  pytest test_ac1_ac2_pin_update_canary_gate.py
  test_ac3_ac4_doctor_canary_trigger.py test_ac5_ac6_ac7_pin_to_rollback.py
  test_scope_markers.py -q` — 15 тестов, все зелёные (AC-1..AC-7, AC-8 —
  легальный skip, ci-covered, из итерации 1 без изменений).
- `python3 scripts/codebase_map.py` (из корня worktree) +
  `git diff --stat -- docs/codebase-map.md` — пусто, карта уже актуальна
  (включая `built_at_sha`, регенерация не изменила файл вовсе).
- `python3 scripts/guard.py tasks/01M1NGFK3N6MRMYGCC09H975V3/SPEC.md
  tasks/01M1NGFK3N6MRMYGCC09H975V3/PLAN.md
  tasks/01M1NGFK3N6MRMYGCC09H975V3/ANSWER-1.md` — «GUARD: ок (3 файлов)».
- `git diff --name-only main...HEAD -- .github gates.yaml roles.yaml
  templates skills` — пусто, защищённые пути не затронуты; `git show
  --stat 77378ee2 9c55cd47` — оба task-специфичных коммита ограничены
  `orchestrator/*`/`tests/*`, зона задачи не нарушена.
- Полный набор `tests/` не гонялся (решение Оператора 05.09,
  review-checklist) — CI гоняет его на каждый пуш ветки.

## Предложения системе

- Четвёртый подтверждённый случай класса «якорный sha пакета не отражает
  фактический коммит вердикта» (ранее T082, T087, и в этом же прогоне —
  соседняя задача 01M1REVP9WGRHDDNVEVE8BBH0Z независимо описала третий
  случай в своей REVIEW.md). Здесь конкретный механизм новый и хуже
  «пустого диффа»: взятый пакетом sha (`9c55cd47`) — это сам коммит-ФИКС
  разработчика по итогам итерации 1, а не sha, на котором стоял код в
  МОМЕНТ вынесения прошлого вердикта (`77378ee2`) — в результате
  инкрементальный diff НЕ ПУСТ (что насторожило бы), а полон правдоподобно
  выглядящего, но полностью постороннего содержимого (мерж чужой задачи из
  main) — ложноположительная иллюзия «есть что ревьюить», хотя предмет
  этой итерации (сам фикс R1-F1..R1-F4) в diff вообще не попал.
  Стоит однозначно зафиксировать: анкор = sha, на котором артефактная
  ветка стояла при вынесении ПРОШЛОГО вердикта reviewer'а (коммит
  автокоммита REVIEW.md той итерации в артефактной ветке), а не
  «последний известный коммит кода до какой-либо последующей подтяжки».
- Путь материализации PLAN.md в брифе снова оказался абсолютным от корня
  ОСНОВНОГО репозитория (`/Users/…/artel/tasks/…`), а не от этого
  worktree — тот же класс, что уже дважды заведён в бэклоге («Бриф роли
  называет артефакты абсолютным путём корня пульта», ТЗ готово). Здесь
  сломалась не запись (Write), а именно СБОРКА пакета: PLAN.md по этому
  неверному пути не нашёлся вовсе и не попал в пакет молча, хотя на диске
  этого worktree файл был на месте.
- `docs/codebase-map.md`/git-статус этой задачи несёт стороннюю деталь: в
  индексе кодовой ветки на HEAD трекнут файл
  `tasks/01M1NGFK3N6MRMYGCC09H975V3/acceptance_tests/test_pin_canary_binding.py`
  (закоммичен на раннем шаге test_author, `19654d59`, до текущей планки),
  которого уже нет на диске (заменён текущими `test_ac1_ac2_…`/`test_ac3_
  ac4_…`/`test_ac5_ac6_ac7_…`) — `git status` числит его «deleted». Файл
  вне зоны текущей проверки (не тронут ни одним коммитом разработчика) и
  не блокирует эту задачу, но подтверждает, что артефакты `tasks/<id>/`
  иногда всё же попадают в индекс кодовой ветки вопреки конвенции
  «не коммитить» — стоит на досуге понять источник (вероятно, ранний
  test_author-коммит до того, как конвенция закрепилась/стала соблюдаться
  штатной автоматикой шага).
