---
task: 01M290PS4ZXK1RCZ3PXQSXK0Y9
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: lease — перехват мёртвого держателя на своём хосте без ожидания порога протухания

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (AC-1) — немедленный перехват мёртвого pid на своём host, независимо от возраста heartbeat | OK | `orchestrator/lease.py:95-104,118-129,146-155` — `pre_row`/`dead_on_own_host` вычисляются, ветка `if not dead_on_own_host` пропускает отказ и проваливается к перехвату. Юнит-тест `tests/test_lease.py:128` и приёмочный `test_ac1_ac8_dead_pid_immediate_intercept.py` зелёные. |
| 2 (AC-3/AC-4/AC-5) — порог остаётся единственным основанием для живого pid на своём host и для любого чужого host | OK | Ветка `dead_on_own_host` строго требует `row["hostname"] == hostname`, для чужого host не срабатывает никогда (AC-4/AC-5); для живого pid на своём host отказ прежний (AC-3, `tests/test_lease.py:151`). Существующий `test_intercept_of_foreign_host_keeps_the_heartbeat_cause` не менялся и зелёный. Приёмочный `test_ac3_ac4_ac5_refusal_paths_unchanged.py` зелёный. |
| 3 (AC-6) — гонка двух перехватчиков одного мёртвого lease: один перехват, второй — именованный отказ, без второй записи журнала | OK | CAS-приём через `pre_row`, снятый ДО `BEGIN IMMEDIATE` (`orchestrator/lease.py:95-104,129-141`) отличает «перехвачено кем-то другим в промежутке» от честного продления живой сессией. Юнит-тест `tests/test_lease.py:660` и locked-приёмочный `test_ac6_concurrent_intercept_race.py` зелёные. |
| 4 (AC-7) — доктор подсказывает про самостоятельный перехват | OK (вне кода этой ветки, как и требует SPEC) | `orchestrator/doctor/leases.py` не тронут в diff (проверено: `git diff --stat main...HEAD -- orchestrator/doctor/leases.py` пуст) — вне зон задачи, занят 01M28VZ8Q1. Unified-диф приложением в PLAN.md; `git apply --check` на текущем HEAD (ae9e82de) подтверждён мной локально — применяется чисто. Пометка `# AC-7: manual` обоснована зоной конфликта. |
| 5 (AC-9) — существующие тесты lease/doctor не ослаблены | OK | `git diff main...HEAD -- tests/test_lease.py` — только добавления новых методов плюс смена базового класса `ResolveSessionIdTest` (унаследовано от слитой чужой ветки, не от этой задачи, докстринг объясняет причину); ни один существующий ассерт не тронут. Регрессионные прогоны — зелёные (см. «Проверено исполнением»). |

## Замечания

(пусто — R1-F1 закрыто, новых замечаний нет)

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | tests/test_lease.py:151, tests/test_lease.py:228, tests/test_lease.py:660 | три новых теста без заявки `Ловит мутацию: …` в докстринге | нарушение обязательной конвенции skills/test-authoring.md | Проверено: все три метода (`test_live_pid_on_own_host_with_fresh_heartbeat_still_refuses:154`, `test_intercept_of_dead_pid_on_this_host_with_fresh_heartbeat_names_the_cause:233`, `test_concurrent_acquire_of_dead_pid_own_host_exactly_one_intercepts:666`) несут конкретную, правдоподобную заявку `Ловит мутацию: …`, совпадающую по существу с предложенными формулировками; `tests/test_lease.py -q` — 36 passed. Закрыто. |

## Вердикт

approved — единственное замечание прошлой итерации (R1-F1) устранено и подтверждено; логика перехвата (AC-1..AC-6), причины и формат записи журнала, разграничение своего/чужого host, приоритет `same_host_ok`/`force`, зона `doctor/leases.py` (не тронута, диф-приложение применяется чисто), приёмочные тесты и регрессия — без замечаний.

Дополнительно вне прямого diff задачи, но в ветке: коммит `ac130b53` («живой pid (os.getpid()) в фикстурах чужого lease своего хоста») чинит хрупкость фикстур `tests/test_budget_live_lease_and_escalation.py`/`tests/test_detached_cycle.py` (жёстко зашитый pid 999, не существующий на CI-Linux, ложно считался мёртвым новой веткой перехвата) — проверил построчно: сценарии (foreign live lease своего/чужого host, force-перехват) не изменены, только pid заменён на заведомо живой `os.getpid()`; тесты остаются тем же самым свойством, что и раньше.

## Проверено исполнением

- `python3 -m pytest tests/test_lease.py -q` — 36 passed.
- `python3 -m pytest tasks/01M290PS4ZXK1RCZ3PXQSXK0Y9/acceptance_tests/ -q` — 8 passed (включая locked `test_ac6_concurrent_intercept_race.py`).
- `python3 -m pytest tests/test_budget_live_lease_and_escalation.py tests/test_detached_cycle.py -q` — 43 passed.
- `python3 -m pytest tests/test_doctor.py -q -k "lease or Lease"` — 14 passed, 112 deselected.
- `python3 -m pytest tests/test_pause.py tests/test_pause_now.py tests/test_kill_cleanup.py tests/test_kill_live_cycle_refusal.py tests/test_release.py tests/test_workspace.py tests/test_auto_cycle.py -q` — 137 passed, 28 subtests passed.
- `git apply --check` для unified-диффа `orchestrator/doctor/leases.py` (приложение PLAN.md, извлечён скриптом из блока ```diff```) на текущем HEAD (ae9e82de) — успех, применяется чисто.
- `python3 scripts/codebase_map.py` (регенерация на HEAD) — расхождение только в строке `built_at_sha` (ac130b53 → ae9e82de, ожидаемо, HEAD ушёл на подтяжку main без правки `*.py` в зонах задачи); содержимое карты идентично; изменение файла не оставлено (`git checkout -- docs/codebase-map.md`).
- `git diff main...HEAD -- orchestrator/doctor/leases.py` — пусто (файл вне зоны задачи не тронут, как требует SPEC).
- `git diff main...HEAD -- tests/test_lease.py` — только добавления методов, ни один существующий сценарий не удалён/смягчён (сверка diff, не только пересказ).
- Полный набор `tests/` не запускался (штатно гоняется CI на каждый пуш; CI коммита ae9e82de — зелёный, 7 проверок, см. «Статус CI» пакета).

## Предложения системе
