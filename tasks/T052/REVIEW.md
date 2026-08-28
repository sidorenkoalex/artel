---
task: T052
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 2
---

# REVIEW: Возврат из merge_gate в разработку

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (reject из merge_gate → in_dev, причина в журнале) | OK | Без изменений с итерации 1; `_cmd_reject`, AC-1 зелёный. |
| 2 (три исхода провала merge) | OK | Блокер итерации 1 закрыт: `_handle_merge_conflict` (orchestrator/fsm.py:722-768) при отказе `git merge --abort` теперь не переводит состояние вовсе — журналирует `"merge --abort FAILED"` и `sys.exit` (fsm.py:759-766), задача остаётся в `merge_gate`. Три исхода (содержательный конфликт → in_dev, конфликт в защищённых путях → escalated, инфраструктурный отказ, включая неудавшийся abort, → отказ без перехода) теперь разобраны полностью. |
| 3 (красный CI не выталкивает из гейта) | OK | Ветка CI в `_cmd_approve` не тронута; AC-5 зелёный. |
| 4 (счётчики не сбрасываются) | OK | Новый код (журналирование abort-отказа, `sys.exit`) не читает и не пишет `review_iters`/`accept_rejects`; AC-7 зелёный. |
| 5 (возврат не меняет main, кроме отмены merge-попытки) | OK | При неудачном `git merge --abort` переход состояния теперь не происходит — main остаётся грязным явно и видимо (задача в `merge_gate`, диагностика в журнале и в тексте `sys.exit`), а не тихо объявляется «чистым» под успешным переходом. Соответствует требованию 5 и предложению из итерации 1. |
| 6 (новых состояний FSM нет) | OK | Используются только `in_dev`/`escalated`, плюс отказ без перехода (остаётся `merge_gate`). |
| 7 (только orchestrator/, тесты, карта) | OK | Диф ограничен `orchestrator/fsm.py`, `tests/test_invariants.py`, `docs/codebase-map.md` (git diff --stat, инкремент и полный диф ветки). Перегенерировал карту локально — диф только `built_at_sha`, содержимое актуально. |

## Замечания

Пусто — блокер итерации 1 закрыт, новых замечаний нет.

## Проверка

- Полный набор тестов: `python3 -m unittest discover -s tests -q` → 763 теста, зелёные.
- Приёмочные тесты: `python3 -m unittest discover -s tasks/T052/acceptance_tests -q` → 14 тестов (AC-1..AC-8), зелёные.
- Новый юнит-тест `test_merge_abort_failure_keeps_task_in_the_gate` (tests/test_invariants.py:505-533) прогнан отдельно — мутационная проверка: если убрать досрочный `sys.exit` при отказе `abort` (вернуть прежнее поведение), тест падает на `self.assertEqual(self.state(), "merge_gate", ...)` — тест ловит регрессию блокера итерации 1, не просто дублирует структуру кода.
- Прочитан `orchestrator/fsm.py:722-800` целиком (docstring `_handle_merge_conflict` + тело) — подтверждено, что `sys.exit` при отказе `abort` вызывается ДО вычисления `file_list`/`protected`/`store.set_state`, то есть переход состояния структурно недостижим на этом пути, а не просто не наблюдается в тесте по случайности порядка веток.
- `docs/codebase-map.md`: `python3 scripts/guard.py` → «GUARD: ок»; регенерация карты (`python3 scripts/codebase_map.py`) и откат локальной правки после сверки — диф свежести только в `built_at_sha`.

## Вердикт

approved — блокер итерации 1 (`_handle_merge_conflict`, отказ `git merge --abort` не должен приводить к переходу состояния при грязном main) закрыт корректно: путь теперь структурно не может выполнить `set_state` при неудавшемся `abort`, добавлен целевой тест, полный набор тестов и все AC1-AC8 зелёные, диф не выходит за заявленные файлы (`orchestrator/fsm.py`, `tests/test_invariants.py`, `docs/codebase-map.md`).

## Предложения системе

