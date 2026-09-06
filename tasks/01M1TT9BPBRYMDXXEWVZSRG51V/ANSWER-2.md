---
task: 01M1TT9BPBRYMDXXEWVZSRG51V
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: ответ Оператора

## Ответы

Ответ Оператора на эскалацию «приёмочные тесты красные после подтяжки
main» (06.09.2026).

Что сделано Оператором (ADR-0012, две правки планки, журнал 13:50Z и
13:53Z):
1. Помощник планки `_shared.py` никогда не попадал в артефактную ветку:
   имя вне белого списка каталога планки (01M1SAA01Y), автокоммит
   отбрасывал его трижды с записью «посторонние файлы в каталоге
   планки». Восстановлен из транскрипта test_author (Write 07:52Z) под
   разрешённым именем `_sandbox.py`; импорты в
   `test_doctor_split_contract.py` и `test_doctor_split_structure.py`
   переведены на `_sandbox`.
2. Снимки помощника дополнены до состояния `doctor.py` на main к
   моменту разреза (после мержей 01M1TQ0X14 и 01M1TQ0ZCY): 18-й
   разделитель «сверка артефактной ветки с origin/CI», три новые
   публичные проверки и коллаборатор `ci` в именах фасада, хеши восьми
   новых функций, запись `("artifact-branch-parent-ancestry", "skip")`
   в ожидаемом порядке `all_checks` после `branch-freshness`.

Что остаётся разработчику (два красных теста планки):
- AC-3 (`test_doctor_split_structure`): восемь функций раздела «сверка
  артефактной ветки с origin/CI» и родителя первого коммита в
  `orchestrator/doctor/artifact_branches.py` отличаются по AST от
  `origin/main:orchestrator/doctor.py` — тела переписаны при переносе.
  Требование 2 SPEC: перенос, не рефакторинг. Перенести дословно
  (`git show origin/main:orchestrator/doctor.py`, строки разделов
  ~829–900 и ~1799–1979), доступ к коллаборантам — тем же приёмом, что у
  остальных подмодулей, где хеши совпали. Эталонные хеши (первые 16 hex
  sha256 от `ast.dump(ast.parse(inspect.getsource(fn)))`):
  `check_artifact_branch_sync` 5caf200ad060ba08,
  `check_artifact_branch_ci` 3f015bf0bcadab32,
  `check_artifact_branch_parent_ancestry` a46e1239c182eb0c,
  `_artifact_branch_candidates` 0e203d57115ba8d6,
  `_is_ancestor` d3e932176d6105c1, `_sync_direction` 21486112c1f51f5d,
  `_artifact_branch_ci_runs` 51cb017fbde30ea1,
  `_artifact_branch_first_commit_parent` 9346055c81f53cee.
- AC-6 (`test_doctor_split_docs`): после подтяжки main перегенерировать
  `docs/codebase-map.md` штатным `python3 scripts/codebase_map.py` и
  закоммитить.

Планку не править (лок 10cc12f2); прогон планки из worktree:
`python3 -m unittest discover -s tasks/<id>/acceptance_tests`.
