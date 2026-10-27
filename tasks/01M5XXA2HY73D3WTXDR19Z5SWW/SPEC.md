---
task: 01M5XXA2HY73D3WTXDR19Z5SWW
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/fsm.py, orchestrator/fsm_merge_gate.py, orchestrator/fsm_advance.py, orchestrator/targets.py, orchestrator/zone_lock.py, orchestrator/config.py, orchestrator/auto.py, orchestrator/board.py, orchestrator/report.py, orchestrator/watch.py, orchestrator/catalog.py, orchestrator/merge_after.py, orchestrator/cleanup.py, orchestrator/answer.py, orchestrator/store.py, orchestrator/schema.py, orchestrator/github_adapter.py, orchestrator/advance_gates/tests_writing.py, tests/
merge_after: 01M5WDB7JY0VJGHVKCABA2QC5T
budget_usd: 70
---

# SPEC: GitLab Б2.1 — гейт мержа `target-human`: MR вместо слияния, состояние `awaiting_human`

## Контекст
ADR-0029 (п. 1, 2, 7, 12) вводит доставку во внешний проект через MR,
который вливают люди проекта (`merge_gate: target-human`). Сегодня гейт
мержа (`fsm_merge_gate._cmd_approve_merge_gate`, `fsm_merge_gate.py:1442`)
умеет только сливать ветку сам и отправлять `base`; состояния «ждём людей
проекта» в `fsm.STATES` (`fsm.py:33-37`) нет; черновой MR заводится только
для GitHub через `gh` (`github_adapter.ensure_draft_mr`,
`github_adapter.py:118`). Поля `policy.mr_assignee`, `draft_mr`,
`max_in_flight` уже объявлены и проверяются (`targets.py:339-340`,
`:357-360`, `:648-657`), но нигде вне `targets.py` не читаются;
`forge.open_mr`/`undraft_mr`/`assign_mr`/`mr_status` реализованы для
GitLab (А1.1/А1.2). `target-human` до шага Б2.3 неподдержан
(`targets.SUPPORTED_MERGE_GATES = ("operator",)`): поддержка в тестах
включается подменой `targets.SUPPORTED_MERGE_GATES`/`SUPPORTED_FORGES`
внутри теста, значения в коде не меняются.

## Требования

1. **Поля записи** (`targets.py`, раздел `policy`, проверка при загрузке):
   `policy.max_awaiting` — целое > 0, по умолчанию 3;
   `policy.awaiting_holds_zones` — bool, по умолчанию `true`. Значение
   другого типа или `max_awaiting` ≤ 0 — отказ загрузки записи с
   именованной причиной. Предикат «мерж делают люди проекта» — функция
   `targets.py` (по образцу `push_whitelisted`, `targets.py:537-542`); вне
   `targets.py` значение `merge_gate` с литералами не сравнивается (сторож
   А0 AC-9).
