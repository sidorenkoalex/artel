---
task: 01M5KBGF184B07SVXMD4R1NXXC
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/fsm_autogate.py, tests/
budget_usd: 25
---

# SPEC: Отказ автогейта приёмки из-за окружения — отдельный класс «окружение» в журнале и в подсказке

## Контекст
Находка ревизии кода 22.10 CR-2026-10-22-17: 7 из 43 отказов автогейта
приёмки 30.09–22.10 вызваны окружением (таймаут прогона — 5, «машина
занята» — 2), 39 из 43 отказов сняты ручным approve. На отказе
`_maybe_autogate_acceptance` (`orchestrator/fsm_autogate.py:415`) пишет одну
запись журнала «автогейт acceptance не пройден» (`:450`), одну строку вывода
«… — жду Оператора» (`:452`) и зовёт `models.suspend_on_autogate_refusal`
(`:455`). Класса отказа нет ни в записи, ни в выводе: таймаут прогона и
занятая машина выглядят так же, как красный набор или критерии manual.
Правило вины (`models.autogate_refusal_blame`, `orchestrator/models.py:1099`)
уже относит их к `BLAME_PULT`, но в журнал и вывод автогейта не попадает.
Задача добавляет отдельную запись и строку подсказки для класса «окружение»,
не меняя ни прежней записи, ни поведения гейта.

## Требования

1. В `orchestrator/fsm_autogate.py` — константа `ENV_REFUSAL_CLASS =
   "окружение"` и функция `autogate_refusal_class(reason: str) -> str | None`:
   после снятия префикса `models.AUTOGATE_REFUSAL_PREFIX` и схлопывания
   пробельных символов причина относится к классу «окружение», если
   начинается с «прогон полного набора tests/ превысил » (вид «таймаут
   прогона», `acceptance.FULL_SUITE_TIMEOUT`) или с
   `f"{acceptance.FULL_SUITE_NOT_STARTED}: машина занята"` (вид «машина
   занята»). Возвращается вид (`"таймаут прогона"` или `"машина занята"`);
   иначе `None`. Начала строк берутся от констант и функций
   `orchestrator/acceptance.py` (`FULL_SUITE_TIMEOUT`,
   `FULL_SUITE_NOT_STARTED`, `_full_suite_timeout_note`, `_not_started_note`),
   не копируются литералами без сверки (сверку держит требование 6).
2. Отказ класса «окружение» в `_maybe_autogate_acceptance`: прежняя запись
   журнала «автогейт acceptance не пройден» с прежней деталью и прежняя
   строка вывода «`[<id>] <причина> — жду Оператора`» — побайтно как сейчас;
   сразу за ними — вторая запись журнала с новым действием
   `AUTOGATE_ENV_REFUSAL_ACTION = "автогейт acceptance: отказ окружения"`
   (actor `fsm`), деталь — `класс: окружение (<вид>) — качество задачи не
   оценено; повторить проверку: artel.py approve <id>`, и строка вывода
   `[<id>] класс отказа: окружение (<вид>) — качество задачи не оценено;
   повторить проверку: artel.py approve <id>`. Затем — прежний вызов
   `models.suspend_on_autogate_refusal`.
3. Отказ вне класса «окружение» (красный набор, критерии manual/skip,
   критерий ci, пробный период набора, пустой каталог планки, файлы БД
   пульта в дереве прогона, итог неизвестен, бюджет): журнал и вывод —
   побайтно прежние, второй записи и второй строки нет.
4. Поведение гейта не меняется: на отказе любого класса задача остаётся в
   `acceptance`, перехода `state -> merge_gate` нет, повторного прогона и
   автоматического approve нет; предел времени прогона не меняется;
   `models.autogate_refusal_blame` и `models.suspend_on_autogate_refusal` не
   меняются.
