---
task: 01M5XZ9Z68V75VXF5Z66C708T4
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/fsm.py, orchestrator/targets.py, orchestrator/zone_lock.py, orchestrator/config.py, orchestrator/auto.py, orchestrator/board.py, orchestrator/report.py, orchestrator/watch.py, orchestrator/catalog.py, orchestrator/merge_after.py, orchestrator/cleanup.py, orchestrator/answer.py, orchestrator/amend.py, orchestrator/store.py, orchestrator/schema.py, orchestrator/gitcmd.py, orchestrator/doctor/branch_freshness.py, tests/
merge_after: 01M5WDB7JY0VJGHVKCABA2QC5T
budget_usd: 45
---

# SPEC: Б2.1а — состояние `awaiting_human` и его учёт в перечнях пульта

## Контекст
Часть 1 из 2 задачи 01M5XXA2HY73D3WTXDR19Z5SWW (GitLab Б2.1, ADR-0029
п. 1, 2, 12; ADR-0003 п. 7–8). Для проекта с `merge_gate: target-human`
MR вливают люди проекта, и задаче нужно состояние «ждём людей проекта».
Сегодня его в `fsm.STATES` (`fsm.py:33-37`) нет, перечни состояний пульта
(`zone_lock.py:110`, `config.py:870`, `:923`, `auto.py:70`, `:1150`,
`:1168`, `board.py:19-20`, `report.py:42`, `:48`, `watch.py:40`,
`merge_after.py:769`, `catalog.py:1353`, `fsm.py:839`, `:1959`) его не
знают, полей `policy.max_awaiting`/`awaiting_holds_zones` в записи
`targets.py` нет, ссылки на MR задачи в БД нет. Эта часть вводит
состояние, поля, ссылку на MR и поведение в состоянии; путь входа в
состояние с гейта мержа — часть 2. `target-human` до шага Б2.3
неподдержан (`targets.SUPPORTED_MERGE_GATES = ("operator",)`), поэтому
состояние штатно недостижимо, а проекты с `operator` ведут себя как
прежде. Адреса строк и решения Оператора — SPEC родителя (требования 1,
2, 3, 8, 9, 10 в части `FSM_STATES`, 11) и решения гейта SPEC этой
задачи 27.10.2026 (возврат с решениями п. 1–8).

## Требования

1. **Поля записи** (`targets.py`, раздел `policy`, проверка при загрузке):
   `policy.max_awaiting` — целое > 0; `policy.awaiting_holds_zones` —
   bool. Значение другого типа или `max_awaiting` ≤ 0 — отказ загрузки
   записи с именованной причиной.
2. **Функция чтения полей доставки** — `targets.delivery_policy(entry) ->
   dict` с умолчаниями: `max_awaiting` 3, `awaiting_holds_zones` `True`,
   `draft_mr` `True`, `max_in_flight` `None`, `mr_assignee` `None`.
   Умолчания отдаёт только она.
3. **`policy.mr_assignee`** (решение гейта SPEC, п. 1): проверка загрузки
   (`targets.py:648-651`) допускает целое (не bool) наряду с непустой
   строкой — расширение допустимых значений, не ослабление; прочие
   значения (пустая строка, bool, иной тип) по-прежнему отказ загрузки.
   Толкование значения: целое и строка цифр — id исполнителя, иное —
   строка как в Б1.1.
   `tests/test_01m5wdb7f14sq30qvwjy2xybg2_record_fields.py:169` не
   трогается.
4. **Предикат «мерж делают люди проекта»** — функция `targets.py` по
   образцу `push_whitelisted` (`targets.py:537`); вне `targets.py`
   значение `merge_gate` с литералами не сравнивается.
5. **Состояние `awaiting_human`** — в `fsm.STATES` сразу после
   `merge_gate`; не окончательное (не в `fsm.TERMINAL_STATES`); без гейта
   Оператора.
6. В модели доски `waiting_on` для `awaiting_human` — `human`
   (`board.py`).
