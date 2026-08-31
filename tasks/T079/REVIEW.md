---
task: T079
type: review
author_role: reviewer
status: approved        # draft | approved | changes_requested | escalate
iteration: 2
schema_version: 2    # версия формата артефакта, см. scripts/guard.py
---

# REVIEW: B1b: GitHub-адаптер, Draft-MR и состояние verifying

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (Draft MR на первый вход в in_dev, один на цикл) | Реализовано верно | Замечание 1 итерации 1 закрыто: `_maybe_ensure_draft_mr` теперь стоит на всех 8 фактических точках входа в `in_dev` — проверено построчно (`grep -n 'set_state(conn, task_id, "in_dev"\|back = t\[.escalated_from.\]'` даёт 8 совпадений, `grep -n '_maybe_ensure_draft_mr'` — 8 вызовов, каждый привязан к своему `set_state`/ветке `back == "in_dev"`, включая корректно исключённые ветки — возврат из эскалации не в `in_dev` (fsm.py:1333) и эскалацию по лимиту приёмки (fsm.py:1377-1380), которые узел заводить не должны). Идемпотентность несёт `draft_mr_created` в `github_adapter.ensure_draft_mr`. |
| 2 (undraft на входе в merge_gate) | OK | Не тронуто этой итерацией; подтверждено повторным прогоном `UndraftMrTest`. |
| 3 (merge — побочный эффект локального push, не API-вызов) | OK | Не тронуто этой итерацией. |
| 4 (verifying между review и acceptance) | Реализовано верно, с открытой эскалацией (не закрывает вердикт) | Не тронуто этой итерацией; конфликт с `tests/test_invariants.py` (3 теста) остаётся тем же, что и в итерации 1 — подтверждён повторным прогоном, корректно проанализирован в PLAN «Эскалация», решение за Оператором. |
| 5 (четыре исхода статуса CI в verifying) | OK | Не тронуто этой итерацией. |
| 6 (потолок ожидания → escalated) | OK | Не тронуто этой итерацией. |
| 7 (красный CI не выталкивает автоматически) | OK | Не тронуто этой итерацией. |
| 8 (reject расширен на verifying) | OK | Не тронуто этой итерацией. |
| 9 (механизм периодического вызова advance вне объёма) | OK | Не тронуто этой итерацией. |

## Замечания

Замечаний нет. Замечание 1 итерации 1 (major, два пропущенных входа
в `in_dev`) закрыто классово, а не точечно: `orchestrator/fsm.py:1333-1334`
(возврат из `escalated`, только когда `back == "in_dev"`) и
`orchestrator/fsm.py:1386` (`reject` из `acceptance`, ветка «лимит не
исчерпан») — две новые точки; уже стоявшие в итерации 1
`orchestrator/fsm.py:1358, 1371` (`reject` из `merge_gate`/`verifying`)
не тронуты. Регресс на оба новых места и их отрицательные соседние
ветки — `tests/test_fsm_draft_mr_reentry.py` (5 тестов, включая
проверку, что возврат из эскалации в состояние, отличное от `in_dev`,
и эскалация по лимиту приёмки узел НЕ зовут).

Замечание 2 итерации 1 (minor, гонка `gh pr create` на «уже
существует») этой итерацией не закрывалось — ожидаемо: minor не
блокирует, PLAN на него не ссылается как на закрытое, узкий случай
покрыт инцидент-алертом и не ломает FSM.

## Вердикт

approved — замечание 1 (major) итерации 1 закрыто полностью на всех
8 точках входа в `in_dev`, регресс есть, полный юнит-сьют и локед
acceptance_tests зелёные (кроме заранее эскалированного и
проанализированного конфликта с `tests/test_invariants.py`,
не входящего в объём «исправь и подай снова» — решение за Оператором,
см. «Эскалация» в PLAN.md, актуальна без изменений с итерации 1).

## Проверено исполнением

- `git log --oneline -5` / `git status` — ветка чистая, коммит
  `c167c55` («T079: закрыт REVIEW замечание 1 — Draft MR на всех
  входах в in_dev») поверх `d5fb77b` (REVIEW итерации 1).
- Прочитан `orchestrator/fsm.py` целиком вокруг всех 8 точек входа
  в `in_dev` (строки 835-848, 925-940, 1115-1123, 1260-1271,
  1300-1335, 1347-1386) — каждый вызов `_maybe_ensure_draft_mr`
  привязан к правильному `set_state`/условию, отрицательные ветки
  (возврат эскалации не в `in_dev`, эскалация по лимиту приёмки)
  корректно его не зовут.
- `grep -n 'set_state(conn, task_id, "in_dev"\|back = t\[.escalated_from.\]' orchestrator/fsm.py`
  — 8 совпадений; `grep -n '_maybe_ensure_draft_mr' orchestrator/fsm.py`
  — 9 строк (1 определение + 8 использований в перечисленных местах)
  — построчное соответствие подтверждено (см. «Соответствие SPEC»,
  требование 1).
- `python3 -m unittest discover -s tests` — 1068 тестов, 3 красных
  (`test_invariants.CountersNeverResetTest::
  test_no_transition_of_the_full_cycle_resets_a_counter`,
  `test_invariants.FreshVerdictGuardsAcceptanceTest::
  test_escalation_and_return_do_not_make_the_verdict_fresh`,
  `test_invariants.FreshVerdictGuardsAcceptanceTest::
  test_every_return_to_dev_requires_a_new_verdict`) — список идентичен
  заявленному в PLAN.md и итерации 1, новых красных нет.
- `python3 -m unittest tests.test_fsm_draft_mr_reentry tests.test_merge_lock tests.test_advance_guard`
  — 23/23 зелёные (5 новых регресс-тестов на оба закрытых пробела +
  их отрицательные ветки; T052/T053 не задеты, AC-13).
- `cd tasks/T079/acceptance_tests && python3 -m unittest discover -s . -p "test_*.py"`
  — 19/19 зелёные (AC-1..AC-14, включая AC-4).
- `git diff main --stat -- gates.yaml roles.yaml targets.yaml .github/ templates/ skills/ docs/invariants.md tests/test_invariants.py CLAUDE.md`
  — пусто: ни один путь `no_paths` target `artel` не тронут (AC-14).
- `python3 scripts/codebase_map.py` (регенерация вручную, изменения
  затем отменены `git checkout -- docs/codebase-map.md`) — diff свёлся
  только к строке `built_at_sha` (ветка ушла на один коммит вперёд
  после того, как карта была закоммичена вместе с ним) — содержимое
  карты без sha идентично закоммиченному, регенерация не устарела.

## Предложения системе

Нет новых сверх уже зафиксированных в PLAN.md и REVIEW.md итерации 1
(класс «промежуточное состояние ломает свипы test_invariants.py» и
класс «побочный эффект входа в состояние X не на всех фактических
путях входа» — оба уже описаны там, повторять не буду).
