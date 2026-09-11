---
task: 01M1SHJX22EMEP4AJ9FFJJ09DC
type: review
author_role: reviewer
status: approved
iteration: 3
schema_version: 5
---

# REVIEW: approve без набора sha: сверка фиксации механикой; перечитывание budget_usd на гейте SPEC

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (confirm_fixation сверяет живой sha с `tasks.fixed_sha` на 4 гейтах) | OK | Без изменений с итерации 2 — `orchestrator/fsm.py:530-600`; сама сверка не тронута этой итерацией (диф итерации — только докстринги тестов + подтяжка main). `test_ac2_matching_fixation_auto_confirms.py` — 2/2 (прогнано лично). |
| 2 (явный `approve <id> <sha>` — прежняя семантика) | OK | Ветка `sha is not None` (`orchestrator/fsm.py:601-615`) не тронута; `test_ac4_explicit_sha_semantics_unchanged.py` — 3/3, `tests/test_git_fixation.py` — 41/41 (прогнано лично). |
| 3 (удаление строки «sha только копированием» из `docs/operator-session.md`, диффом-приложением) | OK | Строка на месте в файле (сейчас `docs/operator-session.md:137-138` — сдвинулась после подтяжки main с внешней задачей 01M1VBEKRN, содержимое не менялось: `git diff origin/main -- docs/operator-session.md` пуст). Дифф-приложение PLAN.md (хедер хунка `@@ -130,8 +130,6 @@`) перепроверен `git apply --check` на текущем HEAD — применяется чисто, несмотря на сдвиг (context-based match, git apply нашёл контекст). |
| 4 (approve на spec_gate перечитывает `budget_usd` и применяет `apply_spec_budget`) | OK | Без изменений по существу с итерации 2 — `orchestrator/budget.py:53-109`, `orchestrator/fsm.py:672` (вызов внутри `_approve_spec_gate`, перенесённой R3-декомпозицией). Код прочитан заново после подтяжки main — идентичен описанному в PLAN. |
| 5 (журнал при изменении потолка, без дублей при совпадении) | OK | Без изменений — см. 4; `test_ac8_*` — 2/2 (прогнано лично). |
| 6 (инвариант 25, `docs/invariants.md`) | OK (осознанно не в этой задаче) | Без изменений — `git diff origin/main -- docs/invariants.md` пуст (ANSWER-3 исполнена), AC-9 `manual` легитимен. |

## Замечания

Новых замечаний нет. Единственное открытое замечание прошлой итерации (R2-F1) закрыто по существу — см. реестр.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/budget.py:91-103 | `apply_spec_budget` не перечитывала изменённое значение из SPEC при `budget_source=spec` | Требование 4/5 не работало для мотивирующего сценария SPEC | Закрыто в итерации 2, подтверждено повторным чтением кода в этой итерации — без изменений. |
| R1-F2 | accepted | orchestrator/fsm.py:591-599 | Подсказка повтора при расхождении sha называла зафиксированный (`fixed`) sha вместо живого (`current`) | Подсказанная команда детерминированно проваливалась повторно | Закрыто в итерации 2, подтверждено повторным чтением кода в этой итерации — без изменений. |
| R1-F3 | accepted | tests/test_git_fixation.py, tests/test_spec_budget.py | Новая логика не имела постоянного покрытия в `tests/` | Регрессия не ловилась бы после исчезновения эфемерной `acceptance_tests/` | Закрыто в итерации 2, подтверждено прогоном (`test_git_fixation.py` 41/41, `test_spec_budget.py` 46/46) в этой итерации. |
| R2-F1 | accepted | tests/test_git_fixation.py:909,936; tests/test_spec_budget.py:545 | Три из четырёх новых постоянных тестов (закрывающих R1-F3) были без обязательной строки `Ловит мутацию: …` в докстринге | Ревьювер/будущий читатель не мог сверить тест с заявленной мутацией без чтения кода теста | Проверено чтением коммита `7c664ee1`: все три докстринга получили строку `Ловит мутацию: …` с конкретной правдоподобной мутацией (`{fixed or current}` вместо `{current}`; пропуск проверки `clean`; `source is not None` вместо `source == BUDGET_SOURCE_SPEC and value == old`) — формулировки соответствуют предложенным ревьювером, код тестов не менялся. Прогон подтверждает: тесты по-прежнему зелёные. Замечание закрыто, `fixed -> accepted`. |

