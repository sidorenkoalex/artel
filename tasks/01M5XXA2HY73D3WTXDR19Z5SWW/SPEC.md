---
task: 01M5XXA2HY73D3WTXDR19Z5SWW
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/fsm.py, orchestrator/fsm_merge_gate.py, orchestrator/fsm_advance.py, orchestrator/targets.py, orchestrator/zone_lock.py, orchestrator/config.py, orchestrator/auto.py, orchestrator/board.py, orchestrator/report.py, orchestrator/watch.py, orchestrator/catalog.py, orchestrator/merge_after.py, orchestrator/cleanup.py, orchestrator/answer.py, orchestrator/store.py, orchestrator/schema.py, orchestrator/github_adapter.py, orchestrator/advance_gates/tests_writing.py, orchestrator/gitcmd.py, orchestrator/doctor/branch_freshness.py, tests/
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

Решения Оператора на гейте SPEC 27.10.2026 (возврат из `spec_gate`) вошли
в требования ниже: источник истины о MR — ссылка в БД; запрет отправки
ветки в `awaiting_human` — в единой точке отправки `gitcmd.py`; набор
задач `max_in_flight` — по записи журнала «ветка отправлена»; поведение
надзора эпика, `_refuse_if_main_red`, `doctor` свежести ветки, умолчания
полей и форма `mr_assignee`. Гейт SPEC №2 (27.10.2026) точечно уточнил:
`mr_assignee` при загрузке — как в Б1.1, нечисловой — MR без
исполнителя; признак 409 — по `reason` результата `forge`; шаги гейта
мержа для `target-human`; `max_in_flight` — в точке отправки
`gitcmd.py` перед первой отправкой; ссылка на MR — пара (`iid`,
`web_url`); `awaiting_human` вне `APPROVE_NEEDS_SHA`/`SET_MODELS_STATES`/
`STATE_ROLE`.

## Требования

1. **Поля записи** (`targets.py`, раздел `policy`, проверка при загрузке):
   `policy.max_awaiting` — целое > 0; `policy.awaiting_holds_zones` —
   bool. Значение другого типа или `max_awaiting` ≤ 0 — отказ загрузки
   записи с именованной причиной. Умолчания полей доставки
   (`max_awaiting` 3, `awaiting_holds_zones` `true`, `draft_mr` `true`)
   отдаёт одна функция чтения в `targets.py`; читатели вне `targets.py`
   умолчаний сами не подставляют. `policy.mr_assignee` при загрузке
   проверяется как в Б1.1 без изменений: непустая строка либо целое
   (`yamlmini` даёт `int` для `mr_assignee: 42` — допустимо); новых
   отказов загрузки по `mr_assignee` нет (держит
   `tests/test_01m5wdb7f14sq30qvwjy2xybg2_record_fields.py:169`, значение
   `"alice"` допустимо). При открытии MR: значение из одних цифр (строка)
   или `int` — в `forge` уходит исполнитель `int` (`assignee_id`); любое
   иное значение — MR открывается без исполнителя, и в журнал задачи
   пишется запись «исполнитель не числовой id — не назначен». Предикат «мерж делают люди проекта» — функция `targets.py`
   (по образцу `push_whitelisted`, `targets.py:537-542`); вне `targets.py`
   значение `merge_gate` с литералами не сравнивается (сторож А0 AC-9).
2. **Состояние `awaiting_human`** — в `fsm.STATES` сразу после
   `merge_gate`; не окончательное (не в `fsm.TERMINAL_STATES`); без гейта
   Оператора. В модели доски `waiting_on` для него — новое значение
   `human`. Учитывается во всех местах перечня состояний (ADR-0029 п. 2):
   - `zone_lock.BLOCKING_STATES` (`zone_lock.py:110`, производные `:119`,
     `:126`): зоны задачи в `awaiting_human` заняты при
     `policy.awaiting_holds_zones: true` и свободны при `false`;
   - `config.AUTO_STOP` (`config.py:923`), `auto._NO_ALERT_FINAL_STATES`
     (`auto.py:70`): `auto` в `awaiting_human` останавливается без алерта;
   - надзор эпика (`auto.EPIC_GATE_STATES` `auto.py:1150`,
     `auto._NOT_HOLDING_STOP_STATES` `auto.py:1168`, статус задачи
     `auto.py:1298-1306`, `view.live` `auto.py:1338`): `awaiting_human` —
     остановка без удержания места: надзор не перезапускает задачу, не
     считает её в лимите параллельности эпика, не считает ждущей
     Оператора и показывает её статусом «ждёт людей проекта»;
   - `board.OPERATOR_STATES`/`CI_STATES`/`waiting_on` (`board.py:20-44`),
     `report.STATE_ORDER` (`report.py:48`), `watch._GATE_STATES`
     (`watch.py:40`), метка `status` (`catalog.py:1353`): `report`, `watch`,
     `status` и доска показывают состояние `awaiting_human` и ссылку на MR
     задачи; `awaiting_human` не помечается «ЖДЁТ ОПЕРАТОРА»;
     `report.MANUAL_GATE_STATES` (`report.py:42`) — без `awaiting_human`;
   - `merge_after.STATUS_WAIT_STATES` (`merge_after.py:55`), ожидание
     `done` (`merge_after.py:649`, `:769`): задача, зависящая по
     `merge_after` от задачи в `awaiting_human`, ждёт `done` зависимости;
   - `fsm.APPROVE_NEEDS_SHA` (`fsm.py:839`) — `awaiting_human` в нём нет;
     `fsm.SET_MODELS_STATES` (`fsm.py:1959`) — нет; `config.STATE_ROLE`
     (`config.py:870`) — нет (у состояния нет роли);
   - эскалация из `awaiting_human` (`escalated_from`, `fsm.py:1757`)
     возвращает задачу в `awaiting_human`;
   - рабочая копия задачи в `awaiting_human` хранится до `done`/`kill`
     (`fsm_merge_gate.py:1365-1378`, `cleanup.py:215`);
   - задача в `awaiting_human` не занимает место в `MAX_PARALLEL_TASKS`
     (лимит считает живые lease, `parallel_limit.py:24-36`);
   - `doctor` проверку свежести ветки (`doctor/branch_freshness.py:40`) к
     задаче в `awaiting_human` не применяет (ADR-0029 п. 2).
