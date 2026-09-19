---
task: 01M2XFSJ1Z7BS6HR69SAT1D81Y
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Возврат из эскалации test_author: пред-advance не повторяет старую пометку escalate до шага роли

Пакет не нёс SPEC.md/PLAN.md (их нет в кодовой ветке — штатно, артефакты
живут в артефактной ветке); оба прочитаны из материализованного
`tasks/01M2XFSJ1Z7BS6HR69SAT1D81Y/` рабочего каталога вместе с TZ.md и
планкой `acceptance_tests/`. Прошлого REVIEW.md нет (`git log --all --
tasks/<id>/REVIEW.md` пуст) — итерация 1, инкрементальный diff = полный.

## Фаза A: гейт плана

1. Таблица покрытия полна: требования 1-6 разложены по шагам 1-5, у каждого
   AC-1..AC-7 есть тест планки (`test_ac1_ac2_…`, `test_ac3_ac4_…`,
   `test_ac5_ac6_…`, `test_ac7_…`).
2. Шаги — единицы размера одного MR (константа, три точки записи, одно
   условие в читателе, модуль тестов, регенерация карты); не
   микрооперации и не «сделать всё».
3. Подход переиспользует существующий приём `pull.PULL_CONFLICT_ROLE_STEP_
   MARKER` без переноса константы (SPEC «Не входит»); место константы в
   `fsm.py` обосновано отсутствием новых импортов — проверил: `auto.py:11`
   и `fsm_advance.py` уже импортируют `fsm`, обратного цикла нет.
   Решение не распространять стоп-кран `_pull_conflict_marker_streak` на
   новый маркер (PLAN п.4) согласуется с требованием 5/AC-5: повторная
   эскалация после шага роли легитимна и каждый круг требует ответа
   Оператора, сам по себе цикл не крутится.

Замечаний к плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (маркер в `tests_writing`) | OK | `fsm_advance.py:314-318`: `_mark_artifact_escalation` сразу после `set_state(..., "escalated")`, `detail` — текст эскалации; `fsm.py:54` — своя константа, `pull.py` не тронут (`git diff --name-only` его не содержит). Между переходом и маркером стоит только хук фиксации sha (`store.set_state`), как и у образца `pull.py:265-271`. |
| 2 (маркер в `spec_writing`) | OK | Обе ветки: ветка-источник `fsm_advance.py:104-108` и путь через диск `fsm_advance.py:128-132`; тот же helper, та же константа. |
| 3 (запись возврата за маркером — анкер) | OK | `auto.py:283-284` (`_ROLE_STEP_REQUIRED_MARKERS`), `auto.py:348-350`: единственная правка условия. Прошёл трассировку журнала инцидента руками: `state -> tests_writing` (первый вход) → `agent run finished` test_author → `state -> escalated` → маркер → `state -> tests_writing` («эскалация разрешена, продолжаем»): `role_step_required=True` на маркере, запись возврата попадает в `last_entry`, шага роли после неё нет → `(False, detail)` → `_rework_gate_blocks` держит пред-advance. `_REWORK_GATE_STATES` (`auto.py:189`) содержит и `tests_writing`, и `spec_writing`. |
| 4 (гашение первым переходом) | OK | Существующий цикл `auto.py:351-357`: сброс `role_step_required` на любой `state -> {state}` (израсходован) и на любом `state -> X`, `X` ≠ `escalated`; для нового маркера отдельного кода не нужно. Покрыто тестами `test_marker_is_consumed_by_the_first_return`, `test_marker_is_reset_by_another_state_transition`, `test_escalated_transition_between_marker_and_return_keeps_it` и планкой AC-6. |
| 5 (после шага роли — прежнее поведение) | OK | Тела `tests_writing`/`spec_writing` после точек эскалации не менялись; строки `detail` эскалаций побайтно те же (только вынесены в переменную). `_review_escalate`, `_in_dev_plan_escalate`, `_pre_advance_step` не тронуты. Планка AC-5 (оба исхода) зелёная. |
| 6 (тесты; AC-7 зелёный) | OK | Новый `tests/test_artifact_escalation_marker.py` (11 тестов, все с заявкой «Ловит мутацию»). `tests/test_auto_escalated_return_rework_gate.py` в diff отсутствует, прогнан отдельно — зелёный; `git diff -- tests/` не содержит ни одной удалённой строки. |

