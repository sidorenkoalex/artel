---
task: 01M283NJV2PNDSS7J2HKS19YHJ
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/fsm_advance.py, orchestrator/acceptance.py, tests/
budget_usd: 25
---

# SPEC: регрессия №16 — планка на переходе `in_dev -> verifying` гоняется и при свежей ветке

## Контекст

На переходе `in_dev -> verifying` (`fsm_advance.in_dev`) порядок такой:
сначала подтяжка main (`fsm._pull_main_or_escalate` → `pull.evaluate`),
затем прогон планки (`_acceptance_run_refuses`). Когда ветка отстаёт от
main, `pull.py` после merge материализует `tasks/<id>/acceptance_tests/`
из артефактной ветки в worktree и гоняет планку — этот путь работает
верно. Когда ветка свежая (исход `Fresh`, подтяжка ничего не делает),
`_acceptance_run_refuses` для собственного target берёт
`acc_tdir = <worktree>/tasks/<id>`, а этот каталог после автокоммита
шага пуст — `tasks/<id>/` перенесён в артефактную ветку и убран с диска.
`acceptance.run` в этом случае молча отвечает зелёным «acceptance_tests/
нет — приёмочные тесты не заведены», и залоченная планка не гоняется.
Типичный случай — возврат из ревью → шаг developer → advance, пока main
не сдвинулся. Для внешнего target `_acceptance_run_refuses` уже
материализует планку тем же приёмом (`acceptance.materialize_from_branch`)
— для собственного target такого шага нет.

## Требования

1. `_acceptance_run_refuses` для собственного target материализует
   планку из артефактной ветки в worktree задачи
   (`acceptance.materialize_from_branch(task_id, branch, <worktree>)`) ДО
   `acceptance.run`, независимо от исхода подтяжки (`Fresh`/`Pulled`) —
   как уже сделано для внешнего target.
2. Планка не найдена в источнике при `tests_locked_sha` (или при
   AC-разметке SPEC без `skip_tests`) — именованный отказ перехода
   «планка не найдена в источнике», не зелёное «не заведены»; легитимное
   отсутствие — только `skip_tests` либо SPEC без AC-разметки (то же
   правило, что у `pull.py`).
3. Повторный прогон на пути `Pulled` (подтяжка уже гоняла планку)
   допустимо оставить; ослаблять до «ни одного прогона» нельзя.
4. Тесты: задача с залоченной планкой, worktree на ветке, пустой
   `tasks/<id>` в worktree, ветка не отстаёт от main → планка
   материализована и прогнана, красный тест отказывает переход (мутация
   «пропуск материализации» — красный); планки нет в артефактной ветке
   при локе → отказ; `skip_tests` → переход проходит. Существующие
   тесты — без правки ассертов.

## Критерии приёмки

AC-1. Для собственного target `_acceptance_run_refuses` вызывает
`acceptance.materialize_from_branch(task_id, branch, <worktree>)` ДО
`acceptance.run`, независимо от исхода подтяжки (`Fresh` или `Pulled`).

AC-2. Планка не найдена в источнике (артефактная ветка не несёт
`tasks/<id>/acceptance_tests/`) при `tests_locked_sha`, либо при
AC-разметке SPEC без `skip_tests`, — переход `in_dev -> verifying`
отклоняется именованным отказом «планка не найдена в источнике», не
зелёным исходом «acceptance_tests/ нет — приёмочные тесты не заведены».

AC-3. Отсутствие планки не блокирует переход только тогда, когда SPEC
несёт `skip_tests`, либо SPEC не несёт AC-разметки.

AC-4. На пути `Pulled` (подтяжка уже прогнала планку) `_acceptance_run_
refuses` всё равно прогоняет планку — поведение не ослаблено до
отсутствия повторного прогона на этом переходе.

AC-5. Тест воспроизводит регрессию №16: задача с залоченной планкой
(`tests_locked_sha`), worktree на своей ветке, пустой `tasks/<id>` на
диске worktree, ветка не отстаёт от main (исход `Fresh`) — переход
материализует и прогоняет планку; тест красный на мутации «пропуск
материализации». Отдельные тесты покрывают: отсутствие планки в
артефактной ветке при локе (отказ из AC-2) и `skip_tests` (переход
проходит). Существующие тесты остаются зелёными без правки ассертов.

## Не входит

- `orchestrator/pull.py` — путь `Pulled`/`Conflict` не правится, только
  используется как есть.
- `orchestrator/checkpoint.py`.
- Порядок состояний ADR-0015 (последовательность гейтов `in_dev ->
  verifying`) — не меняется, только исправляется отсутствующий шаг
  материализации внутри существующего гейта `_acceptance_run_refuses`.
- Автогейт приёмки.

## Материалы

- Бэклог П1, регрессия №16 (`docs/backlog.md`).
- R2 (01M1TKNXX5YN5KT4WHG4T44JWV) и «CI до ревью» (01M1TQ0TRC…,
  ADR-0015) — условие старта, закрыли регрессию №16 лишь частично.
- Тот же приём для внешнего target: `orchestrator/fsm_advance.py`,
  `_acceptance_run_refuses`, ветка `if target != config.DEFAULT_TARGET`.
- Именованный отказ «планка не найдена в источнике» — прецедент
  `orchestrator/pull.py::_materialize_and_run_plank`.