3. **Ссылка на MR задачи** хранится в БД (`store.py`/`schema.py`) парой
   (`iid`, `web_url`) — поля `iid`/`url` ответа `forge.MergeRequest`
   (`forge.py:67-74`) — и пишется в журнал задачи при каждом
   открытии/снятии черновика MR. `undraft_mr`/`assign_mr` получают `iid`
   из этой пары. Ссылка в БД — источник истины о MR задачи; списочного
   запроса MR по ветке к хостингу нет (`forge.py`/`gitlab_adapter.py`
   только чтение).
4. **`approve` на `merge_gate` для записи с `target-human`** (ADR-0029
   п. 1). Исполняются без изменений: сверка sha (`fsm.py:1802-1808`),
   ссылка документов, `no_paths`, неослабление по тексту и по исходам, лок
   планки, зелёный CI головы ветки, подтяжка при сдвиге base (тем же
   методом `freshness`; после неё — новый CI и гейт по исходам, возврат на
   гейт тем же путём, что для `operator`), публикация головы ветки
   (`_ensure_branch_head_published`, `fsm_merge_gate.py:1513`), отказ во
   время канарейки (`_refuse_during_canary`, `fsm_merge_gate.py:1541`) —
   до открытия MR, мьютекс merge-окна (`fsm_merge_gate.py:1581-1601`).
   Подтверждённый sha обязан совпасть с головой, которая уходит в MR,
   иначе отказ. Не исполняются: отказ по красному CI base
   (`_refuse_if_main_red`, `fsm_merge_gate.py:1525` — CI base дело людей
   проекта), слияние в scratch, приложения PLAN, `checks_local` по дереву
   мержа, карта и `guard --all`, отправка base, коммит закрытия
   (`cleanup._commit_closing`, `fsm_merge_gate.py:1545` — задача не
   `done`), ожидание CI base, справочник ядра, удаление ветки и рабочей
   копии. Задача с приложениями PLAN — отказ с причиной «приложения не
   применяются в проекте с target-human — правку вносят люди проекта».
   Затем пульт через `forge`:
   - ссылки на MR в БД нет — открывает MR ветки задачи в `base` с
     исполнителем по правилу `policy.mr_assignee` (требование 1);
   - ссылка на MR в БД есть — новый MR не открывает: снимает черновик
     (`undraft_mr`) и назначает исполнителя (`assign_mr`) у MR по `iid`
     ссылки;
   - `open_mr` ответил «уже существует» (409), а ссылки в БД нет —
     эскалация задачи с причиной «MR ветки уже существует, ссылки в БД
     нет», второй MR не открывается. Признак 409 — разбор кода из `reason`
     результата `forge` в `orchestrator/fsm_merge_gate.py` по нынешнему
     тексту адаптера (`gitlab_adapter.py:209`, «GitLab ответил кодом 409
     на …»), без правки `forge.py`/`gitlab_adapter.py`;
   пишет ссылку на MR в БД и журнал и переводит задачу в `awaiting_human`.
   Любой другой отказ `forge` (в том числе `undraft_mr`/`assign_mr`) —
   задача остаётся на `merge_gate` с именованной причиной.
   Без `policy.mr_assignee` MR открывается без исполнителя, и в журнал
   задачи пишется запись об этом.
5. **Предел `max_awaiting`**: если задач этого проекта в `awaiting_human`
   уже `policy.max_awaiting`, `approve` на `merge_gate` отказывает с
   причиной, задача остаётся на гейте; `status` показывает «очередь:
   предел awaiting_human». Задачи других проектов в счёт не входят.
6. **Черновой MR через `forge`** (ADR-0029 п. 7): для записи с
   `target-human` и `draft_mr: true` — черновой MR при первой отправке
   ветки (вход в `verifying`) через `forge.open_mr(draft=True)`, а не
   через `gh`; для `draft_mr: false` — MR один, открывается на гейте
   мержа; в описании MR — подсветка изменённых защищённых путей.
   Поведение GitHub-проектов с `operator` не меняется.
7. **`max_in_flight`** (ADR-0029 п. 12): предел проверяется в единой
   точке отправки `orchestrator/gitcmd.py` перед ПЕРВОЙ отправкой ветки
   задачи (у задачи ещё нет записи «ветка отправлена»), а не только на
   входе в `verifying`: если незакрытых задач этого проекта с веткой на
   сервере уже `policy.max_in_flight`, отправка отказывается до вызова
   git с именованной причиной в журнале и в `status`. Это покрывает любой
   путь первой отправки, в том числе черновой MR GitHub на входе в
   `in_dev` (`github_adapter.py:163-166`), `amend-tests`
   (`amend.py:834`) и путь сжатия (`tests_writing.py:66-67`). На входе в
   `verifying` задача при таком отказе ждёт в `in_dev`. «Задача с веткой
   на сервере» — задача этого проекта в любом неокончательном состоянии,
   у которой в журнале есть запись «ветка отправлена»
   (`gitcmd.PUSH_SENT_ACTION`, `gitcmd.py:176`), включая `in_dev` после
   возврата, `review` и `escalated`. Задачи других проектов в счёт не
   входят. Повторные отправки задачи, уже имеющей запись «ветка
   отправлена», пределом не отказываются.