7. `zone_lock.BLOCKING_STATES` (`zone_lock.py:110`) и производные:
   зоны задачи в `awaiting_human` заняты при
   `policy.awaiting_holds_zones: true` и свободны при `false`.
8. `config.AUTO_STOP` (`config.py:923`) и `auto._NO_ALERT_FINAL_STATES`
   (`auto.py:70`): `auto` в `awaiting_human` останавливается без алерта.
9. Надзор эпика (`auto.py:1150`, `:1168`, `:1298-1306`, `:1338`):
   `awaiting_human` — остановка без удержания места: надзор не
   перезапускает задачу, не считает её в лимите параллельности эпика, не
   считает ждущей Оператора, показывает статус «ждёт людей проекта», не
   крутит цикл перезапуска.
10. `report.STATE_ORDER` (`report.py:48`) и `watch._GATE_STATES`
    (`watch.py:40`) учитывают `awaiting_human`;
    `report.MANUAL_GATE_STATES` (`report.py:42`) — без `awaiting_human`.
    Метка `status` в `catalog.py` (`catalog.py:1353`) показывает состояние
    и ссылку на MR и не ставит «ЖДЁТ ОПЕРАТОРА».
11. `merge_after`: задача, зависящая от задачи в `awaiting_human`, ждёт
    `done` зависимости — отказ гейта мержа по незавершённой зависимости
    (`merge_after.py:769`, `s != "done"`) и добавка `status`
    (`merge_after.py:792`). На main это уже так; требование — защита от
    регрессии, новой механики в этой части нет.
12. В `fsm.APPROVE_NEEDS_SHA` (`fsm.py:839`), `fsm.SET_MODELS_STATES`
    (`fsm.py:1959`) и ключах `config.STATE_ROLE` (`config.py:870`)
    `awaiting_human` нет (роли у состояния нет).
13. Эскалация из `awaiting_human` возвращает задачу в `awaiting_human`
    (механика `escalated_from`, `fsm.py:1757`) — защита от регрессии. Путь
    входа в эскалацию из `awaiting_human` — только ручной (`answer`/`kill`
    Оператора); новых путей входа в эскалацию эта часть не вводит.
14. Рабочая копия задачи в `awaiting_human` хранится до `done`/`kill`;
    задача в `awaiting_human` не считается в `MAX_PARALLEL_TASKS`.
15. `doctor` проверку свежести ветки (`doctor/branch_freshness.py:40`) к
    задаче в `awaiting_human` не применяет.
16. **Ссылка на MR задачи** (решение гейта SPEC, п. 2) — новые столбцы
    задачи `mr_iid INTEGER` и `mr_url TEXT` (`schema.py`, миграция по
    образцу существующих `add_column(conn, "tasks", …)`, `schema.py:330-444`);
    запись и чтение — функциями `store.py`. Ссылка показывается в
    `status`, `report`, `watch` и на доске; ссылка в БД — источник истины
    о MR.
17. **В `awaiting_human`** `approve`, `reject`, `answer` отказывают с
    подсказкой «состояние ждёт людей проекта — mr-sync (шаг Б2.2)»; пульт
    ничего не отправляет в ветку задачи и не меняет MR.
18. **Запрет отправки** — в единой точке отправки `orchestrator/gitcmd.py`:
    отправка ветки задачи в `awaiting_human` отказывается до вызова git с
    именованной причиной для любой формы отправки — обычная отправка,
    явный refspec, `--delete`, `:<ветка>` (удаление в `gitcmd._push_plan`
    отделено от отправляемых веток, `gitcmd.py:816-832`).
19. **`amend-tests` в `awaiting_human`** (решение гейта SPEC, п. 5) —
    отказ в начале команды, до коммита, с подсказкой mr-sync; проверка
    состояния — в `amend.py`.
20. **`kill` задачи с `target-human`**, ветка которой отправлена — в любом
    состоянии после первой отправки, включая `in_dev` после возврата
    (признак — запись журнала «ветка отправлена», `gitcmd.PUSH_SENT_ACTION`,
    `gitcmd.py:176`, в том числе записи старого вида): сервер не трогается
    — ветку на сервере не удаляет, MR не закрывает (при любом хостинге);
    убирает только рабочую копию, т. е. рабочую копию, локальную ветку и
    локальный каталог задачи, как сейчас; `refs/artifacts` и сервер не
    трогаются; ссылку на MR пишет в журнал.
