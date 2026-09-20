---
task: 01M2YWRB9HWW99R57HWGP2M7MQ
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: reject на гейте SPEC: возврат аналитику с причиной, гейт переделки и бриф «Причина возврата»

Итерация 1. SPEC.md и PLAN.md в пакете не показаны («не существует в
ветке задачи») — они живут в артефактной ветке, прочитаны оттуда:
`git show artifact/01m2ywrb9hww99r57hwgp2m7mq:tasks/<id>/SPEC.md` и
`…/PLAN.md` (те же тексты лежат материализованными в рабочем каталоге
шага). Diff пакета (910ee62e…HEAD) полон: у задачи один кодовый коммит
8f92006d, `git log --oneline` это подтверждает.

## Фаза A: гейт плана

1. Таблица покрытия полна: требования 1–9 разложены по шагам 1–4,
   каждое требование имеет адресата (требование 6 — честно расписано на
   «форма detail» + «закрепление тестом», а не на правку `auto.py`).
2. Шаги — единицы размера MR (ветка команды, перечень брифа, абзац
   документации, тесты + карта), без микроопераций и без «сделать всё».
   Монолит обоснован: части по отдельности дают рабочую команду с
   неработающим циклом переделки — проверено по коду, `_rework_gate_
   blocks` зовёт только `_cmd_auto`, и без анкера пред-advance вернул бы
   задачу на гейт по тому же отклонённому SPEC.
3. Подход не конфликтует с конвенциями и архитектурой: четвёртая ветка в
   уже ветвящейся `_cmd_reject` тем же приёмом, что T052/T079; перечень
   по целевому состоянию в `brief.py` вместо общего `_RETURN_TRIGGER_
   STATES` — обоснование в PLAN п. 3 верно, проверено сценарием approve
   `spec_gate -> tests_writing`/`in_dev`.
4. «Влияние на систему» сверено с фактическим diff: затронуты ровно
   `orchestrator/fsm.py`, `orchestrator/brief.py`,
   `docs/operator-gates.md`, три файла `tests/`, `docs/codebase-map.md`
   (COMMON_ZONES). `orchestrator/auto.py`, `fsm_advance.py`,
   `artifact_branch.py`, `templates/SPEC.md` не тронуты, как заявлено;
   защищённых путей и файлов `tasks/` в кодовом коммите нет (`git diff
   --name-only 910ee62e..HEAD -- skills/ templates/ gates.yaml
   roles.yaml .github/ tasks/` — пусто). Откат — revert одного коммита,
   путь описан.

Неточность PLAN о `budget_usd` — в реестре (R1-F1), на решение по плану
не влияет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (`reject` на `spec_gate` → `spec_writing`, detail «возврат из spec_gate: <причина>») | OK | `orchestrator/fsm.py:919–950`: `store.set_state(..., "spec_writing", "operator", expected_state=state, detail=f"возврат из spec_gate: {reason}")` — та же форма, что у веток `merge_gate`/`verifying`. Прогон планки AC-1 и юнита `test_reject_on_spec_gate_returns_the_task_to_the_analyst` зелёные; свой прогон сценария (песочница планки) дал `spec_writing` и ровно одну запись перехода |
| 2 (счётчики не растут) | OK | Ветка стоит ДО `if state != "acceptance"` (fsm.py:951), до `rejects = t["accept_rejects"] + 1` исполнение не доходит; `review_iters` не трогается никем на этом пути. Юнит `…keeps_both_counters` берёт ненулевые (2, 1) — нули не отличили бы «сохранено» от «обнулено» |
| 3 (`zones`/`budget_usd` отклонённого SPEC не пишутся) | OK | В ветке нет ни `update_task(zones=…)`, ни `apply_spec_budget`. Проверено прогоном полного пути (advance → гейт → reject): `zones` остаётся `None`, `budget_usd` — тем же значением, что было до команды. Комментарий к ветке при этом описывает происхождение `budget_usd` неточно — R1-F1 |
| 4 (пустая причина — отказ команды) | OK | `if not reason.strip(): sys.exit(...)` до любой записи журнала (fsm.py:941–943); `artel.py:807` подставляет `""`, когда аргумент не передан, — путь живой, не теоретический. Юнит гоняет обе формы (`""` и `"  \t "`) с проверкой «состояние прежнее, записи перехода нет»; lease при `sys.exit` отпускается `finally` в `lease.run_locked:356–360` — залипания нет |
| 5 (бриф analyst несёт причину; штатный approve — не возврат) | OK | `brief.py:60` `_RETURN_TRIGGER_STATES_BY_TARGET = {"spec_writing": frozenset({"spec_gate"})}`, применён в `_return_context:755`. Запись `spec_gate -> spec_writing` создаёт ТОЛЬКО эта ветка reject (`grep '"spec_writing"' orchestrator/` — других писателей нет), так что расширение не ловит чужих переходов. Штатный `spec_gate -> tests_writing`/`in_dev` разделa не даёт (юнит `…unchanged_on_the_approve_out_of_spec_gate`, планка AC-6) |
| 6 (гейт переделки: анкер до шага analyst) | OK | detail «возврат из spec_gate: …» не входит ни в `_ESCALATED_RETURN_DETAILS`, ни в `_LEGIT_FIRST_ENTRY_DETAILS`/`_PREFIXES` (auto.py:250–257, 281–282), значит становится анкером `_role_step_since_state_entry`; `spec_writing` уже в `_REWORK_GATE_STATES`. Обе половины закреплены юнитами и планкой AC-7 (прогон `auto.cmd_auto`: шаг analyst раньше записи `state -> spec_gate`) |
| 7 (остальные состояния — как сегодня) | OK | Ветки `acceptance`/`merge_gate`/`verifying` в diff не изменены ни на строку; проверка причины живёт внутри ветки `spec_gate`. Юниты `…reason_is_required_only_on_the_spec_gate` (пустая причина у трёх соседей по-прежнему проходит) и `…neighbour_returns_keep_their_outcome_and_detail` (свой detail у каждого), плюс планка AC-5. Финальный отказ остался тем же именованным отказом, перечисление пополнено `spec_gate` — иначе текст печатал бы Оператору неправду |
| 8 (`docs/operator-gates.md`) | OK | `docs/operator-gates.md:85–97`: форма команды, порядок «`reject` → `auto` → аналитик переписывает SPEC → новый `approve`», предупреждение «сам по себе отказ задачу не двигает», редактура сохранена как законный ход с границей «одну-две строки». Планка AC-8 зелёная |
| 9 (тесты покрывают 1–7; соседние зелёные) | OK | Новый `tests/test_fsm_spec_gate_reject.py` (8 методов), +2 метода в `test_brief.py`, +2 в `test_auto_escalated_return_rework_gate.py`. Diff `tests/` — только добавления (`git diff … -- tests/ \| grep -c '^-[^-]'` → 0), ни один существующий `assert` не тронут. 168 тестов затронутых модулей зелёные, CI коммита зелёный (7 проверок) |

