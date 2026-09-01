---
task: T095
type: review
author_role: reviewer
status: approved        # draft | approved | changes_requested | escalate
iteration: 1
schema_version: 2    # версия формата артефакта, см. scripts/guard.py
---

# REVIEW: Метрика «трение» — доля непродуктивных токенов шага

## Фаза A — проверка плана

1. Покрытие: все 5 требований SPEC отражены в таблице «Покрытие требований» PLAN.md,
   каждое — конкретным шагом или разделом «Подход». Требование 4 (выбор способа
   получения данных) обосновано с явным учётом retention логов (`docs/retention.md`,
   `orchestrator/prune.py`) — вариант (а) выбран и обоснование отвечает на «почему
   не (б)» (AC-7 выполнен).
2. Три шага плана — последовательные части одного MR разумного размера
   (низкоуровневая функция → агрегация/рендер → регенерация карты и прогон тестов),
   не микрооперации и не «сделать всё».
3. Подход опирается на существующие прецеденты (T092 `_metrics_html`/`_gate_ratio`,
   T040/T082 разбор stream-json) и не конфликтует с конвенциями — не заведена новая
   колонка БД, не тронут `runner.py`/`checkpoint.py`.

Претензий к плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 / AC-1 | OK | `agent_log.step_friction` — детерминированный разбор `stream-json`, три сигнала ТЗ реализованы (`orchestrator/agent_log.py:132-263`). Проверено юнит- и приёмочными тестами на все три сигнала по отдельности, границы (пустой лог, лог без tool_use), недвойной учёт вызова с двумя сигналами. |
| 2 / AC-2 | OK | Агрегация на задачу — `report._task_friction` (среднее по логам задачи); на корпус — `report._friction_by_task` (список по последним задачам) + `report._friction_trend`. Приёмочные тесты AC-2 подтверждают реакцию на изменение логов своей/чужой/новой задачи. |
| 3 / AC-3 | OK | Блок «Метрика «трение»» в `_render()` (`report.py:392-393`) — значения по последним задачам + подраздел «Тренд» (`_friction_html`). |
| 4 / AC-7 | OK | Выбран вариант (а), обоснование в PLAN учитывает retention логов и зону задачи. |
| 5 / AC-8 | OK | Изменения строго в `orchestrator/agent_log.py` и `orchestrator/report.py` (+ `docs/codebase-map.md`, тесты, артефакты задачи) — подтверждено `git diff --stat main...HEAD` и приёмочными тестами `test_ac6_ac8_protected_zones.py` (все защищённые файлы нетронуты). |
| AC-4 | OK | `cmd_report()` не делает новых обращений к `state.db` сверх уже читаемых `store.py`-функций, не открывает сеть; `test_ac4_no_network_dependency.py` (сокеты заблокированы моком) — зелёный. |
| AC-5 | OK | `report._task_friction` перехватывает `OSError` на отдельном логе, пропуская только его; `test_ac5_missing_log_honest_skip.py` подтверждает, что `report` не падает при полном отсутствии логов задачи. |
| AC-6 | OK | Вариант (б) не выбирался, но список защищённых файлов (catalog/store-ядро, fsm, guard, coldstart, canary, ветко-чтения) нетронут в любом случае — подтверждено тем же тестом, что и AC-8. |
| AC-9 | OK | Ни `alerts.raise_alert`, ни констант с «THRESHOLD»/«ПОРОГ» в добавленных строках зоны нет — `test_ac9_no_thresholds_or_alerts.py` зелёный. `LARGE_TOOL_RESULT_CHARS` — эвристика формы сигнала 3, не порог гейтования метрики (согласуется с текстом «Не входит» SPEC). |
| AC-10 | OK | Ни `median(`, ни `kind="threshold"` в добавленных строках зоны — `test_ac10_no_regression_flags.py` зелёный. |
| AC-11 | OK | Существующие публичные функции `agent_log.py` (`render_agent_line`, `tee_lines`, `stream_to_log`, `OutputPump`) не изменены — только добавлены новые. `tests/test_agent_log.py` (старые кейсы) остаются зелёными. |
| AC-12 | OK | `python3 -m unittest discover -s tests` — 1168 тестов, все зелёные (см. «Проверено исполнением»). |

## Замечания

- minor — `orchestrator/report.py:392` — заголовок блока «Метрика «трение»: непродуктивные
  токены шага» обещает метрику по токенам, а фактический расчёт (`step_friction`,
  `orchestrator/agent_log.py:220-223`) — по числу вызовов инструментов (событий), не по
  токенам usage; PLAN это решение осознанно и обоснованно фиксирует («Риски»,
  событийный, не токенный знаменатель), но заголовок в самом отчёте вводит читающего
  Оператора в заблуждение относительно единицы измерения. Предложение: в следующей
  правке скорректировать заголовок секции на нейтральную формулировку («доля
  непродуктивных вызовов инструментов» или просто «Метрика «трение»» без уточнения
  «токены») — не блокирует эту задачу, расхождение чисто текстовое, значения и логика
  верны.

## Вердикт

approved

## Проверено исполнением

- `python3 -m unittest discover -s tests -v` — 1168 тестов, все зелёные (OK).
- `python3 tasks/T095/acceptance_tests/test_ac1_step_friction_function.py -v` — 6/6 OK.
- `python3 tasks/T095/acceptance_tests/test_ac2_aggregation_task_and_corpus.py -v` — 3/3 OK.
- `python3 tasks/T095/acceptance_tests/test_ac3_report_friction_block.py -v` — 3/3 OK.
- `python3 tasks/T095/acceptance_tests/test_ac4_no_network_dependency.py -v` — 1/1 OK.
- `python3 tasks/T095/acceptance_tests/test_ac5_missing_log_honest_skip.py -v` — 1/1 OK.
- `python3 tasks/T095/acceptance_tests/test_ac6_ac8_protected_zones.py -v` — 2/2 OK.
- `python3 tasks/T095/acceptance_tests/test_ac9_no_thresholds_or_alerts.py -v` — 2/2 OK.
- `python3 tasks/T095/acceptance_tests/test_ac10_no_regression_flags.py -v` — 2/2 OK.
  (`test_manual_criteria.py` — без исполняемых проверок, AC-7/AC-11/AC-12 подтверждены
  чтением PLAN.md и прогонами выше, см. таблицу.)
- `python3 scripts/guard.py tasks/T095/SPEC.md tasks/T095/PLAN.md tasks/T095/TZ.md` —
  «GUARD: ок (3 файлов)».
- `python3 scripts/codebase_map.py` в рабочем дереве (с последующим откатом файла) —
  дифф ограничился строкой `built_at_sha` (карта на HEAD, построена на более раннем
  коммите ветки, содержимое совпадает) — не дефект (built_at_sha законно отстаёт,
  см. review-checklist).
- Прочитан вручную `orchestrator/agent_log.py:132-263` (`step_friction` и приватные
  помощники) и `orchestrator/report.py:117-320` (агрегаторы и рендер) — сверено с
  логикой сигналов, описанной в PLAN, построчной трассировкой на фикстурах трёх
  сигналов и кейса «двойного сигнала на одном вызове» (дедуп через `set`).
- `git diff --stat main...task/t095-metrika-trenie-neproduktivnye` — подтверждён
  список изменённых файлов, зона ограничена `orchestrator/agent_log.py`,
  `orchestrator/report.py`, `docs/codebase-map.md`, артефактами/тестами задачи.

## Предложения системе

(пусто)
