---
task: 01M290PVYG2VJK6442H5BAX9MA
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: чекпоинты пульта коммитят только зоны задачи и tasks/<id>/; на подтяжке посторонний файл — отказ, не предупреждение; гейт зон видит неотслеживаемые файлы

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (все WIP-чекпоинты коммитят только зоны задачи) | OK | без изменений с итерации 1 — подтверждено повторным прогоном |
| 2 (одна запись журнала «посторонние файлы в worktree») | OK | без изменений с итерации 1 |
| 2/AC-3/AC-4 (подтяжка отказывает переходу целиком) | OK | без изменений с итерации 1; `orchestrator/pull.py` не менялся между итерациями (сверено диффом) |
| 3/AC-5 (белый список `commit_step_artifacts` — источник guard) | OK | без изменений с итерации 1 |
| 4/AC-6 (гейт зон видит неотслеживаемые файлы) | OK | без изменений с итерации 1; `orchestrator/fsm_advance.py` не менялся между итерациями |
| 5/AC-7 (`.gitignore` — черновики ролей) | OK | без изменений с итерации 1 |
| 6 (тесты покрывают класс, существующие наборы не ослаблены) | OK | пробел итерации 1 (не было теста «зона + посторонний файл» на `commit_success_checkpoint`) закрыт регресс-тестом `CommitSuccessCheckpointSummaryTest` + юнит-тестами `CommitSummaryTest`; `tests/test_review_package.py` обновлён точным списком git-вызовов вслед за удалением лишнего предварительного `numstat` (не ослабление — список стал короче потому, что стало меньше git-вызовов, сама проверка «список исчерпывающий» сохранена) |

## Замечания

(пусто — обе итерации не выявили новых дефектов сверх реестра ниже)

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/checkpoint.py:471-479 (было), теперь `_commit_summary`/`commit_success_checkpoint` | `_staged_change_summary` считала файлы/строки ДО зонного фильтра `_commit_worktree_change` | журнал «код закоммичен пультом за роль» лгал о составе коммита, противоречил соседней записи «посторонние файлы в worktree» о том же файле | подтверждено: `_staged_change_summary` удалена, заменена на `_commit_summary(wt, sha)` — считает `git show --numstat` уже по факту закоммиченному `sha`, вызывается ПОСЛЕ `_commit_worktree_change` и только при `committed=True` (orchestrator/checkpoint.py:392-479). Регресс-тест `tests/test_checkpoint_zone_filter.py::CommitSuccessCheckpointSummaryTest::test_stray_file_outside_zones_is_not_listed_as_committed` воспроизводит ровно сценарий баг-репорта итерации 1 (зона + посторонний файл) и зелёный; повторил ручной репро итерации 1 логикой кода — `_commit_summary` больше не может включить путь, не вошедший в `sha`, по построению (источник данных — сам коммит, не предварительный индекс) |
| R1-F2 | accepted | orchestrator/checkpoint.py:906-914 (было) | `_commit_worktree_change`, ветка `refuse_on_stray=True` — обе ветки `if unstage_all.returncode != 0` возвращали одно и то же | мёртвый код, лишняя когнитивная нагрузка при чтении | подтверждено: текущий код (orchestrator/checkpoint.py:931-933) — `gitcmd.in_repo(wt, "reset", "-q"); return False, "", stray`, без ветвления по коду возврата |
| R1-F3 | accepted | orchestrator/checkpoint.py:915-917 (было) | `_commit_worktree_change`, ветка `refuse_on_stray=False` — на отказе `git reset` возврат обнулял `stray` до `[]`, в отличие от соседних return-точек той же функции | несогласованный контракт возврата, ловушка для будущего вызывающего кода, читающего третий элемент кортежа | подтверждено: строка orchestrator/checkpoint.py:936 теперь `return False, "", stray` — согласовано со всеми остальными return-точками функции |

## Вердикт

approved — оба замечания итерации 1 (1 major + 2 minor) исправлены по существу и покрыты тестами; полный список изменений между вердиктом итерации 1 (6efa9388) и текущим HEAD ограничен заявленными зонами задачи и не несёт стороннего дрейфа (см. «Проверено исполнением»).

## Проверено исполнением

