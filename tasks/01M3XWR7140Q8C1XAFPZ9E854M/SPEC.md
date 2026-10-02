---
task: 01M3XWR7140Q8C1XAFPZ9E854M
type: spec
author_role: analyst
status: ready
schema_version: 5
zones: orchestrator/amend.py, tests/test_amend_remove.py, docs/codebase-map.md
budget_usd: 25
---

# SPEC: amend-tests переносит удаление файла планки в артефактную ветку и не делает пустых коммитов

## Контекст
02.10 08:30Z Оператор удалил в worktree задачи 01M3SA3ANYZ7036AAGXZG753E3
файл `tasks/<id>/acceptance_tests/README.md` (без заголовочного блока) и
выполнил `amend-tests`. Журнал записал «правка планки» со сдвигом
`tests_locked_sha` на 101965d0, но этот коммит не меняет ни одного файла —
README остался в артефактной ветке. Причина: `_tests_snapshot`
(`orchestrator/amend.py:197`) пропускает удалённый, но отслеживаемый файл,
а коммит правки `artifact_branch.commit_files(task_id, disk, …)`
(`orchestrator/amend.py:584` и `:653`) только записывает файлы — параметр
`remove` (`artifact_branch.write_commit` уже умеет `update-index
--force-remove`) не передаётся. Следствие: `scripts/guard.py --all` на
снимке артефактной ветки падает («acceptance_tests/README.md: нет
frontmatter»), мерж задачи сделал бы main красным. Задачи
01M3SA3ANYZ7036AAGXZG753E3 и 01M3XTFJCC5TG63FHW907GQM4D ждут этого
исправления.

## Требования
1. `amend-tests` из worktree в обоих режимах — без перечня долгоживущих и
   с перечнем (`_amend_with_long_lived`): файл, который есть под
   `tasks/<id>/acceptance_tests/` на артефактной ветке, но отсутствует на
   диске worktree, удаляется из артефактной ветки тем же коммитом правки —
   через параметр `remove` у `artifact_branch.commit_files`.
2. Файл перечня `long_lived.sha256.txt` удалению по требованию 1 не
   подлежит: его по-прежнему пишет только команда.
3. Если дерево коммита правки совпадает с деревом родителя (ничего не
   изменилось ни записью, ни удалением), команда отказывает именованно,
   не сдвигает `tests_locked_sha` и не пишет запись журнала «правка
   планки» (fail-closed, ADR-0002).
4. Удаление тестового файла `test_*.py` проходит те же проверки, что
   правка сегодня (трассируемость AC, строки групп, прогон планки), — по
   итоговому состоянию планки без удалённого файла; удаление не обходит
   ни одной проверки.
5. Запись журнала «правка планки» перечисляет удалённые пути (например
   «удалены: acceptance_tests/README.md»).
6. Тесты — в новом файле `tests/test_amend_remove.py` по образцу
   `tests/test_amend.py` и `tests/test_amend_long_lived.py`, каждый с
   пометкой «Ловит мутацию: …».

## Критерии приёмки
AC-1. Удаление переносится в обоих режимах. Задача без перечня: файл
`acceptance_tests/README.md` удалён на диске worktree → после
`amend-tests` его нет в артефактной ветке, а `tests_locked_sha` указывает
на коммит без него. Задача с перечнем (целиком долгоживущая планка): то
же самое. Файл `long_lived.sha256.txt` при этом не удаляется из
артефактной ветки. Тесты несут пометки «Ловит мутацию: `remove` не
передан — файл остаётся, коммит пустой» (режим без перечня) и «Ловит
мутацию: удаление перенесено только в одном из двух режимов» (режим с
перечнем).

AC-2. Коммит правки дал дерево, равное дереву родителя (в тесте — подмена
записи коммита так, что удаление не применилось): команда отказывает
именованно, `tests_locked_sha` не сдвинут, записи журнала «правка планки»
нет. Тест несёт пометку «Ловит мутацию: проверка пустого коммита убрана —
повтор случая 101965d0».

AC-3. Удалённый на диске `test_*.py`, который был единственным тестом,
покрывавшим некоторый AC, приводит к отказу `amend-tests` по
трассируемости — так же, как при правке файла; `tests_locked_sha` не
сдвигается. Тест несёт пометку «Ловит мутацию: удалённые файлы исключены
из проверок».

AC-4. Запись журнала «правка планки» после `amend-tests` с удалением
называет удалённый путь (например «удалены:
acceptance_tests/README.md»).

AC-5. Тесты AC-1…AC-4 лежат в `tests/test_amend_remove.py`, каждый с
пометкой «Ловит мутацию: …»; `tests/test_amend.py` и
`tests/test_amend_long_lived.py` не изменены.

## Оценка объёма и деление
Сигналов «подозрения на большой объём» нет: 5 критериев, 3 файла зоны
(один из них — регенерируемая карта), `budget_usd` 25 (рамка ТЗ $15 ниже
нижней планки $25 по skills/spec-authoring.md, поэтому взята планка).

## Не входит
- Режим `amend-tests --from-branch`.
- Отказ guard на `.md` без заголовочного блока в `acceptance_tests/` на
  выходе из `tests_writing`.
- Проверка `guard --all` по снимку на гейте мержа (задача
  01M3SF7DPFGEZ7VYEGGXGTX49E).
- Правка планок задач 01M3SA3ANY… и 01M3XTFJCC… — её делает Оператор
  после мержа этой задачи и сдвига пина.
- Правки файлов только для чтения по ТЗ: `orchestrator/artifact_branch.py`,
  `orchestrator/acceptance.py`, `orchestrator/advance_gates/`,
  `orchestrator/fsm.py`, `orchestrator/fsm_advance.py`,
  `orchestrator/store.py`, `scripts/guard.py`, существующие файлы
  `tests/` (включая `tests/test_invariants.py`), `skills/`, `docs/adr/`,
  `docs/invariants.md`, `tasks/`.
- Неослабление существующих тестов и зелёный полный набор `tests/`
  (требование 6 ТЗ) — их держит пульт.

## Материалы
- ТЗ: tasks/01M3XWR7140Q8C1XAFPZ9E854M/TZ.md (строка копилки 02.10, П1).
- `orchestrator/amend.py:197` (`_tests_snapshot`), `:584`, `:653`
  (`commit_files` без `remove`); `orchestrator/artifact_branch.py:46`
  (`write_commit`, параметр `remove`), `:157` (`commit_files`).
- Пустой коммит правки: 101965d0 (задача 01M3SA3ANYZ7036AAGXZG753E3).