2. **Состояние `awaiting_human`** — в `fsm.STATES` сразу после
   `merge_gate`; не окончательное (не в `fsm.TERMINAL_STATES`); без гейта
   Оператора. В модели доски `waiting_on` для него — новое значение
   `human`. Учитывается во всех местах перечня состояний (ADR-0029 п. 2):
   - `zone_lock.BLOCKING_STATES` (`zone_lock.py:110`, производные `:119`,
     `:126`): зоны задачи в `awaiting_human` заняты при
     `policy.awaiting_holds_zones: true` и свободны при `false`;
   - `config.AUTO_STOP` (`config.py:923`), `auto._NO_ALERT_FINAL_STATES`
     (`auto.py:70`): `auto` в `awaiting_human` останавливается без алерта;
   - `auto.EPIC_GATE_STATES` (`auto.py:1150`), `auto._NOT_HOLDING_STOP_STATES`
     (`auto.py:1168`): надзор эпика не держит место за задачей в
     `awaiting_human` и не считает её ждущей Оператора;
   - `board.OPERATOR_STATES`/`CI_STATES`/`waiting_on` (`board.py:20-44`),
     `report.STATE_ORDER` (`report.py:48`), `watch._GATE_STATES`
     (`watch.py:40`), метка `status` (`catalog.py:1353`): `report`, `watch`,
     `status` и доска показывают состояние `awaiting_human` и ссылку на MR
     задачи; `awaiting_human` не помечается «ЖДЁТ ОПЕРАТОРА»;
   - `merge_after.STATUS_WAIT_STATES` (`merge_after.py:55`), ожидание
     `done` (`merge_after.py:649`, `:769`): задача, зависящая по
     `merge_after` от задачи в `awaiting_human`, ждёт `done` зависимости;
   - `fsm.APPROVE_NEEDS_SHA` (`fsm.py:839`), `fsm.SET_MODELS_STATES`
     (`fsm.py:1959`), `config.STATE_ROLE` (`config.py:870`) — учитываются
     по смыслу состояния без роли и без гейта Оператора;
   - эскалация из `awaiting_human` (`escalated_from`, `fsm.py:1757`)
     возвращает задачу в `awaiting_human`;
   - рабочая копия задачи в `awaiting_human` хранится до `done`/`kill`
     (`fsm_merge_gate.py:1365-1378`, `cleanup.py:215`);
   - задача в `awaiting_human` не занимает место в `MAX_PARALLEL_TASKS`
     (лимит считает живые lease, `parallel_limit.py:24-36`).
3. **Ссылка на MR задачи** хранится в БД (`store.py`/`schema.py`) и
   пишется в журнал задачи при каждом открытии/снятии черновика MR.
4. **`approve` на `merge_gate` для записи с `target-human`** (ADR-0029
   п. 1). Исполняются без изменений: сверка sha (`fsm.py:1804`), ссылка
   документов, `no_paths`, неослабление по тексту и по исходам, лок
   планки, зелёный CI головы ветки, подтяжка при сдвиге base (тем же
   методом `freshness`; после неё — новый CI и гейт по исходам, возврат на
   гейт). Подтверждённый sha обязан совпасть с головой, которая уходит в
   MR, иначе отказ. Не исполняются: слияние в scratch, приложения PLAN,
   `checks_local` по дереву мержа, карта и `guard --all`, отправка base,
   ожидание CI base, справочник ядра, удаление ветки и рабочей копии.
   Задача с приложениями PLAN — отказ с причиной «приложения не
   применяются в проекте с target-human — правку вносят люди проекта».
   Затем пульт через `forge` открывает MR ветки задачи в `base` с
   исполнителем `policy.mr_assignee` (при `draft_mr: true` — снимает
   черновик с уже открытого MR и назначает исполнителя), пишет ссылку на
   MR в БД и журнал и переводит задачу в `awaiting_human`. Любой отказ
   `forge` — задача остаётся на `merge_gate` с именованной причиной; MR не
   открывается дважды (сверка открытых MR ветки).
5. **Предел `max_awaiting`**: если задач проекта в `awaiting_human` уже
   `policy.max_awaiting`, `approve` на `merge_gate` отказывает с причиной,
   задача остаётся на гейте; `status` показывает «очередь: предел
   awaiting_human».
6. **Черновой MR через `forge`** (ADR-0029 п. 7): для записи с
   `target-human` и `draft_mr: true` — черновой MR при первой отправке
   ветки (вход в `verifying`) через `forge.open_mr(draft=True)`, а не
   через `gh`; для `draft_mr: false` — MR один, открывается на гейте
   мержа; в описании MR — подсветка изменённых защищённых путей.
   Поведение GitHub-проектов с `operator` не меняется.
7. **`max_in_flight`** (ADR-0029 п. 12): задача проекта не отправляет
   ветку на входе в `verifying`, если незакрытых задач проекта с веткой на
   сервере (состояния от `verifying` до `awaiting_human`) уже
   `policy.max_in_flight`; задача ждёт в `in_dev` с именованной причиной в
   журнале и в `status`.
