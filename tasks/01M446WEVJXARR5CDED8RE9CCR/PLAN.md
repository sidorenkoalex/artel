---
task: 01M446WEVJXARR5CDED8RE9CCR
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: auto — единые правила «отказ, который чинит роль → повтор шага роли»; run продвигает состояние

## Подход
- **Один перечень** — новый модуль `orchestrator/advance_gates/refusal_classes.py`:
  словарь `REFUSAL_CLASSES` «действие журнала → класс» (таблица «Перечень
  отказов» SPEC), `refusal_class(action)` с дефолтом «чинит Оператор»,
  подкласс `ROLE_NOT_FINISHED_REFUSAL_ACTIONS` и константы новых действий.
  Модуль без импортов пакета — поэтому его читают `auto.py`, `brief.py` и
  `watch.py` без цикла импорта, и три копии перечня РНЗ сведены к одной.
  Тексты, уже объявленные константами в модулях гейтов, повторены в
  перечне литералами; расхождение ловит `tests/test_refusal_classes.py`.
- **Реакция `auto`** (`auto._pre_advance_step`): возврат `True` от
  `cmd_advance` (guard) больше не останавливает цикл — отказ guard'а
  читается из журнала, как любой другой. Класс «чинит Оператор» (и
  действие вне перечня) — `Stop` с первого отказа; «чинит роль» — `None`
  (шаг роли), тот же отказ после завершённого шага той же роли в визите —
  `Stop` (`_role_step_between_repeated_refusals`, теперь для всего класса и
  всех четырёх состояний). Подкласс РНЗ из повтор-остановки исключён
  (ANSWER-1, вопрос 2 — вариант A): артефакта роли на ветке ещё нет, как у
  нежурналируемого «PLAN.md не ready». Порог холостых шагов считает и шаги
  роли на отказах «чинит роль». Исход `Refused` (холостой шаг без роли)
  больше не возникает — удалён.
- **Разделение действий** (требование 5): сбой git гейта заявки мутации →
  «переход отклонён: гейт заявки мутации — git не ответил»; рабочая копия не
  заведена/не выписана на выходе `in_dev` → «переход отклонён: рабочая копия
  задачи не готова к приёмке»; сбой git проверки долгоживущих файлов →
  «переход отклонён: долгоживущие файлы tests/ — git не ответил» (дифф, файл
  на голове, дерево main, сумма, запись перечня); перечисление ветки,
  подсчёт `ANSWER-*.md` и чтение чужого документа (SPEC.md в
  `tests_writing`, в подтяжке и при поиске планки) → «переход отклонён:
  ветка документов не прочитана» (`fsm._branch_unread_refusal`,
  `fsm._read_foreign_branch_text_or_refuse`). «Дерево не на ветке задачи»
  остаётся только за артефактом роли текущего состояния. Условия гейтов не
  менялись. Тексты новых действий содержат прежнее имя гейта —
  существующие проверки `assertIn("гейт заявки мутации", action)` остаются
  верными.
- **`run` → `advance`** (требование 6): `runner.cmd_run` возвращает `True`
  на успешном шаге (запись `agent run finished` этого вызова — не таймаут и
  не остановка потолком); новая `runner.cmd_run_and_advance` зовётся только
  из диспетчера `artel.py run` (`_cmd_run_or_detach`) и после успеха один
  раз делает `fsm.cmd_advance`, печатая исход строкой `run: advance …`.
  Шаг внутри `auto`/канарейки зовёт `cmd_run` напрямую — продвижения не
  получает.

## Шаги
1. Перечень классов, реакция `auto`, разделение действий гейтов, `run` →
   `advance`, описание в `docs/operator-session.md`, карта
   (`python3 scripts/codebase_map.py`) — сделано, код в worktree.
2. По ANSWER-1 (вопрос 1 — вариант A, мандат на ослабление шести методов):
   правка утверждений шести методов ровно как в эскалации; методы не
   удалены и не переименованы. Докстринги двух изменённых методов
   (`test_ac1_…`, `test_ac3_…`) дополнены заявкой «Ловит мутацию»
   (проверено `guard.test_functions_without_mutation_claim` против main —
   пусто). По вопросу 2 (вариант A) — причина исключения РНЗ описана в
   докстринге `refusal_classes.py` и ниже в «Влиянии на систему». Карта
   регенерирована.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1. Один перечень классов, дефолт «чинит Оператор» | 1 (`refusal_classes.py`) |
| 2. «Чинит роль» → шаг роли, отказ в брифе, повтор → остановка | 1 (`auto._pre_advance_step`) |
| 3. «Чинит Оператор» → остановка с первого отказа | 1 |
| 4. Guard артефакта — класс «чинит роль» | 1 |
| 5.1–5.4. Разделение действий | 1 (`review.py`, `acceptance.py`, `tests_writing.py`, `fsm.py`, `fsm_advance.py`, `pull.py`) |
| 6. `run` → один `advance` | 1 (`runner.cmd_run_and_advance`, `artel.py`) |
| 7. Ограничители | 1 (порог холостых шагов считает шаги роли; лимит шагов и стоп-кран конфликта подтяжки не тронуты) |
| Неослабление существующих тестов | 2 (правка шести методов по мандату ANSWER-1) |

