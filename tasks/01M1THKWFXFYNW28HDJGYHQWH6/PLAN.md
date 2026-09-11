---
task: 01M1THKWFXFYNW28HDJGYHQWH6
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: ADR-0014, часть 2 — однократная переоценка бюджета на PLAN

## Подход
Канал переоценки живёт в `orchestrator/fsm_advance.py::in_dev`, тем же
местом в последовательности, каким `budget.apply_spec_budget` стоит
перед `spec_gate` в `spec_writing` — потолок применяется прямо перед
переходом в `verifying`, до того как задача продолжит тратить деньги.

Однократность держится на `t["review_iters"] == 0 and
t["accept_rejects"] == 0` (новая функция `_apply_plan_budget`,
`orchestrator/fsm_advance.py:1127`) — БЕЗ новой колонки БД. Оба
счётчика уже существуют и уже никогда не сбрасываются (docs/invariants.md,
инвариант 4): `review_iters` растёт на возврате из ревью
(`changes_requested`, `_review_changes_requested`), `accept_rejects` —
на возврате из приёмки (`reject`, `fsm.py::_cmd_reject`, ветка `state ==
"acceptance"`) — оба и есть единственные два пути, которыми требование 4
явно называет закрытие канала («из ревью... или из приёмки»). Reject из
`verifying`/`merge_gate` ни один из счётчиков не трогает (тот же
`_cmd_reject`, ветки `state in ("merge_gate", "verifying")`) — тем самым
за пределы явно названных в требовании 4 путей канал не расширяется,
но и не сужается: SPEC называет ровно эти два.

Разбор значения и потолок ролей переиспользуют `budget.spec_budget` —
тот же парсер, что и у `apply_spec_budget` (число, `ROLE_BUDGET_CAP`,
причины отказа) — без правки `orchestrator/budget.py` (файл вне зон
этой задачи, дублировать парсинг не было причины). `budget_usd` этой
задачи ($25 по SPEC) расхождения с фактическим объёмом (2 файла кода +
1 документ + 1 тестовый файл) не показывает — поле `budget_usd` в
frontmatter этого PLAN не заполнено, переоценка своего же потолка не
применяется.

Журнальная запись «бюджет из PLAN» (замечание ANSWER-1/2 п.2, AC-1)
теперь явно называет источник: `f"${value:.2f} (прежний потолок
${old:.2f}, источник {config.BUDGET_SOURCE_PLAN})"` — старый потолок,
новый потолок и слово `plan` в одной строке, буквально как того требует
AC-1 и проверяет `test_ac1_higher_plan_budget_raises_ceiling_on_first_
submission` (`assertIn("plan", tail)`).

`docs/invariants.md` (инвариант 10) этим PLAN в код-ветку НЕ вносится
(ANSWER-1/2 п.3: «роль инварианты не правит — с 11.09 инварианты и ADR
меняет только Оператор своим коммитом») — предлагаемая формулировка
вынесена приложением «## Приложение: инвариант 10» ниже, Оператор вносит
её сам после мержа. Диф `skills/coding-standards.md` — тем же приёмом,
приложением «## Приложение: unified-диф skills/coding-standards.md»,
в код-ветку не попадает (защищённый путь).

ANSWER-3 (вариант (a)): Оператор через `amend-tests` перевёл
`test_ac7_invariant_ten_names_plan_as_a_channel` в manual-маркер — код
этот шаг не менял. Перепрогон `tasks/01M1THKWFXFYNW28HDJGYHQWH6/
acceptance_tests/` целиком: 12 из 12 исполняемых методов зелёные.

REVIEW.md итерации 1, замечание R1-F1 (major): 5 из 8 методов
`PlanBudgetOneTimeReassessmentTest` не несли заявку `Ловит мутацию: …`
в докстринге (`test_ac2_missing_field_leaves_ceiling_untouched` — вовсе
без докстринга). Закрыто: все 5 методов
(`test_ac2_missing_field_leaves_ceiling_untouched`,
`test_ac4_return_from_review_closes_the_channel`,
`test_ac4_return_from_acceptance_reject_closes_the_channel`,
`test_ac8b_fires_only_once_across_a_full_cycle`,
`test_ac8a_value_above_role_cap_does_not_raise_ceiling`) получили строку
`Ловит мутацию: …` по образцу трёх уже оформленных методов того же
класса — формулировки взяты из предложений самого REVIEW.md.
`python3 -m unittest tests.test_invariants` — 60 passed;
приёмочная планка задачи — 12 из 12 исполняемых зелёные (см. «Реестр
замечаний» REVIEW.md — R1-F1 размечена `fixed`).

## Шаги
1. `orchestrator/config.py` — константа `BUDGET_SOURCE_PLAN = "plan"`.
2. `orchestrator/fsm_advance.py` — `_apply_plan_budget` (требования 1-6)
   и её вызов в `in_dev` перед переходом в `verifying`; журнальная запись
   «бюджет из PLAN» называет источник явным словом `plan` (ANSWER-1/2 п.2).
