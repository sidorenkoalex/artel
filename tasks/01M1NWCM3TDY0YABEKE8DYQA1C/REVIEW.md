---
task: 01M1NWCM3TDY0YABEKE8DYQA1C
type: review
author_role: reviewer
status: changes_requested        # draft | approved | changes_requested | escalate
iteration: 1
schema_version: 3
---

# REVIEW: Стоимость частичного шага при таймауте: курс токенов вместо тишины

## Фаза A: план

1. Покрытие требований в PLAN.md (таблица «Покрытие требований») полно —
   каждое из требований 1-9 привязано к шагу; сверено построчно с
   реализацией, расхождений не найдено.
2. Шаги PLAN.md — проверяемые единицы (по модулю), не микрооперации;
   монолит на один MR обоснован в SPEC («Оценка объёма и деление» —
   задача принята Оператором 04.09.2026 до появления правила деления,
   деление задним числом дороже монолита) — принимается без вопросов.
3. Подход (курс — таблица словарей в config.py, `spent_estimate_usd` —
   отдельная колонка, три ветки `charge_missing_result`, сумма в
   бюджетном гейте) не конфликтует с существующей архитектурой T040 —
   расширяет её ровно так, как описывает PLAN.

Замечаний к плану нет.

## Соответствие SPEC

| Требование/AC | Вердикт | Комментарий |
|---|---|---|
| 1 / AC-1 | OK | `config.TOKEN_RATES` (orchestrator/config.py:307-316) несёт все 4 роли конвейера с `input_usd_per_token`/`output_usd_per_token`/`calibrated_at`; `roles.yaml` не тронут — `git diff main...HEAD -- roles.yaml` пуст. Тест `test_ac1_token_rate_table.py` (3 теста) зелёный. |
| 2 / AC-2 | OK | `spend.partial_cost_usd`+`charge_missing_result` (orchestrator/spend.py:143-212): известный курс — `store.charge` ненулевой суммой, журнал «частичная стоимость по курсу» с $ и токенами. `test_ac2_known_rate_partial_charge.py` зелёный. |
| 3 / AC-3 | OK | Неизвестный курс — алерт `kind=threshold` с ролью/задачей/токенами, `store.charge_estimate` константой `STEP_COST_ESTIMATE_USD`, журнал «верхняя оценка стоимости шага». Повтор отказа копит оценку заново, алерт дедупится (`alerts.raise_alert`). `test_ac3_unknown_rate_alert_and_estimate.py` (4 теста) зелёный. |
| 4 / AC-4 | OK | Ветка `saw_usage_event=False` не изменена — журнал «стоимость шага неизвестна», `kind=incident source=spend.unknown_cost`, обе колонки не тронуты. `test_ac4_no_usage_events_unchanged.py` зелёный. |
| 5 / AC-5 | OK | `budget.spent_with_estimate` (orchestrator/budget.py:91-97) = `spent_usd + spent_estimate_usd`; `budget_block`/`enforce_budget` считают по ней. `test_ac5_budget_gate_includes_estimate.py` (3 теста) зелёный. |
| 6 / AC-6 | OK | `report._metrics_html`/`cmd_report` — отдельная строка «Суммарная верхняя оценка» (orchestrator/report.py:333-364), не сложена с точным расходом. `test_ac6_report_shows_estimate_separately.py` зелёный. |
| 7 / AC-7 | OK | `retro._cost_block` (orchestrator/retro.py:209-221) добавляет строку оценки только при `spent_estimate_usd > 0`; `parse_total_cost`/`TOTAL_COST_RE` (retro.py:31) якорится на «Стоимость итого:», новую строку не подхватывает — реcид программного расхода не задваивается. `test_ac7_retro_shows_estimate_separately.py` зелёный. |
| 8 / AC-8 | OK | Полный набор `tests/` зелёный (см. «Проверено исполнением»), включая два теста T040, переписанных разработчиком по ANSWER-2.md варианту A с докстрингом-обоснованием (`tests/test_step_cost.py:319,391` — `ChargeMissingResultTest.test_partial_tokens_are_journaled_without_touching_spent`, `CmdRunPartialCostTest.test_timeout_with_usage_events_charges_a_partial_token_sum`). AC-8 честно помечен `# AC-8: skip` — регрессия уже покрыта CI/автогейтом (класс «ci-covered»). |
| 9 / AC-9 | OK | Миграция `add_column(..., "spent_estimate_usd", "REAL DEFAULT 0")` (store.py:214) не бэкфиллит; `test_ac9_no_recompute_of_past_steps.py` на легаси-схеме подтверждает `spent_usd` старой задачи не тронут, `spent_estimate_usd` = 0. |

## Замечания

