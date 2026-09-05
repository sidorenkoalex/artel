---
task: 01M1REVMB50SND1KJ3CYQMV2ST
type: plan
author_role: developer
status: ready
schema_version: 4
---

# PLAN: эскалация «конфликт подтяжки main» называет конфликтные файлы

## Подход

`_pull_main_or_escalate` (`orchestrator/fsm.py`) на неудачном `git merge`
писал `detail` эскалации только из `merge.stderr` — а git печатает
«CONFLICT (content): …»/«Automatic merge failed» в `stdout`, не в
`stderr`, и список конфликтующих файлов туда вообще не попадал.

Список конфликтов (`_conflicting_files`, T067) уже вычислялся ДО
`merge --abort` для решения об авторазрешении карты (`_auto_resolve_
map_conflict`) — переиспользуем то же значение для detail, не гоняем
`git diff` второй раз. Формат сборки (список файлов + хвост stdout +
хвост stderr, пустые части выброшены) вынесен в отдельную чистую
функцию `_merge_conflict_note(files, merge)`, чтобы не разрастать и
так длинный `_pull_main_or_escalate` и чтобы формат был тестируем без
дублирования всей FSM-песочницы.

`_auto_resolve_map_conflict` и условие её вызова (`files == [MAP_REL]`)
не тронуты — задача только читает уже собранный список, не меняет
логику разрешения (SPEC «Не входит»).

## Шаги

1. `orchestrator/fsm.py`: `files = _conflicting_files(wt_path)` теперь
   вычисляется безусловно при неудачном merge (раньше — только внутри
   `if merge is not None:`, что и требовалось для решения об
   авторазрешении карты); новая функция `_merge_conflict_note(files,
   merge)` собирает `detail` по формату AC-1..AC-3; вызов на месте
   прежнего `note = merge.stderr.strip()[:500] ...` заменён на неё.
   Прогон `tests/test_branch_freshness_gate.py` и `tests/test_fsm_map_
   conflict_autoresolve.py` без изменений (AC-4) и локальный юнит-тест
   `tests/test_fsm_merge_conflict_note.py` на саму функцию.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 (тот же detail — существующий канал печати `store.set_state`, отдельного кода вывода не добавлено) |
| 3 | 1 (`_auto_resolve_map_conflict` и условие её вызова не изменены) |

## Влияние на систему

Изменение локально в `_pull_main_or_escalate`: меняется только состав
строки `detail` эскалации конфликта подтяжки, которая раньше могла
быть пустой. Поведение переходов (успешный merge, «ветка не отстала»,
красная приёмка после подтяжки, авторазрешение карты) не меняется —
`_auto_resolve_map_conflict` и её условие вызова не тронуты, `git merge
--abort` по-прежнему выполняется до записи эскалации. Тесты/гейты не
ослабляются: `tests/test_branch_freshness_gate.py` и `tests/test_fsm_
map_conflict_autoresolve.py` остаются зелёными без правки утверждений
(AC-4), приёмочные тесты задачи (`tasks/01M1REVMB50SND1KJ3CYQMV2ST/
acceptance_tests/test_pull_conflict_detail.py`) зелёные. Откат —
одиночный revert коммита, новая функция не используется больше нигде.

## Риски

Нет.

## Предложения системе
