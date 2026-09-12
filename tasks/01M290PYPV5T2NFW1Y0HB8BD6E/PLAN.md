---
task: 01M290PYPV5T2NFW1Y0HB8BD6E
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: `auto` после эскалации по конфликту подтяжки начинает с шага роли, не с предварительного advance

## Подход

Единый маркер эскалации, никакого нового поля задачи (`store.py` — вне
зоны задачи, `orchestrator/store.py — занят задачами 01M28NWPS3 и
01M28VZ8Q1`): `orchestrator/pull.py::_handle_merge_failure` журналирует
фиксированным текстом `PULL_CONFLICT_ROLE_STEP_MARKER` СРАЗУ после
`state -> escalated`, но только когда эскалирует именно `in_dev`
(`state == "in_dev"`) и именно по неразрешённому конфликту содержимого
(ветка после `git merge --abort`, не инцидент очистки worktree и не
авторазрешаемая `docs/codebase-map.md`) — ровно та эскалация, что описана
в требовании 1.

`orchestrator/auto.py::_role_step_since_state_entry` (требование 1,
AC-1/AC-2) читает этот маркер как исключение из уже существующего
пропуска `_ESCALATED_RETURN_DETAILS`: запись возврата `state -> in_dev`,
которой предшествовал маркер, сама становится анкером рубежа «роль ещё
не отработала шаг после возврата» — вместо того, чтобы пропускаться (как
для прочих эскалаций — провал агента/лимит, у которых своего основания
переделки нет). Гейт `_rework_gate_blocks` уже существовал и уже
обслуживает `in_dev` (SPEC 01M1RHFRQ2C0P4A57XJJ1WZV8N) — новой логики
блокировки не потребовалось, только новый повод не пропускать анкер.

Требование 2 (AC-4, стоп-кран) реализовано отдельной функцией
`_pull_conflict_marker_streak`: считает подряд идущие маркеры, сбрасывая
счёт любым переходом состояния ВНЕ пары `escalated`/`in_dev` (реальный
прогресс мимо конфликта). `_pre_advance_step`, увидев, что ИМЕННО этот
вызов `fsm.cmd_advance` только что эскалировал по маркеру И счёт достиг
2 — возвращает `Stop` с именованной причиной вместо обычного `Advanced`.
Место включения выбрано так, что единственный гарантированный шанс роли
(требование 1) всегда успевает состояться ДО того, как стоп-кран сможет
сработать: гейт (а) `_rework_gate_blocks` обязательно блокирует
предварительный advance до первого шага роли, стоп-кран (б) видит вторую
эскалацию только на ИТЕРАЦИИ ПОСЛЕ этого шага.

Требование 3 (AC-5/AC-6): единый список текстов класса «роль ещё не
закончила» физически продублирован (не импортирован) между `auto.py`
(`ROLE_NOT_FINISHED_REFUSAL_ACTIONS`, откуда его в отдельной задаче
прочитает `watch.py`) и `brief.py`
(`_ROLE_NOT_FINISHED_REFUSAL_ACTIONS`) — тем же приёмом, что уже
дублирует `REFUSAL_ACTION_PREFIX` между `store.py` и `auto.py`.
Причина не в стиле, а в топологии импортов: `orchestrator/auto.py ->
orchestrator/fsm.py -> orchestrator/review.py -> orchestrator/brief.py`
уже существует, обратный импорт `brief.py -> auto.py` замкнул бы цикл.
Заодно вынесен в именованную константу `TREE_NOT_ON_BRANCH_REFUSAL_
ACTION` ранее инлайновый литерал `_pre_advance_step` — чтобы оба списка
(`auto.py`/`brief.py`) ссылались на один и тот же текст без риска
разъехаться при будущей правке.

`fsm.py` в зоне SPEC, но правки не потребовал: `_approve_escalated`
(возврат `escalated -> in_dev`) уже безусловно общий для любого основания
эскалации, и раздел брифа «Причина возврата» (AC-3) уже несёт detail
эскалации (включая «конфликтные файлы: …») и ссылку на последний ANSWER
для ЛЮБОГО предшественника `escalated` — механика существует до этой
задачи (SPEC 01M1SAA2AZX3ERQ779QJ5TS9J4) и не требует изменения для
конкретно конфликта подтяжки, только приёмочного теста-стража (AC-3,
зелёный с рождения).

## Шаги

1. `orchestrator/pull.py`: константа `PULL_CONFLICT_ROLE_STEP_MARKER` +
   журналирование маркера в `_handle_merge_failure` при `state ==
   "in_dev"` на ветке неразрешённого конфликта содержимого.
