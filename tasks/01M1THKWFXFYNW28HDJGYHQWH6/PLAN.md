---
task: 01M1THKWFXFYNW28HDJGYHQWH6
type: plan
author_role: developer
status: escalate
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

## Шаги
1. `orchestrator/config.py` — константа `BUDGET_SOURCE_PLAN = "plan"`.
2. `orchestrator/fsm_advance.py` — `_apply_plan_budget` (требования 1-6)
   и её вызов в `in_dev` перед переходом в `verifying`.
3. `docs/invariants.md` — инвариант 10, формулировка канала PLAN
   (требование 7).
4. `tests/test_invariants.py` — `PlanBudgetOneTimeReassessmentTest`,
   8 методов на AC-1..AC-5, AC-8(a/b/c) (требование 8).
5. `docs/codebase-map.md` — перегенерирована (`scripts/codebase_map.py`)
   после правки `.py`-файлов.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 2 |
| 2 | 2 |
| 3 | 2 |
| 4 | 2 |
| 5 | 2 |
| 6 | 2 (эта задача не добавляет отдельной обработки — см. «Не входит» SPEC) |
| 7 | 3 |
| 8 | 4 |
| 9 | приложение диффа ниже |

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

## Риски
Точечный — без ADR-0009/из этой задачи.

## Предложения системе
- Локальный лок `acceptance_tests/` не переживает подтяжку main,
  меняющую порядок состояний FSM, если фикстура зафиксирована раньше
  такой подтяжки — класс риска не покрыт ни одним скилом сегодня (см.
  раздел «Эскалация» ниже, конкретный инцидент этой задачи). Стоит
  явно записать в skills/review-checklist.md или в docs/invariants.md
  «как добавить инвариант»: локальная фикстура приёмки, залоченная ДО
  структурного изменения порядка состояний FSM (ADR-класса), должна
  либо пере-фиксироваться той же подтяжкой, либо нести явную пометку
  «подлежит проверке на актуальность порядка состояний».

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

## Эскалация

- **Вопросы** —
  1. (блокирует приёмку) `tasks/01M1THKWFXFYNW28HDJGYHQWH6/acceptance_tests/`
     залочен под порядок состояний FSM `in_dev -> review -> verifying
     -> acceptance` (одна `advance` = один переход `in_dev` прямиком в
     `review`; `_sandbox.py::reach_acceptance` дальше ждёт `verifying`
     ПОСЛЕ `review`). Сегодняшний код ветки несёт уже смерженный
     ADR-0015 («CI до ревью»): порядок `in_dev -> verifying -> review ->
     acceptance` (docs/invariants.md, инвариант 36; `orchestrator/
     fsm_advance.py:1244-1247` — переход из `in_dev` ведёт в
     `verifying`, не в `review`; `verifying()`, строки 369-391, — в
     `review` только по зелёному CI ОТДЕЛЬНЫМ вызовом `advance`).
     Расхождение подтверждено прогоном: `submit_plan()` (одна `advance`)
     после моей реализации останавливается в `verifying` (не в
     `review`) — семь из восьми исполняемых методов 3 файлов
     (`test_ac1_ac2_ac3_first_submission.py`,
     `test_ac4_no_repeat_after_return.py`,
     `test_ac5_operator_ceiling_not_overridden.py`) падают РОВНО на
     `assertEqual(self.state(), "review")`, и только на этом — я
     проверил отдельным прогоном (не закоммичен, только для
     диагностики): второй вызов `fsm.cmd_advance` сразу после первого
     доводит `verifying -> review`, и дальше ВСЕ содержательные
     ассерты (`budget_usd`, `budget_source`, текст журнала) проходят
     буквально как того требует критерий. Правка кода этой задачи под
     старый порядок означала бы либо вернуть `in_dev` к прямому
     переходу в `review` (откат ADR-0015 — чужой, уже принятый и
     протестированный инвариант 36, вне зоны и полномочий этой задачи),
     либо руками звать `verifying()` изнутри `in_dev` (слияние двух
     состояний FSM в одно — тот же запрет). Правка самой фикстуры мне
     недоступна (`acceptance_tests/` залочен, tasks/T023) — варианты:
     - **(a)** Оператор поручает test_author (или использует
       `amend-tests`) обновить `_sandbox.py` (`submit_plan`/
       `reach_acceptance`) под текущий порядок `in_dev -> verifying ->
       review -> acceptance` (лишний `fsm.cmd_advance` между `in_dev` и
       `review`; `review -> acceptance` — без `verifying` посередине,
       он уже позади), я перепрогоняю приёмку без изменений в
       `orchestrator/`.
     - **(b)** Оператор признаёт фикстуру устаревшей относительно
       мержа ADR-0015 в main ПОСЛЕ её фиксации (сама ветка задачи явно
       моложе задачи ADR-0015 по ULID: `01M1THKW...` < `01M1TQ0T...`,
       то есть заведена раньше, чем ADR-0015 решился) и принимает
       покрытие AC-8(a/b/c) `tests/test_invariants.py::
       PlanBudgetOneTimeReassessmentTest` (8 методов, все зелёные) как
       достаточное для этой задачи, закрывая/обходя приёмку вручную.
     - Дефолт при молчании: **(a)** — лок `acceptance_tests/` существует
       именно для того, чтобы спор с тестом решался пересмотром теста
       по каналу T023, а не тихим ослаблением кода; `amend-tests`
       (`orchestrator/amend.py`) — штатный канал для этого класса
       правки.
- **Контекст** — Код полностью реализован и закоммичен в ветку:
  `orchestrator/config.py` (`BUDGET_SOURCE_PLAN`), `orchestrator/
  fsm_advance.py` (`_apply_plan_budget`, вызов перед переходом в
  `verifying`), `docs/invariants.md` (инвариант 10), `tests/
  test_invariants.py` (`PlanBudgetOneTimeReassessmentTest`, 8/8
  зелёных), `docs/codebase-map.md` (перегенерирована). Юнит-тесты
  прогнаны: `python3 -m unittest tests.test_invariants` — 60/60
  зелёных; `tests.test_spec_budget`, `tests.test_step_cost`,
  `tests.test_zones_gate`, `tests.test_capacity_gate`, `tests.
  test_fsm_review_rework_gate`, `tests.test_acceptance_tests_flow`,
  `tests.test_guard_split_signals`, `tests.test_guard_zones`, `tests.
  test_guard_schema` — все зелёные, регрессий не обнаружено.
  Приёмочные тесты `tasks/01M1THKWFXFYNW28HDJGYHQWH6/acceptance_tests/`:
  `test_ac6_over_cap_blocks_transition.py` (1/1) и
  `test_ac7_invariant_wording.py` (4/4) зелёные без изменений; три
  остальных файла падают исключительно на описанном выше расхождении
  порядка состояний. Унифицированный дифф `skills/coding-standards.md`
  приложен выше, `git apply --check` на чистом дереве прошёл.
- **Блокирует** — Довести PLAN.md до `status: ready` (и тем самым
  переход `in_dev -> verifying`, который проверяет `acceptance_tests/`
  целиком) без ответа по вопросу выше нельзя: `_acceptance_run_refuses`
  прогоняет РОВНО эту планку, и без её починки переход не пройдёт
  структурно, независимо от корректности кода части 2.