3. `tests/test_invariants.py` — `PlanBudgetOneTimeReassessmentTest`,
   8 методов на AC-1..AC-5, AC-8(a/b/c) (требование 8).
4. `docs/codebase-map.md` — перегенерирована (`scripts/codebase_map.py`)
   после правки `.py`-файлов.

Формулировка инварианта 10 (требование 7) — НЕ шаг этого PLAN: вносится
Оператором из приложения «## Приложение: инвариант 10» (ANSWER-1/2 п.3).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 2 |
| 2 | 2 |
| 3 | 2 |
| 4 | 2 |
| 5 | 2 |
| 6 | 2 (эта задача не добавляет отдельной обработки — см. «Не входит» SPEC) |
| 7 | приложение «## Приложение: инвариант 10» — Оператор вносит после мержа (ANSWER-1/2 п.3), не код-ветка этой задачи |
| 8 | 3 |
| 9 | приложение «## Приложение: unified-диф skills/coding-standards.md» |

## Влияние на систему
Новая колонка БД не вводится — переоценка держится на существующих
`review_iters`/`accept_rejects`, инвариант 4 («счётчики никогда не
сбрасываются») делает канал закрытым навсегда после первого срабатывания
без дополнительного состояния. Потолок Оператора (`budget_source ==
operator`) проверяется как отдельный, независимый слой перед применением
— тем же приёмом, что и `apply_spec_budget` — значение из PLAN никогда
не перебивает его. Значение выше `ROLE_BUDGET_CAP` не доходит до
`_apply_plan_budget` вовсе (guard части 1 отказывает переходу раньше);
внутри функции та же граница проверяется вторым, независимым слоем
через `budget.spec_budget` — на случай будущего расхождения версии
guard с версией этой проверки. Откат: удалить вызов
`_apply_plan_budget` из `in_dev` и саму функцию — потолок задачи
перестанет реагировать на `budget_usd` PLAN, поведение вернётся к
состоянию части 1 (только SPEC и Оператор).

Текст инварианта 10 и код при этом временно расходятся (код уже умеет
канал PLAN, таблица инвариантов ещё называет только SPEC) — до тех пор,
пока Оператор не внесёт формулировку из приложения ниже своим коммитом;
это сознательное следствие ANSWER-1/2 п.3, не дефект этой задачи.

## Риски
Точечный — без ADR-0009/из этой задачи.

## Предложения системе
- Локальный лок `acceptance_tests/` не переживает подтяжку main,
  меняющую порядок состояний FSM, если фикстура зафиксирована раньше
  такой подтяжки — класс риска не покрыт ни одним скилом сегодня
  (конкретный инцидент этой задачи, см. эскалацию в истории артефактов
  задачи — ANSWER-1/2). Стоит
  явно записать в skills/review-checklist.md или в docs/invariants.md
  «как добавить инвариант»: локальная фикстура приёмки, залоченная ДО
  структурного изменения порядка состояний FSM (ADR-класса), должна
  либо пере-фиксироваться той же подтяжкой, либо нести явную пометку
  «подлежит проверке на актуальность порядка состояний».
- Тот же класс риска повторился в этой же задаче ВТОРОЙ раз другой
  гранью: `test_ac7_invariant_wording.py` (акт приёмки этой задачи)
  писан test_author'ом, когда `docs/invariants.md` ещё считался обычным
  документом зоны SPEC (докстринг теста прямо это фиксирует: «не
  защищённый путь — обычный документ»); решение Оператора «с 11.09
  инварианты и ADR меняет только Оператор» (ANSWER-1/2 п.3) сделало этот
  документ протектед-путём ПОСЛЕ фиксации планки — тест был красным
  структурно, не по дефекту кода, до `amend-tests` Оператора (ANSWER-3).
  Наблюдение: не только «порядок состояний FSM» (первый пункт), а любое расширение
  списка protected-путей задним числом бьёт по уже зафиксированным
  локальным приёмочным планкам, которые эти пути читали как обычный
  документ, — стоит фиксировать общим правилом, не по одному прецеденту
  на класс.

## Приложение: инвариант 10
Предлагаемая замена строки 10 таблицы `docs/invariants.md` (роль эту
правку в код-ветку не коммитит — ANSWER-1/2 п.3, Оператор вносит после
мержа):