Реестр закрыт целиком (все записи `accepted`) — гейт `review -> verifying` пройдёт.

## Вердикт

approved — все требования SPEC выполнены и подтверждены прогоном; реестр замечаний закрыт целиком (R2-F1 переведён в `accepted`, R1-F1/F2/F3 остаются `accepted` без изменений); блокеров и major-замечаний нет.

Отдельно проверено расхождение пакета ревью: инкрементальный diff в присланном пакете показал «изменений нет», потому что sha предыдущего вердикта (f6149604) совпал с текущим HEAD ветки — тот же класс несовпадения базы сравнения, что описан в skills/review-checklist.md (T087). Фактические изменения этой итерации (коммит `7c664ee1` — докстринги R2-F1; коммит `f6149604` — подтяжка main, слияние с внешней задачей 01M1VBEKRN) найдены и проверены вручную через `git log`/`git show`/`git diff origin/main...HEAD`.

## Проверено исполнением

- `python3 -m unittest tests.test_git_fixation -v` — 41/41 OK.
- `python3 -m unittest tests.test_spec_budget -v` — 46/46 OK.
- `python3 -m unittest tests.test_cmd_approve_dispatch tests.test_zones_approve tests.test_fsm_advance_gate_smoke tests.test_invariants -v` — 64/64 OK (включает `SpecCeilingRespectsRoleBudgetCapTest` и `InvariantsTableWellFormedTest`).
- `python3 -m unittest discover -s tasks/01M1SHJX22EMEP4AJ9FFJJ09DC/acceptance_tests -p "test_ac*.py" -v` — 16/16 OK (все исполняемые критерии планки; AC-5/AC-9 — manual с обоснованием, без изменений с итерации 1).
- `python3 scripts/guard.py tasks/01M1SHJX22EMEP4AJ9FFJJ09DC/PLAN.md tasks/01M1SHJX22EMEP4AJ9FFJJ09DC/SPEC.md` — ок.
- `git apply --check` на извлечённом из PLAN.md unified-диффе `docs/operator-session.md` (файл-черновик создан во временной директории рабочего каталога и удалён `git clean -f` сразу после проверки) — применяется чисто на текущем HEAD.
- `git diff origin/main -- docs/operator-session.md` и `git diff origin/main -- docs/invariants.md` — оба пусты (требования 3 и 6 подтверждены).
- `git diff origin/main...HEAD --stat` — только `docs/codebase-map.md`, `orchestrator/budget.py`, `orchestrator/fsm.py`, `tests/test_git_fixation.py`, `tests/test_spec_budget.py`: соответствует зоне SPEC, посторонних файлов нет; подтверждает, что подтяжка main (`f6149604`) не оставила конфликтов/хвостов.
- `git show 7c664ee1 -- tests/test_git_fixation.py tests/test_spec_budget.py` — фактический фикс-коммит R2-F1, три докстринга с `Ловит мутацию: …` подтверждены построчно.
- `python3 scripts/codebase_map.py` — прогнан для проверки свежести: диф только в строке `built_at_sha` (законное отставание, скил review-checklist), содержимое идентично; изменение отменено `git checkout -- docs/codebase-map.md`.
- Полный набор `tests/` не гонял (запрещено скилом ревьювера — гоняет CI; CI коммита f6149604 зелёный, 14 проверок, согласно пакету).

## Предложения системе

- Класс «sha предыдущего вердикта пакета ревью совпадает с текущим HEAD, инкрементальный diff пустой при фактических изменениях» подтверждён третий раз подряд на этой же задаче (после T082/T087) — стоит чинить построение sha пакета на стороне оркестратора, а не полагаться на то, что каждый ревьювер вручную перепроверит `git log`/`git show`.