8. **В `awaiting_human`**: `approve`, `reject`, `answer` отказывают с
   подсказкой «состояние ждёт людей проекта — mr-sync (шаг Б2.2)»; пульт
   ничего не отправляет в ветку задачи и не меняет MR. Запрет отправки — в
   единой точке отправки `orchestrator/gitcmd.py`: отправка ветки задачи в
   состоянии `awaiting_human` отказывается до вызова git с именованной
   причиной — для любого пути отправки, в том числе `amend-tests`
   (`amend.py:834`).
9. **`kill` задачи с `target-human`**, ветка которой отправлена (в любом
   состоянии после первой отправки): ветку на сервере не удаляет, MR не
   закрывает (при любом хостинге), убирает только рабочую копию и пишет
   ссылку на MR в журнал.
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
    которые меняет ADR-0029 (без ослабления, с матрицей ниже), только в
    строках с перечнями состояний, поимённо:
    - `tests/test_auto_cycle.py:64-66` — кортеж `FSM_STATES`: добавить
      `"awaiting_human"`; утверждение `:382-383` не меняется;
    - `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_board_model.py:192-199` —
      помощник `expected_waiting`: ветка `state == "awaiting_human"` →
      `"human"` до ветки `"role"`.
    `OPERATOR_STATES` (`board_model.py:37`) не меняется; докстринги
    `board_model.py:131-133` и `tests/test_report.py:255`, `:270` перечней
    состояний не несут и не правятся. `tests/test_invariants.py` — только
    приложением PLAN (требование 10). Правка других существующих тестов —
    эскалация. Правка — добавление элемента в кортеж и ветки в помощник,
    не смена скалярного литерала утверждения, поэтому раздела «Меняемое
    поведение» нет.

## Критерии приёмки

AC-1. Функция чтения полей доставки `targets.py` по записи без
`policy.max_awaiting`, `policy.awaiting_holds_zones`, `policy.draft_mr`
даёт 3, `true`, `true`; `max_awaiting: 0`, отрицательное, нецелое или
`awaiting_holds_zones` не-bool — отказ загрузки записи с именованной
причиной.

AC-2. Запись с `policy.mr_assignee` `"alice"` и с `mr_assignee: 42`
(целое) загружается без отказа. На подменённом `forge`: `mr_assignee`
`"42"` (строка из цифр) и `42` (целое) уходят в `forge.open_mr`/
`assign_mr` исполнителем `int` 42; `mr_assignee` `"alice"` — MR открыт
без исполнителя, в журнале задачи запись «исполнитель не числовой id —
не назначен»; без `mr_assignee` MR открывается без исполнителя, а в
журнале задачи есть запись об этом.

AC-3. `approve` на `merge_gate` записи с `target-human` на подменённом
`forge`: MR ветки задачи в `base` открыт с исполнителем
`policy.mr_assignee`, задача в `awaiting_human`, ссылка на MR — пара
(`iid`, `web_url`) — в БД и в журнале задачи. В том же `approve`
исполнены публикация головы ветки, проверка канарейки (до вызова
`open_mr`) и захват мьютекса merge-окна проекта; во время живой
канарейки `approve` отказывает и `open_mr` не зван.

AC-4. В том же `approve` шпионы не видят слияния в scratch, отправки
`base`, коммита закрытия, удаления ветки (локально и на сервере) и
рабочей копии, ожидания CI base.

AC-5. При красном CI base `approve` записи с `target-human` не отказывает
по нему и открывает MR; при красном CI головы ветки — отказ, MR не
открыт, задача на `merge_gate`.

AC-6. sha `approve` не совпал с головой ветки, уходящей в MR, — отказ,
MR не открыт, задача на `merge_gate`.

AC-7. На `approve` сдвинулся base: подтяжка выполнена, задача
возвращается тем же путём, что для проекта с `operator` (новый CI, гейт
по исходам, возврат на гейт), MR не открыт.

AC-8. Задача с приложениями PLAN — отказ `approve` с причиной «приложения
не применяются в проекте с target-human — правку вносят люди проекта»,
MR не открыт, задача на `merge_gate`.

AC-9. Отказ `forge` при открытии MR — задача остаётся на `merge_gate` с
именованной причиной, ссылки на MR в БД нет.

AC-10. Ссылка на MR в БД есть: `approve` не зовёт `open_mr`, зовёт
`undraft_mr` и `assign_mr` с `iid` из ссылки; задача в `awaiting_human`.

AC-11. Подменённый `forge.open_mr` вернул результат без `iid` с `reason`
в тексте адаптера для кода 409 («GitLab ответил кодом 409 на …») при
отсутствии ссылки в БД — задача эскалирована с причиной «MR ветки уже
существует, ссылки в БД нет»; второй вызов `open_mr` не сделан. С
`reason` другого кода (например 403) — задача на `merge_gate` с
именованной причиной, не эскалирована.

AC-12. `draft_mr: true`, отказ `undraft_mr` или `assign_mr` — задача на
`merge_gate` с именованной причиной; повторный `approve` не зовёт
`open_mr` (второй MR не открыт).

AC-13. Предел `max_awaiting`: при `policy.max_awaiting` = N и N задачах
этого проекта в `awaiting_human` `approve` на `merge_gate` (N+1)-й
задачи — отказ с причиной, задача на `merge_gate`, MR не открыт; `status`
этой задачи показывает «очередь: предел awaiting_human». При N−1 задачах
этого проекта и любом числе задач другого проекта в `awaiting_human`
`approve` проходит.

AC-14. `draft_mr: true`: на входе в `verifying` открыт черновой MR через
`forge.open_mr(draft=True)` (шпион `gh` не видит создания PR); на
`approve` гейта мержа черновик снят и исполнитель назначен, второй MR не
открыт.