8. **В `awaiting_human`**: `approve`, `reject`, `answer` отказывают с
   подсказкой «состояние ждёт людей проекта — mr-sync (шаг Б2.2)»; пульт
   ничего не отправляет в ветку задачи и не меняет MR.
9. **`kill` задачи с `target-human`**, ветка которой отправлена: ветку на
   сервере не удаляет, MR не закрывает (при любом хостинге), убирает
   только рабочую копию и пишет ссылку на MR в журнал.
10. **Инварианты** — приложением PLAN к `tests/test_invariants.py`
    (защищённый путь; приложение накладывается и в CI ветки —
    `scripts/plan_appendix_ci.py`, — и на мерже): `FSM_STATES`
    (`tests/test_invariants.py:78`, а также `:611`, обходы `:1003`/`:1019`)
    с `awaiting_human`; новый тест «для проекта с `target-human` пульт не
    выполняет слияние, не отправляет `base` и ничего не отправляет в ветку
    задачи в `awaiting_human`» (по образцу `MergeOnlyFromMergeGateTest`);
    новый тест «MR открывается или снимается с черновика только для
    подтверждённой головы с зелёным CI».
11. **Существующие тесты** — правка по мандату Оператора 26.10 на тесты,
    которые меняет ADR-0029 (без ослабления, с матрицей и независимой
    проверкой), через гейт SPEC; ожидаются только добавления нового
    состояния в перечни: `tests/test_auto_cycle.py:64` (`FSM_STATES`;
    утверждение `:382-383` остаётся как есть),
    `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_board_model.py:37`
    (`OPERATOR_STATES` — без `awaiting_human`), `:131-133`, помощник
    `expected_waiting` `:192-199` (ветка `awaiting_human` → `"human"`),
    `tests/test_report.py:255`, `:270`; `tests/test_invariants.py` — только
    приложением PLAN (требование 10). Правка других существующих тестов —
    эскалация. Это добавления в константы-кортежи и в помощник, не смена
    скалярного литерала утверждения, поэтому раздела «Меняемое поведение»
    в SPEC нет: правка идёт по названному мандату Оператора.

## Критерии приёмки

AC-1. Загрузка записи `targets` без `policy.max_awaiting` и
`policy.awaiting_holds_zones` даёт значения 3 и `true`; `max_awaiting: 0`,
отрицательное, нецелое или `awaiting_holds_zones` не-bool — отказ загрузки
с именованной причиной.

AC-2. `approve` на `merge_gate` записи с `target-human` на подменённом
`forge`: MR ветки задачи в `base` открыт с исполнителем
`policy.mr_assignee`, задача в `awaiting_human`, ссылка на MR в БД и в
журнале задачи.

AC-3. В том же `approve` шпионы не видят слияния в scratch, отправки
`base`, удаления ветки (локально и на сервере) и рабочей копии, ожидания
CI base.

AC-4. sha `approve` не совпал с головой ветки, уходящей в MR, — отказ,
MR не открыт, задача на `merge_gate`.

AC-5. Задача с приложениями PLAN — отказ `approve` с причиной «приложения
не применяются в проекте с target-human — правку вносят люди проекта»,
MR не открыт, задача на `merge_gate`.

AC-6. Отказ `forge` при открытии MR — задача остаётся на `merge_gate` с
именованной причиной; повторный `approve` после того, как MR ветки уже
открыт, второй MR не открывает.

AC-7. Предел `max_awaiting`: при `policy.max_awaiting` = N и N задачах
проекта в `awaiting_human` `approve` на `merge_gate` (N+1)-й задачи —
отказ с причиной, задача на `merge_gate`, MR не открыт; `status` этой
задачи показывает «очередь: предел awaiting_human».

AC-8. `draft_mr: true`: на входе в `verifying` открыт черновой MR через
`forge.open_mr(draft=True)` (шпион `gh` не видит создания PR); на
`approve` гейта мержа черновик снят и исполнитель назначен, второй MR не
открыт.

