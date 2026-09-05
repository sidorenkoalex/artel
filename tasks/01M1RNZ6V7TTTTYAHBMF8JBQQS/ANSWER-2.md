---
task: 01M1RNZ6V7TTTTYAHBMF8JBQQS
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: ответ Оператора

## Ответы

1. Пока задача была в разработке, в main вошёл аварийный hotfix
   (коммит 88b38022, ADR-0013): `acceptance.run(tdir, code_root=None)` —
   параметр `code_root` задаёт cwd прогона; `fsm._pull_main_or_escalate`
   передаёт `workspace.path(task_id)` для self-target. Это частичное
   закрытие того же дефекта. Требуется влить `origin/main` в ветку
   (ожидаются три конфликта в acceptance.py/fsm.py) и привести код к SPEC
   поверх hotfix: параметр `code_root` сохранить как публичный контракт
   `acceptance.run`; материализация планки — в worktree по штатному пути
   `tasks/<id>/acceptance_tests/` поверх устаревшей копии (требование 1),
   один вход материализации и один вход прогона для подтяжки и автогейта
   (требование 3), отказ называет каталог и cwd (требование 4).
2. Замечание ревью R1-F1 (различать `None` и `[]` у `ls_tree_files`)
   остаётся в силе после слияния.
3. Проверка: собственная планка (Ran 11 OK до слияния), тесты №12
   (`tests/test_artifact_materialization.py`, `test_fsm_autogate.py`),
   `tests/test_branch_freshness_gate.py`; полный набор `tests/` в шаге не
   гонять — его гоняет CI.
