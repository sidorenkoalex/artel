---
task: 01M1VBEDGMEXHVGWAH42FTDZ4X
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: budget под живым шагом и возврат из эскалации без холостого шага роли

## Соответствие SPEC

Фаза A (гейт плана, в одном прогоне с ревью MR): PLAN.md покрывает все
три требования таблицей «Покрытие требований», подход точечный (три
независимых узла, без нового состояния FSM/колонок БД), не
конфликтует с конвенциями — гейты через существующий каркас
`_run_gates`, keyword-only параметр с безопасным дефолтом, отложенный
импорт по образцу `lease.warn_foreign_live`. Отдельно зафиксирован и
корректно разрешён конфликт подтяжки main (ADR-0015, ANSWER-1) —
проверено: `_origin_push_gate`/`is_canary` вызываются только в
`in_dev()` (fsm_advance.py:1180-1181), в `review()` не дублируются;
новый гейт вставлен ровно в место, указанное ANSWER-1.

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (budget под живым lease) | OK | AC-1..4, AC-10, AC-11 — тесты `tests/test_budget_live_lease_and_escalation.py` + приёмочные AC-1..4/10/11, все зелёные; `same_host_ok=True` передаёт только `budget.cmd_budget`, 9 остальных вызывателей `run_locked`/`acquire` не тронуты (проверено grep). |
| 2 (рубеж «возврат не отработан») | OK | AC-5..7, AC-12, AC-13 — `_ESCALATED_RETURN_DETAILS` покрывает оба известных текста возврата (`fsm.py`/`budget.py`), unit- и приёмочные тесты зелёные, мутационный AC-13 подтверждён отдельным сценарием. |
| 3 (budget-эскалация из review, sha) | OK, см. замечание R1-F1 | Поведение реализовано верно (эмпирически проверено отключением гейта — AC-15 корректно краснеет), но конкретный тест AC-9 (ручной advance) НЕ ловит заявленную мутацию — см. «Замечания». |
| AC-16 (регресс) | OK | Прогнаны `test_budget*`, `test_lease`, `test_auto_cycle`, `test_fsm_review_rework_gate`, гейт-сьюты — без правки утверждений, все зелёные (см. «Проверено исполнением»). |

## Замечания

- major — `tasks/01M1VBEDGMEXHVGWAH42FTDZ4X/acceptance_tests/test_ac8_ac9_ac14_ac15_review_verdict_sha.py:93-112` (тест `test_ac9_manual_advance_does_not_reach_verifying_on_changed_sha`, класс `ChangedShaBlocksTheTransitionTest`) — докстринг заявляет «Ловит мутацию: требование 3 не реализовано вовсе — advance доведёт задачу до `verifying`», но фактическая проверка `self.assertNotEqual(self.state(), "verifying")` этой мутации не ловит. Эмпирически проверено: временно убрал вызов `_review_escalation_sha_gate` из `fsm_advance.py::review()` (единственная точка отказа требования 3) и перезапустил файл теста — AC-9 остался зелёным (AC-15, интеграционный дубль в том же файле, при этом корректно покраснел, как и должен). Причина: assertion унаследована из порядка состояний ДО подтяжки main (ADR-0015), когда approved review вёл прямиком в `verifying`; после подтяжки approved review ведёт в `acceptance` (`fsm_advance.py:280`, `_review_approved`), поэтому без гейта состояние становится `acceptance`, а не `verifying`, — «не verifying» проходит тривиально и ничего не проверяет по существу. Файл — зафиксированная приёмочная планка (лок `a77a7e0f`, применена через `amend-tests`/ADR-0012 по ANSWER-2), и именно ЭТОТ конкретный тест не был поправлен при том аменде (соседние AC-8/AC-14 корректно проверяют `state == "acceptance"`). Последствие: если гейт `_review_escalation_sha_gate` в будущем случайно сломается на самом ручном пути `advance` (а не только на пути `auto`), тест AC-9 регресс не заметит — сработает только AC-15, который проверяет другое свойство (`agent.calls`), не итоговое состояние. Предложение: запросить у Оператора ещё один `amend-tests` (со ссылкой на ADR-0012) с заменой assertion на `self.assertEqual(self.state(), "review", "переход в acceptance не должен был случиться — гейт обязан отказать")` — это действительно проверяет «гейт держит задачу в review», а не побочный факт «конечное состояние не называется verifying».