5. Тесты детерминированные, без сети: допустимо подменять
   `fsm_autogate.gates.policy`, `fsm_autogate._log_acceptance_checklist`,
   `fsm_autogate._autogate_conditions`,
   `fsm_autogate.models.suspend_on_autogate_refusal`; БД — `TmpRootTest`.
   Сценарии тестов — критерии AC-1..AC-6.
6. В `orchestrator/fsm_autogate.py` меняется только перечисленное: новая
   константа(ы) `ENV_REFUSAL_CLASS`, `AUTOGATE_ENV_REFUSAL_ACTION`, новая
   функция `autogate_refusal_class` и ветка отказа в
   `_maybe_autogate_acceptance`; `_autogate_conditions` и тексты причин не
   меняются. Существующие тесты не правятся и остаются зелёными.

## Критерии приёмки

AC-1. Причина `"автогейт: " + acceptance._full_suite_timeout_note()` с
выжимкой прогона (политика `auto`, `_autogate_conditions` подменён на эту
причину): в журнале задачи две записи — «автогейт acceptance не пройден» с
прежней деталью (сама причина) и следом `AUTOGATE_ENV_REFUSAL_ACTION`
(`"автогейт acceptance: отказ окружения"`, actor `fsm`) с деталью
`класс: окружение (таймаут прогона) — качество задачи не оценено; повторить
проверку: artel.py approve <id>`; в выводе — строка `[<id>] <причина> — жду
Оператора` и за ней строка `[<id>] класс отказа: окружение (таймаут прогона)
— качество задачи не оценено; повторить проверку: artel.py approve <id>`;
состояние задачи — `acceptance`, перехода в `merge_gate` нет. (На текущем
коде — красный: второй записи и строки нет.)

AC-2. Причина `"автогейт: " + acceptance._not_started_note(<держатель
замка>)` — то же, что в AC-1, с видом «машина занята»: две записи журнала
(вторая — `AUTOGATE_ENV_REFUSAL_ACTION` с «окружение (машина занята)»), две
строки вывода, состояние — `acceptance`. (На текущем коде — красный.)

AC-3. Причины `"автогейт: " + acceptance._db_in_tree_note(…)`,
`"автогейт: " + acceptance.FULL_SUITE_NO_TESTS_NOTE`, `"автогейт: полный
набор tests/ красный: …"`, `"автогейт: критерии manual — AC-1 (…)"`,
`"автогейт: бюджет задачи исчерпан"` и причина с `acceptance.UNKNOWN_PREFIX`:
записей с `AUTOGATE_ENV_REFUSAL_ACTION` в журнале нет, запись «автогейт
acceptance не пройден» с причиной в детали — ровно одна, вывод — ровно одна
строка `[<id>] <причина> — жду Оператора`, состояние — `acceptance`.

AC-4. Отказ класса «окружение» при подменённом
`fsm_autogate.models.suspend_on_autogate_refusal`: подмена вызвана ровно один
раз с прежней причиной (той же строкой, что в детали записи «автогейт
acceptance не пройден»); `models.autogate_refusal_blame(<причина>) ==
models.BLAME_PULT`.

AC-5. `canary._acceptance_from_steps` по журналу отказа класса «окружение»
(после AC-1-подобного отказа) возвращает прежнюю деталь записи «автогейт
acceptance не пройден» — вторая запись `AUTOGATE_ENV_REFUSAL_ACTION` её не
подменяет.

AC-6. Сверка с производителями: `fsm_autogate.autogate_refusal_class`
возвращает `"таймаут прогона"` для `acceptance._full_suite_timeout_note()` и
`acceptance._full_suite_timeout_note((1500, "профиль тестов проекта
artel"))` (с префиксом `models.AUTOGATE_REFUSAL_PREFIX` и без), `"машина
занята"` — для `acceptance._not_started_note(<держатель>)`, в том числе с
суффиксом пометки дерева приложений (`appendix_tree`, `[без приложений PLAN:
…]`); возвращает `None` для `acceptance._db_in_tree_note(…)`,
`acceptance.FULL_SUITE_NO_TESTS_NOTE` и текста с `acceptance.UNKNOWN_PREFIX`.
Для каждой причины класса «окружение» `models.autogate_refusal_blame(...) ==
models.BLAME_PULT`.