- minor/major (см. обоснование ниже) — `tests/test_report.py:156,163,264`, `tests/test_retro.py:292,305,364,370`, `tests/test_spec_budget.py:529,534,542,550`, `tests/test_spent_estimate_store.py:28,31,36,42,58,61,71`, `tests/test_step_cost.py:381,394,421,430,435` — ни один из перечисленных НОВЫХ юнит-тестов не несёт в докстринге заявку «Ловит мутацию: …» (skills/test-authoring.md, review-checklist п.3): часть вовсе без докстринга (например `test_report.py:156`, весь `test_spent_estimate_store.py`, `test_step_cost.py:421-435`), часть — с докстрингом, пересказывающим SPEC/поведение, а не называющим конкретную мутацию, которую тест обязан ловить (например `test_retro.py:292` — «юнит-угол на build_done, дополняющий приёмочный…» — это адрес, не заявка о мутации). Показательно, что оба теста T040, которые ANSWER-2.md прямо обязал переписать (`tests/test_step_cost.py:319` и `:634`), заявку несут буквально («Ловит мутацию: разработчик оставляет прежнее поведение T040 без курса для developer — assertGreater ниже упадёт на 0.0») — то есть автор умеет и обычно делает это для тестов, которые сам считает рискованными, но не сделал этого ни для одного из НОВЫХ тестов, добавленных вокруг той же функциональности. Без заявки я не могу свериться с тем, какую мутацию тест на самом деле обязан ловить (требование п.3 чеклиста ревью), а не подтвердить это на глаз задним числом. Предложение: дописать «Ловит мутацию: …» в докстринг каждого перечисленного теста — по каждому из них видно из самого теста, какая порча кода должна была бы его покраснить (например, `test_spent_estimate_store.py:36` явно ловит потерю накопления при повторном вызове `charge_estimate`, `test_step_cost.py:430` ловит эффективную ставку, ошибочно возвращающую `None`/исключение вместо 0.0 при `partial_tokens=0`) — работа в основном техническая, не поисковая.

Классифицирую как единый blocker-класс уровня **major**: отсутствие заявки затрагивает практически ВСЕ новые юнит-тесты этого MR (не приёмочные — там дисциплина соблюдена образцово), это системный пробел практики автора на весь диф, а не одна забытая строка.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | open | tests/test_report.py:156,163,264; tests/test_retro.py:292,305,364,370; tests/test_spec_budget.py:529,534,542,550; tests/test_spent_estimate_store.py:28,31,36,42,58,61,71; tests/test_step_cost.py:381,394,421,430,435 | Новые юнит-тесты не несут в докстринге заявку «Ловит мутацию: …» (review-checklist п.3, skills/test-authoring.md) | Ревьювер/будущий разработчик не может свериться с тем, какую порчу кода тест обязан ловить, не восстанавливая это по наитию — именно то, что чеклист явно запрещает | Дописать «Ловит мутацию: …» в докстринг каждого перечисленного теста, описывая конкретный сценарий порчи и то, какая ассерция на нём падает |

## Вердикт

changes_requested — единственное замечание R1-F1 (major): доисправить
докстринги перечисленных тестов заявкой «Ловит мутацию: …» и вернуть на
следующую итерацию. Функциональная часть (требования 1-9/AC-1..AC-9)
реализована полностью и верно, весь код прогнан и зелёный — блокеров по
корректности, безопасности или системной целостности нет.

## Проверено исполнением

Рабочее дерево ветки на момент старта ревью несло 12 файлов
`tasks/01M1NWCM3TDY0YABEKE8DYQA1C/*` как unstaged-удалённые (та же
механика, что и в прошлых прецедентах — файлы существуют в истории
ветки, просто пропали из рабочего дерева); восстановлены командой
`git checkout -- tasks/01M1NWCM3TDY0YABEKE8DYQA1C/` перед прогоном
тестов (после восстановления `git status --porcelain` — пусто, дерево
чистое, никаких переписанных файлов).

- `git diff main...HEAD -- roles.yaml` — пусто: `roles.yaml` не
  тронут (AC-1).
- `python3 scripts/codebase_map.py`, затем `git diff -- docs/codebase-map.md`
  — расхождение только в строке `built_at_sha` (не дефект, см. скил
  review-checklist); откачено `git checkout -- docs/codebase-map.md`
  после проверки — карта в ветке актуальна по содержимому.
- `python3 -m pytest tasks/01M1NWCM3TDY0YABEKE8DYQA1C/acceptance_tests/ -v`
  — 18 passed, 12 subtests passed (все AC-1..AC-9, кроме AC-8 без
  исполняемых тестов по решению test_author).
- `python3 -m unittest discover -s tests` — Ran 1438 tests in 184.9s,
  OK (включая переписанные по ANSWER-2.md `tests/test_step_cost.py`
  и все существующие тесты бюджета/частичной стоимости T007/T012/T040).

## Предложения системе

(нет)
