---
task: 01M3XWR7140Q8C1XAFPZ9E854M
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: amend-tests переносит удаление файла планки и не делает пустых коммитов

# ТЗ: amend-tests переносит удаление файла планки в артефактную ветку и не делает пустых коммитов

Источник: строка копилки 02.10 (П1) «amend-tests молча не удаляет файлы
планки»; решение Оператора 02.10 — задачи 01M3SA3ANYZ7036AAGXZG753E3
(merge_gate) и 01M3XTFJCC5TG63FHW907GQM4D ждут этого исправления.

Факты (origin/main):
- 02.10 08:30Z Оператор удалил в worktree 01M3SA3ANYZ7036AAGXZG753E3 файл
  `tasks/<id>/acceptance_tests/README.md` (без заголовочного блока) и
  выполнил `amend-tests`. Журнал записал «правка планки» со сдвигом
  `tests_locked_sha` на 101965d0, но коммит 101965d0 не меняет ни одного
  файла: README остался в артефактной ветке.
- Причина: `_tests_snapshot` (`orchestrator/amend.py:197`) берёт
  `git ls-files --cached --others`, и удалённый, но отслеживаемый файл
  пропускается на `read_bytes` (OSError). Сверка «есть ли правка» видит
  разницу с артефактной веткой, но коммит
  `artifact_branch.commit_files(task_id, disk, …)` (`amend.py:584` и
  `:653`) только записывает файлы из `disk`; параметр `remove`
  (`artifact_branch.write_commit`, уже умеет `update-index
  --force-remove`) не передаётся.
- Проверка артефактов `scripts/guard.py --all` на origin/main вместе со
  снимком artifact/01m3sa3any… падает: «acceptance_tests/README.md: нет
  frontmatter», rc=1. Мерж этой задачи сделал бы main красным (как 30.09).

Требуется:
1. `amend-tests` из worktree (оба режима: без перечня долгоживущих и с
   перечнем, `_amend_with_long_lived`): файл, который есть под
   `tasks/<id>/acceptance_tests/` на артефактной ветке, но отсутствует на
   диске worktree, удаляется из артефактной ветки тем же коммитом правки
   — через `remove` у `artifact_branch.commit_files`. Файл перечня
   `long_lived.sha256.txt` удалению не подлежит: его пишет только
   команда (как сегодня).
2. Если дерево коммита правки совпадает с деревом родителя (ничего не
   изменилось ни записью, ни удалением), команда отказывает именованно
   и не сдвигает `tests_locked_sha`, не пишет запись «правка планки»
   (fail-closed, ADR-0002).
3. Удаление тестового файла `test_*.py` проходит те же проверки, что
   сегодня (трассируемость AC, строки групп, прогон планки) — по
   итоговому состоянию планки без удалённого файла; удаление не
   обходит ни одной проверки.
4. Запись журнала «правка планки» перечисляет удалённые пути
   (например «удалены: acceptance_tests/README.md»).
5. Тесты в `tests/` (по образцу `tests/test_amend.py` и
   `tests/test_amend_long_lived.py`), каждый с «Ловит мутацию: …»:
   а) задача без перечня: удалён `README.md` на диске → после
      `amend-tests` его нет в артефактной ветке, `tests_locked_sha`
      указывает на коммит без него («Ловит мутацию: `remove` не
      передан — файл остаётся, коммит пустой»);
   б) задача с перечнем (целиком долгоживущая планка): то же
      («Ловит мутацию: удаление перенесено только в одном из двух
      режимов»);
   в) коммит правки дал дерево, равное дереву родителя (в тесте —
      подмена записи коммита так, что удаление не применилось), —
      отказ, лок не сдвинут, записи «правка планки» нет («Ловит
      мутацию: проверка пустого коммита убрана — повтор случая
      101965d0»);
   г) удалённый `test_*.py`, покрывавший AC без другого теста, — отказ
      трассируемости, как при правке («Ловит мутацию: удалённые файлы
      исключены из проверок»);
   д) запись журнала называет удалённый путь.
6. Существующие тесты не ослабляются и не удаляются; полный набор
   `tests/` зелёный.

Зоны: orchestrator/amend.py, tests/test_amend_remove.py, docs/codebase-map.md.

Только чтение (не менять): orchestrator/artifact_branch.py,
orchestrator/acceptance.py, orchestrator/advance_gates/, orchestrator/fsm.py,
orchestrator/fsm_advance.py, orchestrator/store.py, scripts/guard.py,
tests/test_amend.py, tests/test_amend_long_lived.py, остальные файлы
tests/, skills/, docs/adr/, docs/invariants.md, tests/test_invariants.py,
tasks/.

Не входит: режим `--from-branch`; отказ guard на `.md` без заголовочного
блока в `acceptance_tests/` на выходе из `tests_writing`; проверка
`guard --all` по снимку на гейте мержа (задача 01M3SF7DPFGEZ7VYEGGXGTX49E);
правка планок 01M3SA3ANY… и 01M3XTFJCC… (её делает Оператор после мержа
этой задачи и сдвига пина).

Рамка: $15.
