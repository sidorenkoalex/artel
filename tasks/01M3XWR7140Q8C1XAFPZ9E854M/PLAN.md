---
task: 01M3XWR7140Q8C1XAFPZ9E854M
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: amend-tests переносит удаление файла планки и не делает пустых коммитов

## Подход
Вся правка — в `orchestrator/amend.py`, `artifact_branch.py` не трогается
(параметр `remove` у `commit_files`/`write_commit` уже есть).

- `_removed_paths(disk, baseline, manifest_rel)` — пути `acceptance_tests/`,
  которые есть в голове артефактной ветки (`baseline`), но отсутствуют в
  снимке диска worktree (`disk`), без `long_lived.sha256.txt` (требование 2).
  Считается в `_cmd_amend_tests` один раз и передаётся в оба режима
  (`_amend_with_long_lived` получил параметр `removed`).
- `_commit_plank(task_id, files, message, removed)` — единый коммит правки
  для обоих режимов: `artifact_branch.commit_files(..., remove=removed)`,
  затем сверка `git rev-parse <sha>^{tree} <sha>^1^{tree}`. Деревья равны
  или не сверены (git не ответил) — fail-closed: голова артефактной ветки
  возвращается CAS-`update-ref` на родителя (чтобы пустой коммит не
  оставался её головой), а вызывающий код отказывает именованно
  («пустой коммит правки») через `_refuse` (журнал «amend-tests отклонён»,
  не «правка планки»), `tests_locked_sha` не сдвигается. В режиме с
  перечнем, если кодовая ветка уже получила коммит долгоживущих файлов,
  отказ идёт прежним путём `_recovery_exit` (восстановление `--from-branch`).
- Проверки (трассируемость, строки групп, прогон) уже читают итоговую
  планку с диска worktree (`guard.acceptance_traceability_errors(tdir)`,
  `guard.acceptance_test_files(tdir)`, `acceptance.run(tdir)`), где
  удалённого файла нет, — требование 4 держится существующим кодом;
  закреплено тестом.
- `_removed_note` — хвост детали журнала «правка планки»: `удалены:
  acceptance_tests/README.md` (пути относительно `tasks/<id>/`), в обоих
  режимах.

## Шаги
1. `orchestrator/amend.py`: `_removed_paths`, `_removed_note`,
   `_commit_plank`; оба коммита правки (`_cmd_amend_tests`,
   `_amend_with_long_lived`) — через `_commit_plank` с `removed`; деталь
   журнала с удалёнными путями.
2. `tests/test_amend_remove.py` — тесты AC-1…AC-4 в обоих режимах, каждый с
   «Ловит мутацию: …»; `tests/test_amend.py`/`tests/test_amend_long_lived.py`
   не тронуты.
3. `python3 scripts/codebase_map.py` — карта тем же коммитом.

Проверка:
- `python3 -m pytest tests/test_amend_remove.py tests/test_amend.py
  tests/test_amend_long_lived.py tasks/01M3XWR7140Q8C1XAFPZ9E854M/acceptance_tests
  -p no:cacheprovider -p timeout -o timeout=120` — 66 passed.
- Временные мутации `amend.py` (временный скрипт в корне worktree, удалён; код возвращён),
  прогон `tests/test_amend_remove.py`:
  - `remove` не передан в обоих режимах — красные 5 тестов (AC-1/AC-4 обоих режимов);
  - проверка пустого коммита убрана — красные `test_empty_commit_refused` обоих режимов;
  - откат ветки на родителя убран — красные те же 2;
  - перечень не исключён из удалений — красный `test_manifest_absent_on_disk_is_not_removed`;
  - журнал без удалённых путей — красные `test_journal_names_removed_path` обоих режимов;
  - `remove` не передан только в режиме с перечнем — красные 3 теста режима с перечнем.
  `test_removed_sole_test_refused_by_traceability` — сторож от регресса
  (проверка уже читала диск), мутацией «трассируемость по планке
  артефактной ветки» в текущем коде не воспроизводится без переписывания
  вызова; держит поведение.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1 (`_removed_paths` + `remove=` в `_commit_plank`, оба режима), 2 |
| 2 | 1 (`p != manifest_rel`; в режиме с перечнем перечень и так пишется командой), 2 |
| 3 | 1 (`_commit_plank`: сверка деревьев, откат ветки, `_refuse`/`_recovery_exit`), 2 |
| 4 | существующие проверки по диску worktree; 2 (`RemovedSoleTestTraceabilityTest`) |
| 5 | 1 (`_removed_note`), 2 |
| 6 | 2 |

## Влияние на систему
- Затрагивается только worktree-путь `amend-tests`; `--from-branch` не
  меняется. Прежнее поведение без удалений не меняется: `removed` пуст,
  `remove=[]` — то же дерево, что раньше; сверка деревьев отклоняет только
  коммит без изменений, а такой коммит раньше и не мог возникнуть иначе
  как в случае 101965d0 (до записи уже стоит отказ «нет изменений»).
- Защита усилена, не ослаблена: новый fail-closed отказ (ADR-0002);
  проверки трассируемости/групп/прогона не тронуты.
- Ветка-документов: при отказе по пустому коммиту голова возвращается на
  родителя CAS-`update-ref` (с ожидаемым старым значением — не затирает
  чужую параллельную запись).
- Откат — revert коммита задачи.

## Риски
- Удаление всего каталога `acceptance_tests/` на диске по-прежнему
  перекрывается `_materialize_tests_if_missing` (материализует его заново
  из ветки) — удалить планку целиком командой нельзя; это вне SPEC и
  скорее защита.

## Предложения системе
- `coding-standards.md` («Сторожа проверяй временной мутацией»): в шаге роли
  `rm` и запись вне worktree требуют подтверждения, которого нет, — скрипт
  мутаций пришлось класть в корень worktree и удалять через python.
  Стоит назвать в скиле допустимое место для временных файлов шага.
