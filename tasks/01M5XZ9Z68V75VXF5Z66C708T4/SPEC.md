---
task: 01M5XZ9Z68V75VXF5Z66C708T4
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/fsm.py, orchestrator/targets.py, orchestrator/zone_lock.py, orchestrator/config.py, orchestrator/auto.py, orchestrator/board.py, orchestrator/report.py, orchestrator/watch.py, orchestrator/catalog.py, orchestrator/merge_after.py, orchestrator/cleanup.py, orchestrator/answer.py, orchestrator/store.py, orchestrator/schema.py, orchestrator/gitcmd.py, orchestrator/doctor/branch_freshness.py, tests/
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
`merge_after.py:55`, `catalog.py:1353`, `fsm.py:839`, `:1959`) его не знают,
полей `policy.max_awaiting`/`awaiting_holds_zones` в записи `targets.py`
нет, ссылки на MR задачи в БД нет. Эта часть вводит состояние, поля,
ссылку на MR и поведение в состоянии; путь входа в состояние с гейта мержа
— часть 2. `target-human` до шага Б2.3 неподдержан
(`targets.SUPPORTED_MERGE_GATES = ("operator",)`), поэтому состояние
штатно недостижимо, а проекты с `operator` ведут себя как прежде.
Адреса строк и решения Оператора — SPEC родителя (требования 1, 2, 3, 8,
9, 10 в части `FSM_STATES`, 11).

## Требования

1. **Поля записи** (`targets.py`, раздел `policy`, проверка при загрузке):
   `policy.max_awaiting` — целое > 0; `policy.awaiting_holds_zones` —
   bool. Значение другого типа или `max_awaiting` ≤ 0 — отказ загрузки
   записи с именованной причиной. Умолчания `max_awaiting` 3,
   `awaiting_holds_zones` `true`, `draft_mr` `true` отдаёт одна функция
   чтения в `targets.py`. `policy.mr_assignee` при загрузке — как в Б1.1
   без изменений: непустая строка либо целое; новых отказов загрузки нет,
   `tests/test_01m5wdb7f14sq30qvwjy2xybg2_record_fields.py:169` не
   трогается.
2. **Предикат «мерж делают люди проекта»** — функция `targets.py` по
   образцу `push_whitelisted` (`targets.py:537`); вне `targets.py`
   значение `merge_gate` с литералами не сравнивается.
3. **Состояние `awaiting_human`** — в `fsm.STATES` сразу после
   `merge_gate`; не окончательное (не в `fsm.TERMINAL_STATES`); без гейта
   Оператора.
4. В модели доски `waiting_on` для `awaiting_human` — `human`
   (`board.py`).
5. `zone_lock.BLOCKING_STATES` (`zone_lock.py:110`) и производные:
   зоны задачи в `awaiting_human` заняты при
   `policy.awaiting_holds_zones: true` и свободны при `false`.
6. `config.AUTO_STOP` (`config.py:923`) и `auto._NO_ALERT_FINAL_STATES`
   (`auto.py:70`): `auto` в `awaiting_human` останавливается без алерта.
7. Надзор эпика (`auto.py:1150`, `:1168`, `:1298-1306`, `:1338`):
   `awaiting_human` — остановка без удержания места: надзор не
   перезапускает задачу, не считает её в лимите параллельности эпика, не
   считает ждущей Оператора, показывает статус «ждёт людей проекта», не
   крутит цикл перезапуска.
8. `report.STATE_ORDER` (`report.py:48`) и `watch._GATE_STATES`
   (`watch.py:40`) учитывают `awaiting_human`;
   `report.MANUAL_GATE_STATES` (`report.py:42`) — без `awaiting_human`.
   Метка `status` в `catalog.py` (`catalog.py:1353`) показывает состояние
   и ссылку на MR и не ставит «ЖДЁТ ОПЕРАТОРА».
9. `merge_after` (`merge_after.py:55`): задача, зависящая от задачи в
   `awaiting_human`, ждёт `done` зависимости.
10. В `fsm.APPROVE_NEEDS_SHA` (`fsm.py:839`), `fsm.SET_MODELS_STATES`
    (`fsm.py:1959`) и ключах `config.STATE_ROLE` (`config.py:870`)
    `awaiting_human` нет (роли у состояния нет).
11. Эскалация из `awaiting_human` возвращает задачу в `awaiting_human`.
12. Рабочая копия задачи в `awaiting_human` хранится до `done`/`kill`;
    задача в `awaiting_human` не считается в `MAX_PARALLEL_TASKS`.
