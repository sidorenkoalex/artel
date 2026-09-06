---
task: 01M1REVMB50SND1KJ3CYQMV2ST
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 4
---

# REVIEW: эскалация «конфликт подтяжки main» называет конфликтные файлы

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `_merge_conflict_note(files, merge)` (`orchestrator/fsm.py:213-235`) собирает «конфликтные файлы: a, b» + хвост `stdout` (500 симв.) + хвост `stderr` (500 симв., если не пуст), в этом порядке — совпадает с форматом SPEC. Проверено юнит-тестами (`tests/test_fsm_merge_conflict_note.py`) и приёмочными (AC-1/AC-2/AC-3/AC-5) — все зелёные. |
| 2 | OK | Отдельного кода вывода не добавлено (как и требовалось «Не входит») — существующий `store.set_state` печатает `detail` (`orchestrator/store.py:425`); проверил чтением этой строки — `print(f"[{task_id}] -> {state}" + (f"  ({detail})" if detail else ""))`. |
| 3 | OK | `_auto_resolve_map_conflict` и условие её вызова (`files == [MAP_REL]`) не тронуты; `git merge --abort` по-прежнему выполняется до записи эскалации (`orchestrator/fsm.py:385-386`). AC-5 зелёный (авторазрешение карты не сломано, провал регенерации по-прежнему эскалирует со списком конфликтов). |

## Замечания

- major — `tests/test_fsm_merge_conflict_note.py:28,34,39,47,54,60,70` — ни один из 7 новых тестовых методов (`test_files_and_stdout_conflict_line`, `test_multiple_files_joined_by_comma`, `test_stdout_truncated_to_500_chars`, `test_nonempty_stderr_kept_alongside_stdout`, `test_stderr_truncated_to_500_chars`, `test_all_empty_has_no_dangling_separators`, `test_merge_none_degrades_to_git_did_not_answer`) не несёт докстринга с заявкой «Ловит мутацию: …» (skills/test-authoring.md, требование review-checklist «пустой… тоже замечание»). Файловый докстринг описывает модуль в целом, но не подменяет докстринг конкретного теста — по нему нельзя сверить, какую мутацию должен ловить именно этот тест (для сравнения — приёмочный файл `tasks/01M1REVMB50SND1KJ3CYQMV2ST/acceptance_tests/test_pull_conflict_detail.py` такие докстринги несёт на каждом методе). Предложение: добавить каждому методу докстринг вида «Ловит мутацию: …» по образцу соседнего приёмочного файла — сами тесты и их ассерты менять не нужно, они по существу корректны (прогнаны, зелёные, действительно проверяют заявленное).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | fixed | tests/test_fsm_merge_conflict_note.py:28,37,49,61,73,84,102 | 7 новых тестов без докстринга «Ловит мутацию: …» | нарушение конвенции test-authoring, следующий ревьювер/разработчик не может свериться, какую регрессию тест ловит, без чтения тела теста | добавлен докстринг каждому из 7 методов (заявка сценария + формулировка мутации, которую тест ловит) — ассерты и тестируемая логика не менялись |

## Вердикт

changes_requested — единственное замечание (R1-F1): добавить докстринги «Ловит мутацию: …» всем 7 тестам `tests/test_fsm_merge_conflict_note.py`. Логика и тестовое покрытие по существу верны, менять код `orchestrator/fsm.py` не требуется.

## Проверено исполнением

- `python3 -m unittest tests.test_fsm_merge_conflict_note tests.test_branch_freshness_gate tests.test_fsm_map_conflict_autoresolve -v` — 24 теста, все зелёные (AC-4: существующие тесты подтяжки/авторазрешения карты не ослаблены — сверил diff `tests/`, кроме нового файла ничего не менялось).
- `python3 -m unittest tasks.01M1REVMB50SND1KJ3CYQMV2ST.acceptance_tests.test_pull_conflict_detail -v` — 8 тестов (AC-1/AC-2/AC-3/AC-5), все зелёные.
- Прочитал `orchestrator/fsm.py:80-96` (`_conflicting_files`) и `:355-420` (тело `_pull_main_or_escalate` вокруг изменения) — подтвердил, что `_auto_resolve_map_conflict` и её условие вызова не задеты, `merge --abort` по-прежнему безусловен при неразрешённом конфликте.
- Регенерировал `docs/codebase-map.md` (`python3 scripts/codebase_map.py`) и сравнил с закоммиченной версией без строки `built_at_sha` (`grep -v '^built_at_sha:'`) — расхождений нет, карта свежая; рабочее дерево вернул в исходное состояние (`git checkout -- docs/codebase-map.md`) после сверки.
- Сверил `git diff --stat main...HEAD` — изменены только `docs/codebase-map.md`, `orchestrator/fsm.py`, `tests/test_fsm_merge_conflict_note.py` — в границах зон SPEC (`orchestrator/fsm.py`, `tests/`) плюс обязательная регенерация карты.

## Предложения системе