- Инкрементальный diff пакета от `a297fd4e627d2303a0f29748473c214e9dd4a264` до HEAD пуст, потому что этот sha и есть текущий HEAD (тот же класс, что T087 в скиле review-checklist) — реальный коммит вердикта итерации 1 найден вручную: `git log --oneline --all -- tasks/01M290PVYG2VJK6442H5BAX9MA/REVIEW.md` → `6efa9388` (REVIEW.md со status=changes_requested, iteration=1). Весь код-ревью этой итерации сделан по диапазону `6efa9388..HEAD`, в частности по коммитам `12baaa34` (адаптация вызова `_commit_worktree_change` в `commit_success_checkpoint` под новую сигнатуру — конфликт, принесённый ПОСЛЕДУЮЩЕЙ подтяжкой main с чужой задачей 01M283NC4JJXK7QS68Y9ET8TBK) и `15245b9f` («закрываю замечания ревью…» — собственно фикс R1-F1/F2/F3).
- `git diff main...HEAD --stat -- . ':!tasks' ':!docs/backlog.md'` — 9 файлов: `.gitignore`, `docs/codebase-map.md`, `orchestrator/checkpoint.py`, `orchestrator/fsm_advance.py`, `orchestrator/pull.py`, `tests/test_checkpoint_zone_filter.py`, `tests/test_pull.py`, `tests/test_review_package.py`, `tests/test_zones_gate.py` — ровно заявленные зоны (`orchestrator/checkpoint.py`, `orchestrator/fsm_advance.py`, `.gitignore`, `tests/`) + мандат расширения `orchestrator/pull.py` (ANSWER-1/ANSWER-2) + законный побочный эффект правки `*.py` — регенерация `docs/codebase-map.md`; стороннего дрейфа нет.
- `grep -n "<<<<<<<" orchestrator/checkpoint.py orchestrator/pull.py orchestrator/fsm_advance.py .gitignore` — пусто, конфликтных маркеров не осталось.
- `python3 -m pytest tests/test_checkpoint_zone_filter.py tests/test_pull.py tests/test_zones_gate.py tests/test_timeout_checkpoint.py tests/test_step_autocommit.py tests/test_checkpoint_external_step_artifacts.py tests/test_checkpoint_stray_acceptance_files.py tests/test_guard_task_root_subdirectory.py tests/test_review_package.py -q` — 202 passed, 19 subtests passed за 109.5с.
- `python3 -m pytest tasks/01M290PVYG2VJK6442H5BAX9MA/acceptance_tests/ tests/test_guard_extraneous_acceptance_files.py tests/test_fsm_advance_gate_smoke.py tests/test_advance_guard.py tests/test_protected_paths_gate.py -q` — 40 passed, 13 subtests passed.
- `python3 scripts/codebase_map.py --check` — тихий успех, карта свежая относительно HEAD.
- `python3 -m scripts.guard --all` — «ок (774 файлов)», два предупреждения по `_sandbox.py` двух ДРУГИХ задач (01M1RA0R9AH9RBAHD4A2Z5SEWQ, T067) — не блокирующие, вне зоны этой задачи.
- Прочитан код `_commit_worktree_change`/`_commit_summary`/`commit_success_checkpoint` (orchestrator/checkpoint.py:392-479, 917-946) построчно — подтверждает все три решения реестра текстом кода, не только прогоном тестов.
- Прочитан diff коммита `15245b9f` для `tests/test_review_package.py` — сокращение ожидаемого списка git-вызовов соответствует реально удалённому предварительному `numstat`-проходу, проверка «список исчерпывающий» не ослаблена (тест по-прежнему падает на любой лишний git-вызов).

## Предложения системе

- Повторный случай пустого/тождественного HEAD инкрементального diff ревью-пакета (класс T087, скил review-checklist, раздел «Инкрементальный diff пакета») — на этот раз из-за ДВУХ последовательных подтяжек main в рамках одной задачи (ANSWER-1 разрешил первую, вторая подтяжка main принесла конфликт сигнатуры `_commit_worktree_change` из чужой задачи и потребовала отдельного фикс-коммита `12baaa34` без промежуточного ревью). Стоит явно упомянуть в PLAN.md «Влияние на систему», если после сдачи на ревью в ветку прилетела ещё одна подтяжка main — иначе следующий ревьювер тратит время на восстановление реального диапазона коммитов вручную.