13. `doctor` проверку свежести ветки (`doctor/branch_freshness.py:40`) к
    задаче в `awaiting_human` не применяет.
14. **Ссылка на MR задачи** хранится в БД (`store.py`/`schema.py`) парой
    (`iid`, `web_url`) и показывается в `status`, `report`, `watch` и на
    доске; ссылка в БД — источник истины о MR.
15. **В `awaiting_human`** `approve`, `reject`, `answer` отказывают с
    подсказкой «состояние ждёт людей проекта — mr-sync (шаг Б2.2)»; пульт
    ничего не отправляет в ветку задачи и не меняет MR.
16. Запрет отправки — в единой точке отправки `orchestrator/gitcmd.py`:
    отправка ветки задачи в `awaiting_human` отказывается до вызова git с
    именованной причиной для любого пути, в том числе `amend-tests`
    (`amend.py:834`).
17. **`kill` задачи с `target-human`**, ветка которой отправлена (в любом
    состоянии после первой отправки): ветку на сервере не удаляет, MR не
    закрывает (при любом хостинге), убирает только рабочую копию и пишет
    ссылку на MR в журнал.
18. Приложением PLAN к `tests/test_invariants.py` (защищённый путь):
    `FSM_STATES` (`tests/test_invariants.py:78`, `:611`, обходы `:1003`/
    `:1019`) с `awaiting_human`.
19. **Существующие тесты** — по мандату Оператора 26.10 (без ослабления),
    только строки с перечнями состояний:
    - `tests/test_auto_cycle.py:64-66` — кортеж `FSM_STATES`: добавить
      `"awaiting_human"`;
    - `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_board_model.py:192-199` —
      помощник `expected_waiting`: ветка `awaiting_human` → `"human"`.
    Правка других существующих тестов — эскалация. Правка — добавление
    элемента в кортеж и ветки в помощник, не смена скалярного литерала
    утверждения, поэтому раздела «Меняемое поведение» нет.

Поддержка `target-human` в тестах — подменой
`targets.SUPPORTED_MERGE_GATES`/`SUPPORTED_FORGES` внутри теста;
состояние `awaiting_human` — прямой установкой в песочнице.

## Критерии приёмки

AC-1. Функция чтения полей доставки `targets.py` по записи без
`policy.max_awaiting`, `policy.awaiting_holds_zones`, `policy.draft_mr`
даёт 3, `true`, `true` (умолчания одной функцией); `max_awaiting` ≤ 0 или
не целое, `awaiting_holds_zones` не bool — отказ загрузки записи с
именованной причиной.

AC-2. Запись с `policy.mr_assignee` `"alice"` и с `mr_assignee: 42`
загружается без отказа.

AC-3. `awaiting_human` нет в `fsm.APPROVE_NEEDS_SHA`, нет в
`fsm.SET_MODELS_STATES` и нет среди ключей `config.STATE_ROLE` — по
утверждению на каждый перечень.

AC-4. В `awaiting_human` `approve`, `reject`, `answer` отказывают с
подсказкой «состояние ждёт людей проекта — mr-sync (шаг Б2.2)».

AC-5. Отправка ветки задачи в `awaiting_human` через единую точку
`gitcmd.py` отказана с именованной причиной; путь `amend-tests` по задаче
в `awaiting_human` отказан; шпион git не видит вызова отправки.

AC-6. `auto` по задаче в `awaiting_human` останавливается без алерта.

AC-7. Зоны задачи в `awaiting_human` держатся (вторая задача с
пересекающейся зоной получает отказ занятости) при
`awaiting_holds_zones: true` и свободны при `false`.

AC-8. Задача, зависящая по `merge_after` от задачи в `awaiting_human`,
ждёт `done` зависимости.

AC-9. Модель доски по задаче в `awaiting_human` даёт `waiting_on:
"human"`.

AC-10. `report`, `watch` и `status` по задаче в `awaiting_human`
показывают состояние `awaiting_human` и ссылку на MR из БД; `status` не
помечает её «ЖДЁТ ОПЕРАТОРА».

AC-11. Надзор эпика по задаче в `awaiting_human` не перезапускает её, не
считает её в лимите параллельности эпика и показывает статус «ждёт людей
проекта».

AC-12. Эскалация из `awaiting_human` возвращает задачу в
`awaiting_human`.