AC-9. `draft_mr: false`: на входе в `verifying` MR не открывается; MR
открывается только на `approve` гейта мержа.

AC-10. Описание MR, открытого пультом, называет изменённые веткой
защищённые пути.

AC-11. `max_in_flight`: при `policy.max_in_flight` = N и N незакрытых
задачах проекта в состояниях от `verifying` до `awaiting_human` задача на
входе в `verifying` ветку не отправляет (шпион отправок не видит её
ветки), остаётся в `in_dev`, именованная причина — в журнале и в `status`.

AC-12. В `awaiting_human`: `approve`, `reject`, `answer` отказывают с
подсказкой «состояние ждёт людей проекта — mr-sync (шаг Б2.2)»; шпионы не
видят отправки в ветку задачи и вызовов `forge`, меняющих MR.

AC-13. `auto` по задаче в `awaiting_human` останавливается без алерта.

AC-14. Зоны задачи в `awaiting_human` держатся (вторая задача с
пересекающейся зоной получает отказ занятости) при
`awaiting_holds_zones: true` и свободны при `false`.

AC-15. Задача, зависящая по `merge_after` от задачи в `awaiting_human`,
ждёт `done` зависимости (гейт мержа зависимой отказывает).

AC-16. Модель доски по задаче в `awaiting_human` даёт `waiting_on:
"human"`; `report`, `watch`, `status` показывают состояние
`awaiting_human` и ссылку на MR; `status` не помечает её «ЖДЁТ
ОПЕРАТОРА».

AC-17. Надзор эпика не держит место за задачей в `awaiting_human` и не
считает её ждущей Оператора.

AC-18. Эскалация из `awaiting_human` после ответа возвращает задачу в
`awaiting_human`.

AC-19. `kill` задачи в `awaiting_human`: шпион отправок не видит
`--delete` ветки, MR не закрыт (вызова закрытия PR/MR нет при любом
хостинге), рабочая копия убрана, ссылка на MR — в журнале.

AC-20. PLAN несёт приложение к `tests/test_invariants.py`, которое
применяется к base (`git apply --check`), добавляет `awaiting_human` в
`FSM_STATES` и два теста из требования 10.

## Оценка объёма и деление

Сработавшие сигналы: файлов зоны ≥ 5 (18 модулей `orchestrator/` поимённо);
критериев приёмки ≥ 10 (20); `budget_usd` ≥ $30 ($70 — рамка ТЗ); зона
задевает механизм записей `docs/invariants.md` (гейт мержа, переходы FSM,
`tests/test_invariants.py`).

Решение — **нарезка на 2 части** (рамка ТЗ $70 делится 35 + 35). Граница
— по механике: часть 1 вводит состояние и его учёт во всех перечнях,
часть 2 — путь входа в него (гейт мержа → MR) и отправку ветки через
`forge`. Общие файлы (`fsm.py`, `catalog.py`, `targets.py`) правятся
частями в разных местах; части идут строго последовательно, зону-файл
одновременно не держат.

- Часть 1 самостоятельно мержима: состояние `awaiting_human` есть во всех
  перечнях, но недостижимо штатно — `target-human` неподдержан
  (`targets.SUPPORTED_MERGE_GATES = ("operator",)`), проекты с `operator`
  ведут себя как прежде; планка проверяет поведение в состоянии прямой
  установкой состояния в песочнице. Промежуточного нерабочего состояния
  нет.
- Часть 2 опирается на состояние, поля и ссылку на MR части 1 и без них
  смысла не имеет; после неё ТЗ закрыто целиком.

Альтернатива — монолит: решение Оператора на гейте SPEC; довод за него —
рамка $70 ТЗ уже рассчитана на одну задачу; довод против — 20 критериев
и 18 файлов зоны выше класса «~85 или деление» калибровки.

## Деление

### Б2.1а: состояние awaiting_human и его учёт в перечнях пульта

