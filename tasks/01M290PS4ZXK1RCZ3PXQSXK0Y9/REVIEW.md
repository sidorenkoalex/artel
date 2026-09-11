---
task: 01M290PS4ZXK1RCZ3PXQSXK0Y9
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: lease — перехват мёртвого держателя на своём хосте без ожидания порога протухания

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (AC-1) — немедленный перехват мёртвого pid на своём host, независимо от возраста heartbeat | OK | `orchestrator/lease.py:95-104,118-120,129,146-155` — `pre_row`/`dead_on_own_host` вычисляются, ветка `if not dead_on_own_host` пропускает отказ и проваливается к перехвату. Юнит-тест `tests/test_lease.py:120` и приёмочный `tasks/.../acceptance_tests/test_ac1_ac8_dead_pid_immediate_intercept.py` зелёные. |
| 2 (AC-3/AC-4/AC-5) — порог остаётся единственным основанием для живого pid на своём host и для любого чужого host | OK | Ветка `dead_on_own_host` строго требует `row["hostname"] == hostname`, поэтому для чужого host не срабатывает никогда (AC-4/AC-5 не тронуты); для живого pid на своём host отказ прежний (AC-3). Существующий тест `test_intercept_of_foreign_host_keeps_the_heartbeat_cause` не менялся и зелёный; новый `test_live_pid_on_own_host_with_fresh_heartbeat_still_refuses` (`tests/test_lease.py:143`) подтверждает AC-3. Приёмочный `test_ac3_ac4_ac5_refusal_paths_unchanged.py` зелёный. |
| 3 (AC-6) — гонка двух перехватчиков одного мёртвого lease: один перехват, второй — именованный отказ, без второй записи журнала | OK | CAS-приём через `pre_row`, снятый ДО `BEGIN IMMEDIATE` (`orchestrator/lease.py:95-104,129-141`) — корректно отличает «я видел мёртвого держателя до входа в блокировку, а сейчас держатель другой живой» от честного продления. Юнит-тест `tests/test_lease.py:644` и locked-приёмочный `test_ac6_concurrent_intercept_race.py` зелёные (прогнаны локально, см. «Проверено исполнением»). |
| 4 (AC-7) — доктор подсказывает про самостоятельный перехват | OK (вне кода этой ветки, как и требует SPEC) | `orchestrator/doctor/leases.py` — вне зон задачи (занят 01M28VZ8Q1), правка оформлена unified-диф приложением в PLAN.md. `git apply --check` на текущем HEAD (403f8c8f) подтверждён локально — патч применяется чисто. Приёмочная пометка `# AC-7: manual` в `test_ac7_doctor_hint_manual.py` обоснована зоной конфликта, тот же протокол, что уже применялся в двух прежних задачах (ссылки в комментарии файла) — легитимно. |
| 5 (AC-9) — существующие тесты lease/doctor не ослаблены | OK | Diff `tests/test_lease.py` — только добавления (новые методы), ни один существующий ассерт/сценарий не тронут и не удалён. Регрессионные прогоны (`tests/test_lease.py`, `tests/test_doctor.py -k lease`, `tests/test_budget_live_lease_and_escalation.py`, плюс смежные `pause`/`kill`/`release`/`workspace`/`auto_cycle`) зелёные. Пометка `# AC-9: skip` в приёмочном легитимна — дублирующий прогон полного `tests/` уже даёт CI (класс «ci-covered»). |

## Замечания