Карта свежая: `python3 scripts/codebase_map.py` даёт отличие только в
строке `built_at_sha` (не дефект, T053/T072); файл возвращён
`git checkout`.

## Замечания

- minor — `orchestrator/fsm.py:927–930` и `tasks/01M2YWRB9HWW99R57HWGP2M7MQ/PLAN.md:26` —
  комментарий ветки утверждает, что `tasks.zones` и `budget_usd`
  «читает и применяет только `_approve_spec_gate`», а «принятыми
  остаются значения последней редакции, которую Оператор действительно
  принял». Для `zones` это верно, для `budget_usd` — нет:
  `orchestrator/fsm_advance.py:143` зовёт `budget.apply_spec_budget` на
  переходе `spec_writing -> spec_gate`, то есть потолок ОТКЛОНЁННОЙ
  редакции уже записан в колонку до гейта и после `reject` остаётся в
  силе. Проверено прогоном: SPEC с `budget_usd: 51` → advance печатает
  «бюджет из SPEC: $51.00», колонка 51.0 → `reject` → колонка 51.0,
  `zones` по-прежнему `None`. Сценарий последствия: следующий читатель
  этого узла (например, задача про перечитывание зон/потолка, П3
  бэклога) опирается на комментарий и считает, что после возврата в
  `spec_writing` действует потолок последней ПРИНЯТОЙ редакции, хотя
  шаг analyst идёт под потолком отклонённой. На требование 3 и AC-3 это
  не влияет — оба говорят «значения равны тем, что были до команды», и
  они равны. Предложение (правки кода не требует): сузить фразу до
  `zones` и назвать `fsm_advance.spec_writing` вторым местом применения
  потолка — при ближайшей правке этого узла.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/fsm.py:927–930; tasks/01M2YWRB9HWW99R57HWGP2M7MQ/PLAN.md:26 | комментарий ветки и PLAN называют `_approve_spec_gate` единственным местом применения `budget_usd`, хотя потолок пишет ещё и `fsm_advance.spec_writing:143` на входе в гейт | читатель узла решит, что после возврата действует потолок принятой редакции, а действует потолок отклонённой (проверено прогоном: 51.0 до и после `reject`) | minor, только текст комментария/плана: поведение соответствует требованию 3 и AC-3, кода правка не требует. Закрыто ревьювером на месте (тот же приём, что R2-F1/R2-F2 ревью 01M2XJKKPHM5XDAE42838AMBQH) — `accepted`, чтобы гейт `review -> verifying` не отклонил `approved` |

## Вердикт