Зоны: orchestrator/fsm.py, orchestrator/targets.py, orchestrator/zone_lock.py, orchestrator/config.py, orchestrator/auto.py, orchestrator/board.py, orchestrator/report.py, orchestrator/watch.py, orchestrator/catalog.py, orchestrator/merge_after.py, orchestrator/cleanup.py, orchestrator/answer.py, orchestrator/store.py, orchestrator/schema.py, tests/
Порядок: после 01M5WDB7JY0VJGHVKCABA2QC5T
Рамка: $35

Часть 1 из 2 задачи 01M5XXA2HY73D3WTXDR19Z5SWW (GitLab Б2.1, ADR-0029
п. 1, 2, 12; ADR-0003 п. 7–8). Факты и адреса строк — ТЗ и SPEC
родителя (требования 1, 2, 3, 8, 9, 10 в части `FSM_STATES`, 11).

Требуется:
1. Поля записи `targets.py`, раздел `policy`, проверка при загрузке:
   `policy.max_awaiting` (целое > 0, по умолчанию 3),
   `policy.awaiting_holds_zones` (bool, по умолчанию `true`). Предикат
   «мерж делают люди проекта» — функция `targets.py` по образцу
   `push_whitelisted`; вне `targets.py` значение `merge_gate` с литералами
   не сравнивается.
2. Состояние `awaiting_human` в `fsm.STATES` после `merge_gate`, не
   окончательное, без гейта Оператора; `waiting_on` в модели доски —
   `human`. Учтено во всех перечнях: `zone_lock.BLOCKING_STATES` и
   производные (по `awaiting_holds_zones`), `config.AUTO_STOP` и
   `auto._NO_ALERT_FINAL_STATES` (остановка `auto` без алерта),
   `auto.EPIC_GATE_STATES`/`_NOT_HOLDING_STOP_STATES` (надзор эпика не
   держит место и не считает ждущей Оператора), `board`, `report.STATE_ORDER`,
   `watch._GATE_STATES`, метка `status` в `catalog.py` (состояние и ссылка
   на MR, без «ЖДЁТ ОПЕРАТОРА»), `merge_after` (зависимые ждут `done`),
   `fsm.APPROVE_NEEDS_SHA`, `fsm.SET_MODELS_STATES`, `config.STATE_ROLE`;
   эскалация из `awaiting_human` возвращает в него же; рабочая копия
   хранится до `done`/`kill`; в `MAX_PARALLEL_TASKS` не считается.
3. Ссылка на MR задачи — колонка БД (`store.py`/`schema.py`), показ в
   `status`/`report`/`watch`/доске.
4. В `awaiting_human` `approve`, `reject`, `answer` отказывают с подсказкой
   «состояние ждёт людей проекта — mr-sync (шаг Б2.2)»; пульт ничего не
   отправляет в ветку задачи и не меняет MR.
5. `kill` задачи с `target-human`, ветка которой отправлена: ветку на
   сервере не удаляет, MR не закрывает (при любом хостинге), убирает
   только рабочую копию и пишет ссылку на MR в журнал.
6. Приложением PLAN к `tests/test_invariants.py`: `FSM_STATES` (`:78`,
   `:611`, обходы `:1003`/`:1019`) с `awaiting_human`.
7. Существующие тесты — по мандату Оператора 26.10 (без ослабления):
   добавление `awaiting_human` в перечни `tests/test_auto_cycle.py:64`,
   `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_board_model.py:37`, `:131-133`,
   `:192-199`, `tests/test_report.py:255`, `:270`. Иное — эскалация.

Критерии приёмки (поддержка `target-human` в тестах — подменой
`targets.SUPPORTED_MERGE_GATES`/`SUPPORTED_FORGES` внутри теста, состояние
`awaiting_human` — прямой установкой в песочнице): поля и умолчания,
отказ загрузки на неверных значениях; `approve`/`reject`/`answer` — отказ с
подсказкой; `auto` остановлен без алерта; зоны держатся при
`awaiting_holds_zones: true` и свободны при `false`; задача по
`merge_after` ждёт `done`; доска — `waiting_on: human`; `report`/`watch`/
`status` показывают состояние и ссылку на MR; надзор эпика не держит
место; эскалация возвращает в `awaiting_human`; `kill` — ветка на сервере
и MR не тронуты (шпион отправок не видит `--delete`), рабочая копия
убрана, ссылка на MR в журнале; проекты с `operator` ведут себя как
прежде.