- minor — `orchestrator/fsm_advance.py:220` (докстринг `_review_escalation_sha_gate`: «не должна пропускать переход в `verifying`») и тот же класс формулировок в `tasks/01M1VBEDGMEXHVGWAH42FTDZ4X/acceptance_tests/test_ac8_ac9_ac14_ac15_review_verdict_sha.py:3-4,19-27,67-68,71-73` — текст устарел после разрешения конфликта подтяжки main: фактически (см. `_review_approved`, `fsm_advance.py:280`) approved review теперь ведёт в `acceptance`, и гейт защищает переход `review -> acceptance`, а не `review -> verifying`. PLAN.md сам фиксирует, что «имя цели уточнено после подтяжки main» (раздел «Влияние на систему»), но правка не попала в сам докстринг кода. Не блокирует поведение (гейт работает верно), но собьёт с толку следующего читателя. Предложение: заменить «verifying» на «acceptance» в перечисленных докстрингах при следующей правке этих файлов.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | tasks/01M1VBEDGMEXHVGWAH42FTDZ4X/acceptance_tests/test_ac8_ac9_ac14_ac15_review_verdict_sha.py:93-112 | AC-9 не ловит заявленную мутацию требования 3 (assertion унаследована из порядка состояний до ADR-0015) | регресс гейта на ручном пути advance останется незамеченным этим тестом | новый amend-tests (ADR-0012): assertEqual(state(), "review") вместо assertNotEqual(state(), "verifying") |
| R1-F2 | open | orchestrator/fsm_advance.py:220 и test_ac8_ac9_ac14_ac15_review_verdict_sha.py (докстринги) | докстринги называют целью перехода `verifying`, фактически — `acceptance` (после ADR-0015) | вводит в заблуждение будущего читателя, не влияет на поведение | поправить формулировку на `acceptance` |

## Вердикт

changes_requested — один major (R1-F1: тест AC-9 не ловит заявленную
мутацию требования 3, нужен ещё один `amend-tests` со ссылкой на
ADR-0012) и один minor (R1-F2: устаревшая формулировка «verifying» в
докстрингах после переезда ADR-0015). Сама механика требований 1-3
реализована верно и покрыта тестами корректно в остальных случаях —
после правки R1-F1 (и по желанию R1-F2) задача готова к аппруву без
дальнейшего разбора логики.

## Проверено исполнением

- `python3 -m unittest tests.test_budget_live_lease_and_escalation tests.test_auto_escalated_return_rework_gate tests.test_fsm_review_rework_sha_gate -v` — 33 теста, все зелёные.
- `python3 -m unittest discover -s tasks/01M1VBEDGMEXHVGWAH42FTDZ4X/acceptance_tests -v` — 16 из 16 зелёных (планка задачи, лок a77a7e0f).
- `python3 -m unittest tests.test_fsm_review_rework_gate tests.test_advance_guard tests.test_review_freshness tests.test_review_registry_gate tests.test_zones_gate tests.test_capacity_gate tests.test_branch_freshness_gate tests.test_verifying_ceiling tests.test_cmd_approve_dispatch tests.test_fsm_advance_gate_smoke tests.test_fsm_advance_gate_framework -v` — 94 теста, все зелёные (регресс гейтов `fsm_advance.py`, AC-16).
- `python3 -m unittest tests.test_lease tests.test_step_cost tests.test_spec_budget tests.test_auto_cycle -v` — 173 теста, все зелёные (регресс `lease.py`/`budget.py`/`auto.py`, AC-16).
- Мутационная проверка вручную (не автоматизирована, только для этого ревью): временно заменил тело `if status == "approved": if _run_gates(...): return False` в `orchestrator/fsm_advance.py::review()` на no-op, прогнал `tasks/.../test_ac8_ac9_ac14_ac15_review_verdict_sha.py` — AC-15 покраснел (ожидаемо), AC-9 остался зелёным (находка R1-F1); файл возвращён `git checkout -- orchestrator/fsm_advance.py`, `git status` подтвердил чистое дерево до и после эксперимента.
- `python3 scripts/codebase_map.py` — сверил регенерацию: `git diff docs/codebase-map.md` расходится только строкой `built_at_sha` (не признак дефекта, см. скил), содержимое совпадает; изменение отменено `git checkout -- docs/codebase-map.md`, чтобы не коммитить побочный артефакт ревью.
- `git diff --stat c0bd6b901ba6330887e02c3cba28b67ae6298d44...HEAD -- . ':!tasks'` — изменены только файлы заявленной зоны (`orchestrator/{budget,lease,fsm_advance,auto}.py`, `docs/codebase-map.md`, три новых `tests/test_*.py`); `fsm.py` в зоне, но не тронут — не нарушение (зона разрешает, не обязывает).
- CI коммита dc305890 — зелёный (14 проверок), по данным ревью-пакета; повторный прогон полного `tests/` в шаге ревью не делал (решение Оператора 05.09 — гоняет CI на каждый пуш).

## Предложения системе

- Класс «докстринг/приёмочный тест несёт словесный остаток старого
  порядка состояний FSM после ADR, который его переставил» — уже
  отмечен в PLAN.md этой задачи («Предложения системе») применительно
  к самой планке; в этом ревью тот же класс всплыл ещё раз — в
  докстринге кода (`fsm_advance.py:220`) И в конкретной assertion
  (R1-F1), а не только в тексте. Стоит завести чек-лист-пункт для
  ролей после разрешения конфликта подтяжки, затронувшего порядок
  состояний: искать не только буквальные имена состояний в
  assertion'ах (что уже поймано amend'ом), но и *семантику* негативных
  проверок вида "не оказался в состоянии X" — такая проверка тихо
  теряет силу, если X перестаёт быть достижимым путём вообще, независимо
  от того, сработал ли защищаемый гейт.
