---
task: 01M5KBGF184B07SVXMD4R1NXXC
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Отказ автогейта приёмки из-за окружения — отдельный класс «окружение» в журнале и в подсказке

# Отказ автогейта приёмки из-за окружения — отдельный класс «окружение» в журнале и в подсказке

## Факты

Находка ревизии кода 22.10 CR-2026-10-22-17 (отчёт `docs/audits/code-revision-2026-10-22.md` копии ревизии, раздел находок: 7 из 43 отказов автогейта приёмки 30.09–22.10 — таймаут прогона 5 и «машина занята» 2; 39 из 43 отказов сняты ручным approve). Ссылки сверены с `origin/main` 71ce9904; `orchestrator/fsm_autogate.py` между пином и `origin/main` изменился в `_plank_rule_refusal` (номера строк ниже `:250` на `origin/main` больше пиновых на 11).

- Решение автогейта — `orchestrator/fsm_autogate.py:415` (`_maybe_autogate_acceptance`). Причину отказа одной строкой отдаёт `orchestrator/fsm_autogate.py:272` (`_autogate_conditions`); для полного набора — `return ok, f"автогейт: {tree.mark(run.detail)}"` (`orchestrator/fsm_autogate.py:397`), где `run.detail` строит `orchestrator/acceptance.py:2477` (`_full_suite_detail`).
- На отказе — одна запись журнала `store.journal(conn, task_id, "fsm", "автогейт acceptance не пройден", reason)` (`orchestrator/fsm_autogate.py:450`), одна строка вывода `print(f"[{task_id}] {reason} — жду Оператора")` (`:452`) и `models.suspend_on_autogate_refusal(conn, t, reason)` (`:455`). Класса отказа нет ни в записи, ни в выводе: таймаут прогона и занятая машина выглядят так же, как красный набор или критерии manual.
- Тексты исходов окружения — функции производителя в `orchestrator/acceptance.py`: таймаут — `_full_suite_timeout_note` (`orchestrator/acceptance.py:2353`, начало «прогон полного набора tests/ превысил »); «машина занята» — `_not_started_note` (`orchestrator/acceptance.py:2365`, начало `f"{FULL_SUITE_NOT_STARTED}: машина занята прогоном "`, `FULL_SUITE_NOT_STARTED = "прогон не начат"` — `orchestrator/acceptance.py:2333`). Тем же началом «прогон не начат: » идут исходы, которые окружением не являются: файлы БД пульта в дереве прогона — `_db_in_tree_note` (`orchestrator/acceptance.py:2385`, лечится `worktree-db-clean`), и итог неизвестен — `UNKNOWN_PREFIX` (`orchestrator/acceptance.py:355`).
- Правило вины отказа автогейта уже есть: `orchestrator/models.py:1099` (`autogate_refusal_blame`) относит таймаут и «прогон не начат» к `BLAME_PULT` (`orchestrator/models.py:1023`, `_PULT_BLAME_STARTS`) вместе с пустым каталогом планки и исчерпанным бюджетом, поэтому `suspend_on_autogate_refusal` пару набора на них не приостанавливает. Правило служит канарейке и допуску пар; в журнал и в вывод автогейта оно не попадает.
- Читатели записи отказа по точному имени действия: `orchestrator/canary.py:1970` (`_AUTOGATE_REFUSAL_ACTION`) — выдержка журнала и `_acceptance_from_steps` (деталь записи становится `canary_runs.autogate_refusal`). Новое действие журнала они не читают; прежняя запись обязана остаться побайтно прежней.
- Журнал главной копии (чтение, 23.10): действие «автогейт acceptance не пройден» с деталью «прогон полного набора tests/ превысил 1500с …» — у 01M4AG3QYV, 01M4P4ZP37, 01M55VDVVD, 01M5ENWTDD, 01M5FRYVP4, 01M5J0JYW3; «прогон не начат: машина занята прогоном …» — у 01M4R4JQZE, 01M55VGDHX; «прогон не начат: полный набор tests/ не проверен — в дереве прогона лежат файлы БД пульта» — у 01M4TVBT9Z (не окружение).
- Защита, которую задача не трогает: предел времени прогона полного набора (решение Оператора 19.10) и сам отказ автогейта — задача остаётся в `acceptance` и ждёт Оператора.

## Требования