Не входит: путь входа в `awaiting_human` с гейта мержа, `max_awaiting` на
гейте, черновой MR через `forge`, `max_in_flight` (часть 2); `mr-sync` и
закрытие по вливанию MR (Б2.2); `pre-push`, `doctor`, подмодуль,
открытие `SUPPORTED_FORGES`/`SUPPORTED_MERGE_GATES` (Б2.3); `full_suite`
(В1); `verify` (В2). Блок `COMPONENT_FIELDS` в `targets.py` держит В1.

### Б2.1б: гейт мержа target-human открывает MR, черновой MR и max_in_flight через forge

Зоны: orchestrator/fsm.py, orchestrator/fsm_merge_gate.py, orchestrator/fsm_advance.py, orchestrator/github_adapter.py, orchestrator/advance_gates/tests_writing.py, orchestrator/catalog.py, orchestrator/targets.py, tests/
Порядок: после части 1
Рамка: $35

Часть 2 из 2 задачи 01M5XXA2HY73D3WTXDR19Z5SWW (GitLab Б2.1, ADR-0029
п. 1, 7, 12). Опирается на состояние `awaiting_human`, поля `policy` и
ссылку на MR части 1. Факты и адреса строк — ТЗ и SPEC родителя
(требования 4–7, 10 в части новых тестов).

Требуется:
1. `approve` на `merge_gate` для записи с `target-human`: исполняются без
   изменений сверка sha, ссылка документов, `no_paths`, неослабление по
   тексту и по исходам, лок планки, зелёный CI головы, подтяжка при
   сдвиге base (тем же методом `freshness`; после неё — новый CI и гейт по
   исходам, возврат на гейт). Подтверждённый sha обязан совпасть с
   головой, которая уходит в MR, иначе отказ. Не исполняются: слияние в
   scratch, приложения PLAN, `checks_local` по дереву мержа, карта и
   `guard --all`, отправка base, ожидание CI base, справочник ядра,
   удаление ветки и рабочей копии. Задача с приложениями PLAN — отказ
   «приложения не применяются в проекте с target-human — правку вносят
   люди проекта». Затем пульт через `forge` открывает MR ветки задачи в
   `base` с исполнителем `policy.mr_assignee` (при `draft_mr: true` —
   снимает черновик с уже открытого и назначает исполнителя), пишет
   ссылку на MR в БД и журнал и переводит задачу в `awaiting_human`.
   Любой отказ `forge` — задача остаётся на гейте с именованной причиной;
   MR не открыт дважды (сверка открытых MR ветки).
2. Предел `max_awaiting`: сверх предела задач проекта в `awaiting_human`
   `approve` на `merge_gate` отказывает с причиной, задача остаётся на
   гейте; `status` показывает «очередь: предел awaiting_human».
3. Черновой MR через `forge`: для `target-human` и `draft_mr: true` —
   черновой MR при первой отправке ветки (вход в `verifying`) через
   `forge.open_mr(draft=True)`, а не через `gh`; для `draft_mr: false` —
   MR один, на гейте мержа; в описании MR — подсветка изменённых
   защищённых путей. Поведение GitHub-проектов с `operator` не меняется.
4. `max_in_flight`: задача проекта не отправляет ветку на входе в
   `verifying`, если незакрытых задач проекта с веткой на сервере (от
   `verifying` до `awaiting_human`) уже `max_in_flight`; задача ждёт в
   `in_dev` с именованной причиной в журнале и `status`.
5. Приложением PLAN к `tests/test_invariants.py`: тест «для проекта с
   `target-human` пульт не выполняет слияние, не отправляет `base` и
   ничего не отправляет в ветку задачи в `awaiting_human`» (по образцу
   `MergeOnlyFromMergeGateTest`); тест «MR открывается или снимается с
   черновика только для подтверждённой головы с зелёным CI».