21. Приложением PLAN к `tests/test_invariants.py` (защищённый путь):
    `FSM_STATES` (`tests/test_invariants.py:78`, `:611`, обходы `:1003`/
    `:1019`) с `awaiting_human`.
22. **Существующие тесты** — по мандату Оператора 26.10 (без ослабления),
    только правка перечней состояний: кортеж `FSM_STATES`
    `tests/test_auto_cycle.py:64-66` (+ `"awaiting_human"`); помощник
    `expected_waiting`
    `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_board_model.py:192-199`
    (+ ветка `awaiting_human` → `"human"`) и прочие перечни состояний
    того же файла модели доски; перечни состояний в тестах `report`
    (`tests/test_report.py`). Правка — добавление элемента в перечень и
    ветки в помощник, не смена скалярного литерала утверждения, поэтому
    раздела «Меняемое поведение» нет. Если гейт неослабления сочтёт такую
    правку ослаблением — эскалация с вопросом, строку мандата выдаст
    Оператор. Правка иных существующих тестов — эскалация.

Поддержка `target-human` в тестах — подменой
`targets.SUPPORTED_MERGE_GATES`/`SUPPORTED_FORGES` внутри теста;
состояние `awaiting_human` — прямой установкой в песочнице.

## Критерии приёмки

AC-1. `targets.delivery_policy(entry)` по записи без `policy.max_awaiting`,
`policy.awaiting_holds_zones`, `policy.draft_mr`, `policy.max_in_flight`,
`policy.mr_assignee` даёт `max_awaiting` 3, `awaiting_holds_zones` `True`,
`draft_mr` `True`, `max_in_flight` `None`, `mr_assignee` `None`;
`max_awaiting` ≤ 0 или не целое, `awaiting_holds_zones` не bool — отказ
загрузки записи с именованной причиной.

AC-2. Запись с `policy.mr_assignee` `"alice"` и с `mr_assignee: 42`
загружается без отказа; `delivery_policy` толкует целое и строку цифр как
id исполнителя, `"alice"` — как строку (утверждение на оба вида).

AC-3. `awaiting_human` нет в `fsm.APPROVE_NEEDS_SHA`, нет в
`fsm.SET_MODELS_STATES` и нет среди ключей `config.STATE_ROLE` — по
утверждению на каждый перечень.

AC-4. В `awaiting_human` `approve`, `reject`, `answer` отказывают с
подсказкой «состояние ждёт людей проекта — mr-sync (шаг Б2.2)».

AC-5. Обычная отправка ветки задачи в `awaiting_human` через единую
точку `gitcmd.py` отказана с именованной причиной; шпион git не видит
вызова отправки.

AC-6. Отправка ветки задачи в `awaiting_human` явным refspec отказана
`gitcmd.py` с именованной причиной; шпион git не видит вызова отправки.

AC-7. Отправка `--delete` ветки задачи в `awaiting_human` отказана
`gitcmd.py` с именованной причиной; шпион git не видит вызова отправки.

AC-8. Отправка `:<ветка>` (удаление пустым источником) ветки задачи в
`awaiting_human` отказана `gitcmd.py` с именованной причиной; шпион git
не видит вызова отправки.

AC-9. `amend-tests` по задаче в `awaiting_human` отказывает в начале
команды с подсказкой mr-sync: ни коммита, ни отправки.

AC-10. `auto` по задаче в `awaiting_human` останавливается без алерта.

AC-11. Зоны задачи в `awaiting_human` держатся (вторая задача с
пересекающейся зоной получает отказ занятости) при
`awaiting_holds_zones: true` и свободны при `false`.

AC-12. Защита от регрессии: задача, зависящая по `merge_after` от задачи в
`awaiting_human`, ждёт `done` зависимости.