AC-15. `draft_mr: false`: на входе в `verifying` MR не открывается; MR
открывается только на `approve` гейта мержа.

AC-16. Описание MR, открытого пультом, называет изменённые веткой
защищённые пути.

AC-17. `max_in_flight`: при `policy.max_in_flight` = N и N незакрытых
задачах этого проекта с записью «ветка отправлена» в журнале — среди них
задача в `review`, задача в `in_dev` после возврата и задача в
`escalated` — задача на входе в `verifying` ветку не отправляет (шпион
отправок не видит её ветки), остаётся в `in_dev`, именованная причина — в
журнале и в `status`. При N−1 таких задачах этого проекта и любом числе
таких задач другого проекта ветка отправляется.

AC-18. В `awaiting_human`: `approve`, `reject`, `answer` отказывают с
подсказкой «состояние ждёт людей проекта — mr-sync (шаг Б2.2)»; шпионы не
видят отправки в ветку задачи и вызовов `forge`, меняющих MR.

AC-19. Отправка ветки задачи в `awaiting_human` через единую точку
`gitcmd.py` отказана с именованной причиной; путь `amend-tests` по задаче
в `awaiting_human` отказан, шпион git не видит вызова отправки.

AC-20. `auto` по задаче в `awaiting_human` останавливается без алерта.

AC-21. Зоны задачи в `awaiting_human` держатся (вторая задача с
пересекающейся зоной получает отказ занятости) при
`awaiting_holds_zones: true` и свободны при `false`.

AC-22. Задача, зависящая по `merge_after` от задачи в `awaiting_human`,
ждёт `done` зависимости (гейт мержа зависимой отказывает) — защита от
регрессии.

AC-23. Модель доски по задаче в `awaiting_human` даёт `waiting_on:
"human"`; `report`, `watch`, `status` показывают состояние
`awaiting_human` и ссылку на MR; `status` не помечает её «ЖДЁТ
ОПЕРАТОРА».

AC-24. Надзор эпика по задаче в `awaiting_human` (после шага роли): не
перезапускает её (`auto` по ней не запускается на повторных проходах
надзора), не считает её в лимите параллельности эпика, не считает ждущей
Оператора и показывает статус «ждёт людей проекта»; эпик, где кроме неё
живых задач нет, не крутит цикл перезапуска.

AC-25. Эскалация из `awaiting_human` после ответа возвращает задачу в
`awaiting_human` — защита от регрессии.

AC-26. `kill` задачи с `target-human` в каждом из состояний после первой
отправки ветки — `verifying`, `review`, `acceptance`, `merge_gate`,
`awaiting_human`, `escalated`: шпион argv `gitcmd.git`/`gitcmd.in_repo`
не видит ни одной отправки с `--delete`, в журнале задачи нет ни одной
записи «отправка отказана», MR не закрыт (вызова закрытия PR/MR нет),
рабочая копия убрана, ссылка на MR (если есть) — в журнале. Проверяется
в двух вариантах: `forge: gitlab` и `forge: github` с `target-human`
(PR не закрыт — шпион `gh` не видит закрытия PR).

AC-27. `doctor` проверку свежести ветки к задаче в `awaiting_human` с
отставшей от base веткой не применяет (нет строки об этой задаче); к
задаче в `in_dev` с той же веткой — применяет.

AC-28. PLAN несёт приложение к `tests/test_invariants.py`, которое
применяется к base (`git apply --check`), добавляет `awaiting_human` в
`FSM_STATES` и два теста из требования 10.

AC-29. Существующие тесты `approve`, `kill`, `cleanup`, доски, `report`,
`auto` для проектов с `operator` (артель, GitHub) зелёные без правки,
кроме двух мест мандата требования 11.

AC-30. `awaiting_human` нет в `fsm.APPROVE_NEEDS_SHA`, нет в
`fsm.SET_MODELS_STATES` и нет среди ключей `config.STATE_ROLE` — по
утверждению на каждый перечень.

AC-31. `max_in_flight` на пути `amend-tests`: при `policy.max_in_flight`
= N, N задачах этого проекта с записью «ветка отправлена» и задаче в
`in_dev` без такой записи `amend-tests` по ней не отправляет ветку
(шпион argv `gitcmd.git`/`gitcmd.in_repo` не видит её отправки), в
журнале — именованная причина предела. При N−1 таких задачах ветка
отправлена.

AC-32. `max_in_flight` на пути входа в `in_dev` (черновой MR GitHub,
`github_adapter.ensure_draft_mr`): при N задачах этого проекта с записью
«ветка отправлена» первая отправка ветки новой задачи отказана до вызова
git с именованной причиной в журнале; задача этого проекта, у которой
запись «ветка отправлена» уже есть, отправляет ветку повторно без отказа.

## Оценка объёма и деление

Сработавшие сигналы: файлов зоны ≥ 5 (20 модулей `orchestrator/`
поимённо); критериев приёмки ≥ 10 (32); `budget_usd` ≥ $30 ($70 — рамка
ТЗ); зона задевает механизм записей `docs/invariants.md` (гейт мержа,
переходы FSM, точка отправки, `tests/test_invariants.py`).

Решение — **нарезка на 2 части** (принята Оператором на гейте SPEC
27.10.2026, рамка каждой части $45). Граница — по механике: часть 1
вводит состояние, поля и их учёт во всех перечнях, запрет отправки в
состоянии и `kill`; часть 2 — путь входа в состояние (гейт мержа → MR),
черновой MR через `forge` и `max_in_flight`. Общие файлы (`fsm.py`,
`catalog.py`, `targets.py`) правятся частями в разных местах; части идут
строго последовательно, зону-файл одновременно не держат.