## Оценка объёма и деление

Сработавшие сигналы: «число затрагиваемых модулей/файлов» (guard считает
все упомянутые в тексте пути `orchestrator/*.py`), «прогноз диффа не дан».

Прогноз диффа: 12 КиБ

**Обоснование монолита.** Сигнал по числу файлов — от перечня модулей
только для чтения (раздел «Не входит», «Материалы»); меняется один файл кода
`orchestrator/fsm_autogate.py` (константы, функция классификации, ветка
отказа в `_maybe_autogate_acceptance`) и тесты в `tests/`. Резать нечего:
функция классификации без ветки отказа никем не читается, а ветка без
функции не может отличить класс — промежуточная часть не несла бы
наблюдаемого поведения ни одного критерия. Решение — за Оператором на гейте
SPEC.

## Не входит

- Автоматический повтор прогона после освобождения машины и любое изменение
  расписания прогонов (решение Оператора; находка оставляет вопрос открытым).
- Изменение предела времени прогона полного набора (решение Оператора 19.10).
- Класс «окружение» в `models.autogate_refusal_blame`, в сводке канарейки и в
  `report`.
- Отказы гейта мержа и ручного `approve` с теми же исходами прогона.
- Разметка прежних отказов в БД.
- Правки только для чтения: `orchestrator/acceptance.py` (тексты исходов),
  `orchestrator/models.py` (правило вины), `orchestrator/canary.py` (читатель
  записи отказа, `_AUTOGATE_REFUSAL_ACTION` и `_acceptance_from_steps`),
  `orchestrator/fsm_advance.py` (вызывающий), `orchestrator/appendix_tree.py`,
  `orchestrator/suite_lock.py`, `orchestrator/store.py`,
  `orchestrator/gates.py`, `orchestrator/report.py`, `gates.yaml`,
  `orchestrator/suite_run.py`, `orchestrator/fsm_merge_gate.py`,
  `orchestrator/advance_gates/outcome_integrity.py` — не меняются.
- Отдельный тест в `tests/` сверх приёмочных тестов критериев AC-1..AC-6:
  свойства держат долгоживущие приёмочные тесты автора тестов (ADR-0020),
  повтор не заказывается.
- Зелёный полный набор `tests/` и CI ветки — их держит пульт.

## Материалы

- ТЗ: `tasks/01M5KBGF184B07SVXMD4R1NXXC/TZ.md`; находка CR-2026-10-22-17
  (`docs/audits/code-revision-2026-10-22.md` копии ревизии).
- Номера строк сверены с деревом задачи (HEAD 1521d8f2): `fsm_autogate.py:415,
  450, 452, 455`; `acceptance.py:355` (`UNKNOWN_PREFIX`), `:2326`
  (`FULL_SUITE_TIMEOUT`), `:2333` (`FULL_SUITE_NOT_STARTED`), `:2343`
  (`FULL_SUITE_NO_TESTS_NOTE`), `:2353`, `:2365`, `:2385`;
  `models.py:997` (`BLAME_PULT`), `:1001` (`AUTOGATE_REFUSAL_PREFIX`),
  `:1099`; `canary.py:1970`, `:2012`.
- Бюджет: ТЗ называет $15, но калибровка (`config.BUDGET_CALIBRATION_TABLE`,
  пол `BUDGET_CALIBRATION_FLOOR_USD = 25.0`; правило скила «планка не ниже
  $25») не допускает ниже $25; класс задачи (6 критериев, 2 зоны) по таблице —
  $40, поставлено $25 — минимум, ближайший к заявке Оператора.
  Оператор вправе править на гейте.
- Новых состояний FSM задача не вводит — `tests/test_invariants.py` по числу
  шагов не задевается.