AC-13. Модель доски по задаче в `awaiting_human` даёт `waiting_on:
"human"`.

AC-14. Доска и `status` по задаче со ссылкой на MR в БД (`mr_iid`,
`mr_url`, записанные функцией `store.py`) показывают эту ссылку.

AC-15. `report`, `watch` и `status` по задаче в `awaiting_human`
показывают состояние `awaiting_human` и ссылку на MR из столбцов
`mr_iid`/`mr_url` (чтение функцией `store.py`); `status` не помечает её
«ЖДЁТ ОПЕРАТОРА».

AC-16. Надзор эпика по задаче в `awaiting_human` не перезапускает её, не
считает её в лимите параллельности эпика и показывает статус «ждёт людей
проекта».

AC-17. Защита от регрессии: эскалация из `awaiting_human` возвращает
задачу в `awaiting_human`.

AC-18. `kill` задачи с `target-human` в каждом из состояний после первой
отправки ветки — `in_dev` (после возврата; в том числе с записью «ветка
отправлена» старого вида), `verifying`, `review`, `acceptance`,
`merge_gate`, `awaiting_human`, `escalated`: шпион argv
`gitcmd.git`/`gitcmd.in_repo` не видит отправки с `--delete`, в журнале
задачи нет записи «отправка отказана», MR не закрыт, рабочая копия,
локальная ветка и локальный каталог задачи убраны, `refs/artifacts`
задачи на месте, ссылка на MR из `mr_iid`/`mr_url` — в журнале.
Проверяется в вариантах `forge: gitlab` и `forge: github` с
`target-human` (PR не закрыт).

AC-19. `doctor` не проверяет свежесть ветки задачи в `awaiting_human`.

AC-20. Существующие тесты для `operator`-проектов зелёные без правки,
кроме правок по мандату (требование 22).

## Оценка объёма и деление

Сработавшие сигналы: файлов зоны ≥ 5 (17 модулей `orchestrator/`
поимённо и `tests/`); критериев приёмки ≥ 10 (20); `budget_usd` ≥ $30
($45 — рамка части, утверждённая Оператором); зона задевает механизм
записей `docs/invariants.md` (переходы FSM, точка отправки,
`tests/test_invariants.py`).

