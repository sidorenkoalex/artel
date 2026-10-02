---
task: 01M3XWR7140Q8C1XAFPZ9E854M
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: amend-tests переносит удаление файла планки и не делает пустых коммитов

## Фаза A: план
- Таблица покрытия полна: требования 1–6 сопоставлены шагам; требование 4
  честно отнесено к существующим проверкам по диску worktree
  (`guard.acceptance_traceability_errors(tdir)`, `acceptance.run(tdir)`) и
  закреплено тестом.
- Шаги размера MR (код / тесты / карта), не микрооперации.
- Подход не трогает файлы только для чтения по SPEC
  (`artifact_branch.py` не изменён — использован уже существующий `remove=`).
- «Влияние на систему» = diff: изменены только `orchestrator/amend.py`,
  новый `tests/test_amend_remove.py`, карта; `--from-branch` не тронут.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `_removed_paths` (amend.py:251) считает `baseline − disk` по голове артефактной ветки; передаётся в оба режима, коммит — через `_commit_plank(..., remove=removed)` (amend.py:631, :703). Удалённый отслеживаемый файл в `_tests_snapshot` пропускается по `OSError` → в `disk` его нет → попадает в `removed`. |
| 2 | OK | `p != manifest_rel` в `_removed_paths`; в режиме с перечнем перечень к тому же пишется командой в `docs_files`. Тест `test_manifest_absent_on_disk_is_not_removed`. |
| 3 | OK | `_commit_plank` сверяет `sha^{tree}` и `sha^1^{tree}`; равенство или несверка → CAS-`update-ref` ветки на родителя и `_refuse(..., "пустой коммит правки")` (журнал «amend-tests отклонён», не «правка планки»); `tests_locked_sha` не сдвигается. В режиме с перечнем при уже записанной кодовой ветке — `_recovery_exit`, как и прежде. |
| 4 | OK | Проверки идут по `tdir` на диске worktree, где удалённого файла нет; удаление не обходит ни трассируемость, ни строки групп, ни прогон. `RemovedSoleTestTraceabilityTest`. |
| 5 | OK | `_removed_note` дописывает `удалены: acceptance_tests/…` в деталь обоих режимов. |
| 6 | OK | Новый `tests/test_amend_remove.py`, каждый метод с «Ловит мутацию: …»; `tests/test_amend.py`, `tests/test_amend_long_lived.py` не изменены (`git diff --stat 0915d6bc..HEAD` по ним пуст). |

## Замечания
Замечаний уровня blocker/major/minor нет.

Наблюдение без замечания: `_tests_snapshot` (amend.py:223–226) по-прежнему
глушит любой `OSError`, а не только «файла нет»; теперь такой файл
считается удалённым. Нечитаемый `test_*.py` всё равно отсечёт прогон
планки, нечитаемый `.md` — нет; сценарий (права на файл в собственном
worktree Оператора) не реалистичен для пульта, поэтому замечанием не
заводится.

Тесты: заявки «Ловит мутацию» называют наблюдаемое расхождение (README в
дереве нового лока, сдвиг лока/запись журнала, путь в детали). Заявка
`test_removed_sole_test_refused_by_traceability` — сторож от регресса
(PLAN это признаёт): наблюдаемость есть (лок сдвинулся бы, отказа не
было бы), нынешний код её просто уже держит — приемлемо.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет.

## Вердикт
approved

## Проверено исполнением
- `python3 -m pytest tests/test_amend_remove.py tests/test_amend.py tests/test_amend_long_lived.py tasks/01M3XWR7140Q8C1XAFPZ9E854M/acceptance_tests -p no:cacheprovider -q -p timeout -o timeout=120` — 66 passed, 9 subtests passed (105 с).
- Временная мутация: в `_commit_plank` сверка деревьев заменена на `if True: return sha, ""` (проверка пустого коммита убрана) → `tests/test_amend_remove.py`: красные `PlainModeRemovalTest::test_empty_commit_refused` и `LongLivedModeRemovalTest::test_empty_commit_refused` (2 failed, 6 passed); код возвращён `git checkout -- orchestrator/amend.py`, `git status` чист.
- `python3 scripts/codebase_map.py` → `git diff -- docs/codebase-map.md | grep '^[-+]' | grep -v built_at_sha` — расхождений по содержимому нет (только `built_at_sha`); карта возвращена `git checkout`.
- `git diff --stat 0915d6bc..HEAD -- tests/test_amend.py tests/test_amend_long_lived.py` — пусто (AC-5).
- CI коммита 64d38145 — зелёный (из пакета).

## Предложения системе