- Часть 1 самостоятельно мержима: состояние `awaiting_human` есть во всех
  перечнях, но недостижимо штатно — `target-human` неподдержан
  (`targets.SUPPORTED_MERGE_GATES = ("operator",)`), проекты с `operator`
  ведут себя как прежде; планка проверяет поведение в состоянии прямой
  установкой состояния в песочнице. Промежуточного нерабочего состояния
  нет.
- Часть 2 опирается на состояние, поля и ссылку на MR части 1 и без них
  смысла не имеет; после неё ТЗ закрыто целиком.

## Деление

### Б2.1а: состояние awaiting_human и его учёт в перечнях пульта

Зоны: orchestrator/fsm.py, orchestrator/targets.py, orchestrator/zone_lock.py, orchestrator/config.py, orchestrator/auto.py, orchestrator/board.py, orchestrator/report.py, orchestrator/watch.py, orchestrator/catalog.py, orchestrator/merge_after.py, orchestrator/cleanup.py, orchestrator/answer.py, orchestrator/store.py, orchestrator/schema.py, orchestrator/gitcmd.py, orchestrator/doctor/branch_freshness.py, tests/
Порядок: после 01M5WDB7JY0VJGHVKCABA2QC5T
Рамка: $45

Часть 1 из 2 задачи 01M5XXA2HY73D3WTXDR19Z5SWW (GitLab Б2.1, ADR-0029
п. 1, 2, 12; ADR-0003 п. 7–8). Факты и адреса строк — ТЗ и SPEC
родителя (требования 1, 2, 3, 8, 9, 10 в части `FSM_STATES`, 11).

Требуется:
1. Поля записи `targets.py`, раздел `policy`, проверка при загрузке:
   `policy.max_awaiting` (целое > 0), `policy.awaiting_holds_zones`
   (bool); неверный тип или `max_awaiting` ≤ 0 — отказ загрузки с
   именованной причиной. Умолчания `max_awaiting` 3,
   `awaiting_holds_zones` `true`, `draft_mr` `true` — одной функцией чтения
   в `targets.py`. `policy.mr_assignee` при загрузке — как в Б1.1 без
   изменений (непустая строка либо целое; новых отказов загрузки нет,
   `tests/test_01m5wdb7f14sq30qvwjy2xybg2_record_fields.py:169` не
   трогается). Предикат «мерж делают люди проекта» — функция `targets.py` по
   образцу `push_whitelisted`; вне `targets.py` значение `merge_gate` с
   литералами не сравнивается.
2. Состояние `awaiting_human` в `fsm.STATES` после `merge_gate`, не
   окончательное, без гейта Оператора; `waiting_on` в модели доски —
   `human`. Учтено во всех перечнях: `zone_lock.BLOCKING_STATES` и
   производные (по `awaiting_holds_zones`), `config.AUTO_STOP` и
   `auto._NO_ALERT_FINAL_STATES` (остановка `auto` без алерта), надзор
   эпика (`auto.py:1150`, `:1168`, `:1298-1306`, `:1338`: остановка без
   удержания места — не перезапускает задачу, не считает в лимите
   параллельности, не считает ждущей Оператора, статус «ждёт людей
   проекта», без цикла перезапуска), `board`, `report.STATE_ORDER`
   (`report.MANUAL_GATE_STATES` — без `awaiting_human`),
   `watch._GATE_STATES`, метка `status` в `catalog.py` (состояние и ссылка
   на MR, без «ЖДЁТ ОПЕРАТОРА»), `merge_after` (зависимые ждут `done`);
   в `fsm.APPROVE_NEEDS_SHA`, `fsm.SET_MODELS_STATES` и
   `config.STATE_ROLE` состояния нет (роли нет); эскалация из `awaiting_human` возвращает в него же; рабочая копия
   хранится до `done`/`kill`; в `MAX_PARALLEL_TASKS` не считается;
   `doctor` проверку свежести ветки (`doctor/branch_freshness.py:40`) к
   `awaiting_human` не применяет.
3. Ссылка на MR задачи — в БД (`store.py`/`schema.py`) парой (`iid`,
   `web_url`), показ в `status`/`report`/`watch`/доске; ссылка в БД —
   источник истины о MR.
4. В `awaiting_human` `approve`, `reject`, `answer` отказывают с подсказкой
   «состояние ждёт людей проекта — mr-sync (шаг Б2.2)»; пульт ничего не
   отправляет в ветку задачи и не меняет MR. Запрет отправки — в единой
   точке отправки `orchestrator/gitcmd.py`: отправка ветки задачи в
   `awaiting_human` отказывается до вызова git с именованной причиной для
   любого пути, в том числе `amend-tests` (`amend.py:834`).
5. `kill` задачи с `target-human`, ветка которой отправлена (в любом
   состоянии после первой отправки): ветку на сервере не удаляет, MR не
   закрывает (при любом хостинге), убирает только рабочую копию и пишет
   ссылку на MR в журнал.
6. Приложением PLAN к `tests/test_invariants.py`: `FSM_STATES` (`:78`,
   `:611`, обходы `:1003`/`:1019`) с `awaiting_human`.
7. Существующие тесты — по мандату Оператора 26.10 (без ослабления),
   только строки с перечнями состояний: кортеж `FSM_STATES`
   `tests/test_auto_cycle.py:64-66` (+ `"awaiting_human"`), помощник
   `expected_waiting`
   `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_board_model.py:192-199`
   (+ ветка `awaiting_human` → `"human"`). Иное — эскалация.

