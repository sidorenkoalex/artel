---
task: 01M1GJ3ZP1YGG5QRB6FQ44NN8D
type: plan
author_role: developer
status: ready
schema_version: 3
---

# PLAN: Сухой прогон приёмки — предпросмотр без исполнения

## Подход

Новая read-only CLI-команда `acceptance-dry-run <id>`, реализация в новом
модуле `orchestrator/dry_run.py`, регистрация в таблице диспетчера
`orchestrator/artel.py::main`.

Чтение `SPEC.md` и `tasks/<id>/acceptance_tests/` — ВСЕГДА через git
(`gitcmd.branch_exists`/`gitcmd.ls_tree_files`/`gitcmd.show`), никогда с
диска рабочей копии, безусловно (не только при «чужом чекауте» — SPEC
требование 5 явно требует ветко-корректности независимо от текущего
чекаута, а AC-7 проверяет это конфликтующим содержимым на диске).
Это сильнее, чем ветвление `on_foreign_branch` в `orchestrator/fsm.py` и
диск-приоритет в `orchestrator/fsm_advance.py` (тот код читает диск,
когда worktree задачи заведён на своей ветке — здесь так нельзя, диск
никогда не источник). Разбор содержимого — `scripts/guard.py::
scan_ac_content` над списком текстов, прочитанных `gitcmd.show` (SPEC
требование 2, AC-4): тот же путь, что «чужой чекаут» ветка в
`orchestrator/fsm.py::_tests_writing_ac_state`. Ничего не пишется на
диск — `acceptance.materialize_from_branch` (временный каталог,
подходящий для `guard.scan_acceptance_tests`/`acceptance.run`) сознательно
не используется: он лишний, раз есть `scan_ac_content` над текстом, а
временный каталог создавал бы риск для AC-6 (ничего не материализуется
и не остаётся на диске) без всякой выгоды.

Список ВСЕХ обнаруженных тестовых файлов/методов (AC-1, независимо от
AC-разметки) — по тем же путям и текстам, что уже прочитаны для
`scan_ac_content`, методы — regex `guard.TEST_METHOD` (тот же паттерн,
которым `scripts/guard.py::count_test_methods` считает методы) —
переиспользование существующего паттерна, не новый парсер.

Список AC из SPEC — `guard.AC_ITEM.findall(guard.section_body(spec_text,
"Критерии приёмки"))`, тот же приём, что использует
`guard.traceability_errors_from_content` внутри себя.

Два разных именованных отказа (AC-8): ветки нет (`gitcmd.branch_exists`
= False) — называет ветку; ветка есть, но `gitcmd.ls_tree_files(branch,
"tasks/<id>/acceptance_tests")` не содержит ни одного `test_*.py` —
называет каталог. Порядок проверок исключает попадание в общий текст
на оба случая.

Read-only (AC-5): никаких `store.journal`/`store.set_state`/
`lease.acquire`/`subprocess`-вызовов unittest — только `store.db()` +
`store.resolve_task_id` + `store.get_task` (обе — `SELECT`) для ветки
задачи, дальше — только чтения git. Маркер «сухой прогон — не является
прохождением приёмки» — константа модуля, напечатанная дословно (AC-6);
ничего не сохраняется — печать в stdout, возврат `None`.

## Шаги

1. `orchestrator/dry_run.py`: `cmd_acceptance_dry_run(task_id)` —
   резолв задачи/ветки, два именованных отказа, разбор через
   `guard.scan_ac_content`, печать (файлы/методы, AC-маркеры с
   причинами, сводка трассируемости, маркер сухого прогона).
   Регистрация `"acceptance-dry-run"` в `orchestrator/artel.py::main`
   (таблица диспетчера + строка в перечне модулей докстринга).
2. `tests/test_dry_run.py` — юнит-тесты чистых частей модуля
   (`_is_test_file`, отказы по `branch_exists`/`ls_tree_files`,
   основной сценарий через `gitcmd`/`store` заглушки) тем же приёмом,
   что у соседних модулей (`tests/sandbox.py`, `fake_git`), плюс
   regression-прогон приёмочных тестов задачи (`tasks/
   01M1GJ3ZP1YGG5QRB6FQ44NN8D/acceptance_tests/`, залочены — код
   подгоняется под них, не наоборот).
3. `python3 scripts/codebase_map.py` — регенерация карты (правится
   `orchestrator/artel.py`, заводится новый `orchestrator/dry_run.py`).

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1 |
| 5 | 1 |
| 6 | 1 |

## Влияние на систему

Новый модуль и одна строка регистрации в диспетчере `artel.py` —
изолированное добавление, не трогает существующие переходы FSM
(`fsm.py`/`fsm_advance.py`/`fsm_autogate.py` не меняются, как и
требует SPEC «Не входит»). Общий разбор (`guard.scan_ac_content`,
`guard.TEST_METHOD`, `guard.AC_ITEM`, `guard.section_body`) —
только чтение существующих публичных имён модуля, `scripts/guard.py`
не меняется ни строкой. Внешних побочных эффектов у команды по
построению нет (AC-5/AC-6) — ни один существующий тест/гейт/инвариант
не ослабляется, ничего не откатывать, кроме удаления новой команды из
таблицы диспетчера при необходимости.

`orchestrator/catalog.py` и `orchestrator/fsm_advance.py` — зоны чужих
незамерженных задач (SPEC «Не входит») — не трогаются вовсе.

## Риски

- Регэксп-парсинг (`guard.TEST_METHOD`/`AC_ITEM`) статический, как и у
  `guard.scan_acceptance_tests` — те же ограничения (не различает
  закомментированный код), уже принятые остальной системой.
- Формат вывода — решение разработчика (SPEC явно не фиксирует текст),
  приёмочные тесты задачи проверяют присутствие конкретных подстрок
  (имена файлов/методов, номера AC, причины, дословный маркер), не
  формат целиком — сверено построчно с `acceptance_tests/*.py` этой
  задачи на шаге 1.

## Предложения системе

(пусто)
