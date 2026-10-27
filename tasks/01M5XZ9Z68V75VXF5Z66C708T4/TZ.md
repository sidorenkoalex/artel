---
task: 01M5XZ9Z68V75VXF5Z66C708T4
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Б2.1а: состояние awaiting_human и его учёт в перечнях пульта

Родительская задача: 01M5XXA2HY73D3WTXDR19Z5SWW — GitLab Б2.1: гейт мержа target-human — MR вместо слияния, состояние awaiting_human
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