- major — `tests/test_lease.py:143`, `tests/test_lease.py:216`, `tests/test_lease.py:644` — три из четырёх новых тестовых метода (`test_live_pid_on_own_host_with_fresh_heartbeat_still_refuses`, `test_intercept_of_dead_pid_on_this_host_with_fresh_heartbeat_names_the_cause`, `test_concurrent_acquire_of_dead_pid_own_host_exactly_one_intercepts`) не несут в докстринге обязательную заявку `Ловит мутацию: …` (skills/test-authoring.md, «Чувствительность: у теста — заявленная мутация»; review-checklist прямо требует «заявки нет вовсе → замечание»). Только `test_dead_pid_on_own_host_is_intercepted_immediately_even_when_fresh` (`tests/test_lease.py:120`) содержит такую заявку. Без неё ревьювер и последующие читатели не могут сверить, действительно ли тест ловит правдоподобную мутацию, а не исполняет ритуал покрытия — сверить осталось только моим собственным мысленным мутационным тестом (см. проверку ниже), что и есть тот самый обходной путь, который скилл запрещает. Предложение: дописать в каждый из трёх докстрингов конкретную мутацию, например: для `test_live_pid_on_own_host_with_fresh_heartbeat_still_refuses` — «Ловит мутацию: если `dead_on_own_host` перестанет проверять `liveness._pid_alive` и полагаться только на `hostname == hostname`, живой держатель на своём host будет ошибочно перехвачен вместо отказа»; для `test_intercept_of_dead_pid_on_this_host_with_fresh_heartbeat_names_the_cause` — «Ловит мутацию: если причина перехвата для немедленного пути (fresh heartbeat) по ошибке возьмётся из ветки „heartbeat протух“ вместо `dead_on_own_host`, текст записи журнала не будет содержать „мёртв“»; для `test_concurrent_acquire_of_dead_pid_own_host_exactly_one_intercepts` — «Ловит мутацию: если новый путь перехвата (`dead_on_own_host`) выполнит `update_lease`/`journal` вне блокировки `BEGIN IMMEDIATE` или без сверки `pre_row`, конкурентный прогон даст больше одной записи „lease перехвачен“».

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | fixed | tests/test_lease.py:143, tests/test_lease.py:216, tests/test_lease.py:644 | три новых теста без заявки `Ловит мутацию: …` в докстринге | нарушение обязательной конвенции skills/test-authoring.md — чувствительность тестов к правдоподобным мутациям не задекларирована и не проверяема формально | fixed: в докстринги всех трёх методов дописана строка `Ловит мутацию: …` с конкретной мутацией (те же формулировки, что предложены в замечании) — `tests/test_lease.py -q` 36 passed после правки |

## Вердикт

changes_requested — единственное препятствие: R1-F1 (три новых юнит-теста без обязательной заявки `Ловит мутацию: …`). Логика перехвата (AC-1..AC-6), причины и формат записи журнала, разграничение своего/чужого host, приоритет `same_host_ok`/`force`, приёмочные тесты и регрессия — без замечаний.

## Проверено исполнением

- `python3 -m pytest tests/test_lease.py -q` — 36 passed.
- `python3 -m pytest tasks/01M290PS4ZXK1RCZ3PXQSXK0Y9/acceptance_tests/ -q` — 8 passed (включая locked `test_ac6_concurrent_intercept_race.py`).
- `python3 -m pytest tests/test_budget_live_lease_and_escalation.py -q` — 15 passed.
- `python3 -m pytest tests/test_doctor.py -q -k "lease or Lease"` — 14 passed, 112 deselected.
- `python3 -m pytest tests/test_pause.py tests/test_pause_now.py tests/test_kill_cleanup.py tests/test_kill_live_cycle_refusal.py tests/test_release.py tests/test_workspace.py tests/test_auto_cycle.py -q` — 137 passed, 28 subtests passed.
- `git apply --check` для unified-диффа `orchestrator/doctor/leases.py` (приложение PLAN.md) на текущем HEAD (403f8c8f) — успех, патч применяется чисто.
- `python3 scripts/codebase_map.py` (регенерация на HEAD) — расхождение только в строке `built_at_sha` (текущая vs пересобранная), содержимое карты идентично; изменение не закоммичено обратно (сверка, не правка).
- Полный набор `tests/` не запускался (штатно гоняется CI на каждый пуш; CI коммита 403f8c8f — зелёный, 7 проверок).

## Предложения системе