Критерии приёмки (поддержка `target-human` в тестах — подменой
`targets.SUPPORTED_MERGE_GATES`/`SUPPORTED_FORGES` внутри теста, состояние
`awaiting_human` — прямой установкой в песочнице): поля, умолчания одной
функцией и отказ загрузки на неверных значениях, `mr_assignee` `"alice"`
и `42` загружаются без отказа; `awaiting_human` нет в
`fsm.APPROVE_NEEDS_SHA`, `fsm.SET_MODELS_STATES`, ключах
`config.STATE_ROLE` — утверждение на каждый перечень;
`approve`/`reject`/`answer` — отказ с
подсказкой; отправка ветки в `awaiting_human` отказана в `gitcmd.py`, путь
`amend-tests` отказан, шпион git не вызван; `auto` остановлен без алерта;
зоны держатся при `awaiting_holds_zones: true` и свободны при `false`;
задача по `merge_after` ждёт `done`; доска — `waiting_on: human`;
`report`/`watch`/`status` показывают состояние и ссылку на MR; надзор
эпика не перезапускает задачу, не считает её в лимите, статус «ждёт людей
проекта»; эскалация возвращает в `awaiting_human`; `kill` в каждом из
`verifying`, `review`, `acceptance`, `merge_gate`, `awaiting_human`,
`escalated` после первой отправки — шпион argv `gitcmd.git`/
`gitcmd.in_repo` не видит отправки с `--delete`, в журнале нет записи
«отправка отказана», MR не закрыт, рабочая копия убрана, ссылка на MR в
журнале — в вариантах `forge: gitlab` и `forge: github` с `target-human`
(PR не закрыт); `doctor` не проверяет свежесть ветки `awaiting_human`;
существующие тесты для `operator`-проектов зелёные без правки, кроме
мандата.

Не входит: путь входа в `awaiting_human` с гейта мержа, `max_awaiting` на
гейте, черновой MR через `forge`, `max_in_flight` (часть 2); `mr-sync` и
закрытие по вливанию MR (Б2.2); `pre-push`, прочие строки `doctor`,
подмодуль, открытие `SUPPORTED_FORGES`/`SUPPORTED_MERGE_GATES` (Б2.3);
`full_suite` (В1); `verify` (В2). Блок `COMPONENT_FIELDS` в `targets.py`
держит В1.

### Б2.1б: гейт мержа target-human открывает MR, черновой MR и max_in_flight через forge

Зоны: orchestrator/fsm.py, orchestrator/fsm_merge_gate.py, orchestrator/fsm_advance.py, orchestrator/github_adapter.py, orchestrator/advance_gates/tests_writing.py, orchestrator/catalog.py, orchestrator/targets.py, orchestrator/gitcmd.py, tests/
Порядок: после части 1
Рамка: $45

Часть 2 из 2 задачи 01M5XXA2HY73D3WTXDR19Z5SWW (GitLab Б2.1, ADR-0029
п. 1, 7, 12). Опирается на состояние `awaiting_human`, поля `policy`,
функцию чтения умолчаний и ссылку на MR части 1. Факты и адреса строк —
ТЗ и SPEC родителя (требования 4–7, 10 в части новых тестов).

Требуется:
1. `approve` на `merge_gate` для записи с `target-human`: исполняются без
   изменений сверка sha, ссылка документов, `no_paths`, неослабление по
   тексту и по исходам, лок планки, зелёный CI головы, подтяжка при
   сдвиге base (тем же методом `freshness`; после неё — новый CI и гейт по
   исходам, возврат на гейт тем же путём), публикация головы
   (`fsm_merge_gate.py:1513`), `_refuse_during_canary`
   (`fsm_merge_gate.py:1541`) — до открытия MR, мьютекс merge-окна
   (`fsm_merge_gate.py:1581-1601`). Подтверждённый sha обязан совпасть с
   головой, которая уходит в MR, иначе отказ. Не исполняются: отказ по
   красному CI base (`_refuse_if_main_red`), слияние в scratch,
   приложения PLAN, `checks_local` по дереву мержа, карта и
   `guard --all`, отправка base, коммит закрытия
   (`fsm_merge_gate.py:1545`, задача не `done`), ожидание CI base,
   справочник ядра, удаление ветки и рабочей копии. Задача с приложениями
   PLAN — отказ «приложения не применяются в проекте с target-human —
   правку вносят люди проекта». Затем через `forge`: ссылки на MR в БД
   нет — открыть MR ветки в `base`; исполнитель: `mr_assignee` из одних
   цифр или `int` → `assignee_id` `int`, иное — MR без исполнителя и
   запись журнала «исполнитель не числовой id — не назначен», без
   `mr_assignee` — без исполнителя и с записью журнала; ссылка есть —
   нового MR не открывать, снять черновик и назначить исполнителя у MR по
   `iid` ссылки; `open_mr` ответил 409 при отсутствии ссылки — эскалация
   «MR ветки уже существует, ссылки в БД нет», без второго MR (признак
   409 — разбор кода из `reason` результата `forge` в
   `fsm_merge_gate.py` по тексту `gitlab_adapter.py:209`). Ссылку — пару
   (`iid`, `web_url`) — в БД и журнал, задачу — в `awaiting_human`. Любой другой отказ `forge` (в том числе
   `undraft_mr`/`assign_mr`) — задача остаётся на гейте с именованной
   причиной. Списочного запроса MR не добавлять (`forge.py`/
   `gitlab_adapter.py` только чтение).
2. Предел `max_awaiting`: сверх предела задач этого проекта в
   `awaiting_human` `approve` на `merge_gate` отказывает с причиной,
   задача остаётся на гейте; `status` показывает «очередь: предел
   awaiting_human». Задачи других проектов не считаются.
3. Черновой MR через `forge`: для `target-human` и `draft_mr: true` —
   черновой MR при первой отправке ветки (вход в `verifying`) через
   `forge.open_mr(draft=True)`, а не через `gh`; для `draft_mr: false` —
   MR один, на гейте мержа; в описании MR — подсветка изменённых
   защищённых путей. Поведение GitHub-проектов с `operator` не меняется.