Сверка тестов с заявками «Ловит мутацию» — по каждому тесту нового
модуля прошёл журнал руками против заявленной мутации:

- `test_return_after_the_marker_blocks_until_the_role_step` — мутация
  «читатель знает только pull-маркер» действительно делает возврат
  пропуском, анкером остаётся первый вход, после которого шаг был →
  `ran=True`. Правдоподобно, ловится.
- `test_role_step_after_the_marked_return_unblocks` — срез
  `rows[last_entry + 1:]` перепутан → `ran=False`. Ловится.
- `test_first_spec_writing_visit_return_after_the_marker_is_an_anchor` —
  мутация «маркер учитывается только при уже существующем `last_entry`»
  → `(True, None)`. Ловится, и это единственный тест на реальную
  особенность `spec_writing` (первый вход `cmd_new` не журналирует).
- `test_return_without_a_marker_is_still_skipped` — «возврат всегда
  анкер» → `ran=False`. Ловится (то же, что AC-7 планки).
- `test_marker_is_consumed_by_the_first_return`, `…_reset_by_another_
  state_transition`, `…_escalated_transition_between_marker_and_return_
  keeps_it` — три ветки гашения, каждая мутация даёт противоположный
  `ran`. Ловятся.
- Четыре теста записи (`MarkerWrittenByTheEscalationPointsTest`) —
  мутации «маркер не пишется в tests_writing», «только в tests_writing»,
  «только на ветке-источнике, не на диске», «вынесен в общий узел
  `set_state`» — каждая проверяется своей точкой входа через настоящий
  `fsm.cmd_advance` в песочнице `AutoCycleTest`. Ловятся.

Импорт `AutoCycleTest` в новый модуль не дублирует чужие тесты: базовый
класс тестовых методов не несёт (`grep "def test_" tests/test_auto_cycle.py`
— все методы в наследниках), loader собрал ровно 11 собственных тестов.

Планка задачи: пометок `manual`/`skip` нет; AC-7 «зелёный с рождения»
обоснован в докстринге (критерий сохранения, а не появления поведения) и
сверяет имена методов на включение, не на равенство — ослабления не
вводит.

## Замечания

Замечаний нет: blocker/major не найдено, minor — тоже (два наблюдения
уровня «не дефект» вынесены в «Предложения системе»).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет — замечаний в итерации 1 не заведено.

## Корректность и целостность (Фаза B, п.2, 5, 6)

- **Граничные случаи читателя.** Хук фиксации sha (`sha зафиксирован`) и
  записи `lease` между `state -> escalated` и маркером не начинаются с
  `state -> ` и на состояние `role_step_required` не влияют. Повторная
  запись `state -> escalated` до возврата маркер сохраняет (тест есть).
  Возврат в другое состояние (`escalated_from` иной) — сброс, маркер не
  протекает на несвязанный визит (AC-6).
- **Другие читатели журнала.** Проверил всех потребителей записи
  `state -> escalated` (`brief.py:752`, `retro.py:157`, `canary.py:705`)
  и `brief.advance_refusal_history`: все фильтруют по `action` или
  префиксу «переход отклонён», ни один не читает «следующую за переходом
  строку» — новая запись с actor `fsm` для них инертна.
  `_pre_advance_step` (`auto.py:717-719`) ищет только pull-маркер среди
  строк своего вызова — новый маркер стоп-кран не задевает, что и
  заявлено PLAN п.4.