AC-13. `kill` задачи с `target-human` в каждом из состояний после первой
отправки ветки — `verifying`, `review`, `acceptance`, `merge_gate`,
`awaiting_human`, `escalated`: шпион argv `gitcmd.git`/`gitcmd.in_repo`
не видит отправки с `--delete`, в журнале задачи нет записи «отправка
отказана», MR не закрыт, рабочая копия убрана, ссылка на MR — в журнале.
Проверяется в вариантах `forge: gitlab` и `forge: github` с
`target-human` (PR не закрыт).

AC-14. `doctor` не проверяет свежесть ветки задачи в `awaiting_human`.

## Оценка объёма и деление

Сработавшие сигналы: файлов зоны ≥ 5 (16 модулей `orchestrator/`
поимённо и `tests/`); критериев приёмки ≥ 10 (14); `budget_usd` ≥ $30
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
поля `policy` (требование 1–2), ссылка на MR (требование 14) и `kill`
(требование 17), но каждый из этих кусков проверяется лишь на задаче в
`awaiting_human` и в одиночку не мержим с осмысленной планкой.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| `FSM_STATES` в `tests/test_invariants.py:78` (+ обходы `:1003`, `:1019`) — приложением PLAN | Свипы инвариантов по всем состояниям; сверка с `fsm.STATES` — `tests/test_invariants.py:611` | остаётся, строже (свип покрывает новое состояние) | `tests/test_invariants.py:611` после приложения | ок |
| `FSM_STATES` в `tests/test_auto_cycle.py:64-66` (+ `"awaiting_human"`) | Полнота `AUTO_STOP` и свипы `tests/test_auto_cycle.py` | остаётся (утверждения не меняются, `awaiting_human` уходит в `AUTO_STOP`) | `tests/test_auto_cycle.py` + AC-6 | ок, мандат 26.10 |
| `expected_waiting` в `tests/test_01m5tbbdfs6dwqy6ms263t1kpy_board_model.py:192-199` (+ ветка `awaiting_human` → `"human"`) | `waiting_on` для каждого состояния — тест того же файла | остаётся, строже (новое значение для нового состояния) | тот же файл + AC-9 | ок, мандат 26.10 |
| `zone_lock.BLOCKING_STATES` + `awaiting_holds_zones: false` | Зона занята до `done` — `zone_lock.py:110` | осознанно ослабляется полем по ADR-0029 п. 2 (умолчание — держит) | AC-7 | ок по ADR |
| `kill` для `target-human`: ветка на сервере и MR не трогаются | Уборка хвостов — `cleanup.py` | исчезает для `target-human` по ADR-0029 / ADR-0003 п. 7 | AC-13 | ок по ADR |
| Отказ отправки ветки в `awaiting_human` в `gitcmd.py` | Белый список отправок `gitcmd._whitelist_refusal` (`gitcmd.py:625`) | остаётся, строже (новый отказ сверх белого списка) | AC-5 | ок |
| `doctor` свежесть ветки без `awaiting_human` | `doctor/branch_freshness.py:40` | остаётся для прочих неокончательных состояний; для `awaiting_human` исчезает по ADR-0029 п. 2 | AC-14 | ок по ADR |

## Не входит

- Путь входа в `awaiting_human` с гейта мержа, `max_awaiting` на гейте,
  черновой MR через `forge`, `max_in_flight` (часть 2 родителя).
- `mr-sync` и закрытие задачи по вливанию MR (Б2.2).
- Хук `pre-push`, прочие строки `doctor` (кроме свежести ветки
  `awaiting_human`), подмодуль, открытие
  `targets.SUPPORTED_FORGES`/`SUPPORTED_MERGE_GATES` в коде (Б2.3).
- `full_suite` (В1), `verify` (В2); блок `COMPONENT_FIELDS` в
  `targets.py` держит В1.
- Зелёность существующих тестов для проектов с `operator` без правки,
  кроме двух мест мандата (требование 19), — её держит пульт (полный
  зелёный `tests/` и гейт неослабления).

## Материалы

- ТЗ: `tasks/01M5XZ9Z68V75VXF5Z66C708T4/TZ.md`.
- SPEC родителя: `refs/artifacts/01M5XXA2HY73D3WTXDR19Z5SWW`,
  `tasks/01M5XXA2HY73D3WTXDR19Z5SWW/SPEC.md` (требования 1, 2, 3, 8, 9,
  10, 11; разделы «Деление», «Матрица неослабления»).
- ADR-0029 (`docs/adr/0029-external-delivery-via-mr.md`) п. 1, 2, 12;
  ADR-0003 п. 7–8.
- Запись журнала «ветка отправлена» — `gitcmd.PUSH_SENT_ACTION`
  (`gitcmd.py:176`).