Критерии приёмки (поддержка `target-human` — подменой
`targets.SUPPORTED_MERGE_GATES`/`SUPPORTED_FORGES` внутри теста):
`approve` на подменённом `forge` — MR открыт с исполнителем, задача в
`awaiting_human`, ссылка в журнале; шпионы не видят слияния, отправки
base, удаления ветки и рабочей копии, ожидания CI base; sha не совпал с
головой — отказ, MR не открыт; задача с приложениями PLAN — отказ с
причиной; отказ `forge` — задача на гейте, повторный `approve` не
открывает второй MR; (предел+1)-я задача по `max_awaiting` — отказ,
задача на гейте; `draft_mr: true` — черновой MR на входе в `verifying`,
на гейте снят черновик; `draft_mr: false` — MR только на гейте; описание
MR называет изменённые защищённые пути; `max_in_flight` — сверх предела
ветка не отправлена, задача в `in_dev` с причиной; проекты с `operator`
(артель, GitHub) ведут себя как прежде.

Не входит: `mr-sync` и закрытие по вливанию MR (Б2.2); `pre-push`,
`doctor`, подмодуль, открытие `SUPPORTED_FORGES`/`SUPPORTED_MERGE_GATES`
(Б2.3); `full_suite` (В1); `verify` (В2). Только чтение:
`scripts/plan_appendix_ci.py`, `orchestrator/forge.py`,
`orchestrator/gitlab_adapter.py`, `orchestrator/gitcmd.py`,
`orchestrator/acceptance.py`, `orchestrator/advance_gates/outcome_integrity.py`.

## Не входит

- Команда `mr-sync` и закрытие задачи по вливанию MR (Б2.2).
- Хук `pre-push`, строки `doctor`, подмодуль, открытие
  `targets.SUPPORTED_FORGES`/`SUPPORTED_MERGE_GATES` в коде (Б2.3).
- `full_suite` (В1), `verify` (В2); блок `COMPONENT_FIELDS` в
  `targets.py` держит параллельная В1.
- Правка файлов только для чтения: `scripts/plan_appendix_ci.py`,
  `orchestrator/forge.py`, `orchestrator/gitlab_adapter.py`,
  `orchestrator/gitcmd.py`, `orchestrator/acceptance.py`,
  `orchestrator/advance_gates/outcome_integrity.py` (держит В1),
  `docs/adr/0029-external-delivery-via-mr.md`,
  `docs/adr/0003-target-projects.md`.
- Перечни состояний вне Факта 2 ТЗ (`brief.py:87`, `pull.py:87`,
  `doctor/hung_test_watchdog.py:318`) — ТЗ требований по ним не ставит.
- Зелёность существующих тестов `approve`, `kill`, `cleanup`, доски,
  `report`, `auto` для проектов с `operator` (артель, GitHub) — её держит
  пульт (полный набор `tests/` и гейт неослабления).

## Материалы

- ТЗ задачи: `tasks/01M5XXA2HY73D3WTXDR19Z5SWW/TZ.md` (Факты 1–8 с
  адресами строк).
- ADR-0029 (`docs/adr/0029-external-delivery-via-mr.md`) п. 1, 2, 7, 12;
  ADR-0003 п. 7–8.
- Вызовы чернового MR сегодня: `fsm._maybe_ensure_draft_mr` (`fsm.py:152`;
  вызовы `fsm.py:1495`, `:1762`, `:1861`, `:1874`, `:1922`,
  `fsm_advance.py:361`, `:648`, `fsm_merge_gate.py:285`, `:1008`);
  `github_adapter._ensure_draft_mr_after_publish` (`github_adapter.py:257`,
  вызов `advance_gates/tests_writing.py:156`); `github_adapter.undraft_mr`
  (`github_adapter.py:301`, вызов `fsm.py:1627`).
