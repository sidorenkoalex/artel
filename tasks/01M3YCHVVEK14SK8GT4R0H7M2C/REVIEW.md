---
task: 01M3YCHVVEK14SK8GT4R0H7M2C
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Пробный период и приостановка пары набора

## Фаза A: план

- Покрытие: таблица PLAN покрывает требования 1–9. Шаги итерации 2 (7–11)
  привязаны к R1-F1..F3 и ANSWER-1.
- Шаги размером с MR: схема/SQL, models, fsm_autogate, artel, docs, тесты.
- Архитектура: SQL только в `store.py`, DDL одним литералом
  `PAIR_SUSPENSION_DDL` в `SCHEMA` и `migrate()`. Хук перехода в
  `store.set_state` устроен как `_close_attention_alert`. `_ensure_pair_tables`
  удалён, запросы к парам DDL больше не исполняют.
- Отступление от буквы ANSWER-1 п.2 в PLAN названо и обосновано («Подход»,
  абзац про отказ автогейта). Буквальное `_last_step_model(...) == model`
  роняет залоченный долгоживущий `test_ac7_…`: в нём задачи входят в
  приёмку без единого шага developer/test_author. Это подтверждено
  мутацией M4 (раздел «Проверено исполнением»). Реализовано так: вину
  снимает только наблюдаемый откат, то есть последний шаг роли на другой
  модели. Это выполняет назначение ответа Оператора («тест на сценарий
  отката шага на боевую модель») и не противоречит планке. Принимаю.
- «Влияние на систему» сходится с diff. Изменено 7 файлов, все в зонах
  SPEC; защищённые пути не тронуты. В `tests/` только новый файл,
  утверждения существующих тестов не менялись.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `models.set_trial_reason`: считает настоящие задачи в `done` с совпадающим `model_set_members`, N = done+1. AC-1/AC-2 зелёные. |
| 2 | OK | Безусловный ручной отказ снят (`fsm_autogate.py:224-233`), сбой разбора состава даёт отказ (fail-closed). AC-3 зелёный. |
| 3 | OK | `_consecutive_returns` по ANSWER-1 п.1 (вариант Б): решает только непосредственно предыдущий вердикт пары после последнего снятия. Одобрение рвёт цепочку. AC-4/AC-5 и юнит на R(P), A(P), R(Q) зелёные. |
| 4 | OK | `suspend_on_autogate_refusal` после любого отказа; вина и роль — из `_ROLE_BLAME_ROLES`. При откате шага на другую модель пара не приостанавливается (ANSWER-1 п.2, оговорка выше). AC-7 зелёный. |
| 5 | OK | `_suspend_pair`: строка БД, запись в журнал, алерт `incident/pair_suspension`. Перекрытие через `set_admitted` и `_set_pair_withdrawn`, текст отката называет боевую модель. AC-6/AC-8 зелёные. |
| 6 | OK | `cmd_pair_resume`: без приостановки отказ до записи в БД; `resumed_after_verdict` отсекает прежние вердикты. AC-9/AC-10 зелёные. |
| 7 | OK | `docs/stack.md` описывает пробный период и приостановку, включая «подряд» по потоку и снятие вины при откате. AC-11 зелёный. |
| 8 | OK | `unclean_reason` при `escalations > 1` даёт причину с числом. AC-12 зелёный. |
| 9 | OK | Долгоживущий файл (11 методов) плюс `tests/test_pair_suspension_units.py` (9 методов). У каждого метода есть «Ловит мутацию» с наблюдаемым расхождением. Три новых сторожа проверены мутацией и покраснели. Долгоживущий файл они не повторяют: поток с одобрением между задачами, откат при отказе автогейта, транзакция вызывающего. |

## Замечания

Блокирующих и major нет. Записи R1-F1..F3 закрыты (реестр ниже).