```diff
diff --git a/docs/invariants.md b/docs/invariants.md
index d7d4c75d..fc5ca892 100644
--- a/docs/invariants.md
+++ b/docs/invariants.md
@@ -34,7 +34,7 @@ docs/adr/0002-integrity-principle.md, CLAUDE.md.
 | 7 | Гейт (spec_gate, acceptance, merge_gate) проходит `approve`/`reject` Оператора ЛИБО автогейт по политике `gates.yaml` — только при выполнении ВСЕХ условий этой политики для данного гейта (ADR-0007); дефолт политики каждого гейта — manual, при нём поведение не отличается от исходного | `test_invariants.ManualGatesNeedTheOperatorTest`; `tasks/T066/acceptance_tests/test_ac1_ac2_ac3_autogate_success.py` | design §4; ADR-0007 |
 | 8 | Потолок задачи = её денежный бюджет: жёсткий, с алертом на 70% | `test_step_cost.CmdRunCostTest` | README 5; design §6, §10 |
 | 9 | Исчерпанный бюджет блокирует запуск агента и не обходится переходами FSM | `test_invariants.ExhaustedBudgetIsNotBypassableTest` | design §6 |
-| 10 | Поднять потолок выше `ROLE_BUDGET_CAP` может только Оператор командой `budget`; в пределах потолка ролей потолок задаёт SPEC на гейте SPEC | `test_invariants.ExhaustedBudgetIsNotBypassableTest.test_only_the_operator_ceiling_unblocks_the_run`; `test_invariants.SpecCeilingRespectsRoleBudgetCapTest`; `test_step_cost.CmdBudgetTest` | design §4 («увеличение лимитов — manual всегда»); ADR-0014 |
+| 10 | Поднять потолок выше `ROLE_BUDGET_CAP` может только Оператор командой `budget`; в пределах потолка ролей потолок задаёт SPEC на гейте SPEC и один раз PLAN при первой сдаче | `test_invariants.ExhaustedBudgetIsNotBypassableTest.test_only_the_operator_ceiling_unblocks_the_run`; `test_invariants.SpecCeilingRespectsRoleBudgetCapTest`; `test_invariants.PlanBudgetOneTimeReassessmentTest`; `test_step_cost.CmdBudgetTest` | design §4 («увеличение лимитов — manual всегда»); ADR-0014 |
 | 11 | Журнал шагов пишется всегда: запуск, исход, стоимость, сбой лога, уборка | `test_agent_log.CmdRunLoggingTest`; `test_step_cost.CmdRunCostTest.test_step_cost_lands_in_spent_and_journal`; `test_kill_cleanup.KillCleanupTest.test_cleanup_is_listed_in_the_journal` | README 5; design §6, §7 |
 | 12 | В main мержит только `approve` из merge_gate — другого пути влить что-либо в main нет. Единственный merge вне гейта — актуализация ветки задачи от main (сверка свежести T051): в worktree задачи (`-C`), вливает main, ветку задачи в аргументах не упоминает, main не изменяет | `test_invariants.MergeOnlyFromMergeGateTest` | design §2, §4; CLAUDE.md; ADR-0006 |
 | 13 | Переход review → acceptance невозможен без свежего вердикта ревьювера | `test_invariants.FreshVerdictGuardsAcceptanceTest`; `test_review_freshness.FreshVerdictIterationTest` | design §4; artifacts.py `fresh_verdict_iteration` |
```

`git apply --check` этого диффа на чистом дереве main проходит — проверено
этим шагом временным файлом (удалён после проверки, в задачу не входит).

## Приложение: unified-диф skills/coding-standards.md
Диф проверен `git apply --check` на чистом дереве ветки — применяется
без конфликтов (требование 9, AC-9). Оператор применяет отдельно, файл
защищённый — эта задача его не коммитит.

```diff
diff --git a/skills/coding-standards.md b/skills/coding-standards.md
index 6b57b9ab..46ab4f51 100644
--- a/skills/coding-standards.md
+++ b/skills/coding-standards.md
@@ -16,6 +16,19 @@
   (урок T011: UnicodeDecodeError починили в artifact_text и оставили
   в git_diff_part).
 
+## Однократная переоценка бюджета на PLAN (ADR-0014 п.3)
+PLAN вправе один раз, при первой сдаче, поднять потолок задачи выше
+значения из SPEC — полем `budget_usd` во frontmatter (шаблон несёт его
+закомментированным). Раскомментируй и впиши сумму ТОЛЬКО при
+расхождении с оценкой SPEC — основание не «показалось мало», а число
+файлов и шагов PLAN, которое SPEC на своей стадии оценить не мог; само
+расхождение и его причина — в разделе «Подход» PLAN.md, коротко, не
+эссе. Пульт применяет значение один раз за всю жизнь задачи и только
+вверх, в пределах потолка ролей (`ROLE_BUDGET_CAP`); возврат из ревью
+или приёмки канал больше не открывает — второй шанс исключён, потолок
+после такого возврата остаётся прежним независимо от значения
+`budget_usd`.
+
 ## Реестр замечаний (schema_version >= 3)
 Если REVIEW.md несёт `schema_version >= 3`, каждое замечание живёт как
 запись секции «Реестр замечаний» с id и статусом (tasks/T100/SPEC.md).
```
