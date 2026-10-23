---
task: 01M5KBGF184B07SVXMD4R1NXXC
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Отказ автогейта приёмки из-за окружения — класс «окружение» в журнале и в подсказке

## Подход
Одна правка `orchestrator/fsm_autogate.py`:
- константы `ENV_REFUSAL_CLASS = "окружение"`, `AUTOGATE_ENV_REFUSAL_ACTION =
  "автогейт acceptance: отказ окружения"`;
- `autogate_refusal_class(reason)`: снимает `models.AUTOGATE_REFUSAL_PREFIX`,
  схлопывает пробельные символы; начало «прогон полного набора tests/ превысил »
  (неизменная часть текста `acceptance._full_suite_timeout_note` до числа
  секунд, сверку держит AC-6) → `acceptance.FULL_SUITE_TIMEOUT` («таймаут
  прогона»); начало `f"{acceptance.FULL_SUITE_NOT_STARTED}: машина занята"` →
  «машина занята»; иначе `None`. «прогон не начат» без «: машина занята»
  (`_db_in_tree_note`) в класс не попадает;
- в ветке отказа `_maybe_autogate_acceptance` после прежних записи и строки
  вывода — при непустом виде вторая запись журнала (actor `fsm`) и строка
  `[<id>] класс отказа: окружение (<вид>) — качество задачи не оценено;
  повторить проверку: artel.py approve <id>`; затем прежний
  `models.suspend_on_autogate_refusal`.

Отдельных тестов в `tests/` не добавлено: SPEC («Не входит») прямо не
заказывает их сверх планки AC-1..AC-6.

## Шаги
1. Константы, `autogate_refusal_class`, ветка отказа в
   `_maybe_autogate_acceptance`; регенерация `docs/codebase-map.md`.
   Проверка: `artel.py plank-run 01M5KBGF184B07SVXMD4R1NXXC` — 6 passed;
   `pytest tests/test_fsm_autogate*.py tests/test_canary_acceptance_reason.py
   tests/test_approve_acceptance_full_suite.py tests/test_model_sets.py …` —
   82 passed; `tests/test_acceptance.py tests/test_long_lived_transitions.py
   tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py` — 55 passed.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1 |
| 5 | 1 (планка test_author) |
| 6 | 1 |

## Влияние на систему
Прежние запись «автогейт acceptance не пройден», строка «— жду Оператора»,
вызов `suspend_on_autogate_refusal`, переходы FSM, `_autogate_conditions`,
правило вины и тексты причин не меняются — добавляется только вторая запись
и строка для класса «окружение». Читатель журнала канарейки
(`canary._acceptance_from_steps`) ищет действие «автогейт acceptance не
пройден» — новое действие другое и его не подменяет (AC-5). Гейты, лимиты,
тесты не ослабляются. Откат — revert коммита задачи.

## Риски
- Смена текста `_full_suite_timeout_note` в `acceptance.py` разошлась бы с
  литералом начала; ловит AC-6 планки (разовый), долгоживущего сторожа нет.

## Предложения системе
- Начало текста таймаута — литерал в `fsm_autogate.py`, потому что
  `acceptance.py` не выносит его константой (как `FULL_SUITE_NOT_STARTED`);
  константа-начало в `acceptance.py` убрала бы дублирование и разовость сверки.