Косметика, в реестр не заношу: докстринг `models.suspend_on_autogate_refusal`
склеен в одну длинную строку («…вину на пару не кладёт. Вина `пульт/пул`…»).
В `tests/test_pair_suspension_units.py` перед
`test_return_after_approved_previous_task_does_not_suspend` лишняя пустая
строка. На поведение не влияет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/models.py `_consecutive_returns` | «Подряд» засчитывал любой возврат предыдущей задачи пары | Приостановка при R(P), A(P), R(Q) | Исправлено по ANSWER-1 п.1 (вариант Б): решает только `earlier[-1]`. Сторож `test_return_after_approved_previous_task_does_not_suspend` краснеет на мутации M1 (возврат к «любой возврат»). |
| R1-F2 | accepted | orchestrator/models.py `suspend_on_autogate_refusal` | Вина отказа автогейта не сверяла модель шага роли | Приостановка пары за работу боевой модели | Исправлено: последний шаг роли на другой модели снимает вину. Без шага вина остаётся на паре — этого требует залоченный AC-7, буквальное `== model` его роняет (M4). Сторож `test_autogate_refusal_after_rollback_to_combat_spares_pair` краснеет на M2. |
| R1-F3 | accepted | orchestrator/store.py `_ensure_pair_tables` | DDL через `executescript` на каждом запросе | Неявный COMMIT транзакции вызывающего | Исправлено: функция удалена, таблицы заводят `SCHEMA`/`migrate()`. Сторож `test_pair_reads_keep_callers_open_transaction` краснеет на M3 (`executescript` в `active_pair_suspension`). |

## Вердикт

approved. Требования 1–9 реализованы; замечания итерации 1 закрыты по
ANSWER-1, отступление от буквы п.2 обосновано залоченной планкой и
подтверждено мутацией.

## Проверено исполнением

- `python3 -m pytest -q tests/test_01m3ychvvek14sk8gt4r0h7m2c_set_trial_suspension.py tests/test_pair_suspension_units.py tasks/01M3YCHVVEK14SK8GT4R0H7M2C/acceptance_tests` — 21 passed.
- Затронутые модули (`test_fsm_autogate*`,
  `test_store_schema_migration_parity`, `test_cas_set_state`,
  `test_runner_role_model`, `test_artel_role_restricted_commands`,
  `test_task_model_set_units`, `test_model_sets`,
  `test_canary_acceptance_reason`, `test_01m3ychs4f*`, `test_01m3ychp*`,
  `test_review_freshness`, `test_fsm_advance_gate_smoke`) — 114 passed.
- Временные мутации (скрипт правил файл, прогонял юнит-файл и долгоживущий
  файл задачи и возвращал исходник; `git status` после — чисто):
  - M1: `_consecutive_returns` возвращён к правилу «любой возврат ранее».
    Красный только `test_return_after_approved_previous_task_does_not_suspend`.
  - M2: убрана сверка `last != model` в `suspend_on_autogate_refusal`.
    Красный только `test_autogate_refusal_after_rollback_to_combat_spares_pair`.
  - M3: `executescript(PAIR_SUSPENSION_DDL)` в `store.active_pair_suspension`.
    Красный только `test_pair_reads_keep_callers_open_transaction`.
  - M4: буквальное ANSWER-1 п.2 (`if last != model: return`). Красный
    долгоживущий `test_ac7_role_blame_refusal_suspends_guilty_pair_pult_does_not`.
    Это подтверждает обоснование отступления в PLAN.
- `python3 scripts/codebase_map.py`: diff карты без строки `built_at_sha`
  пустой, карта свежая; файл возвращён `git checkout`.
- Полный набор `tests/` не гонялся (правило скила); CI коммита b9afd4f1 зелёный.

## Предложения системе

- Ответ Оператора (ANSWER) может буквально противоречить залоченной планке
  (здесь ANSWER-1 п.2 против `test_ac7_…`). Стоит, чтобы скил ревьювера
  предлагал вариант ответа с проверкой против зафиксированных тестов ещё в
  эскалации, а не оставлял выбор разработчику.
