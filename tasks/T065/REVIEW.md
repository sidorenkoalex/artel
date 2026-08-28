---
task: T065
type: review
author_role: reviewer
status: approved        # draft | approved | changes_requested | escalate
iteration: 1
schema_version: 2    # версия формата артефакта, см. scripts/guard.py
---

# REVIEW: К3-канарейка: команда canary, метрики, бейзлайн

## Гейт плана

Покрытие SPEC → PLAN полное (таблица «Покрытие требований» бьёт все 8
требований на шаги 1-5, не оставляет пробелов). Шаги — проверяемые
единицы (схема; catalog/status; retro; сам модуль canary.py + CLI;
тесты), не микрооперации и не «сделать всё разом». Подход (отдельный
кодовый путь в `canary.py`, копирующий узкую ветку гейт-логики
`fsm._cmd_approve` вместо вызова `cmd_approve`/`auto`) не конфликтует
с конвенциями и явно обосновывается требованием 2 SPEC и инвариантом 18
— решение согласовано Оператором на гейте SPEC 28.08 и задокументировано
в PLAN «Подход». Гейт плана пройден.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `cmd_canary` (`orchestrator/canary.py:190-207`) заводит задачу на каждый `*.md` переданного каталога через `catalog.cmd_new(..., tz_path=..., canary=True)`; каталог не жёстко привязан к эталонным файлам — фильтр только по суффиксу. |
| 2 | OK | `_drive_task` (`canary.py:78-101`) гоняет `auto.cmd_auto` до гейта; `_pass_spec_gate`/`_pass_acceptance_gate` — отдельный путь через `store.set_state(..., actor="canary", ...)`, не через `fsm.cmd_approve`/`auto`. Проверено построчным сравнением с `fsm._cmd_approve` (spec_gate/acceptance ветки, `orchestrator/fsm.py:907-954`): `_spec_gate_next_state` использует `guard.requires_ac_markup(meta)`, которая уже сама учитывает `skip_tests` (`scripts/guard.py:137-147`) — расхождения с реальным approve нет, ветвление эквивалентно. `_pass_acceptance_gate` дословно повторяет `_pull_main_or_escalate` + переход в merge_gate. Пометка `canary` — через `actor` перехода, попадает в журнал `set_state`. |
| 3 | OK | `_kill_at_merge_gate` (`canary.py:70-75`) пишет причинную запись и зовёт штатный `cleanup.cmd_kill` — не approve. AC-1 подтверждает: sha main до/после идентичен (тест зелёный). |
| 4 | OK | `_task_metrics`/`_summary` считают шаги/стоимость/итерации ревью/эскалации/исход из журнала и строки `tasks`; отчёт пишется в stdout и `.artel/canary/<timestamp>.json` (`_write_report`). Оценки «уместности» эскалации в отчёте нет — только сырые `detail` записей `state -> escalated`. |
| 5 | OK | `_read_baseline`/`_write_baseline`/`_baseline_warnings` (`canary.py:139-176`) — первый прогон пишет `baseline.json` безусловно, последующие сравнивают и предупреждают при `|отклонение| > config.CANARY_DEVIATION_RATIO` (0.5), не трогая файл без `--rewrite-baseline`. |
| 6 | OK | `tasks.is_canary` — единственный носитель пометки (`store.py:35,143`); `title` канареечной задачи не тронут (`catalog.cmd_new` пишет `title` как есть, только `is_canary` уходит в `insert_task`). `cmd_status`/`retro.build_done`/`build_killed` показывают пометку только по колонке. `store.total_spent` суммирует `spent_usd` по всем строкам без фильтра — расход учтён наравне с продуктовыми (проверено `test_total_spent_counts_canary_task_alongside_product`, AC-4). |
| 7 | OK | Бюджет canary-задачи ставится тем же `budget.apply_spec_budget` на переходе `spec_writing -> spec_gate` внутри обычного `fsm._cmd_advance`, вызываемого из `auto.cmd_auto` — `canary.py` не импортирует и не трогает `orchestrator/budget.py`. |
| 8 | OK | Гейт-переходы `canary.py` живут только в этом модуле, вызываются только из его же `_drive_task` для задач, заведённых им же; `fsm.py`/`auto.py` не изменены ни строкой (diff это подтверждает). AC-5 гоняет `ManualGatesNeedTheOperatorTest`, `MergeOnlyFromMergeGateTest` (`tests/test_invariants.py`) и `AutoNeverPassesAGateTest` (фактически в `tests/test_auto_cycle.py`, а не в `test_invariants.py`, как буквально написано в SPEC/AC-5 — сам приёмочный тест честно фиксирует эту неточность адреса в docstring и импортирует из настоящего места; на предмет критерия это не влияет). |

Критерии приёмки AC-1..AC-5 — прогнаны локально (`python3 -m unittest discover -s tasks/T065/acceptance_tests`), все 5 зелёные. Полный набор (`python3 -m unittest discover -s tests`) — 867 тестов, зелёный. `python3 scripts/guard.py tasks/T065/SPEC.md tasks/T065/PLAN.md` — ок. `python3 scripts/codebase_map.py --check` — карта свежая.

## Замечания

- minor — `orchestrator/canary.py:52` (`_pass_acceptance_gate`) — использует `fsm._pull_main_or_escalate` — функцию с ведущим подчёркиванием, то есть внутреннюю деталь реализации `fsm.py`, не публичный контракт модуля. Ничто в `fsm.py` не сигнализирует о существовании внешнего вызывателя этой функции: будущий рефакторинг `fsm.py` (например, смена сигнатуры `state` на `t["state"]`, или расширение веток `_pull_main_or_escalate` новым исходом помимо `fresh`/`pulled`/`escalated`) может молча сломать `canary.py`, и `fsm.py`'s собственный тестовый набор об этом не предупредит — только упадёт сам `canary.py`. Решение осознанное и обосновано в PLAN («Подход» — не через `cmd_approve`), поэтому не blocker, но стоит держать в уме при следующей правке `_pull_main_or_escalate`.
- minor — `orchestrator/canary.py:24-30` (`_spec_gate_next_state`) — копирует ветвление `fsm._cmd_approve`'s блока `spec_gate` (`fsm.py:907-945`) вместо вызова общей функции. Сегодня логика эквивалентна (`guard.requires_ac_markup` уже учитывает `skip_tests`, проверено построчно и тестами), но это дублирование: если ветвление `_cmd_approve` для `spec_gate` когда-либо получит третье условие (кроме версии схемы и `skip_tests`), `canary.py` не унаследует его автоматически, и расхождение всплывёт только на реальном каноническом прогоне, не на unit/acceptance тестах этой задачи (они гоняют оба пути по отдельности, не сверяя их между собой). Предложение на будущее (не для этой итерации): либо вынести общий предикат «куда идти из spec_gate» в `fsm.py` как публичную функцию, которую зовут оба места, либо завести тест, специально сверяющий `canary._spec_gate_next_state` с `fsm._cmd_approve` на матрице meta-комбинаций.

## Вердикт

approved

## Предложения системе

- `docs/invariants.md`, раздел инварианта 18 — задача независимо подтвердила наблюдение самого PLAN («Предложения системе»): паттерн «отдельный узкий кодовый путь вместо вызова публичной команды approve/auto» встретился уже во второй задаче класса «детерминированная автоматизация поверх конвейера» без Оператора (после `auto` самого). Стоит зафиксировать рецепт рядом с инвариантом 18, чтобы следующая такая задача не выводила границу заново из формулировки и контекста SPEC.
