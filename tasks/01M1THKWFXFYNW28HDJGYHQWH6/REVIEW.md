---
task: 01M1THKWFXFYNW28HDJGYHQWH6
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: ADR-0014, часть 2 — однократная переоценка бюджета на PLAN

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `_apply_plan_budget` (orchestrator/fsm_advance.py:1127) поднимает потолок до значения PLAN, если оно выше текущего и `review_iters==0 and accept_rejects==0`; журнал несёт старый потолок, новый и `источник plan` (замечание ANSWER-1/2 п.2 закрыто — `test_ac1_first_submission_raises_ceiling_within_role_cap` проверяет `budget_source`, приёмочный `test_ac1_higher_plan_budget_raises_ceiling_on_first_submission` зелёный). |
| 2 | OK | `value is None` → тихий возврат без записи в журнал (`test_ac2_missing_field_leaves_ceiling_untouched`). |
| 3 | OK | `value <= old` → потолок не меняется, `detail` буквально несёт «не применён: ниже потолка» (`test_ac3_value_not_above_ceiling_journals_not_applied`). |
| 4 | OK | Оба явно названных SPEC пути закрытия канала — рост `review_iters` (возврат из ревью) и `accept_rejects` (reject приёмки) — проверены раздельно (`test_ac4_return_from_review_closes_the_channel`, `test_ac4_return_from_acceptance_reject_closes_the_channel`); см. отдельно вынесенное наблюдение о возврате из `verifying`/`merge_gate` в «Предложения системе» — эти пути SPEC не называет, и код их сознательно не закрывает (PLAN.md, раздел «Подход»), это не отклонение от требования 4 как оно буквально сформулировано. |
| 5 | OK | Потолок Оператора проверяется отдельной, независимой веткой перед применением (`test_ac5_operator_ceiling_is_not_overridden_by_plan`). |
| 6 | OK | Гейт guard (часть 1, `scripts/guard.py::_budget_usd_over_role_cap`/аналог) отказывает переходу раньше — задача не добавляет отдельной обработки, что и требуется; вторая независимая проверка внутри `budget.spec_budget` подтверждена `test_ac8a_value_above_role_cap_does_not_raise_ceiling`. |
| 7 | OK (не в код-ветке) | Формулировка инварианта 10 вынесена приложением PLAN.md («## Приложение: инвариант 10»), `docs/invariants.md` в ветке не тронут — соответствует ANSWER-1/2 п.3, `git apply --check` диффа заявлен пройденным. |
| 8 | OK, но см. замечание ниже | `PlanBudgetOneTimeReassessmentTest` (tests/test_invariants.py:1021) покрывает (a)/(b)/(c) 8 методами, все зелёные — но 5 из 8 новых тестов не несут обязательной заявки «Ловит мутацию: …» (skills/test-authoring.md), один вовсе без докстринга — см. «Замечания», R1-F1. |
| 9 | OK (не в код-ветке) | Дифф `skills/coding-standards.md` приложен в PLAN.md отдельным разделом, в ветку не попал (защищённый путь), заявлено `git apply --check` пройденным. |

## Замечания

- major — tests/test_invariants.py:1070, 1091, 1104, 1117, 1147 — 5 из 8 новых методов `PlanBudgetOneTimeReassessmentTest` не несут обязательной заявки `Ловит мутацию: …` в докстринге (skills/test-authoring.md, раздел «Чувствительность: у теста — заявленная мутация»; review-checklist.md, Фаза B п.3): `test_ac2_missing_field_leaves_ceiling_untouched` (:1070) вовсе без докстринга — прямое нарушение и «докстринг обязан описывать сценарий», и заявки мутации; `test_ac4_return_from_review_closes_the_channel` (:1091), `test_ac4_return_from_acceptance_reject_closes_the_channel` (:1104), `test_ac8b_fires_only_once_across_a_full_cycle` (:1117), `test_ac8a_value_above_role_cap_does_not_raise_ceiling` (:1147) — докстринг описывает сценарий, но без строки `Ловит мутацию: …`, поэтому ревьювер не может свериться с заявленной мутацией, а не мысленной. Предложение: добавить каждому методу явную строку `Ловит мутацию: <конкретная правдоподобная поломка>` — например, для `test_ac2` — «поле отсутствует, но код всё равно трактует `None` как валидное значение и подставляет 0»; для `test_ac4_*` — «счётчик, растущий на этом пути возврата, перестал проверяться условием `if t["review_iters"] or t["accept_rejects"]`»; для `test_ac8a` — «сравнение с `ROLE_BUDGET_CAP` снято внутри `_apply_plan_budget`, вторая линия защиты пропала»; для `test_ac8b` — «функция перестаёт проверять `review_iters`/`accept_rejects` и срабатывает на каждой сдаче».

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | fixed | tests/test_invariants.py:1070,1091,1104,1117,1147 | 5 из 8 новых тестов `PlanBudgetOneTimeReassessmentTest` не несут заявки `Ловит мутацию: …` (одна — `test_ac2_missing_field_leaves_ceiling_untouched` — вовсе без докстринга) | ревьювер не может сверить тест с заявленной мутацией — риск тавтологичных тестов остаётся неподтверждённым/неопровергнутым | fixed: всем 5 методам добавлена строка `Ловит мутацию: …` (`test_ac2_missing_field_leaves_ceiling_untouched` получил докстринг целиком, у остальных четырёх строка дописана к уже существующему); `python3 -m unittest tests.test_invariants` — 60 passed |

## Вердикт

changes_requested — единственное блокирующее замечание R1-F1: докстринги 5 новых тестов дополнить заявкой `Ловит мутацию: …` (skills/test-authoring.md). По существу код полностью соответствует SPEC (требования 1–9, включая корректно вынесенные вовне код-ветки требования 7 и 9 по ANSWER-1/2/3), приёмочная планка задачи зелёная целиком (12/12 исполняемых), regression по `tests/test_invariants.py` не обнаружен, `docs/codebase-map.md` перегенерирована и соответствует фактическому дереву импортов.

## Проверено исполнением

- `python3 -m pytest tasks/01M1THKWFXFYNW28HDJGYHQWH6/acceptance_tests/ -v` — 12 passed (планка задачи целиком, AC-1..AC-7 исполняемые методы, AC-8/AC-9 — обоснованные `manual`-пометки о размещении в защищённых файлах/применении диффа Оператором).
- `python3 -m pytest tests/test_invariants.py` — 60 passed (весь затронутый модуль, включая новый `PlanBudgetOneTimeReassessmentTest` и все ранее существовавшие классы — регрессий не внесено).
- `python3 scripts/codebase_map.py --check` — без вывода/без ошибок: карта соответствует текущему дереву импортов (сверка per skill — `built_at_sha` не учитывается как признак дефекта).
- `git diff e8cb5bc2091bfb6d7cad660236450784239689b3...HEAD -- docs/invariants.md skills/coding-standards.md` — пусто: оба защищённых файла не тронуты в код-ветке, соответствует ANSWER-1/2/3 п.3.
- Прочитаны `orchestrator/budget.py::spec_budget/apply_spec_budget` для сверки повторного использования парсера и стиля журнальных записей — расхождений с конвенцией не найдено (кроме заявленного SPEC буквально дублирования «не применён» в действии и деталях записи AC-3 — это не дефект, а буквальное требование 3).
- Прочитан `orchestrator/fsm.py::_cmd_reject` (ветки `merge_gate`/`verifying`) для проверки полноты закрытия канала переоценки по всем путям возврата в `in_dev` — путь через `verifying`-reject не растит ни `review_iters`, ни `accept_rejects`; классифицировано как осознанный, буквально соответствующий SPEC требованию 4 выбор (см. «Предложения системе»), не как блокирующее замечание.

## Предложения системе

- SPEC 01M1THKWFXFYNW28HDJGYHQWH6, требование 4, называет ровно два пути закрытия канала переоценки (возврат из ревью и из приёмки) — но `orchestrator/fsm.py::_cmd_reject` умеет ещё и возврат в `in_dev` из `verifying`/`merge_gate` (T052/T079), который ни `review_iters`, ни `accept_rejects` не трогает. Технически при ручном `reject` Оператора из `verifying` канал переоценки не закрывается, и повторная сдача PLAN с ещё большим значением может поднять потолок снова — вопреки заголовку ADR-0014 п.3 «однократная». Риск невысокий (путь требует ручного действия Оператора, у которого и так есть безусловный `budget`-оверрайд), но формулировка требования 4/ADR стоит уточнить явно на будущее: «любой возврат в in_dev» или «только эти два пути» — сейчас читается двусмысленно относительно общего свойства AC-8(b) («не более одного раза за всю жизнь задачи»).
