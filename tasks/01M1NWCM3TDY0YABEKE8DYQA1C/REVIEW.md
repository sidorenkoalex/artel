---
task: 01M1NWCM3TDY0YABEKE8DYQA1C
type: review
author_role: reviewer
status: approved        # draft | approved | changes_requested | escalate
iteration: 2
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

(нет)

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | tests/test_report.py:156,163,264; tests/test_retro.py:292,305,364,370; tests/test_spec_budget.py:529,534,542,550; tests/test_spent_estimate_store.py:28,31,36,42,58,61,71; tests/test_step_cost.py:381,394,421,430,435 | Новые юнит-тесты не несли в докстринге заявку «Ловит мутацию: …» (review-checklist п.3, skills/test-authoring.md) | Ревьювер/будущий разработчик не мог свериться с тем, какую порчу кода тест обязан ловить | Разработчик дописал «Ловит мутацию: …» во ВСЕ 18 перечисленных мест (`git diff e5672ac4..HEAD -- tests/` — только докстринги, ни одной строки продакшн-кода orchestrator/ не тронуто). Прочитал каждую новую заявку и сверил с реальным кодом функции, которую она описывает: `tests/test_spent_estimate_store.py:32-35` (`charge_estimate` копипастит SQL `charge` и бьёт по `spent_usd`) — сверено с orchestrator/store.py:425-439, заявка точная; `tests/test_step_cost.py:434-437` (`partial_cost_usd` трактует `partial_tokens=0` как отсутствие курса и возвращает `None`) — сверено с реальной сигнатурой функции, заявка точная и небанальна (это ровно тот угол, который отличает «нет курса» от «курс есть, токенов 0»); `tests/test_retro.py:296-299`/`:381-384` (`build_done`/`_cost_block` мог бы слить `spent_usd`+`spent_estimate_usd` в одну строку) — сверено с orchestrator/retro.py:209-221,240-241, заявка точная. Ни одна из 18 заявок не пересказывает имя метода вместо мутации — все называют конкретную порчу и конкретную упавшую ассерцию. Замечание закрыто целиком. |

## Вердикт

approved — R1-F1 закрыт: все 18 перечисленных мест получили заявку
«Ловит мутацию: …», проверенную выборочно против реального кода (см.
реестр) и не пересказывающую поведение вместо мутации. Диф с прошлой
итерации (`git diff e5672ac4..HEAD`) касается только докстрингов пяти
тестовых файлов — ни строки продакшн-кода (`orchestrator/`) не
изменилось, поэтому вся таблица «Соответствие SPEC» из итерации 1
остаётся в силе без повторной проверки функциональности (она уже была
верна и не менялась). Полный набор `tests/` и все приёмочные AC-1..AC-9
зелёные (см. «Проверено исполнением»), `roles.yaml` не тронут, карта
кодовой базы актуальна по содержимому. Блокеров по корректности,
тестам, безопасности или системной целостности нет.

## Проверено исполнением

Итерация 2. Рабочее дерево ветки на момент старта ревью снова несло
12 файлов `tasks/01M1NWCM3TDY0YABEKE8DYQA1C/*` как unstaged-удалённые
(последний коммит ветки — WIP-чекпоинт developer после таймаута его же
шага; та же механика восстановления, что и в прошлых прецедентах);
восстановлены командой `git checkout -- tasks/01M1NWCM3TDY0YABEKE8DYQA1C/`
перед началом проверки (после восстановления `git status --porcelain` —
пусто).

- `git log --oneline -- tasks/01M1NWCM3TDY0YABEKE8DYQA1C/REVIEW.md` —
  нашёл коммит вердикта итерации 1 (`e5672ac4`); инкрементальный diff
  из пакета не собрался (невалидное `sha...ветка` выражение), поэтому
  сверял `git diff e5672ac4..HEAD` вручную.
- `git diff e5672ac4..HEAD --stat -- orchestrator/` — пусто:
  продакшн-код не менялся с прошлой итерации, менялись только
  `tests/*.py` (105 insertions, только докстринги — см. реестр R1-F1).
- `git diff main...HEAD -- roles.yaml` — пусто: `roles.yaml` по-прежнему
  не тронут (AC-1).
- `python3 scripts/codebase_map.py`, затем `git diff -- docs/codebase-map.md`
  — расхождение только в строке `built_at_sha` (не дефект, см. скил
  review-checklist); откачено `git checkout -- docs/codebase-map.md`.
- `python3 -m pytest tasks/01M1NWCM3TDY0YABEKE8DYQA1C/acceptance_tests/ -v`
  — 18 passed, 12 subtests passed (все AC-1..AC-9, кроме AC-8 без
  исполняемых тестов по решению test_author) — без изменений от
  итерации 1, как и ожидалось при нетронутом продакшн-коде.
- `python3 -m unittest discover -s tests` (в переднем плане, с явным
  таймаутом 590с) — Ran 1438 tests in 167.832s, OK. Число тестов
  совпадает с итерацией 1 (докстринги новых assert'ов не добавляют).

## Предложения системе

(нет)