- **Стоимость.** После возврата из эскалации по содержимому цикл всегда
  тратит один шаг роли — ровно то, что требует SPEC; для эскалаций других
  классов (падение агента, лимит, бюджет) поведение прежнее (тест
  `test_return_without_a_marker_is_still_skipped`, AC-7).
- **Безопасность / защищённые пути.** Diff трогает только
  `orchestrator/{auto,fsm,fsm_advance}.py`, `tests/`, `docs/codebase-map.md`
  — совпадает с зонами SPEC (`zones:`) и с секцией PLAN «Влияние на
  систему». `ci/`, `.github/`, `gates.yaml`, `roles.yaml`, `templates/`,
  `skills/`, `pull.py`, `answer.py` не тронуты. Секретов и недоверенного
  ввода нет.
- **Неослабление.** В `tests/` — только новый файл, 0 удалённых строк;
  существующие гейты, лимиты и инварианты не менялись (инвариант 36:
  новых состояний/переходов нет). ANSWER-файлов у задачи нет.
- **Откат.** Revert одного коммита `82f33862`; старые маркеры в журналах
  становятся инертными строками — как описано в PLAN.
- **Карта.** `python3 scripts/codebase_map.py` поверх HEAD меняет только
  строку `built_at_sha` — содержимое актуально.

## Вердикт

approved

## Проверено исполнением

- `python3 -m unittest discover -s tasks/01M2XFSJ1Z7BS6HR69SAT1D81Y/acceptance_tests -p 'test_*.py'`
  — 8 тестов (AC-1..AC-7, включая вложенный прогон
  `tests/test_auto_escalated_return_rework_gate.py` внутри AC-7), OK.
- `python3 -m unittest tests.test_artifact_escalation_marker
  tests.test_auto_escalated_return_rework_gate tests.test_auto_cycle
  tests.test_pull tests.test_fsm_branch_correct_status_reads
  tests.test_acceptance_tests_flow tests.test_analyst_role
  tests.test_answer_gate tests.test_answer` — 216 тестов, OK.
- `python3 -m unittest tests.test_fsm_advance_gate_smoke
  tests.test_fsm_advance_gate_framework tests.test_brief
  tests.test_review_package` — 121 тест, OK.
- `python3 -m unittest tests.test_artifact_escalation_marker -v` — 11
  тестов, все собственные (дублей из `AutoCycleTest` нет).
- `python3 scripts/guard.py tasks/01M2XFSJ1Z7BS6HR69SAT1D81Y/SPEC.md` и
  `… PLAN.md` — «GUARD: ок (1 файлов)» оба.
- `python3 scripts/codebase_map.py` + `git diff --stat docs/codebase-map.md`
  — 1 строка (`built_at_sha`), содержимое карты совпадает; результат
  регенерации откачен `git checkout -- docs/codebase-map.md`.
- `git diff 7e1353c0...HEAD -- tests/ | grep -c '^-[^-]'` — 0 удалённых
  строк в `tests/`.
- Полный набор `tests/` в шаге не гонял (решение Оператора 05.09); CI
  коммита 82f33862 по пакету зелёный (7 проверок).

## Предложения системе

- `orchestrator/pull.py:56-59`: подтверждаю наблюдение PLAN — комментарий
  у `PULL_CONFLICT_ROLE_STEP_MARKER` ссылается на копию значения в
  `orchestrator/brief.py`, которой там нет (`grep PULL_CONFLICT
  orchestrator/brief.py` пуст). Класс «комментарий-пересказ разошёлся с
  кодом»; вне зоны задачи, править здесь нельзя.
- `scripts/codebase_map.py`: поле «Назначение» берёт первую строку
  докстринга и режет её на переносе — у нового модуля получилось
  «…артефакта роли (SPEC» с незакрытой скобкой (`docs/codebase-map.md`,
  секция `tests/test_artifact_escalation_marker.py`). Не дефект задачи
  (генератор общий), но читается как обрыв; стоит резать по концу
  предложения или первому абзацу.
