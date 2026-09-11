---
task: 01M1THKWFXFYNW28HDJGYHQWH6
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: ADR-0014, часть 2 — однократная переоценка бюджета на PLAN

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `_apply_plan_budget` (orchestrator/fsm_advance.py:1127) поднимает потолок до значения PLAN, если оно выше текущего и `review_iters==0 and accept_rejects==0`; журнал несёт старый потолок, новый и `источник plan` (`config.BUDGET_SOURCE_PLAN`, orchestrator/config.py:185) — не изменилось с итерации 1. |
| 2 | OK | `value is None` → тихий возврат без записи в журнал (`test_ac2_missing_field_leaves_ceiling_untouched`). |
| 3 | OK | `value <= old` → потолок не меняется, `detail` несёт «не применён: ниже потолка» (`test_ac3_value_not_above_ceiling_journals_not_applied`). |
| 4 | OK | Оба явно названных SPEC пути закрытия канала (возврат из ревью → `review_iters`, reject приёмки → `accept_rejects`) проверены раздельно (`test_ac4_return_from_review_closes_the_channel`, `test_ac4_return_from_acceptance_reject_closes_the_channel`); наблюдение о непокрытом `reject` из `verifying`/`merge_gate` оставлено ниже в «Предложения системе» (перенесено из итерации 1 — код не менялся). |
| 5 | OK | Потолок Оператора проверяется отдельной, независимой веткой перед применением (`test_ac5_operator_ceiling_is_not_overridden_by_plan`). |
| 6 | OK | Гейт guard (часть 1) отказывает переходу раньше — задача не добавляет отдельной обработки; вторая независимая проверка внутри `budget.spec_budget` подтверждена `test_ac8a_value_above_role_cap_does_not_raise_ceiling`. |
| 7 | OK (не в код-ветке) | Формулировка инварианта 10 остаётся приложением PLAN.md («## Приложение: инвариант 10»); `docs/invariants.md` в ветке не тронут (`git diff main...HEAD -- docs/invariants.md` пусто) — соответствует ANSWER-1/2 п.3. AC-7 исполняется тремя методами `test_ac7_invariant_wording.py`, четвёртый (`test_ac7_invariant_ten_names_plan_as_a_channel`) — легальный `# AC-7: manual` по ANSWER-3 (amend-tests Оператора). |
| 8 | **OK, замечание R1-F1 закрыто** | `PlanBudgetOneTimeReassessmentTest` (tests/test_invariants.py:1021) покрывает (a)/(b)/(c) 8 методами, все зелёные. Все 8 методов теперь несут докстринг с заявкой `Ловит мутацию: …` (диф b079525b..964e3435 добавил заявку 5 оставшимся методам) — проверено построчно, каждая заявка называет конкретную правдоподобную поломку кода (`value is None` guard, условие `review_iters or accept_rejects`, сравнение с `ROLE_BUDGET_CAP`) и соответствует тому, что реально проверяет ассерт метода. |
| 9 | OK (не в код-ветке) | Дифф `skills/coding-standards.md` приложен в PLAN.md, в ветку не попал (`git diff main...HEAD -- skills/coding-standards.md` пусто) — соответствует ANSWER-1/2/3 п.3. |

## Замечания

<Пусто при аппруве — блокирующих и существенных находок в этой итерации нет.>

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | tests/test_invariants.py:1070,1091,1104,1117,1147 (было) | 5 из 8 новых тестов `PlanBudgetOneTimeReassessmentTest` не несли заявки `Ловит мутацию: …` | ревьювер не мог сверить тест с заявленной мутацией | закрыто: диф b079525b..964e3435 добавил заявку всем 5 методам; сверено построчно — каждая заявка называет конкретную строку/условие кода (`value is None`, `if t["review_iters"] or t["accept_rejects"]`, сравнение с `ROLE_BUDGET_CAP`) и соответствует ассертам теста; `python3 -m pytest tests/test_invariants.py` — 60 passed |

## Вердикт

approved — замечание R1-F1 предыдущей итерации закрыто по существу (все 8 методов `PlanBudgetOneTimeReassessmentTest` несут содержательную заявку `Ловит мутацию: …`), новых blocker/major находок в этой итерации нет. Код полностью соответствует SPEC (требования 1–9, включая корректно вынесенные вовне код-ветки требования 7 и 9 по ANSWER-1/2/3), приёмочная планка задачи зелёная целиком (12/12 исполняемых методов, 2 легальных `manual`-маркера по ANSWER-1/2/3), regression по `tests/test_invariants.py` не обнаружен, `docs/codebase-map.md` свежая, защищённые файлы (`docs/invariants.md`, `skills/coding-standards.md`) не тронуты в код-ветке.

## Проверено исполнением

- `python3 -m pytest tests/test_invariants.py -q` — 60 passed, 215 subtests passed (117.23s) — весь затронутый модуль, включая `PlanBudgetOneTimeReassessmentTest` и все ранее существовавшие классы; регрессий не внесено.
- `python3 -m pytest tasks/01M1THKWFXFYNW28HDJGYHQWH6/acceptance_tests/ -v` — 12 passed (25.73s) — планка задачи целиком, AC-1..AC-7 исполняемые методы зелёные.
- `python3 scripts/codebase_map.py --check` — без вывода/без ошибок: карта соответствует текущему дереву импортов.
- `git diff main...HEAD --stat` — только `docs/codebase-map.md`, `orchestrator/config.py`, `orchestrator/fsm_advance.py`, `tests/test_invariants.py` (232 insertions, 4 deletions) — совпадает с шагами PLAN и разделом «Влияние на систему», side effects вне заявленной зоны нет.
- `git diff main...HEAD -- docs/invariants.md skills/coding-standards.md` — пусто: оба защищённых файла не тронуты в код-ветке, соответствует ANSWER-1/2/3 п.3.
- Инкрементальный diff пакета (964e3435..HEAD) был пуст, потому что sha предыдущего вердикта в пакете совпал с текущим HEAD (964e3435 — это и есть коммит фикса R1-F1, о котором REVIEW.md итерации 1 ещё не знал); по инструкции скила «Инкрементальный diff… пустой не значит без изменений» нашёл фактический коммит вердикта итерации 1 (`git log -- tasks/.../REVIEW.md` на артефактной ветке → 8077d41a) и сверил дифф b079525b..964e3435 вручную построчно (30 строк tests/test_invariants.py) — это и есть фактическая правка этой итерации.
- Прочитан `orchestrator/fsm_advance.py::_apply_plan_budget` (:1127-1181) для проверки, что каждая заявка `Ловит мутацию:` соответствует реальной строке кода — 4 из 5 заявок описывают наблюдаемый эффект мутации точно; у `test_ac2_missing_field_leaves_ceiling_untouched` формулировка «потолок был бы тихо обнулён» неточна (при снятии проверки `value is None` код попадёт в ветку `value <= old` и оставит `budget_usd` прежним, но добавит запись в журнал — тест это всё равно ловит через `assertEqual(self.journal_actions(), [])`, просто не через «обнуление»); признано редакционной неточностью, не дефектом теста — тест валиден, мутацию из своей же заявки фактически отклоняет, доводить до отдельного замечания/новой итерации не стал.

## Предложения системе

- SPEC 01M1THKWFXFYNW28HDJGYHQWH6, требование 4, называет ровно два пути закрытия канала переоценки (возврат из ревью и из приёмки) — `orchestrator/fsm.py::_cmd_reject` умеет ещё и возврат в `in_dev` из `verifying`/`merge_gate`, который ни `review_iters`, ни `accept_rejects` не трогает (перенесено из итерации 1 без изменений — код не менялся, наблюдение остаётся в силе). Риск невысокий (путь требует ручного действия Оператора, у которого и так есть безусловный `budget`-оверрайд), но формулировку требования 4/ADR стоит уточнить явно на будущее.
- Гейт `_registry_gate` (orchestrator/fsm_advance.py:245) блокирует `approved` при ЛЮБОЙ записи реестра со статусом, отличным от `accepted`, независимо от severity записи — формально это означает, что даже чисто-minor находка, оформленная как «Замечание» с id в реестре, вынуждает ещё одну итерацию ревью, хотя раздел «Вердикт» скила прямо разрешает «0 blocker/major → approved» без оглядки на minor. В этой итерации я обошёл трение, не заведя реестровую запись под редакционную неточность (см. «Проверено исполнением») — но это решение на усмотрение ревьювера, не правило; стоит явно прописать в review-checklist.md, обязана ли minor-находка заводить блокирующую запись реестра или нет.
