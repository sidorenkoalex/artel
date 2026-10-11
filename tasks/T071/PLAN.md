---
task: T071
type: plan
author_role: developer
status: ready
schema_version: 2
---

# PLAN: Ветко-корректное чтение SPEC в approve

## Подход

Единственное содержательное отличие текущего inline-чтения SPEC.md в
`_cmd_approve` (переход `spec_gate`, `orchestrator/fsm.py:1091-1101`) от
общего узла `_read_branch_text_or_refuse` (`orchestrator/fsm.py:476-494`,
T047) — реакция на отказ узла: узел журналирует и печатает отказ и
возвращает `None`, вызывающий код сам решает, что делать дальше; текущий
inline-код после журналирования делает `sys.exit(...)`.

Решение — заменить прямой `gitcmd.show(branch, f"tasks/{task_id}/SPEC.md")`
на вызов `_read_branch_text_or_refuse(conn, task_id, branch, "SPEC.md")`
и при `None` сделать простой `return` (без смены состояния), тем же
приёмом, что уже используют все вызовы узла внутри `_cmd_advance`
(`spec_writing`/`review`/`in_dev`, `orchestrator/fsm.py:616-634, 671-674,
806-809`) — узел сам печатает и журналирует именованный отказ
(«дерево не на ветке задачи» / «SPEC.md ... не прочитан»), сообщение
`sys.exit` было бы дублированием того же текста другим способом.

Это укладывается в допущение SPEC (требование 2): наблюдаемое решение
FSM не меняется — approve останавливает попытку и не переводит задачу в
другое состояние ни при отказе через `sys.exit` (было), ни при `return`
после отказа узла (стало); меняется только код выхода (0 вместо 1) и то,
что сообщение приходит из журнала/stdout узла, а не из текста
исключения. Ветвь `else` (не чужая ветка → чтение с диска через
`artifacts.frontmatter`) не трогается — SPEC требование 3.

## Шаги

1. `orchestrator/fsm.py`, `_cmd_approve`, ветка `state == "spec_gate"`,
   `if gitcmd.on_foreign_branch(branch):` — заменить прямой
   `spec_text, reason = gitcmd.show(...)` + ручной блок
   журнал/print/`sys.exit` на `spec_text = _read_branch_text_or_refuse(
   conn, task_id, branch, "SPEC.md")` + `if spec_text is None: return`.
   `meta = yamlmini.frontmatter(spec_text) or {}` остаётся без изменений.
   Юнит-тесты на прямое поведение узла (mock `_read_branch_text_or_refuse`,
   отказ → `return` без смены состояния, успех → маршрутизация как
   раньше) — в `tests/test_fsm_branch_correct_status_reads.py`.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1 |

## Влияние на систему

Правка ограничена одной веткой одной функции `orchestrator/fsm.py`
(`_cmd_approve`, `state == "spec_gate"`, ветка `on_foreign_branch`).
Затрагиваемый общий узел `_read_branch_text_or_refuse` не меняется —
только получает ещё один вызывающий код, соответствующий его
контракту (T047). Ветвь `else` (чтение с диска), другие переходы
`_cmd_approve` (`acceptance`, `merge_gate`, `escalated`), `_cmd_advance`
и все прочие читатели артефактов — не трогаются (SPEC «Не входит»).

Существующий тест T031 (`SpecGateBranchRoutingTest`,
`tasks/T031/acceptance_tests/test_branch_correct_reads.py`) фиксирует
маршрутизацию `spec_gate` при чужом чекауте на уровне наблюдаемого
поведения (задача не проходит мимо `tests_writing` молча) — правка его
не задевает, т.к. решение FSM не меняется. Локальные тесты T071
(`tasks/T071/acceptance_tests/test_spec_gate_shared_node.py`) закрывают
AC-1..AC-4 напрямую (узел вызван, `gitcmd.show` не вызван, отказ не
меняет состояние, чтение с ветки). Откат — вернуть прежний inline-блок
(правка чисто локальная, git revert одного коммита).

## Риски

Нет — правка сугубо механическая, замена одного вызывающего кода на
контракт уже существующего узла, без новых веток условий.

## Предложения системе

—