4. `max_in_flight`: предел проверяется в единой точке отправки
   `orchestrator/gitcmd.py` перед ПЕРВОЙ отправкой ветки задачи (записи
   «ветка отправлена» у неё нет): если незакрытых задач этого проекта с
   записью журнала «ветка отправлена» (в любом неокончательном состоянии,
   включая `in_dev` после возврата, `review`, `escalated`) уже
   `max_in_flight`, отправка отказывается до вызова git с именованной
   причиной в журнале и `status`. Покрывает все пути первой отправки:
   вход в `verifying` (задача ждёт в `in_dev`), черновой MR GitHub на
   входе в `in_dev` (`github_adapter.py:163-166`), `amend-tests`
   (`amend.py:834`), путь сжатия (`tests_writing.py:66-67`). Задачи
   других проектов не считаются.
5. Приложением PLAN к `tests/test_invariants.py`: тест «для проекта с
   `target-human` пульт не выполняет слияние, не отправляет `base` и
   ничего не отправляет в ветку задачи в `awaiting_human`» (по образцу
   `MergeOnlyFromMergeGateTest`); тест «MR открывается или снимается с
   черновика только для подтверждённой головы с зелёным CI».

Критерии приёмки (поддержка `target-human` — подменой
`targets.SUPPORTED_MERGE_GATES`/`SUPPORTED_FORGES` внутри теста):
`approve` на подменённом `forge` — MR открыт с исполнителем (`int` для
`"42"` и `42`; для `"alice"` — без исполнителя и запись журнала),
задача в `awaiting_human`, ссылка (`iid`, `web_url`) в БД и журнале;
публикация головы, проверка канарейки до `open_mr` и мьютекс исполнены,
во время канарейки — отказ без `open_mr`; шпионы не видят слияния,
отправки base, коммита закрытия, удаления ветки и рабочей копии,
ожидания CI base;
красный CI base не отказывает, красный CI головы — отказ; sha не совпал с
головой — отказ, MR не открыт; сдвиг base — подтяжка и возврат тем же
путём, MR не открыт; задача с приложениями PLAN — отказ с причиной; отказ
`forge` — задача на гейте; ссылка в БД есть — `open_mr` не зван, черновик
снят у MR по `iid` ссылки; `reason` с кодом 409 без ссылки — эскалация
«MR ветки уже существует, ссылки в БД нет», `reason` другого кода — задача
на гейте; отказ `undraft_mr`/`assign_mr` — задача на гейте,
повторный `approve` не открывает второй MR; без `mr_assignee` — MR без
исполнителя и запись журнала; (предел+1)-я задача по `max_awaiting` —
отказ, задачи другого проекта не считаются; `draft_mr: true` — черновой
MR на входе в `verifying`, на гейте снят черновик; `draft_mr: false` — MR
только на гейте; описание MR называет изменённые защищённые пути;
`max_in_flight` — сверх предела (в счёте задачи в `review`, в `in_dev`
после возврата, в `escalated`; задачи другого проекта не считаются) ветка
не отправлена, задача в `in_dev` с причиной; тот же отказ первой
отправки на пути `amend-tests` и на пути входа в `in_dev` (черновой MR
GitHub), повторная отправка задачи с записью «ветка отправлена» не
отказана; существующие тесты для
проектов с `operator` (артель, GitHub) зелёные без правки, кроме мандата.