approved — требования 1–9 реализованы, блокирующих и major-замечаний
нет. Ветка `spec_gate` стоит до счётчиков приёмки и ничего не пишет в
`zones`/`budget_usd`, отказ на пустую причину случается до единой записи
журнала и не держит lease, перечень брифа расширен по целевому
состоянию (штатный approve с гейта разделa возврата не даёт), анкер
гейта переделки работает формой detail, соседние ветки `reject` не
тронуты, планка и тесты затронутых модулей зелёные. Единственное
замечание — minor по точности комментария, закрыт на месте.

## Проверено исполнением

Рабочий каталог `.artel/worktrees/01M2YWRB9HWW99R57HWGP2M7MQ`, HEAD
8f92006d, Python 3.13.

- `python3 -m pytest tasks/01M2YWRB9HWW99R57HWGP2M7MQ/acceptance_tests
  -p no:cacheprovider -q` — 18 passed, 10 subtests passed. Пометок
  `# AC-n: manual|skip` в планке нет (`grep -rn "manual\|skip"` — одно
  упоминание, в докстринге AC-9); AC-9 помечен `ci` — честный класс
  «полный набор `tests/` гоняет CI на каждый пуш», автогейт приёмки не
  выключает.
- `python3 -m pytest tests/test_fsm_spec_gate_reject.py tests/test_brief.py
  tests/test_auto_escalated_return_rework_gate.py tests/test_auto_cycle.py
  tests/test_invariants.py tests/test_fsm_draft_mr_reentry.py -q` — 168
  passed, 251 subtests passed, 117 с. (инвариант 7 и соседние ветки
  `_cmd_reject` — здесь).
- `python3 -m pytest tests/test_zone_lock.py tests/test_cmd_approve_dispatch.py
  tests/test_advance_refusal_history.py -q` — 48 passed, 10 subtests:
  проверял подозрение, что новая запись `state -> spec_writing` сдвинет
  «момент approve» в `zone_lock._approve_marker_id` (он якорится на
  ПОСЛЕДНЮЮ `state -> spec_gate`, запись возврата остаётся до неё —
  влияния нет) и блок «история отказов advance» в брифе (отказ рубежа
  уже отфильтрован `_ROLE_NOT_FINISHED_REFUSAL_ACTIONS`).
- Свой прогон в песочнице планки (`_sandbox.SpecGateRejectSandbox`):
  (а) полный путь `advance` → гейт → `reject` — до advance `(zones=None,
  budget=50.0)`, на гейте `(None, 51.0)`, после reject `spec_writing,
  (None, 51.0)` — основание R1-F1; (б) задача БЕЗ `TZ.md` (роли analyst
  у `spec_writing` нет, `runner.step_role` → None): после reject
  `auto.cmd_auto` не уводит задачу обратно на гейт, а честно встаёт
  («auto остановлен: SPEC ещё пишется») — проверял, не обходится ли
  рубеж переделки в этой конфигурации; не обходится.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md`
  — единственное отличие в строке `built_at_sha`; файл возвращён
  `git checkout`.
- `git diff 910ee62e..HEAD -- tests/ | grep -c '^-[^-]'` → 0 (ни одной
  удалённой строки тестов); `git diff --name-only 910ee62e..HEAD --
  skills/ templates/ gates.yaml roles.yaml .github/ tasks/` — пусто.
- Сверка заявок «Ловит мутацию»: 12 новых тестов (`tests/
  test_fsm_spec_gate_reject.py` — 8, `test_brief.py` — 2,
  `test_auto_escalated_return_rework_gate.py` — 2), у каждого заявка и
  описанный сценарий; правдоподобие проверял по коду — заявка про
  «ветка поставлена ПОСЛЕ проверки `state != acceptance`» бьёт по
  fsm.py:951, заявка про общий `_RETURN_TRIGGER_STATES` — по brief.py:50.
- Чтение по коду: `grep -rn '"spec_writing"' orchestrator/` (единственный
  писатель перехода из `spec_gate` — новая ветка), `lease.run_locked`
  (release в `finally` — `sys.exit` lease не залипает),
  `config.COMMON_ZONES` (карта — общая зона, вне зон SPEC законно).

## Предложения системе

- Ревью-пакет четвёртый раз подряд не показывает SPEC/PLAN: он ищет их
  в КОДОВОЙ ветке задачи, где артефактов не бывает по
  01M1NKTF173WV5CPDZ1C3WW69K. Класс уже записан в скил про
  инкрементальный diff (T082, T087) и в «Предложения системе» ревью
  01M2XJKKPHM5XDAE42838AMBQH; адрес прежний — сборщик пакета должен
  читать `tasks/<id>/SPEC.md`/`PLAN.md` из артефактной ветки
  (`artifact_branch.branch_name`), а не из ветки задачи.