## Влияние на систему
- Прогоны (каждый — `python3 -m pytest <файлы> -p no:cacheprovider -p timeout -o timeout=120`, передний план):
  - планка `artel.py plank-run 01M446WEVJXARR5CDED8RE9CCR` — 10 passed, код 0;
  - долгоживущие `tests/test_01m446wevjxarr5cded8re9ccr_*.py` — 11 passed;
  - `tests/test_refusal_classes.py` — 2 passed; сторож проверен мутацией
    (опечатка в литерале перечня и подмена подкласса РНЗ — оба теста
    красные), код возвращён;
  - `tests/test_invariants.py` — 73 passed (без правки файла);
  - зелёные без правок: test_canary, test_fsm_branch_correct_status_reads,
    test_branch_freshness_gate, test_pull*, test_runner_pre_step_pull,
    test_fsm_advance_gate_smoke/_framework, test_long_lived_*,
    test_fsm_advance_tests_writing_*, test_acceptance_tests_flow,
    test_analyst_role, test_advance_guard, test_answer*,
    test_artifact_escalation_marker, test_detached_cycle, test_watch,
    test_brief, test_advance_refusal_history, test_mutation_claim_gate,
    test_plan_appendix, test_stall_alerts, test_auto_escalated_return_rework_gate,
    test_test_integrity_gate, test_zones_gate, test_capacity_gate,
    test_protected_paths_gate, test_doctor, test_multitarget*, долгоживущие
    файлы прочих задач (01m3…/01m4…), test_codebase_map и др. (≈1700 тестов);
  - после правки по мандату ANSWER-1: `tests/test_auto_cycle.py` — 61
    passed; `tests/test_external_code_copy_refusal.py`,
    `tests/test_refusal_classes.py`, долгоживущие файлы задачи,
    `test_advance_refusal_history`, `test_watch`, `test_brief` — вместе
    125 passed; планка повторно — 10 passed, код 0.
- Изменённые утверждения (мандат ANSWER-1): `advance.calls` 2 → 1 в
  `test_ac1_identical_refusal_twice_in_a_row_stops_the_cycle` и
  `test_legit_first_entry_does_not_skip_the_pre_advance`; `["…гейт зон"] * 2`
  → `* 1` в `test_without_a_mandate_stops_without_running_the_role`;
  `Refused`+`Stop` → `Stop` на первом вызове в
  `test_other_in_dev_refusal_still_stops_on_the_second_repeat`; первый текст
  сценария `test_ac3_two_different_refusal_texts_do_not_stop_the_cycle` —
  «приёмочные тесты» (класс Р) вместо «рабочая копия артефактов грязная»;
  действие журнала в `test_acceptance_run_refuses_with_the_ensure_reason` —
  «переход отклонён: рабочая копия задачи не готова к приёмке».
- Исключение подкласса РНЗ («дерево не на ветке задачи», «замечания ревью
  не отработаны») из повтор-остановки (ANSWER-1, вопрос 2): эти отказы
  значат «артефакта роли на ветке ещё нет», роль законно дописывает его за
  два шага подряд, и остановка на втором таком отказе прерывала бы
  штатные итерации ревью и разработки. От кружения их держит
  `config.AUTO_STALL_STEPS_LIMIT`; четыре теста из вопроса 2 не тронуты и
  зелёные.
- Гейты и их условия не менялись; поменялись только тексты действий
  журнала у причин класса «чинит Оператор» в четырёх местах (требование 5).
  `watch` по-прежнему скрывает только два действия РНЗ — теперь из единого
  перечня.
- Канарейка: её собственная логика `_acceptance_refusal_blocks_in_dev`
  сравнивает точный текст «приёмочные тесты» и не изменилась; `auto`
  внутри канарейки теперь останавливается на отказе «чинит Оператор» с
  первого раза (раньше — со второго), `test_canary` зелёный.
- Откат — revert merge-коммита задачи; схема БД и формат журнала не
  менялись.

## Риски
- Отказ «чинит Оператор» теперь останавливает `auto` с первого раза: если в
  перечне пропущено действие, которое на деле чинит роль, цикл встанет
  раньше, чем раньше (раньше — после холостого шага). Перечень сверен с
  таблицей SPEC; сторож литералов — `tests/test_refusal_classes.py`.
- `run` теперь сам зовёт `advance`: lease берётся дважды подряд (шаг, затем
  advance) — тот же порядок, что при ручном `advance` после `run`.

## Предложения системе
- `orchestrator/advance_gates/*`: тексты действий журнала живут то
  константами модулей, то инлайн-литералами в `GateRefusal(...)` — для
  перечня классов пришлось повторять их литералами. Класс «действие
  журнала без единого имени» стоит закрыть отдельной задачей: все действия
  гейтов — константы `refusal_classes`, модули гейтов импортируют их.
