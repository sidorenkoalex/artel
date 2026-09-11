---
task: 01M28SWSQ46B8A9FX6KBVJ3Y0G
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: `amend-tests` гоняет трассируемость AC перед сдвигом лока планки

## Подход

Оба входа `amend-tests` (`_cmd_amend_tests` — worktree, `_cmd_amend_
tests_from_branch` — расхождение с головой артефактной ветки) уже несут
проверки «есть правка», «правка только в acceptance_tests/» и
обязательный прогон (`acceptance.run`). Не хватает одной проверки между
первыми двумя и прогоном: трассируемости AC той же функцией, которую уже
гоняет гейт `tests_writing -> in_dev` (`guard.acceptance_traceability_
errors`).

Ядро одно и то же (`guard.scan_ac_content`/`guard.traceability_errors_
from_content`), источник текста — разный:

- worktree-путь: `guard.acceptance_traceability_errors(tdir)` буквально,
  как того требует AC-1. Функция читает `tdir/SPEC.md` с диска, а
  `SPEC.md` там после A7 обычно нет (`tasks/<id>/` живёт только в
  артефактной ветке) — материализую его временно (`_materialize_spec_
  if_missing`, по аналогии с уже существующей `_materialize_tests_if_
  missing`) и убираю сразу после проверки (`finally: unlink`). Материализация
  временная и с очисткой — иначе файл остался бы на диске ВНЕ
  `acceptance_tests/`, и следующий вызов `_worktree_changed_paths` читал
  бы его как правку «за пределами», ломая amend-tests для этого worktree
  навсегда (тот же класс, что AC-3 задачи 01M1HNNHDMP2C1AJTH5QF1BTN2).
  Материализация выполняется ПОСЛЕ проверки «изменения только в
  acceptance_tests/» (не раньше) — тем же порядком, что и сама
  трассируемость по SPEC требованию 1.
- `--from-branch`-путь: источника-диска нет вовсе (SPEC требование 2)
  — читаю SPEC.md и acceptance_tests/ головы артефактной ветки git'ом
  (`gitcmd.show`/уже вычисленный `_branch_tests_snapshot`, тот же приём,
  что `orchestrator/fsm.py::_tests_writing_ac_state` уже применяет для
  чужого чекаута, SPEC T031) и прогоняю то же ядро (`guard.scan_ac_
  content`/`guard.traceability_errors_from_content`) без обращения к
  диску — новый хелпер `_branch_traceability_errors` переиспользует уже
  прочитанный `new_snapshot`, второго обхода дерева не требуется.

Оба отказа — общий хелпер `_refuse_traceability`: журнал actor=operator
(AC-2) + `sys.exit` с текстом «[<id>] amend-tests: отказ — трассируемость
AC нарушена: <ошибки guard через '; '>» (AC-1/AC-3, буквальный префикс
проверяет `_sandbox.py::REFUSAL_PREFIX_RE` приёмочных тестов). Действие
журнала — НЕ `AMEND_ACTION` («правка планки»): иначе отказ засчитывался
бы `_amend_events_in_window` как состоявшуюся правку планки, хотя лок не
сдвинулся.

Порядок в обоих путях: изменения есть и только там, где положено (уже
было) -> трассируемость (новое) -> прогон планки (уже было) -> коммит/
сдвиг лока (AC-4).

Зависимость AC-6 (детекция метки с отступом) от задачи 01M28NX43E (зона
`scripts/guard.py`, вне зон этой задачи) — не смержена в main на момент
этого шага: тест `test_ac6_indented_marker_worktree.py` остаётся красным
по причине вне зоны этой задачи (SPEC, раздел «Контекст», прямо
оговаривает это заранее). Зову `guard.acceptance_traceability_errors`
буквально как есть — когда 01M28NX43E смержится, AC-6 станет зелёным без
изменений в этой задаче.

## Шаги

1. `orchestrator/amend.py`: `_materialize_spec_if_missing`,
   `_refuse_traceability`, `_branch_traceability_errors` + вызовы в
   `_cmd_amend_tests`/`_cmd_amend_tests_from_branch` в нужном порядке
   (AC-1..AC-4).
2. Юнит-тесты `tests/test_amend.py`: изоляция новых хелперов (сборка
   `_branch_traceability_errors` из фейкового git, cleanup материализации
   SPEC.md); приёмочные тесты `tasks/01M28SWSQ46B8A9FX6KBVJ3Y0G/
   acceptance_tests/` — уже поставлены test_author, не мои, только
   прогоняю (AC-5..AC-9).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1, 2 |

## Влияние на систему

Новая проверка встаёт МЕЖДУ уже существующими (изменения только в
acceptance_tests/) и (прогон планки) — ни одна из старых проверок не
убрана и не ослаблена, порядок задан SPEC требованием 3 буквально.
Единственный побочный эффект — временный файл `SPEC.md` на диске
worktree в момент проверки; `finally: unlink` убирает его тем же шагом,
до возврата из функции, так что ни `_worktree_changed_paths`, ни любой
другой код, читающий git-статус этого worktree после вызова
`amend-tests`, его не увидит. Откат — правка изолирована в
`orchestrator/amend.py`, `git revert` одним коммитом безопасен.

## Риски

- AC-6 остаётся красным до мержа 01M28NX43E (вне зоны, оговорено в SPEC
  и в этом PLAN выше) — не дефект этой реализации.

## Предложения системе