Не входит: `mr-sync` и закрытие по вливанию MR (Б2.2); `pre-push`,
`doctor`, подмодуль, открытие `SUPPORTED_FORGES`/`SUPPORTED_MERGE_GATES`
(Б2.3); `full_suite` (В1); `verify` (В2). Только чтение:
`scripts/plan_appendix_ci.py`, `orchestrator/forge.py`,
`orchestrator/gitlab_adapter.py`, `orchestrator/acceptance.py`,
`orchestrator/advance_gates/outcome_integrity.py`.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| `FSM_STATES` в `tests/test_invariants.py:78` (+ свипы `:693`, `:1003`, `:1019`) — приложением PLAN | Свипы инвариантов идут по всем состояниям; сверка множества с `fsm.STATES` — `tests/test_invariants.py:616` | остаётся, строже (свип покрывает новое состояние) | `tests/test_invariants.py:616` после приложения (AC-28) | ок |
| `FSM_STATES` в `tests/test_auto_cycle.py:64-66` (+ `"awaiting_human"`) | Полнота `AUTO_STOP` — `tests/test_auto_cycle.py:382-383`; свипы `:329`, `:1166` | остаётся (утверждение не меняется, `awaiting_human` уходит в `AUTO_STOP`) | `tests/test_auto_cycle.py:382-383` + AC-20 | ок |
| `expected_waiting` в `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_board_model.py:192-199` (+ ветка `awaiting_human` → `"human"`) | `waiting_on` для каждого состояния — `test_ac22` (`board_model.py:202-218`) | остаётся, строже (новое значение проверяется для нового состояния) | `board_model.py:202-218` + AC-23 | ок |
| Гейт мержа для `target-human`: нет слияния, отправки base и удаления ветки | Инвариант «в main мержит только approve из merge_gate» — `tests/test_invariants.py:646-720` | остаётся, строже (для `target-human` не мержит никогда) | новый тест инвариантов (треб. 10) + AC-4 | ок |
| Гейт мержа для `target-human`: нет `checks_local`, карты, `guard --all`, ожидания CI base | Дерево мержа проходит проверки — `fsm_merge_gate.py:1535-1540`, `:1548` | исчезает вместе с механизмом (пульт не мержит, ADR-0029 п. 1) | не покрыто — обязанность людей проекта | ок по ADR |
| Гейт мержа для `target-human`: нет отказа по красному CI base `_refuse_if_main_red` | Отказ мержа при красном main — `fsm_merge_gate.py:1525` | исчезает вместе с механизмом (пульт не мержит в base; решение Оператора 27.10); зелёный CI головы ветки остаётся | AC-5 (красный CI головы — отказ) | ок по решению Оператора |
| Приложения PLAN в проекте `target-human` | Правка защищённых путей — только приложением, `fsm_merge_gate.py:1530` | остаётся (отказ `approve`) | AC-8 | ок |
| Подсветка защищённых путей: комментарий `gh` → описание MR | `github_adapter.py:195-208` | остаётся (переезжает) | AC-16 | ок |
| «MR не открыт дважды» — по ссылке в БД, без списочного запроса | Нет (сверки сегодня нет) | новое свойство; MR с потерянным ответом — эскалация по 409, не второй MR | AC-10, AC-11, AC-12 | ок |
| `zone_lock.BLOCKING_STATES` + `awaiting_holds_zones: false` | Зона занята до `done` — `zone_lock.py:110`, `:494` | осознанно ослабляется полем по ADR-0029 п. 2 (умолчание — держит) | AC-21 | ок по ADR |
| `kill` для `target-human`: ветка на сервере и MR не трогаются | Уборка хвостов — `cleanup.py:304-306` | исчезает для `target-human` по ADR-0029 / ADR-0003 п. 7 | AC-26 (все состояния после первой отправки) | ок |
| `_NO_ALERT_FINAL_STATES` + `awaiting_human` | Алерт при остановке `auto` не на гейте — `auto.py:544` | остаётся для прочих состояний | AC-20 | ок |
| Отказ отправки ветки в `awaiting_human` — в точке отправки `gitcmd.py` | Белый список отправок — `gitcmd._whitelist_refusal` (`gitcmd.py:625`) пропускает ветку любой неокончательной задачи | остаётся, строже (новый отказ сверх белого списка; прочие отказы не меняются) | AC-19 + новый тест инвариантов (треб. 10) | ок |
| `doctor` свежесть ветки без `awaiting_human` | Сигнал отставшей ветки активной задачи — `doctor/branch_freshness.py:40` | остаётся для прочих неокончательных состояний; для `awaiting_human` исчезает по ADR-0029 п. 2 | AC-27 | ок по ADR |
| `max_in_flight` и `max_awaiting` — новые пределы; `max_in_flight` — в точке отправки `gitcmd.py` перед первой отправкой | Нет | новые свойства, счёт по своему проекту | AC-13, AC-17, AC-31, AC-32 | ок |
| `mr_assignee` не числовой — MR без исполнителя | Проверка при загрузке Б1.1 (`targets.py:648-657`), тест `tests/test_01m5wdb7f14sq30qvwjy2xybg2_record_fields.py:169` | остаётся без изменений (новых отказов загрузки нет) | AC-2 + `record_fields.py:169` | ок по решению Оператора |

## Не входит

- Команда `mr-sync` и закрытие задачи по вливанию MR (Б2.2).
- Хук `pre-push`, прочие строки `doctor` (кроме свежести ветки
  `awaiting_human`), подмодуль, открытие
  `targets.SUPPORTED_FORGES`/`SUPPORTED_MERGE_GATES` в коде (Б2.3).
- `full_suite` (В1), `verify` (В2); блок `COMPONENT_FIELDS` в
  `targets.py` держит параллельная В1.
- Списочный запрос MR по ветке к хостингу (решение Оператора 27.10).
- Правка файлов только для чтения: `scripts/plan_appendix_ci.py`,
  `orchestrator/forge.py`, `orchestrator/gitlab_adapter.py`,
  `orchestrator/acceptance.py`,
  `orchestrator/advance_gates/outcome_integrity.py` (держит В1),
  `orchestrator/amend.py` (запрет отправки — в `gitcmd.py`),
  `docs/adr/0029-external-delivery-via-mr.md`,
  `docs/adr/0003-target-projects.md`.
- Перечни состояний вне Факта 2 ТЗ (`brief.py:87`, `pull.py:87`,
  `doctor/hung_test_watchdog.py:318`) — ТЗ требований по ним не ставит.

## Материалы

- ТЗ задачи: `tasks/01M5XXA2HY73D3WTXDR19Z5SWW/TZ.md` (Факты 1–8 с
  адресами строк); аудит SPEC `SPEC-AUDIT.md` (вердикт `concerns`, 14
  пунктов) и решения Оператора по нему (возврат из `spec_gate`
  27.10.2026).
- ADR-0029 (`docs/adr/0029-external-delivery-via-mr.md`) п. 1, 2, 7, 12;
  ADR-0003 п. 7–8.
- Вызовы чернового MR сегодня: `fsm._maybe_ensure_draft_mr` (`fsm.py:152`;
  вызовы `fsm.py:1495`, `:1762`, `:1861`, `:1874`, `:1922`,
  `fsm_advance.py:361`, `:648`, `fsm_merge_gate.py:285`, `:1008`);
  `github_adapter._ensure_draft_mr_after_publish` (`github_adapter.py:257`,
  вызов `advance_gates/tests_writing.py:156`, а также из
  `ensure_head_in_origin` после каждой отправки, `github_adapter.py:211-254`;
  вызывающие — `tests_writing.py:69`, `fsm_advance.py:479`,
  `fsm_merge_gate.py:701`, `pull_main.py:93`, `amend.py:834`);
  `github_adapter.undraft_mr` (`github_adapter.py:301`, вызов
  `fsm.py:1627`).
- Запись журнала «ветка отправлена» — `gitcmd.PUSH_SENT_ACTION`
  (`gitcmd.py:176`), чтение последней — `gitcmd.py:220-230`.