1. В `orchestrator/fsm_autogate.py` — константа `ENV_REFUSAL_CLASS = "окружение"` и функция `autogate_refusal_class(reason: str) -> str | None`: после снятия префикса `models.AUTOGATE_REFUSAL_PREFIX` и схлопывания пробельных символов причина относится к классу «окружение», если начинается с «прогон полного набора tests/ превысил » (вид «таймаут прогона», `acceptance.FULL_SUITE_TIMEOUT`) или с `f"{acceptance.FULL_SUITE_NOT_STARTED}: машина занята"` (вид «машина занята»). Возвращается вид (`"таймаут прогона"` или `"машина занята"`); иначе `None`. Начала строк берутся от констант и функций `orchestrator/acceptance.py`, не копируются литералами без сверки (требование 6).
2. Отказ класса «окружение» в `_maybe_autogate_acceptance`: прежняя запись журнала «автогейт acceptance не пройден» с прежней деталью и прежняя строка вывода «… — жду Оператора» — побайтно как сейчас; сразу за ними — вторая запись журнала с новым действием `AUTOGATE_ENV_REFUSAL_ACTION = "автогейт acceptance: отказ окружения"` (actor `fsm`), деталь — `класс: окружение (<вид>) — качество задачи не оценено; повторить проверку: artel.py approve <id>`, и строка вывода `[<id>] класс отказа: окружение (<вид>) — качество задачи не оценено; повторить проверку: artel.py approve <id>`. Затем — прежний вызов `models.suspend_on_autogate_refusal`.
3. Отказ вне класса «окружение» (красный набор, критерии manual/skip, критерий ci, пробный период набора, пустой каталог планки, файлы БД пульта в дереве прогона, итог неизвестен, бюджет): журнал и вывод — побайтно прежние, второй записи и второй строки нет.
4. Поведение гейта не меняется: на отказе любого класса задача остаётся в `acceptance`, перехода `state -> merge_gate` нет, повторного прогона и автоматического approve нет; предел времени прогона не меняется; `models.autogate_refusal_blame` и `models.suspend_on_autogate_refusal` не меняются.
5. Тесты, детерминированные, без сети (можно подменять `fsm_autogate.gates.policy`, `fsm_autogate._log_acceptance_checklist`, `fsm_autogate._autogate_conditions`, `fsm_autogate.models.suspend_on_autogate_refusal`; БД — `TmpRootTest`):
   - причина `"автогейт: " + acceptance._full_suite_timeout_note()` с выжимкой прогона — в журнале две записи (прежняя с прежней деталью и `AUTOGATE_ENV_REFUSAL_ACTION` с «окружение (таймаут прогона)»), в выводе — строка «класс отказа: окружение (таймаут прогона)», состояние задачи — `acceptance` (на текущем коде — красный: второй записи и строки нет);
   - причина `"автогейт: " + acceptance._not_started_note(<держатель замка>)` — то же с видом «машина занята» (на текущем коде — красный);
   - причины `"автогейт: " + acceptance._db_in_tree_note(…)`, `"автогейт: " + acceptance.FULL_SUITE_NO_TESTS_NOTE`, `"автогейт: полный набор tests/ красный: …"`, `"автогейт: критерии manual — AC-1 (…)"`, `"автогейт: бюджет задачи исчерпан"`, причина с `acceptance.UNKNOWN_PREFIX` — записей с `AUTOGATE_ENV_REFUSAL_ACTION` нет, вывод — ровно одна строка `[<id>] <причина> — жду Оператора`;
   - отказ класса «окружение» при подменённом `fsm_autogate.models.suspend_on_autogate_refusal` — подмена вызвана один раз с прежней причиной; `models.autogate_refusal_blame(<причина>) == models.BLAME_PULT`;
   - `canary._acceptance_from_steps` по журналу отказа класса «окружение» возвращает прежнюю деталь записи «автогейт acceptance не пройден» — вторая запись её не подменяет.
6. Тест сверки с производителями: `autogate_refusal_class` относит к «окружению» тексты `acceptance._full_suite_timeout_note()` и `acceptance._full_suite_timeout_note((1500, "профиль тестов проекта artel"))`, `acceptance._not_started_note(<держатель>)`, в том числе с суффиксом пометки дерева приложений (`appendix_tree` `[без приложений PLAN: …]`); не относит `acceptance._db_in_tree_note(…)`, `acceptance.FULL_SUITE_NO_TESTS_NOTE` и текст с `acceptance.UNKNOWN_PREFIX`. Каждая причина класса «окружение» имеет `models.autogate_refusal_blame(...) == models.BLAME_PULT`.
   Существующие тесты не правятся и остаются зелёными.

Зоны: orchestrator/fsm_autogate.py, tests/

Ограничение зон по смыслу: в `orchestrator/fsm_autogate.py` — только новая константа, новая функция классификации и ветка отказа в `_maybe_autogate_acceptance`; `_autogate_conditions` и тексты причин не меняются.

Только чтение: orchestrator/acceptance.py (тексты исходов — не меняются), orchestrator/models.py (правило вины — не меняется), orchestrator/canary.py (читатель записи отказа — не меняется), orchestrator/fsm_advance.py (вызывающий `_maybe_autogate_acceptance` — не меняется), orchestrator/appendix_tree.py, orchestrator/suite_lock.py, orchestrator/store.py, orchestrator/gates.py, orchestrator/report.py, gates.yaml; читатели тех же исходов прогона (не меняются): orchestrator/suite_run.py, orchestrator/fsm_merge_gate.py, orchestrator/advance_gates/outcome_integrity.py.

Не входит: автоматический повтор прогона после освобождения машины и любое изменение расписания прогонов (решение Оператора, находка оставляет вопрос открытым: «не проверено, что правка нужна в коде, а не в расписании»); изменение предела времени прогона; класс «окружение» в `models.autogate_refusal_blame`, в сводке канарейки и в `report`; отказы гейта мержа и ручного `approve` с теми же исходами прогона; разметка прежних отказов в БД.

Бюджет: $15.
