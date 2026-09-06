---
task: 01M1RA0R9AH9RBAHD4A2Z5SEWQ
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 4
---

# REVIEW: Перегенерированная карта после шага роли не ломает подтяжку main

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (очистка карты перед merge) | OK | `orchestrator/fsm.py:331` — `gitcmd.in_repo(wt_path, "checkout", "--", MAP_REL)` перед `git merge`. AC-1/AC-4 зелёные. |
| 2 (WIP-чекпоинт прочего кода по мандату developer) | OK | `orchestrator/fsm.py:332` зовёт новую `checkpoint.commit_pull_checkpoint` (`orchestrator/checkpoint.py:638`), переиспользующую `_commit_worktree_change(exclude=f"tasks/{task_id}")`. AC-2/AC-3/AC-5 зелёные. |
| 3 (после 1-2 «would be overwritten» не возникает по этим причинам) | OK | Наблюдаемое свойство, не отдельная ветка кода — подтверждено AC-4/AC-5 (merge проходит без эскалации после очистки/чекпоинта). |
| 4 (провал очистки — инцидент, не «конфликт подтяжки») | OK | `orchestrator/fsm.py:338-351` — классификация по `PULL_OVERWRITE_MARKER` до ветки конфликтов содержимого, `alerts.raise_alert(kind="incident")`, журнал называет конкретный файл. AC-6 зелёный. |
| 5 (настоящий конфликт содержимого — прежнее поведение) | OK | Ветка `_conflicting_files`/`_auto_resolve_map_conflict`/`--abort` (`orchestrator/fsm.py:353-369`) не тронута, стоит строго ПОСЛЕ новой проверки. AC-7 зелёный. |

## Замечания

Нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт

approved

## Проверено исполнением

- Прочитаны на диске (не только по пакету) `tasks/01M1RA0R9AH9RBAHD4A2Z5SEWQ/SPEC.md`, `PLAN.md`, все 6 файлов `acceptance_tests/` (`_sandbox.py` + 5 `test_ac*.py`) и полный текст правки `orchestrator/fsm.py::_pull_main_or_escalate`, `orchestrator/checkpoint.py::commit_pull_checkpoint`/`_commit_worktree_change` — пакет описи ошибочно сообщил «файл не найден» (git/диск), артефакты фактически на месте в рабочем дереве, ветка `task/01m1ra0r9ah9rbahd4a2z5sewq-peregenerirovannaya-karta-posl`.
- `python3 -m unittest discover -s tasks/01M1RA0R9AH9RBAHD4A2Z5SEWQ/acceptance_tests -p 'test_*.py' -v` — 7 тестов (AC-1..AC-7), все `OK`; AC-8 — легитимный `skip` (класс «ci-covered», регрессия набора несёт CI-джоб).
- `python3 -m unittest tests.test_timeout_checkpoint tests.test_fsm_map_conflict_autoresolve tests.test_branch_freshness_gate -v` — 47 тестов, все `OK` (включая новый класс `CommitPullCheckpointTest` и правки заглушек `checkout`/`reset` в двух других файлах, AC-8).
- Сверка `tests/test_branch_freshness_gate.py`: новый блок `if args[:1] in (("checkout",), ("reset",))` — отдельная ветка ДО учёта `merge_calls`/`abort_calls` (`args[:1] == ("merge",)`), счётчики `len(merge_calls) == 1` не задеты — регрессия не ослаблена. Аналогично в `tests/test_fsm_map_conflict_autoresolve.py` — `("reset",)` добавлен в тот же безобидный no-op список, что и существующие `checkout`/`add`/`commit`.
- `python3 scripts/codebase_map.py`, затем `git diff -- docs/codebase-map.md` — расхождение только в строке `built_at_sha` (карта ветки построена на 77f3cfc1, HEAD ушёл на 7689fd2c за счёт подтяжки main; содержимое совпадает) — не дефект (skills/review-checklist.md, класс подтверждён T053/T072); откачено `git checkout -- docs/codebase-map.md` после проверки, рабочее дерево чистое (кроме `tasks/<id>/`, `git status --short`).
- Прочитан `orchestrator/checkpoint.py::commit_timeout_checkpoint`/`_dirty_refuses` docstring-обоснование ограничения «только догфуд» (`target == config.DEFAULT_TARGET`) у трёх старых чекпоинтов — сверено с тем, что `commit_pull_checkpoint` умышленно НЕ несёт такого ограничения: `_pull_main_or_escalate` вызывает merge в `workspace.ensure()`-worktree для ЛЮБОГО target (в отличие от `fixation`-специфичных проверок, которые для внешнего target смотрят в `.artel/projects/<target>/`, а не в этот worktree) — разница обоснована, не дефект.
- Прочитан `orchestrator/alerts.py::raise_alert`/`KINDS` — `kind="incident"` валиден, сигнатура вызова в `fsm.py` совпадает.

## Предложения системе

- Докстринг «Ловит мутацию» проседает в новых unit-тестах (не только акс.): `tests/test_timeout_checkpoint.py::CommitPullCheckpointTest.test_dirty_tree_commits_with_message_sha_and_journal_entry` несёт докстринг про обоснование фикстуры («правка ВНЕ tasks/<id>/ нужна, чтобы код-коммит вообще состоялся»), а не про наблюдаемую мутацию — в отличие от структурного аналога в том же файле (`CommitTimeoutCheckpointTest.test_dirty_tree_commits_with_message_sha_and_journal_entry`, который прямо говорит «Ловит мутацию: коммит чекпоинта пишется без сообщения/sha в …»). Не блокер (минорно, поведение проверено прогоном) — тот же класс, что уже зафиксирован в памяти ревьювера (feedback_test_authoring_mutation_claim_gap): проверять оба места, приёмочные тесты конвенцию держат, юнит-тесты — не всегда.