Материал для **обоснования монолита** (решение — за Оператором на гейте
SPEC): эта задача уже часть 1 деления родителя 01M5XXA2HY73D3WTXDR19Z5SWW,
принятого Оператором 27.10.2026 с рамкой $45. Ядро задачи — одно новое
значение в `fsm.STATES`: в момент его появления сверка
`tests/test_invariants.py:611` и свипы `tests/test_auto_cycle.py` требуют,
чтобы состояние было учтено во всех перечнях сразу (`AUTO_STOP`, доска,
`report`, `watch`, зоны, надзор эпика). Часть, вводящая состояние без
учёта в перечнях, оставила бы набор красным (`auto` с алертом, доска без
`waiting_on`); перечни без состояния смысла не имеют. Отделимы только
поля `policy` (требования 1–4), ссылка на MR (требование 16) и `kill`
(требование 20), но каждый из этих кусков проверяется лишь на задаче в
`awaiting_human` и в одиночку не мержим с осмысленной планкой.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| `FSM_STATES` в `tests/test_invariants.py:78` (+ обходы `:1003`, `:1019`) — приложением PLAN | Свипы инвариантов по всем состояниям; сверка с `fsm.STATES` — `tests/test_invariants.py:611` | остаётся, строже (свип покрывает новое состояние) | `tests/test_invariants.py:611` после приложения | ок |
| `FSM_STATES` в `tests/test_auto_cycle.py:64-66` (+ `"awaiting_human"`) | Полнота `AUTO_STOP` и свипы `tests/test_auto_cycle.py` | остаётся (утверждения не меняются, `awaiting_human` уходит в `AUTO_STOP`) | `tests/test_auto_cycle.py` + AC-10 | ок, мандат 26.10 |
| `expected_waiting` и перечни состояний в `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_board_model.py:192-199` (+ ветка `awaiting_human` → `"human"`) | `waiting_on` для каждого состояния — тест того же файла | остаётся, строже (новое значение для нового состояния) | тот же файл + AC-13 | ок, мандат 26.10 |
| Перечни состояний в `tests/test_report.py` (+ `awaiting_human`) | Колонки отчёта по `report.STATE_ORDER` — `tests/test_report.py` | остаётся, строже (новое состояние в перечне) | `tests/test_report.py` + AC-15 | ок, мандат 26.10 |
| `policy.mr_assignee`: проверка загрузки `targets.py:648-651` допускает целое (не bool) наряду с непустой строкой; целое и строка цифр — id исполнителя, иное — строка как в Б1.1 | Отказ загрузки на не непустой строке — `targets.py:650-651`, `tests/test_01m5wdb7f14sq30qvwjy2xybg2_record_fields.py:169` | остаётся для пустой строки, bool и иных типов; допустимые значения расширены целым — не ослабление (решение гейта SPEC 27.10, п. 1) | `tests/test_01m5wdb7f14sq30qvwjy2xybg2_record_fields.py:169` + AC-2 | ок, решение Оператора |
| `zone_lock.BLOCKING_STATES` + `awaiting_holds_zones: false` | Зона занята до `done` — `zone_lock.py:110` | осознанно ослабляется полем по ADR-0029 п. 2 (умолчание — держит) | AC-11 | ок по ADR |
| `kill` для `target-human`: ветка на сервере и MR не трогаются | Уборка хвостов — `cleanup.py` | исчезает для `target-human` по ADR-0029 / ADR-0003 п. 7 | AC-18 | ок по ADR |
| Отказ отправки ветки в `awaiting_human` в `gitcmd.py` | Белый список отправок `gitcmd._whitelist_refusal` (`gitcmd.py:625`) | остаётся, строже (новый отказ сверх белого списка) | AC-5, AC-6, AC-7, AC-8 | ок |
| `doctor` свежесть ветки без `awaiting_human` | `doctor/branch_freshness.py:40` | остаётся для прочих неокончательных состояний; для `awaiting_human` исчезает по ADR-0029 п. 2 | AC-19 | ок по ADR |

## Не входит

- Путь входа в `awaiting_human` с гейта мержа, `max_awaiting` на гейте,
  черновой MR через `forge`, `max_in_flight` на гейте (часть 2 родителя).
- Новые пути входа в эскалацию из `awaiting_human` (вход только ручной —
  `answer`/`kill`).
- `mr-sync` и закрытие задачи по вливанию MR (Б2.2).
- Хук `pre-push`, прочие строки `doctor` (кроме свежести ветки
  `awaiting_human`), подмодуль, открытие
  `targets.SUPPORTED_FORGES`/`SUPPORTED_MERGE_GATES` в коде (Б2.3).
- `full_suite` (В1), `verify` (В2); блок `COMPONENT_FIELDS` в
  `targets.py` держит В1.

## Материалы

- ТЗ: `tasks/01M5XZ9Z68V75VXF5Z66C708T4/TZ.md`.
- Решения гейта SPEC 27.10.2026 (возврат с п. 1–8): `mr_assignee` целым,
  имена `delivery_policy`/`mr_iid`/`mr_url`, формы отправки, `kill` в
  `in_dev`, `amend-tests`, AC защиты от регрессии, мандат на перечни,
  показ ссылки MR.
- SPEC родителя: `refs/artifacts/01M5XXA2HY73D3WTXDR19Z5SWW`,
  `tasks/01M5XXA2HY73D3WTXDR19Z5SWW/SPEC.md` (требования 1, 2, 3, 8, 9,
  10, 11; разделы «Деление», «Матрица неослабления»).
- ADR-0029 (`docs/adr/0029-external-delivery-via-mr.md`) п. 1, 2, 12;
  ADR-0003 п. 7–8.
- Запись журнала «ветка отправлена» — `gitcmd.PUSH_SENT_ACTION`
  (`gitcmd.py:176`); разбор отправки — `gitcmd._push_plan`
  (`gitcmd.py:730`, удаление `:816`).