2. `orchestrator/auto.py`: константы `TREE_NOT_ON_BRANCH_REFUSAL_ACTION`/
   `ROLE_NOT_FINISHED_REFUSAL_ACTIONS`; `_role_step_since_state_entry`
   читает маркер требования 1 как исключение из пропуска
   `_ESCALATED_RETURN_DETAILS`; `_pull_conflict_marker_streak` +
   встроенная в `_pre_advance_step` проверка требования 2 (именованный
   `Stop` вместо `Advanced` на второй подряд эскалации).
3. `orchestrator/brief.py`: `_ROLE_NOT_FINISHED_REFUSAL_ACTIONS` +
   фильтрация в `advance_refusal_history` (требование 3/AC-5/AC-6).
4. Юнит-покрытие приёмочных тестов задачи (уже поставлены test_author,
   залочены tasks/T023) — код чинится под них, без правки.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 2 |
| 2 | 2 |
| 3 | 2, 3 |
| 4 | 1, 2, 3 (ни один существующий тест не удалён/ослаблен — см. «Влияние на систему») |

## Влияние на систему

- `orchestrator/pull.py`: новая запись журнала появляется ТОЛЬКО для
  `in_dev` и ТОЛЬКО на ветке неразрешённого конфликта содержимого —
  `acceptance`/`merge_gate` (два других вызывающих `_pull_main_or_
  escalate`) и прочие исходы `Conflict` (инцидент очистки worktree,
  красные приёмочные после подтяжки) не затронуты; `evaluate()`
  возвращает тот же `Conflict(files, note)`, что и раньше, — контракт
  трёх вызывающих точек не меняется (SPEC «Материалы»).
- `orchestrator/auto.py::_role_step_since_state_entry`: новое исключение
  из пропуска `_ESCALATED_RETURN_DETAILS` срабатывает только когда
  маркер реально был журналирован между эскалацией и возвратом — для
  ЛЮБОЙ другой эскалации (провал агента, лимит, budget) поведение
  байт-в-байт прежнее (ловится регрессией `tests/test_auto_escalated_
  return_rework_gate.py`, прогнан зелёным).
- `_pull_conflict_marker_streak`/встроенная проверка в `_pre_advance_
  step`: триггерится только когда ИМЕННО текущий вызов `fsm.cmd_advance`
  только что журналировал маркер (`journaled_before` отсечка, тот же
  приём, что и у соседних функций файла) — не тянет устаревший счёт из
  несвязанного прошлого визита состояния.
- `orchestrator/brief.py::advance_refusal_history`: фильтр вычитает
  только два названных текста; отказы гейта/guard (в т.ч. с ЛЮБЫМ другим
  текстом) проходят как раньше — покрыто `test_ac6_a_real_gate_refusal_
  is_still_included`.
- Существующие тесты не ослаблены и не удалены: `tests/test_auto_cycle.py`
  (50/50), `tests/test_pull.py` (9/9), `tests/test_brief.py` (22/22),
  `tests/test_fsm_merge_conflict_note.py` +
  `tests/test_auto_escalated_return_rework_gate.py` (16/16), плюс
  `tests/test_fsm_advance_gate_framework.py`,
  `tests/test_fsm_advance_gate_smoke.py`, `tests/test_fsm_autogate.py`,
  `tests/test_fsm_branch_correct_status_reads.py`,
  `tests/test_fsm_draft_mr_reentry.py`,
  `tests/test_fsm_map_conflict_autoresolve.py`,
  `tests/test_fsm_map_regen.py`, `tests/test_fsm_merge_gate_done_
  snapshot.py`, `tests/test_fsm_merge_gate_scratch_worktree_cleanup.py`,
  `tests/test_fsm_retro.py`, `tests/test_fsm_review_rework_gate.py`,
  `tests/test_fsm_review_rework_sha_gate.py` (81/81),
  `tests/test_advance_refusal_history.py`, `tests/test_advance_guard.py`,
  `tests/test_cmd_approve_dispatch.py`, `tests/test_answer*.py` (48/48)
  — все прогнаны в шаге, зелёные. Откат — `git revert` коммита: три
  правки независимы по файлам и ортогональны существующему коду (новые
  ветки `if`, ни одна существующая проверка не тронута).
- `orchestrator/store.py`/`orchestrator/watch.py` не тронуты (вне зоны
  SPEC, «Не входит»); порядок состояний FSM не менялся.

## Риски

- Дублирование текстов класса «роль ещё не закончила» между `auto.py` и
  `brief.py` (вместо общего импорта) может разойтись при будущей правке
  одного текста без другого — компромисс топологии импортов, описан в
  комментариях обоих мест; правка text'а requires синхронной правки
  обоих модулей.

## Предложения системе

- `docs/reference/role-home/` (скил coding-standards) не описывает явно
  класс «brief.py — лист графа импортов для fsm/auto/review, но НЕ
  наоборот» — на эту задачу топология пришлось выяснять чтением кода;
  явная пометка в докстринге `orchestrator/brief.py` (уже начата этой
  задачей) сэкономила бы это будущим задачам в той же зоне.
